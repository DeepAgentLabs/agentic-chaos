"""Provider-independent auth and context-window error simulations."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from agentic_chaos.chaos.faults import BaseFault, ChaosFaultError, FaultOutcome
from agentic_chaos.models.chaos_event import ChaosEvent

if TYPE_CHECKING:
    from agentic_chaos.chaos.scope import Scope


class AuthError(ChaosFaultError):
    """Simulated authentication error; status_code is 401 or 403."""

    def __init__(self, message: str, event: ChaosEvent, status_code: int) -> None:
        super().__init__(message, event)
        self.status_code = status_code


class ContextLengthError(ChaosFaultError):
    """Simulated context_length_exceeded (status_code=400)."""

    status_code = 400
    code = "context_length_exceeded"


class AuthErrorFault(BaseFault):
    name = "auth_error"

    def __init__(
        self,
        status_code: int = 401,
        *,
        probability: float = 1.0,
        seed: int | None = None,
        scope: "Scope | None" = None,
    ) -> None:
        super().__init__(probability, seed, scope=scope)
        if status_code not in (401, 403):
            raise ValueError("status_code must be 401 or 403")
        self.status_code = status_code

    def trigger(
        self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, **kwargs: Any
    ) -> FaultOutcome:
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="errored",
            message=f"{self.status_code} authentication failure",
            detail={"status_code": self.status_code},
        )
        return FaultOutcome(event=event, raised=AuthError(event.message, event, self.status_code))


class ContextLengthFault(BaseFault):
    name = "context_length"

    def trigger(
        self, call: Callable[..., Any], *, step_id: str | None, step_name: str | None, **kwargs: Any
    ) -> FaultOutcome:
        event = ChaosEvent(
            fault_type=self.name,
            step_id=step_id,
            step_name=step_name,
            outcome="errored",
            message="400 context_length_exceeded",
            detail={"status_code": 400, "code": "context_length_exceeded"},
        )
        return FaultOutcome(event=event, raised=ContextLengthError(event.message, event))
