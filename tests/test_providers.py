import asyncio
from types import SimpleNamespace

import pytest

from agentic_chaos import (
    AuthErrorFault,
    SilentDegradationFault,
    StreamCutFault,
    chaos_acall,
    chaos_session,
    patch_anthropic,
    patch_google,
    patch_openai,
)
from agentic_chaos.chaos.provider_faults import AuthError


class Resource:
    def create(self, **kwargs):
        return iter(["a", "b", "c"]) if kwargs.get("stream") else "hello"

    def generate_content(self, **kwargs):
        return "hello"

    def generate_content_stream(self, **kwargs):
        return iter(["a", "b", "c"])


@pytest.mark.parametrize(
    "patch,path",
    [(patch_openai, "openai"), (patch_anthropic, "anthropic"), (patch_google, "google")],
)
def test_patch_restores_client_on_exception(patch, path):
    resource = Resource()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=resource), messages=resource, models=resource
    )
    original = resource.create
    with (
        pytest.raises(RuntimeError, match="app failed"),
        chaos_session([SilentDegradationFault(seed=1)]) as session,
    ):
        patch(client)
        call = resource.generate_content if path == "google" else resource.create
        assert call() != "hello"
        assert len(session.events) == 1
        raise RuntimeError("app failed")
    assert resource.create == original
    assert vars(resource) == {}


def test_stream_patch_and_manual_close():
    resource = Resource()
    client = SimpleNamespace(messages=resource)
    with chaos_session([StreamCutFault()]) as session:
        patch = patch_anthropic(client)
        assert list(resource.create(stream=True)) == ["a"]
        assert resource.create() == "hello"
        patch.close()
        assert list(resource.create(stream=True)) == ["a", "b", "c"]
    assert len(session.events) == 1


def test_patch_is_context_scoped():
    import contextvars

    resource = Resource()
    with chaos_session([AuthErrorFault()]):
        patch_anthropic(SimpleNamespace(messages=resource))
        assert contextvars.Context().run(resource.create) == "hello"
        with pytest.raises(AuthError):
            resource.create()


def test_duplicate_and_partial_patch_rollback():
    resource = Resource()
    client = SimpleNamespace(chat=SimpleNamespace(completions=resource), responses=resource)
    with chaos_session([AuthErrorFault()]):
        with pytest.raises(RuntimeError, match="already patched"):
            patch_openai(client)
        assert resource.create() == "hello"
    assert vars(resource) == {}


def test_async_patch_and_async_call():
    async def run():
        class AsyncResource:
            async def create(self, **kwargs):
                if kwargs.get("stream"):

                    async def source():
                        for chunk in ["a", "b", "c"]:
                            yield chunk

                    return source()
                return "hello"

        resource = AsyncResource()
        with chaos_session([SilentDegradationFault(seed=1)]) as session:
            patch_anthropic(SimpleNamespace(messages=resource))
            assert await resource.create() != "hello"
        assert len(session.events) == 1
        with chaos_session([StreamCutFault()]):
            patch_anthropic(SimpleNamespace(messages=resource))
            stream = await resource.create(stream=True)
            assert [chunk async for chunk in stream] == ["a"]
        with chaos_session([AuthErrorFault()]) as session, pytest.raises(AuthError):
            await chaos_acall(resource.create)
        assert len(session.events) == 1

    asyncio.run(run())


def test_async_call_cancellation():
    async def run():
        closed = []

        async def provider():
            try:
                await asyncio.sleep(10)
            finally:
                closed.append(True)

        with chaos_session([SilentDegradationFault()]) as session:
            task = asyncio.create_task(chaos_acall(provider))
            await asyncio.sleep(0.02)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0.01)
        assert session.events == []
        assert closed == [True]

    asyncio.run(run())


def test_patch_requires_session():
    with pytest.raises(RuntimeError, match="active"):
        patch_openai(SimpleNamespace())


@pytest.mark.parametrize("consume", [False, True])
def test_stream_proxy_closes_source_once(consume):
    class Source:
        closes = 0

        def __iter__(self):
            return self

        def __next__(self):
            return "chunk"

        def close(self):
            self.closes += 1

    source = Source()
    resource = SimpleNamespace(create=lambda **kwargs: source)
    with chaos_session([StreamCutFault()]):
        patch_anthropic(SimpleNamespace(messages=resource))
        with resource.create(stream=True) as stream:
            if consume:
                assert list(stream) == ["chunk"]
        stream.close()
    assert source.closes == 1
