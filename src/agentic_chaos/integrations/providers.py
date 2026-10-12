"""Opt-in, reversible instance patches for optional provider SDKs."""

from collections.abc import Sequence
from functools import wraps
from inspect import iscoroutinefunction
from types import TracebackType
from typing import Any

from agentic_chaos.chaos.async_call import chaos_acall
from agentic_chaos.chaos.context import get_active_session
from agentic_chaos.chaos.faults import BaseFault, resolve_faults
from agentic_chaos.chaos.inject import chaos_call
from agentic_chaos.chaos.streaming import StreamFault, chaos_astream, chaos_stream


class ProviderPatch:
    """Patch handle: close() restores the exact pre-patch instance attributes."""

    def __init__(self) -> None:
        self._originals: list[tuple[Any, str, bool, Any]] = []

    def close(self) -> None:
        for target, name, existed, original in reversed(self._originals):
            if existed:
                setattr(target, name, original)
            else:
                delattr(target, name)
        self._originals.clear()


class _Stream:
    def __init__(self, source: Any, wrapped: Any) -> None:
        self.source = source
        self.wrapped = wrapped
        self.started = False
        self.closed = False

    def __iter__(self) -> "_Stream":
        return self

    def __next__(self) -> Any:
        self.started = True
        try:
            return next(self.wrapped)
        except BaseException:
            self.closed = True
            raise

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.wrapped.close()
        # An unstarted Python generator doesn't execute its finally block.
        if not self.started:
            close = getattr(self.source, "close", None)
            if close is not None:
                close()

    def __enter__(self) -> "_Stream":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: TracebackType | None) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.source, name)


class _AsyncStream:
    def __init__(self, source: Any, wrapped: Any) -> None:
        self.source = source
        self.wrapped = wrapped
        self.started = False
        self.closed = False

    def __aiter__(self) -> "_AsyncStream":
        return self

    async def __anext__(self) -> Any:
        self.started = True
        try:
            return await self.wrapped.__anext__()
        except BaseException:
            self.closed = True
            raise

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.wrapped.aclose()
        if not self.started:
            close = getattr(self.source, "aclose", None) or getattr(self.source, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result

    async def aclose(self) -> None:
        await self.close()

    async def __aenter__(self) -> "_AsyncStream":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: TracebackType | None) -> None:
        await self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.source, name)


def _patch(
    client: Any, paths: tuple[str, ...], faults: Sequence[str | BaseFault] | None, provider: str
) -> ProviderPatch:
    session = get_active_session()
    if session is None:
        raise RuntimeError("Provider patching requires an active chaos_session()")
    selected = session.faults if faults is None else resolve_faults(faults)
    if len(selected) != 1:
        raise ValueError(
            "Provider patches require exactly one fault; patch separate clients for others"
        )
    fault = selected[0]
    # Explicit instances must belong to this session; names select its configured instance.
    configured = session.select_faults([fault.name])[0]
    if faults is not None and any(
        isinstance(item, BaseFault) and item is not configured for item in faults
    ):
        raise ValueError("Pass the fault instance already configured in chaos_session()")
    fault = configured
    handle = ProviderPatch()

    def install(target: Any, name: str, original: Any, streaming: bool) -> None:
        if getattr(original, "_chaos_patched", False):
            raise RuntimeError("This provider method is already patched")

        def bypass() -> bool:
            return get_active_session() is not session

        def wrap_stream(result: Any) -> Any:
            if hasattr(result, "__aiter__"):
                return _AsyncStream(
                    result, chaos_astream(result, faults=[fault.name], step_name=provider)
                )
            return _Stream(result, chaos_stream(result, faults=[fault.name], step_name=provider))

        if iscoroutinefunction(original):

            @wraps(original)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if bypass():
                    return await original(*args, **kwargs)
                if isinstance(fault, StreamFault):
                    if not (streaming or kwargs.get("stream", False)):
                        return await original(*args, **kwargs)
                    return wrap_stream(await original(*args, **kwargs))
                return await chaos_acall(
                    original, *args, faults=[fault.name], step_name=provider, **kwargs
                )

            wrapper = async_wrapper
        else:

            @wraps(original)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if bypass():
                    return original(*args, **kwargs)
                if isinstance(fault, StreamFault):
                    if not (streaming or kwargs.get("stream", False)):
                        return original(*args, **kwargs)
                    return wrap_stream(original(*args, **kwargs))
                return chaos_call(
                    original, *args, faults=[fault.name], step_name=provider, **kwargs
                )

            wrapper = sync_wrapper
        wrapper._chaos_patched = True  # type: ignore[attr-defined]
        existed = name in vars(target)
        handle._originals.append((target, name, existed, vars(target).get(name)))
        setattr(target, name, wrapper)

    try:
        for path in paths:
            parts = path.split(".")
            target = client
            for part in parts[:-1]:
                target = getattr(target, part, None)
                if target is None:
                    break
            if target is None:
                continue
            original = getattr(target, parts[-1], None)
            if callable(original):
                install(target, parts[-1], original, path.endswith("generate_content_stream"))
        if not handle._originals:
            raise ValueError(f"Client has no supported {provider} methods")
    except BaseException:
        handle.close()
        raise
    session.cleanups.append(handle.close)
    return handle


def patch_openai(client: Any, *, faults: Sequence[str | BaseFault] | None = None) -> ProviderPatch:
    """Patch this OpenAI/AsyncOpenAI client's chat.completions.create and responses.create."""
    return _patch(client, ("chat.completions.create", "responses.create"), faults, "openai")


def patch_anthropic(
    client: Any, *, faults: Sequence[str | BaseFault] | None = None
) -> ProviderPatch:
    """Patch Anthropic/AsyncAnthropic messages.create (including stream=True).

    The higher-level messages.stream() accumulator is outside this patch surface.
    """
    return _patch(client, ("messages.create",), faults, "anthropic")


def patch_google(client: Any, *, faults: Sequence[str | BaseFault] | None = None) -> ProviderPatch:
    """Patch Google Gen AI models.generate_content[_stream], including client.aio."""
    return _patch(
        client,
        (
            "models.generate_content",
            "models.generate_content_stream",
            "aio.models.generate_content",
            "aio.models.generate_content_stream",
        ),
        faults,
        "google",
    )
