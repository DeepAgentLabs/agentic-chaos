"""Built-in probes: callables, HTTP endpoints, response quality and latency."""

import re
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any, ClassVar, Literal

from agentic_chaos.probes.base import (
    DEFAULT_PHASES,
    Probe,
    _check_number,
    failure,
    short,
)

_UNSET: Any = object()


def _call(fn: Callable[..., Any], query: Any) -> Any:
    return fn() if query is _UNSET else fn(query)


def _callable(name: str, fn: Any) -> None:
    if not callable(fn):
        raise ValueError(f"{name} must be callable")


def _texts(name: str, value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    texts = [value] if isinstance(value, str) else list(value)
    if not all(isinstance(text, str) and text for text in texts):
        raise ValueError(f"{name} must be a non-empty string or a list of them")
    return texts


class FunctionProbe(Probe):
    """Passes when `fn(query)` (or `fn()`) returns and `expect`, if given, accepts it.

    The most general probe: anything you can check in Python. A falsy return
    is still healthy unless `expect` says otherwise.
    """

    kind: ClassVar[str] = "function"

    def __init__(
        self,
        fn: Callable[..., Any],
        query: Any = _UNSET,
        *,
        expect: Callable[[Any], bool] | None = None,
        name: str | None = None,
        phases: str | Iterable[str] = DEFAULT_PHASES,
        retries: int = 0,
        retry_delay_seconds: float = 0.0,
        weight: float = 1.0,
    ) -> None:
        _callable("fn", fn)
        if expect is not None:
            _callable("expect", expect)
        super().__init__(
            name=name or getattr(fn, "__name__", None) or self.kind,
            phases=phases,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            weight=weight,
        )
        self.fn = fn
        self.query = query
        self.expect = expect

    def evaluate(self) -> tuple[str, dict[str, Any]]:
        output = _call(self.fn, self.query)
        observed = {"output": short(output)}
        if self.expect is not None and not self.expect(output):
            raise failure("expect predicate rejected the output", **observed)
        return "healthy", observed


class HttpProbe(Probe):
    """Passes when an HTTP(S) endpoint answers with `expect_status` (and text, if asked).

    Uses only the standard library. Redirects are followed; a status the
    server returns as an error (4xx/5xx) is still compared, so
    ``expect_status=503`` can assert a maintenance page.
    """

    kind: ClassVar[str] = "http"

    def __init__(
        self,
        url: str,
        *,
        expect_status: int = 200,
        method: str = "GET",
        expect_contains: str | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | str | None = None,
        timeout_seconds: float = 5.0,
        name: str | None = None,
        phases: str | Iterable[str] = DEFAULT_PHASES,
        retries: int = 0,
        retry_delay_seconds: float = 0.0,
        weight: float = 1.0,
    ) -> None:
        if not isinstance(url, str) or not re.match(r"^https?://[^\s/]+", url):
            raise ValueError("url must be an absolute http:// or https:// URL")
        if (
            isinstance(expect_status, bool)
            or not isinstance(expect_status, int)
            or not 100 <= expect_status <= 599
        ):
            raise ValueError("expect_status must be an HTTP status code (100-599)")
        if not isinstance(method, str) or not method.isalpha():
            raise ValueError("method must be an HTTP method name such as 'GET'")
        if expect_contains is not None and (
            not isinstance(expect_contains, str) or not expect_contains
        ):
            raise ValueError("expect_contains must be a non-empty string")
        _check_number("timeout_seconds", timeout_seconds)
        if timeout_seconds == 0:
            raise ValueError("timeout_seconds must be greater than 0")
        super().__init__(
            name=name or url,
            phases=phases,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            weight=weight,
        )
        self.url = url
        self.expect_status = expect_status
        self.method = method.upper()
        self.expect_contains = expect_contains
        self.headers = dict(headers or {})
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.timeout_seconds = float(timeout_seconds)

    def parameters(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "expect_status": self.expect_status,
            **super().parameters(),
        }

    def evaluate(self) -> tuple[str, dict[str, Any]]:
        request = urllib.request.Request(
            self.url, data=self.body, headers=self.headers, method=self.method
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 -- scheme checked in __init__
                status = response.status
                text = response.read(65_536).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            text = exc.read(65_536).decode("utf-8", errors="replace") if exc.fp else ""
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise failure(f"request failed: {reason}") from exc
        observed = {"status": status, "latency_ms": (time.monotonic() - started) * 1000}
        if status != self.expect_status:
            raise failure(f"status {status}, expected {self.expect_status}", **observed)
        if self.expect_contains is not None and self.expect_contains not in text:
            raise failure(f"body does not contain {self.expect_contains!r}", **observed)
        return f"status {status}", observed


class ResponseQualityProbe(Probe):
    """Passes when the agent's answer to `query` still meets every quality check.

    Checks (all optional, all must pass): `expect_contains` (every string must
    appear), `expect_not_contains` (none may appear, e.g. an error template),
    `expect_regex`, an `expect` predicate, and -- with `reference` -- a
    similarity of at least `min_similarity` by `judge` (the zero-dependency
    `HeuristicJudge` unless you pass one of the v0.3 judges).
    """

    kind: ClassVar[str] = "response_quality"

    def __init__(
        self,
        fn: Callable[..., Any],
        query: Any = _UNSET,
        *,
        expect_contains: str | Iterable[str] | None = None,
        expect_not_contains: str | Iterable[str] | None = None,
        expect_regex: str | None = None,
        expect: Callable[[Any], bool] | None = None,
        reference: Any = None,
        min_similarity: float | None = None,
        judge: Any = None,
        name: str | None = None,
        phases: str | Iterable[str] = DEFAULT_PHASES,
        retries: int = 0,
        retry_delay_seconds: float = 0.0,
        weight: float = 1.0,
    ) -> None:
        _callable("fn", fn)
        if expect is not None:
            _callable("expect", expect)
        self.expect_contains = _texts("expect_contains", expect_contains)
        self.expect_not_contains = _texts("expect_not_contains", expect_not_contains)
        self.pattern = re.compile(expect_regex) if expect_regex is not None else None
        if min_similarity is not None:
            _check_number("min_similarity", min_similarity)
            if min_similarity > 1:
                raise ValueError("min_similarity must be between 0 and 1")
            if reference is None:
                raise ValueError("min_similarity needs a reference answer")
        if judge is not None and not callable(getattr(judge, "score", None)):
            raise ValueError("judge must have a score(baseline=..., observed=...) method")
        has_check = (
            bool(self.expect_contains)
            or bool(self.expect_not_contains)
            or self.pattern is not None
            or expect is not None
            or min_similarity is not None
        )
        if not has_check:
            raise ValueError(
                "ResponseQualityProbe needs at least one check: expect_contains, "
                "expect_not_contains, expect_regex, expect or reference + min_similarity"
            )
        super().__init__(
            name=name or f"{getattr(fn, '__name__', 'agent')} quality",
            phases=phases,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            weight=weight,
        )
        self.fn = fn
        self.query = query
        self.expect = expect
        self.reference = reference
        self.min_similarity = min_similarity
        self.judge = judge

    def evaluate(self) -> tuple[str, dict[str, Any]]:
        output = _call(self.fn, self.query)
        text = output if isinstance(output, str) else str(output)
        observed: dict[str, Any] = {"output": short(output)}
        missing = [item for item in self.expect_contains if item not in text]
        if missing:
            raise failure(f"answer is missing {missing}", **observed)
        present = [item for item in self.expect_not_contains if item in text]
        if present:
            raise failure(f"answer contains {present}", **observed)
        if self.pattern is not None and self.pattern.search(text) is None:
            raise failure(f"answer does not match /{self.pattern.pattern}/", **observed)
        if self.expect is not None and not self.expect(output):
            raise failure("expect predicate rejected the answer", **observed)
        if self.min_similarity is not None:
            similarity = self._similarity(output)
            observed["similarity"] = similarity
            if similarity < self.min_similarity:
                raise failure(
                    f"similarity {similarity:.2f} is below {self.min_similarity:.2f}", **observed
                )
        return "answer meets every quality check", observed

    def _similarity(self, output: Any) -> float:
        judge = self.judge
        if judge is None:
            from agentic_chaos.judges import HeuristicJudge

            judge = HeuristicJudge()
        return float(judge.score(baseline=self.reference, observed=output))


class LatencyProbe(Probe):
    """Passes when `fn(query)` answers within `max_ms`.

    Takes `samples` calls and compares their `statistic` (``"max"``, the
    default, or ``"median"``) to the limit. A call that raises fails the
    probe: an error is not a fast answer.
    """

    kind: ClassVar[str] = "latency"

    def __init__(
        self,
        fn: Callable[..., Any],
        query: Any = _UNSET,
        *,
        max_ms: float,
        samples: int = 1,
        statistic: Literal["max", "median"] = "max",
        name: str | None = None,
        phases: str | Iterable[str] = DEFAULT_PHASES,
        retries: int = 0,
        retry_delay_seconds: float = 0.0,
        weight: float = 1.0,
    ) -> None:
        _callable("fn", fn)
        _check_number("max_ms", max_ms)
        if max_ms == 0:
            raise ValueError("max_ms must be greater than 0")
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise ValueError("samples must be a positive integer")
        if statistic not in ("max", "median"):
            raise ValueError("statistic must be 'max' or 'median'")
        super().__init__(
            name=name or f"{getattr(fn, '__name__', 'agent')} latency",
            phases=phases,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            weight=weight,
        )
        self.fn = fn
        self.query = query
        self.max_ms = float(max_ms)
        self.samples = samples
        self.statistic = statistic

    def parameters(self) -> dict[str, Any]:
        return {
            "max_ms": self.max_ms,
            "samples": self.samples,
            "statistic": self.statistic,
            **super().parameters(),
        }

    def evaluate(self) -> tuple[str, dict[str, Any]]:
        timings: list[float] = []
        for _ in range(self.samples):
            started = time.monotonic()
            _call(self.fn, self.query)
            timings.append((time.monotonic() - started) * 1000)
        value = max(timings) if self.statistic == "max" else statistics.median(timings)
        observed = {"latency_ms": value, "statistic": self.statistic, "samples": len(timings)}
        if value > self.max_ms:
            raise failure(
                f"{self.statistic} latency {value:.0f} ms > {self.max_ms:.0f} ms", **observed
            )
        return f"{self.statistic} latency {value:.0f} ms <= {self.max_ms:.0f} ms", observed
