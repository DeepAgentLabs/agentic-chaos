from agentic_chaos import (
    HandoffCorruptionFault,
    HeuristicJudge,
    TopologyTracker,
    chaos_session,
    fidelity_session,
    wrap_node,
)
from agentic_chaos.judges import score_outcome


def planner(user_request: str) -> str:
    return f"plan: {user_request}"


def executor(payload: str) -> str:
    return f"executed -> {payload}"


def main() -> None:
    tracker = TopologyTracker()
    tracker.register_node("Planner", type="agent")

    wrapped_executor = wrap_node(
        executor,
        node_name="Executor",
        tracker=tracker,
        caller_node="Planner",
        faults=["handoff_corruption"],
    )

    # Handoff corruption only calls the downstream node once, so it cannot
    # infer a clean baseline automatically. For a pure/idempotent downstream
    # function like this demo, we can capture one explicitly.
    plan = planner("refund order #123")
    baseline = executor(plan)

    with (
        fidelity_session(HeuristicJudge()),
        chaos_session(
            [HandoffCorruptionFault(from_node="Planner", to_node="Executor", mode="corrupt")]
        ) as session,
    ):
        result = wrapped_executor(plan)
        score_outcome(
            session.events[0],
            baseline=baseline,
            observed=result,
            step_id="Executor",
            step_name="Executor",
        )

    print("Observed result:", result)
    print(session.events[0].model_dump(mode="json"))


if __name__ == "__main__":
    main()
