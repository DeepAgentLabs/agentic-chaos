"""Offline streaming demo; also runnable using the supplied CLI profile."""

from contextlib import nullcontext

from agentic_chaos import StreamCutFault, chaos_session, chaos_stream
from agentic_chaos.chaos.context import get_active_session


def main() -> None:
    active = get_active_session()
    context = nullcontext(active) if active is not None else chaos_session([StreamCutFault(2)])
    with context as session:
        chunks = list(
            chaos_stream(
                iter(["Hello", " from", " your", " agent"]),
                faults=["stream_cut"],
                step_name="answer",
            )
        )
        print(f"Delivered chunks: {chunks}")
        assert session is not None
        for event in session.events:
            print(f"Fault: {event.fault_type}; outcome: {event.outcome}")


if __name__ == "__main__":
    main()
