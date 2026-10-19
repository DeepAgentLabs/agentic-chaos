"""v0.8 explosion-radius control: Scope semantics and enforcement at every call path."""

import asyncio
from types import SimpleNamespace

import pytest

from agentic_chaos import (
    AuthErrorFault,
    PoisonedResponseFault,
    RateLimitStormFault,
    Scope,
    SilentDegradationFault,
    StreamCutFault,
    TokenTimeoutFault,
    ToolCallFailureFault,
    cascade,
    chaos_acall,
    chaos_call,
    chaos_session,
    chaos_stream,
    load_profile,
    patch_openai,
    wrap_tool,
)
from agentic_chaos.agents import ToolCallFailureError
from agentic_chaos.chaos.faults import RateLimitStormError
from agentic_chaos.chaos.provider_faults import AuthError
from agentic_chaos.chaos.scope import in_scope


def test_scope_include_exclude_and_fail_closed_labels():
    scope = Scope(steps=["retriever", "planner"], exclude_steps=["safety_check"])
    assert scope.allows(step_name="retriever")
    assert not scope.allows(step_name="safety_check")
    assert not scope.allows(step_name="writer")
    # An include list cannot be proven for an unlabelled call, so it is out of scope.
    assert not scope.allows(step_name=None)
    excluding = Scope(exclude_steps=["safety_check"])
    assert excluding.allows(step_name=None)
    assert excluding.allows(step_name="anything")
    providers = Scope(providers=["openai"], exclude_providers=["anthropic"])
    assert providers.allows(provider="openai")
    assert not providers.allows(provider="anthropic")
    assert not providers.allows(provider=None)


def test_exclusions_win_over_inclusions():
    scope = Scope(steps=["a", "b"], exclude_steps=["b"])
    assert scope.allows(step_name="a")
    assert not scope.allows(step_name="b")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"steps": "retriever"},
        {"steps": []},
        {"steps": [""]},
        {"providers": [1]},
        {"steps": ["a"], "exclude_steps": ["a"]},
        {"providers": ["openai"], "exclude_providers": ["openai"]},
    ],
)
def test_invalid_scopes_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Scope(**kwargs)


def test_scope_json_round_trip_and_repr():
    scope = Scope(steps=["b", "a"], exclude_providers=["google"])
    data = scope.as_json()
    assert data == {"steps": ["a", "b"], "exclude_providers": ["google"]}
    assert Scope.from_json(data) == scope
    assert Scope.from_json(scope) is scope
    assert "steps=['a', 'b']" in repr(scope)
    with pytest.raises(ValueError, match="unknown scope field"):
        Scope.from_json({"step": ["a"]})
    with pytest.raises(ValueError, match="mapping"):
        Scope.from_json(["a"])
    with pytest.raises(ValueError, match="list"):
        Scope.from_json({"steps": "a"})


def test_scope_intersection():
    left = Scope(steps=["a", "b"], exclude_steps=["x"])
    right = Scope(steps=["b", "c"], providers=["openai"], exclude_steps=["y"])
    both = left.intersect(right)
    assert both.steps == frozenset({"b"})
    assert both.providers == frozenset({"openai"})
    assert both.exclude_steps == frozenset({"x", "y"})
    assert left.intersect(None) is left
    with pytest.raises(ValueError, match="share no included"):
        Scope(steps=["a"]).intersect(Scope(steps=["b"]))


def test_out_of_scope_calls_pass_through_without_consuming_state():
    fault = RateLimitStormFault(burst_count=1, scope=Scope(steps=["retriever"]))
    calls = []
    with chaos_session([fault]) as session:
        assert chaos_call(lambda: calls.append("safety") or "ok", step_name="safety") == "ok"
        assert chaos_call(lambda: "ok") == "ok"
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "never", step_name="retriever")
    assert calls == ["safety"]
    assert [event.step_name for event in session.events] == ["retriever"]
    assert fault._fired == 1


def test_scope_is_checked_before_probability_sampling():
    scoped = SilentDegradationFault(seed=3, probability=0.5, scope=Scope(steps=["target"]))
    unscoped = SilentDegradationFault(seed=3, probability=0.5)
    with chaos_session([scoped]) as first:
        for _ in range(5):
            chaos_call(lambda: "text", step_name="other")
        for _ in range(10):
            chaos_call(lambda: "text", step_name="target")
    with chaos_session([unscoped]) as second:
        for _ in range(10):
            chaos_call(lambda: "text", step_name="target")
    assert len(first.events) == len(second.events)


def test_dry_run_plans_only_in_scope_calls():
    fault = ToolCallFailureFault(scope=Scope(exclude_steps=["safety_check"]))
    with chaos_session([fault], dry_run=True) as session:
        chaos_call(lambda: "ok", step_name="safety_check")
        chaos_call(lambda: "ok", step_name="search")
    assert [plan["step_name"] for plan in session.planned_events] == ["search"]


def test_tool_wrappers_respect_scope():
    search = wrap_tool(lambda q: f"results for {q}", tool_name="search")
    guard = wrap_tool(lambda q: "allowed", tool_name="safety_check")
    with chaos_session([ToolCallFailureFault(scope=Scope(exclude_steps=["safety_check"]))]):
        assert guard("q") == "allowed"
        with pytest.raises(ToolCallFailureError):
            search("q")


def test_async_calls_respect_scope():
    async def answer():
        return "ok"

    fault = TokenTimeoutFault(hang_seconds=0, scope=Scope(providers=["openai"]))

    async def run():
        with chaos_session([fault]) as session:
            assert await chaos_acall(answer, chaos_provider="anthropic") == "ok"
            with pytest.raises(Exception, match="timed out"):
                await chaos_acall(answer, chaos_provider="openai")
        return session

    session = asyncio.run(run())
    assert len(session.events) == 1


def test_streams_respect_scope():
    fault = StreamCutFault(scope=Scope(steps=["provider-a"]))
    with chaos_session([fault]) as session:
        assert list(chaos_stream(iter("abc"), step_name="provider-b")) == ["a", "b", "c"]
        assert list(chaos_stream(iter("abc"), step_name="provider-a")) == ["a"]
    assert len(session.events) == 1


def test_provider_patch_labels_provider_for_scope():
    class Completions:
        def create(self, **kwargs):
            return "hello"

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    blocked = AuthErrorFault(scope=Scope(exclude_providers=["openai"]))
    with chaos_session([blocked]) as session:
        patch_openai(client)
        assert client.chat.completions.create() == "hello"
    assert session.events == []
    allowed = AuthErrorFault(scope=Scope(providers=["openai"]))
    with chaos_session([allowed]), pytest.raises(AuthError):
        patch_openai(client)
        client.chat.completions.create()


def test_chaos_provider_is_not_forwarded_to_target():
    seen = {}

    def target(**kwargs):
        seen.update(kwargs)
        return "ok"

    with chaos_session([PoisonedResponseFault(scope=Scope(providers=["openai"]))]):
        chaos_call(target, chaos_provider="google", prompt="hi")
    assert seen == {"prompt": "hi"}


def test_cascade_scope_and_stage_scope():
    fault = cascade(
        first=RateLimitStormFault(burst_count=1, scope=Scope(steps=["a"])),
        then=TokenTimeoutFault(hang_seconds=0),
        scope=Scope(exclude_steps=["guard"]),
    )
    with chaos_session([fault]) as session:
        assert chaos_call(lambda: "ok", step_name="guard") == "ok"
        # Stage one is limited to step "a"; "b" passes through and the stage stays pending.
        assert chaos_call(lambda: "ok", step_name="b") == "ok"
        with pytest.raises(RateLimitStormError):
            chaos_call(lambda: "x", step_name="a")
        with pytest.raises(Exception, match="timed out"):
            chaos_call(lambda: "x", step_name="b")
    assert [event.fault_type for event in session.events] == ["rate_limit_storm", "token_timeout"]


def test_in_scope_helper_supports_custom_faults_without_base_init():
    assert in_scope(object(), step_name="x", provider=None)
    custom = SimpleNamespace(scope=Scope(steps=["a"]))
    assert in_scope(custom, step_name="a", provider=None)
    assert not in_scope(custom, step_name="b", provider=None)


def test_profiles_accept_scope_tables(tmp_path):
    path = tmp_path / "chaos.toml"
    path.write_text(
        '[profiles.scoped]\nfaults = ["tool_failure"]\n'
        "[profiles.scoped.parameters.tool_failure.scope]\n"
        'exclude_steps = ["safety_check"]\n'
    )
    import agentic_chaos.agents  # noqa: F401 -- registers agent faults

    fault = load_profile("scoped", path)[0]
    assert fault.scope == Scope(exclude_steps=["safety_check"])
    path.write_text(
        '[profiles.bad]\nfaults = ["tool_failure"]\n'
        "[profiles.bad.parameters.tool_failure.scope]\n"
        'steps = "safety_check"\n'
    )
    with pytest.raises(ValueError, match="Invalid scope"):
        load_profile("bad", path)


def test_out_of_scope_dry_run_calls_create_no_preview_copy():
    fault = RateLimitStormFault(burst_count=1, scope=Scope(steps=["llm"]))
    stream = StreamCutFault(scope=Scope(steps=["llm"]))
    with chaos_session([fault], dry_run=True) as session:
        chaos_call(lambda: "ok", step_name="guard")
        assert session._preview_faults == {}
        chaos_call(lambda: "ok", step_name="llm")
        assert len(session._preview_faults) == 1
        # The preview, not the real fault, now decides: its burst is used up.
        chaos_call(lambda: "ok", step_name="llm")
    assert len(session.planned_events) == 1
    assert fault._fired == 0
    with chaos_session([stream], dry_run=True) as session:
        assert list(chaos_stream(iter("ab"), step_name="guard")) == ["a", "b"]
        assert session._preview_faults == {}


def test_dry_run_cascade_scope_follows_the_preview_stage():
    fault = cascade(
        first=RateLimitStormFault(burst_count=1, scope=Scope(steps=["a"])),
        then=TokenTimeoutFault(hang_seconds=0, scope=Scope(steps=["b"])),
    )
    with chaos_session([fault], dry_run=True) as session:
        for step in ("b", "a", "a", "b"):
            chaos_call(lambda: "ok", step_name=step)
    assert [(p["step_name"], p["fault_type"]) for p in session.planned_events] == [
        ("a", "cascade"),
        ("b", "cascade"),
    ]
    assert fault.index == 0  # the real cascade never advanced
