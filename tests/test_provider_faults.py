import pytest

from agentic_chaos import AuthErrorFault, ContextLengthFault, chaos_call, chaos_session
from agentic_chaos.chaos.provider_faults import AuthError, ContextLengthError


@pytest.mark.parametrize(
    "fault,error",
    [(AuthErrorFault(status_code=403), AuthError), (ContextLengthFault(), ContextLengthError)],
)
def test_provider_errors_skip_real_call(fault, error):
    calls = []
    with chaos_session([fault]) as session, pytest.raises(error) as exc:
        chaos_call(lambda: calls.append(True))
    assert calls == []
    assert exc.value.event is session.events[0]
    assert exc.value.status_code in (400, 403)
