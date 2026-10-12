"""Optional real SDK smoke tests; mock transport prevents provider network calls."""

import asyncio
import json

import pytest

from agentic_chaos import (
    AuthErrorFault,
    StreamCutFault,
    chaos_session,
    patch_anthropic,
    patch_google,
    patch_openai,
)
from agentic_chaos.chaos.provider_faults import AuthError


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
def test_real_sdk_auth_patch(provider):
    if provider == "openai":
        sdk = pytest.importorskip("openai")
        client = sdk.OpenAI(api_key="test")
        patch = patch_openai
        resource = client.chat.completions
        params = {"model": "test", "messages": []}
        method = "create"
    elif provider == "anthropic":
        sdk = pytest.importorskip("anthropic")
        client = sdk.Anthropic(api_key="test")
        patch = patch_anthropic
        resource = client.messages
        params = {"model": "test", "max_tokens": 1, "messages": []}
        method = "create"
    else:
        sdk = pytest.importorskip("google.genai")
        client = sdk.Client(api_key="test")
        patch = patch_google
        resource = client.models
        params = {"model": "test", "contents": "hello"}
        method = "generate_content"
    original = getattr(resource, method)
    try:
        with chaos_session([AuthErrorFault()]) as session:
            patch(client)
            with pytest.raises(AuthError):
                getattr(resource, method)(**params)
        assert getattr(resource, method) == original
        assert len(session.events) == 1
    finally:
        client.close()


def test_openai_real_stream_context_and_transport_cleanup():
    sdk = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx")
    chunk = {
        "id": "test",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "test",
        "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
    }
    payload = "data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n"
    response = httpx.Response(200, text=payload, headers={"content-type": "text/event-stream"})
    client = sdk.OpenAI(
        api_key="test",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda req: response)),
    )
    try:
        with chaos_session([StreamCutFault(after_chunks=1)]) as session:
            patch_openai(client)
            with client.chat.completions.create(model="test", messages=[], stream=True) as stream:
                chunks = list(stream)
        assert len(chunks) == 1
        assert chunks[0].choices[0].delta.content == "hello"
        assert response.is_closed
        assert len(session.events) == 1
    finally:
        client.close()


def test_real_async_sdk_errors():
    async def run():
        sdk = pytest.importorskip("openai")
        client = sdk.AsyncOpenAI(api_key="test")
        try:
            with chaos_session([AuthErrorFault()]) as session:
                patch_openai(client)
                with pytest.raises(AuthError):
                    await client.responses.create(model="test", input="hello")
            assert len(session.events) == 1
        finally:
            await client.close()

    asyncio.run(run())
