"""Offline instrumented target for `chaos run --experiment`.

    agentic-chaos chaos run examples/chaoshub_app.py \
        --experiment rag-context-poisoning --save hub-report.json

The no-unhandled-error contract only checks availability. Add response-quality
probes or your own contracts to assess whether contradictory context was rejected.
"""

from agentic_chaos import chaos_call
from agentic_chaos.chaos.faults import ChaosFaultError


def main() -> str:
    try:
        return str(chaos_call(lambda: "The reference answer is 4.", step_name="retrieve"))
    except ChaosFaultError:
        return "Retriever unavailable; escalate to a human."


if __name__ == "__main__":
    print(main())
