import asyncio
import sys
import types

import pytest

from agentic_chaos import HeuristicJudge, fidelity_session
from agentic_chaos.agents.faults import MemoryCorruptionFault
from agentic_chaos.chaos import SilentDegradationFault, chaos_call, chaos_session
from agentic_chaos.judges import DeepEvalJudge, PydanticEvalsJudge


def test_fidelity_session_scores_silent_degradation_events() -> None:
    with (
        fidelity_session(HeuristicJudge()),
        chaos_session([SilentDegradationFault(seed=1)]) as session,
    ):
        result = chaos_call(lambda: "important answer", faults=["silent_degradation"])

    assert result != "important answer"
    assert len(session.events) == 1
    assert session.events[0].fidelity_score is not None
    assert 0.0 <= session.events[0].fidelity_score <= 1.0
    assert session.events[0].detail["judge"] == "heuristic"


def test_fidelity_session_scores_memory_corruption_events() -> None:
    with (
        fidelity_session(HeuristicJudge()),
        chaos_session([MemoryCorruptionFault(mode="truncate")]) as session,
    ):
        result = chaos_call(lambda: "persistent memory", faults=["memory_corruption"])

    assert result != "persistent memory"
    assert session.events[0].fidelity_score is not None


def test_pydantic_evals_judge_accepts_callable() -> None:
    judge = PydanticEvalsJudge(lambda **_: 0.42)

    with fidelity_session(judge), chaos_session([SilentDegradationFault(seed=2)]) as session:
        chaos_call(lambda: "baseline", faults=["silent_degradation"])

    assert session.events[0].fidelity_score == 0.42


def test_pydantic_evals_judge_accepts_single_arg_evaluate_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain `def evaluate(ctx): ...` function (not an `Evaluator`
    subclass) is detected by its single required positional parameter and
    also gets a real-shaped `EvaluatorContext` -- not the legacy kwarg call."""

    class FakeEvaluatorContext:
        def __init__(
            self,
            *,
            name,
            inputs,
            metadata,
            expected_output,
            output,
            duration,
            _span_tree,
            attributes,
            metrics,
        ) -> None:
            self.output = output
            self.expected_output = expected_output

    _install_fake_pydantic_evals(monkeypatch, FakeEvaluatorContext)

    def evaluate(ctx: FakeEvaluatorContext) -> float:
        return 1.0 if ctx.output == ctx.expected_output else 0.0

    judge = PydanticEvalsJudge(evaluate)

    assert judge.score(baseline="same", observed="same") == 1.0
    assert judge.score(baseline="expected", observed="different") == 0.0


def test_deepeval_judge_uses_llm_test_case_api(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeLLMTestCase:
        def __init__(
            self, *, input: str, actual_output: str, expected_output: str, context=None, name=None
        ) -> None:
            captured["test_case"] = {
                "input": input,
                "actual_output": actual_output,
                "expected_output": expected_output,
                "context": context,
                "name": name,
            }

    class FakeMetric:
        def __init__(self) -> None:
            self.score = 0.73

        def measure(self, test_case: FakeLLMTestCase) -> None:
            captured["measure_arg"] = test_case

    fake_module = types.ModuleType("deepeval.test_case")
    fake_module.LLMTestCase = FakeLLMTestCase
    monkeypatch.setitem(sys.modules, "deepeval.test_case", fake_module)

    judge = DeepEvalJudge(FakeMetric())
    score = judge.score(
        baseline="expected",
        observed="actual",
        step_id="step-1",
        step_name="Retriever",
    )

    assert score == 0.73
    assert captured["test_case"] == {
        "input": "Retriever",
        "actual_output": "actual",
        "expected_output": "expected",
        "context": ["step_id=step-1", "step_name=Retriever"],
        "name": "Retriever",
    }
    assert captured["measure_arg"] is not None


def _install_fake_pydantic_evals(monkeypatch: pytest.MonkeyPatch, evaluator_context_cls) -> None:
    """Register fake `pydantic_evals.evaluators`/`pydantic_evals.otel` modules.

    `evaluator_context_cls` must require the same keyword-only fields as the
    real `pydantic_evals.evaluators.EvaluatorContext` dataclass (`name`,
    `inputs`, `metadata`, `expected_output`, `output`, `duration`,
    `_span_tree`, `attributes`, `metrics`, all with no defaults) -- so a
    caller that forgets to supply one of them fails the test the same way it
    would fail against the real class.
    """

    class FakeSpanTreeRecordingError(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)

    evaluators_module = types.ModuleType("pydantic_evals.evaluators")
    evaluators_module.EvaluatorContext = evaluator_context_cls
    otel_module = types.ModuleType("pydantic_evals.otel")
    otel_module.SpanTreeRecordingError = FakeSpanTreeRecordingError
    monkeypatch.setitem(sys.modules, "pydantic_evals.evaluators", evaluators_module)
    monkeypatch.setitem(sys.modules, "pydantic_evals.otel", otel_module)


def test_pydantic_evals_judge_uses_evaluator_context_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeEvaluatorContext:
        # Mirrors every keyword-only field the real dataclass requires --
        # not just the ones agentic-chaos happens to have real data for.
        def __init__(
            self,
            *,
            name,
            inputs: str,
            metadata,
            expected_output: str,
            output: str,
            duration: float,
            _span_tree,
            attributes: dict,
            metrics: dict,
        ) -> None:
            captured["context"] = {
                "inputs": inputs,
                "output": output,
                "expected_output": expected_output,
                "metadata": metadata,
                "name": name,
                "duration": duration,
                "span_tree": _span_tree,
                "attributes": attributes,
                "metrics": metrics,
            }

    class FakeEvaluator:
        def evaluate(self, ctx: FakeEvaluatorContext) -> float:
            captured["ctx_instance"] = ctx
            return 0.61

    _install_fake_pydantic_evals(monkeypatch, FakeEvaluatorContext)

    judge = PydanticEvalsJudge(FakeEvaluator())
    score = judge.score(
        baseline="expected",
        observed="actual",
        step_id="step-1",
        step_name="Planner",
    )

    assert score == 0.61
    context = captured["context"]
    assert context["inputs"] == "Planner"
    assert context["output"] == "actual"
    assert context["expected_output"] == "expected"
    assert context["metadata"] == {"step_id": "step-1", "step_name": "Planner"}
    assert context["name"] == "Planner"
    assert context["duration"] == 0.0
    assert context["attributes"] == {}
    assert context["metrics"] == {}
    assert isinstance(context["span_tree"], Exception)
    assert captured["ctx_instance"] is not None


def test_pydantic_evals_judge_runs_async_evaluator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEvaluatorContext:
        def __init__(
            self,
            *,
            name,
            inputs,
            metadata,
            expected_output,
            output,
            duration,
            _span_tree,
            attributes,
            metrics,
        ) -> None:
            pass

    class FakeEvaluator:
        async def evaluate(self, ctx: FakeEvaluatorContext) -> float:
            await asyncio.sleep(0)
            return 0.55

    _install_fake_pydantic_evals(monkeypatch, FakeEvaluatorContext)

    judge = PydanticEvalsJudge(FakeEvaluator())

    assert judge.score(baseline="expected", observed="actual") == 0.55
