from collections.abc import Sequence
from contextvars import Token
from types import TracebackType
from typing import Literal

from agentic_chaos.chaos.context import ChaosSession, active_session
from agentic_chaos.chaos.faults import BaseFault, resolve_faults


class chaos_session:  # noqa: N801 -- lowercase to read as a context manager, like contextlib.suppress
    """Context manager that activates a set of faults for `chaos_call()`.

    Nested `chaos_session()` blocks are not supported -- like AgenticLens's
    `profile()`, a chaos session is a single top-level unit of work.

    ```python
    with chaos_session(["token_timeout", "rate_limit_storm"]):
        ...
    ```

    Pass already-constructed fault instances instead of names to override
    their defaults:

    ```python
    with chaos_session([TokenTimeoutFault(hang_seconds=5.0)]):
        ...
    ```
    """

    def __init__(self, faults: "str | Sequence[str | BaseFault]") -> None:
        self.faults = resolve_faults(faults)
        self.session: ChaosSession | None = None
        self._token: Token[ChaosSession | None] | None = None

    def __enter__(self) -> ChaosSession:
        if active_session.get() is not None:
            raise RuntimeError("Nested chaos_session() blocks are not supported.")
        self.session = ChaosSession(faults=self.faults)
        self._token = active_session.set(self.session)
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        assert self._token is not None
        active_session.reset(self._token)
        return False
