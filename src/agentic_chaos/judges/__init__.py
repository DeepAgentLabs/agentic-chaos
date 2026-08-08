"""Fidelity judges for v0.3.

The core package stays dependency-light: the built-in judge classes accept
already-constructed evaluator objects/callables rather than importing external
evaluation frameworks directly.
"""

import asyncio
import inspect
from collections.abc import Callable, Coroutine
from contextvars import ContextVar, Token
from dataclasses import dataclass
from importlib import import_module
from types import TracebackType
from typing import Any, Literal, Protocol, cast

from agentic_chaos.models.chaos_event import ChaosEvent


class JudgeProtocol(Protocol):
    """A judge that can score a baseline result against an observed result."""

    name: str

    def score(
        self,
        *,
        baseline: Any,
        observed: Any,
        step_id: str | None = None,
        step_name: str | None = None,
    ) -> float: ...


def _coerce_score(value: Any) -> float:
    score = float(value)
    if not 0.0 <= score <= 1.0:
        raise ValueError("Judge scores must be between 0.0 and 1.0.")
    return score


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for attr in ("content", "text"):
        attr_value = getattr(value, attr, None)
        if isinstance(attr_value, str):
            return attr_value
    if isinstance(value, dict):
        for key in ("content", "text"):
            dict_value = value.get(key)
            if isinstance(dict_value, str):
                return dict_value
    return str(value)


def _run_maybe_awaitable(value: Any) -> Any:
    if inspect.isawaitable(value):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cast(Coroutine[Any, Any, Any], value))
        raise RuntimeError(
            "Async judge results cannot be awaited while an event loop is already running."
        )
    return value


def _construct_with_supported_kwargs(factory: Any, **candidates: Any) -> Any:
    """Instantiate `factory`, passing only kwargs it appears to accept."""
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(**candidates)

    parameters = signature.parameters.values()
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters):
        return factory(**candidates)

    accepted = {
        param.name
        for param in parameters
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    filtered = {key: value for key, value in candidates.items() if key in accepted}
    return factory(**filtered)


def _build_step_metadata(step_id: str | None, step_name: str | None) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if step_id is not None:
        metadata["step_id"] = step_id
    if step_name is not None:
        metadata["step_name"] = step_name
    return metadata


def _build_evaluator_context(
    *,
    baseline: Any,
    observed: Any,
    step_id: str | None,
    step_name: str | None,
) -> Any:
    """Build a real `pydantic_evals.evaluators.EvaluatorContext`.

    Outside `pydantic_evals`'s own `Dataset.evaluate()` harness there's no
    OpenTelemetry span data or task-run timing to report, so the
    telemetry-only fields (`duration`, `_span_tree`, `attributes`, `metrics`)
    are filled with honest placeholders rather than fabricated data --
    `SpanTreeRecordingError` is the same value real `pydantic_evals` uses
    when a span tree wasn't captured, so evaluators that read
    `ctx.span_tree` fail the same way they would on a real run without
    tracing configured, instead of silently getting an empty tree.
    """
    evaluators = import_module("pydantic_evals.evaluators")
    otel = import_module("pydantic_evals.otel")
    metadata = _build_step_metadata(step_id, step_name)
    return _construct_with_supported_kwargs(
        evaluators.EvaluatorContext,
        name=step_name or step_id,
        inputs=step_name or step_id or "agentic-chaos fidelity check",
        metadata=metadata or None,
        expected_output=_stringify(baseline),
        output=_stringify(observed),
        duration=0.0,
        attributes={},
        metrics={},
        _span_tree=otel.SpanTreeRecordingError(
            "agentic-chaos does not capture OpenTelemetry spans for fidelity_session() runs."
        ),
    )


@dataclass
class HeuristicJudge:
    """Zero-dependency fallback judge based on text similarity.

    Returns 1.0 for identical outputs and trends lower as the observed output
    diverges from the baseline.
    """

    name: str = "heuristic"

    def score(
        self,
        *,
        baseline: Any,
        observed: Any,
        step_id: str | None = None,
        step_name: str | None = None,
    ) -> float:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, _stringify(baseline), _stringify(observed)).ratio()


@dataclass
class DeepEvalJudge:
    """Adapter for DeepEval metrics using a real `LLMTestCase`."""

    metric: Any
    name: str = "deepeval"

    def score(
        self,
        *,
        baseline: Any,
        observed: Any,
        step_id: str | None = None,
        step_name: str | None = None,
    ) -> float:
        llm_test_case_cls = import_module("deepeval.test_case").LLMTestCase
        test_case = _construct_with_supported_kwargs(
            llm_test_case_cls,
            input=step_name or step_id or "agentic-chaos fidelity check",
            actual_output=_stringify(observed),
            expected_output=_stringify(baseline),
            context=[
                f"{key}={value}" for key, value in _build_step_metadata(step_id, step_name).items()
            ]
            or None,
            name=step_name or step_id,
        )
        result = _run_maybe_awaitable(self.metric.measure(test_case))
        if hasattr(result, "score"):
            return _coerce_score(result.score)
        if hasattr(self.metric, "score"):
            return _coerce_score(self.metric.score)
        return _coerce_score(result)


@dataclass
class PydanticEvalsJudge:
    """Adapter for Pydantic Evals evaluators or lightweight custom callables."""

    evaluator: Callable[..., Any] | Any
    name: str = "pydantic_evals"

    def score(
        self,
        *,
        baseline: Any,
        observed: Any,
        step_id: str | None = None,
        step_name: str | None = None,
    ) -> float:
        if hasattr(self.evaluator, "evaluate"):
            context = _build_evaluator_context(
                baseline=baseline, observed=observed, step_id=step_id, step_name=step_name
            )
            result = _run_maybe_awaitable(self.evaluator.evaluate(context))
        elif callable(self.evaluator):
            signature = inspect.signature(self.evaluator)
            positional_params = [
                param
                for param in signature.parameters.values()
                if param.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and param.default is inspect._empty
            ]
            single_positional_arg = (
                len(positional_params) == 1
                and positional_params[0].kind != inspect.Parameter.VAR_POSITIONAL
            )
            if single_positional_arg:
                context = _build_evaluator_context(
                    baseline=baseline, observed=observed, step_id=step_id, step_name=step_name
                )
                result = _run_maybe_awaitable(self.evaluator(context))
            else:
                result = self.evaluator(
                    baseline=_stringify(baseline),
                    observed=_stringify(observed),
                    step_id=step_id,
                    step_name=step_name,
                )
                result = _run_maybe_awaitable(result)
        else:
            raise TypeError(
                "PydanticEvalsJudge evaluator must be callable or expose evaluate(ctx)."
            )
        if hasattr(result, "score"):
            return _coerce_score(result.score)
        return _coerce_score(result)


@dataclass
class FidelitySession:
    judge: JudgeProtocol


_active_fidelity_session: ContextVar[FidelitySession | None] = ContextVar(
    "active_fidelity_session", default=None
)


def get_active_fidelity_session() -> FidelitySession | None:
    return _active_fidelity_session.get()


class fidelity_session:  # noqa: N801
    """Activate a judge for the duration of a chaos run."""

    def __init__(self, judge: JudgeProtocol) -> None:
        self.session = FidelitySession(judge=judge)
        self._token: Token[FidelitySession | None] | None = None

    def __enter__(self) -> FidelitySession:
        if _active_fidelity_session.get() is not None:
            raise RuntimeError("Nested fidelity_session() blocks are not supported.")
        self._token = _active_fidelity_session.set(self.session)
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        assert self._token is not None
        _active_fidelity_session.reset(self._token)
        return False


def score_outcome(
    event: ChaosEvent,
    *,
    baseline: Any,
    observed: Any,
    step_id: str | None = None,
    step_name: str | None = None,
) -> None:
    """Attach a fidelity score to an event when a judge is active."""
    session = get_active_fidelity_session()
    if session is None or baseline is None:
        return
    score = session.judge.score(
        baseline=baseline,
        observed=observed,
        step_id=step_id,
        step_name=step_name,
    )
    event.fidelity_score = _coerce_score(score)
    event.detail["judge"] = session.judge.name


__all__ = [
    "DeepEvalJudge",
    "FidelitySession",
    "HeuristicJudge",
    "JudgeProtocol",
    "PydanticEvalsJudge",
    "fidelity_session",
    "get_active_fidelity_session",
    "score_outcome",
]
