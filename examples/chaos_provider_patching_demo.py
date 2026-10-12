"""Demonstrate reversible provider patching without SDKs or API credentials."""

from types import SimpleNamespace

from agentic_chaos import AuthErrorFault, chaos_session, patch_openai
from agentic_chaos.chaos.provider_faults import AuthError


class Completions:
    def create(self, **kwargs: object) -> str:
        return "Provider call succeeded"


def main() -> None:
    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    with chaos_session([AuthErrorFault(status_code=403)]) as session:
        patch_openai(client)
        try:
            client.chat.completions.create(model="offline", messages=[])
        except AuthError as error:
            print(f"Caught simulated status {error.status_code}")
    print(f"Recorded {len(session.events)} event; patch restored")
    print(client.chat.completions.create())


if __name__ == "__main__":
    main()
