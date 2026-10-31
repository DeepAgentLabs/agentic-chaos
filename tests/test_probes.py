"""v0.9 resilience probes: phases, retries and the four built-in probe types."""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agentic_chaos.judges import HeuristicJudge
from agentic_chaos.probes import (
    FunctionProbe,
    HttpProbe,
    LatencyProbe,
    Probe,
    ProbeError,
    ResponseQualityProbe,
    check_probes,
    run_probes,
)
from agentic_chaos.probes.base import normalize_phases


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 -- http.server naming
        status, body = {
            "/health": (200, b"ok: all systems go"),
            "/down": (503, b"maintenance"),
        }.get(self.path, (404, b"missing"))
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def agent(query: str = "") -> str:
    return f"The answer to {query!r} is 4."


# -- base -------------------------------------------------------------------


def test_phases_are_validated_and_ordered() -> None:
    assert normalize_phases(["post", "pre"]) == ("pre", "post")
    assert normalize_phases("during") == ("during",)
    with pytest.raises(ValueError, match="unknown probe phase"):
        normalize_phases(["after"])
    with pytest.raises(ValueError, match="at least one phase"):
        normalize_phases([])


def test_default_phases_are_pre_and_post() -> None:
    probe = FunctionProbe(agent)
    assert probe.phases == ("pre", "post")
    assert probe.runs_in("pre") and not probe.runs_in("during")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"name": " "}, "non-empty"),
        ({"retries": -1}, "retries"),
        ({"retries": True}, "retries"),
        ({"retry_delay_seconds": float("nan")}, "retry_delay_seconds"),
        ({"weight": 0}, "weight"),
        ({"weight": -1}, "weight"),
    ],
)
def test_common_probe_options_are_validated(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        FunctionProbe(agent, **kwargs)


def test_run_records_a_passing_result() -> None:
    result = FunctionProbe(agent, "2+2", name="answer").run("post")
    assert result.passed and result.phase == "post" and result.probe == "answer"
    assert result.attempts == 1 and result.duration_ms >= 0
    data = result.as_json()
    assert data["kind"] == "function" and "4" in data["observed"]["output"]
    assert "step" not in data


def test_run_never_raises_and_describes_the_error() -> None:
    def broken() -> str:
        raise ConnectionError("agent offline")

    result = FunctionProbe(broken).run("pre", step="warm-up")
    assert result.status == "failed"
    assert result.message == "raised ConnectionError: agent offline"
    assert result.as_json()["step"] == "warm-up"


def test_retries_let_a_settling_system_pass() -> None:
    calls = {"n": 0}

    def settling() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("still recovering")
        return "ok"

    result = FunctionProbe(settling, retries=2, retry_delay_seconds=0.001).run("post")
    assert result.passed and result.attempts == 3


def test_retries_are_bounded() -> None:
    result = FunctionProbe(lambda: 1 / 0, retries=2).run("post")
    assert result.status == "failed" and result.attempts == 3


def test_custom_probe_subclass_and_probe_error() -> None:
    class QueueDepthProbe(Probe):
        kind = "queue_depth"

        def __init__(self, depth: int) -> None:
            super().__init__(name="queue")
            self.depth = depth

        def evaluate(self):
            if self.depth > 10:
                raise ProbeError(f"queue depth {self.depth} > 10")
            return "queue drained", {"depth": self.depth}

    assert QueueDepthProbe(3).run("post").observed == {"depth": 3}
    failed = QueueDepthProbe(50).run("post")
    assert failed.message == "queue depth 50 > 10" and failed.kind == "queue_depth"
    assert "QueueDepthProbe(name='queue'" in repr(QueueDepthProbe(1))


def test_run_probes_filters_by_phase_and_check_probes_rejects_duplicates() -> None:
    probes = [
        FunctionProbe(agent, name="a"),
        FunctionProbe(agent, name="b", phases=["during"]),
    ]
    assert [r.probe for r in run_probes(probes, "pre")] == ["a"]
    assert [r.probe for r in run_probes(probes, "during", step="s")] == ["b"]
    with pytest.raises(ValueError, match="duplicate probe name"):
        check_probes([FunctionProbe(agent), FunctionProbe(agent)])
    with pytest.raises(ValueError, match="Probe instances"):
        check_probes([agent])


# -- FunctionProbe ------------------------------------------------------------


def test_function_probe_expect_predicate() -> None:
    assert FunctionProbe(lambda: 0).run("pre").passed  # falsy output is still healthy
    rejected = FunctionProbe(lambda: 0, expect=lambda out: out > 0).run("pre")
    assert rejected.message == "expect predicate rejected the output"
    assert rejected.observed == {"output": "0"}
    with pytest.raises(ValueError, match="fn must be callable"):
        FunctionProbe("not callable")  # type: ignore[arg-type]


# -- HttpProbe --------------------------------------------------------------------


def test_http_probe_checks_status_and_body(server: str) -> None:
    result = HttpProbe(f"{server}/health", expect_contains="all systems go").run("pre")
    assert result.passed and result.observed["status"] == 200
    assert result.probe == f"{server}/health"


def test_http_probe_compares_error_statuses(server: str) -> None:
    assert HttpProbe(f"{server}/down", expect_status=503).run("pre").passed
    failed = HttpProbe(f"{server}/down").run("pre")
    assert failed.message == "status 503, expected 200"
    assert failed.observed["status"] == 503


def test_http_probe_fails_on_missing_text_and_unreachable_hosts(server: str) -> None:
    missing = HttpProbe(f"{server}/health", expect_contains="degraded").run("pre")
    assert "does not contain 'degraded'" in missing.message
    unreachable = HttpProbe("http://127.0.0.1:9/health", timeout_seconds=0.5).run("pre")
    assert unreachable.status == "failed" and unreachable.message.startswith("request failed")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"url": "ftp://example.com"}, "http"),
        ({"url": "localhost:8080"}, "http"),
        ({"url": "http://x", "expect_status": 42}, "status code"),
        ({"url": "http://x", "method": "GE T"}, "method"),
        ({"url": "http://x", "expect_contains": ""}, "expect_contains"),
        ({"url": "http://x", "timeout_seconds": 0}, "timeout_seconds"),
    ],
)
def test_http_probe_validation(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        HttpProbe(**kwargs)


def test_http_probe_parameters() -> None:
    probe = HttpProbe("https://example.com/h", method="head", body="x")
    assert probe.method == "HEAD" and probe.body == b"x"
    assert probe.parameters()["url"] == "https://example.com/h"


# -- ResponseQualityProbe -------------------------------------------------------


def test_response_quality_contains_and_not_contains() -> None:
    probe = ResponseQualityProbe(
        agent, "2+2", expect_contains=["answer", "4"], expect_not_contains="sorry"
    )
    assert probe.run("post").passed
    missing = ResponseQualityProbe(agent, "2+2", expect_contains=["4", "five"]).run("post")
    assert missing.message == "answer is missing ['five']"
    present = ResponseQualityProbe(agent, "x", expect_not_contains=["answer"]).run("post")
    assert present.message == "answer contains ['answer']"


def test_response_quality_regex_and_predicate() -> None:
    assert ResponseQualityProbe(agent, "q", expect_regex=r"is \d\.").run("post").passed
    assert (
        "does not match"
        in ResponseQualityProbe(agent, "q", expect_regex=r"^\d+$").run("post").message
    )
    rejected = ResponseQualityProbe(agent, "q", expect=lambda out: len(out) < 5).run("post")
    assert rejected.message == "expect predicate rejected the answer"


def test_response_quality_similarity_uses_heuristic_judge_by_default() -> None:
    reference = agent("2+2")
    probe = ResponseQualityProbe(agent, "2+2", reference=reference, min_similarity=0.9)
    result = probe.run("post")
    assert result.passed and result.observed["similarity"] == 1.0
    drifted = ResponseQualityProbe(
        lambda q: "I cannot help with that.", "2+2", reference=reference, min_similarity=0.9
    ).run("post")
    assert drifted.status == "failed" and "below 0.90" in drifted.message


def test_response_quality_accepts_a_judge() -> None:
    class Strict:
        name = "strict"

        def score(self, *, baseline, observed, step_id=None, step_name=None):
            return 0.0

    probe = ResponseQualityProbe(agent, "q", reference="x", min_similarity=0.1, judge=Strict())
    assert probe.run("post").observed["similarity"] == 0.0
    lenient = ResponseQualityProbe(
        agent, "q", reference="different", min_similarity=0.0, judge=HeuristicJudge()
    )
    assert lenient.run("post").passed


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({}, "at least one check"),
        ({"min_similarity": 0.5}, "reference"),
        ({"reference": "x", "min_similarity": 1.5}, "between 0 and 1"),
        ({"expect_contains": [""]}, "expect_contains"),
        ({"expect_contains": "x", "judge": object()}, "judge"),
    ],
)
def test_response_quality_validation(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        ResponseQualityProbe(agent, "q", **kwargs)


# -- LatencyProbe -------------------------------------------------------------------


def test_latency_probe_passes_and_fails_on_the_statistic() -> None:
    assert LatencyProbe(agent, "q", max_ms=1000, samples=3).run("post").passed

    def slow(query: str) -> str:
        time.sleep(0.03)
        return query

    failed = LatencyProbe(slow, "q", max_ms=5).run("post")
    assert failed.status == "failed" and "max latency" in failed.message
    assert failed.observed["latency_ms"] >= 5


def test_latency_probe_median_ignores_one_outlier() -> None:
    delays = iter([0.0, 0.05, 0.0])

    def flaky(query: str) -> str:
        time.sleep(next(delays))
        return query

    result = LatencyProbe(flaky, "q", max_ms=30, samples=3, statistic="median").run("post")
    assert result.passed and result.observed["statistic"] == "median"


def test_latency_probe_fails_when_a_call_raises() -> None:
    result = LatencyProbe(lambda q: 1 / 0, "q", max_ms=1000).run("post")
    assert result.message.startswith("raised ZeroDivisionError")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"max_ms": 0}, "max_ms"),
        ({"max_ms": 10, "samples": 0}, "samples"),
        ({"max_ms": 10, "statistic": "p99"}, "statistic"),
    ],
)
def test_latency_probe_validation(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        LatencyProbe(agent, "q", **kwargs)


def test_latency_probe_parameters_and_default_name() -> None:
    probe = LatencyProbe(agent, max_ms=10)
    assert probe.name == "agent latency"
    assert probe.parameters() == {
        "max_ms": 10.0,
        "samples": 1,
        "statistic": "max",
        "phases": ["pre", "post"],
    }
