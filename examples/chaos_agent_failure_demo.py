"""agentic-chaos v0.2 demo — Agent Failure Injection

Demonstrates all three v0.2 agent fault types (tool_failure,
memory_corruption, infinite_loop) using plain Python callables —
no LangGraph or other framework required.

Run directly:
    python examples/chaos_agent_failure_demo.py

Run with CLI (injects faults externally):
    agentic-chaos agent run examples/chaos_agent_failure_demo.py \
        --inject tool_failure,memory_corruption
"""

from agentic_chaos import (
    InfiniteLoopFault,
    MemoryCorruptionFault,
    ToolCallFailureFault,
    TopologyTracker,
    chaos_call,
    chaos_session,
    wrap_tool,
)
from agentic_chaos.agents.faults import ToolCallFailureError

# ---------------------------------------------------------------------------
# Mock agent components (replace these with your real agent code)
# ---------------------------------------------------------------------------


def search_knowledge_base(query: str) -> str:
    """Simulates a knowledge-base / RAG retrieval tool."""
    return f"Result for '{query}': The order #123 is shipped and arriving tomorrow."


def check_refund_status(order_id: str) -> dict[str, str]:
    """Simulates a refund-status API tool."""
    return {"order_id": order_id, "status": "approved", "amount": "$49.99"}


def read_agent_memory(key: str) -> str:
    """Simulates reading from shared agent memory/state."""
    return f"Memory[{key}]: Customer is a premium member since 2023."


def agent_decide_next_action(context: str) -> str:
    """Simulates the agent's decision loop (should it take another action?)."""
    return "DONE: I have all the information needed."


# ---------------------------------------------------------------------------
# Demo 1: Tool-call failure (error mode)
# ---------------------------------------------------------------------------


def demo_tool_failure() -> None:
    print("\n" + "=" * 60)
    print("Demo 1: Tool-Call Failure (error mode)")
    print("=" * 60)

    with chaos_session([ToolCallFailureFault(tool_name="search")]) as session:
        # This tool is targeted — it will fail
        try:
            result = chaos_call(
                search_knowledge_base,
                "order status",
                step_name="search",
                faults=["tool_failure"],
            )
            print(f"  Search result: {result}")
        except ToolCallFailureError as exc:
            print(f"  Tool failed (caught): {exc}")
            print("  → Agent would retry or use fallback here.")

    print(f"  Events recorded: {len(session.events)}")


# ---------------------------------------------------------------------------
# Demo 2: Memory corruption (garble mode)
# ---------------------------------------------------------------------------


def demo_memory_corruption() -> None:
    print("\n" + "=" * 60)
    print("Demo 2: Memory Corruption (garble mode)")
    print("=" * 60)

    with chaos_session([MemoryCorruptionFault(mode="garble", seed=42)]) as session:
        result = chaos_call(
            read_agent_memory,
            "customer_profile",
            step_name="memory_read",
            faults=["memory_corruption"],
        )
        print(f"  Corrupted memory: {result}")
        print("  → Agent sees garbled state — will it notice?")

    print(f"  Events recorded: {len(session.events)}")


# ---------------------------------------------------------------------------
# Demo 3: Infinite loop (forced extra turns)
# ---------------------------------------------------------------------------


def demo_infinite_loop() -> None:
    print("\n" + "=" * 60)
    print("Demo 3: Infinite Loop (3 forced extra turns)")
    print("=" * 60)

    with chaos_session([InfiniteLoopFault(force_turns=3)]) as session:
        max_iterations = 10
        for i in range(max_iterations):
            decision = chaos_call(
                agent_decide_next_action,
                f"context_turn_{i}",
                step_name="decide",
                faults=["infinite_loop"],
            )
            print(f"  Turn {i + 1}: {decision[:60]}...")
            if decision.startswith("DONE"):
                print(f"  Agent terminated after {i + 1} turns.")
                break
        else:
            print(f"  ⚠ Agent hit max iterations ({max_iterations}) — no termination!")

    print(f"  Events recorded: {len(session.events)}")


# ---------------------------------------------------------------------------
# Demo 4: wrap_tool() with TopologyTracker
# ---------------------------------------------------------------------------


def demo_wrap_tool_with_topology() -> None:
    print("\n" + "=" * 60)
    print("Demo 4: wrap_tool() + TopologyTracker")
    print("=" * 60)

    tracker = TopologyTracker()
    tracker.register_node("SupportAgent", type="agent")

    # Wrap tools — chaos is injected transparently
    search = wrap_tool(
        search_knowledge_base,
        tool_name="search",
        tracker=tracker,
        caller_node="SupportAgent",
    )
    refund = wrap_tool(
        check_refund_status,
        tool_name="refund",
        tracker=tracker,
        caller_node="SupportAgent",
    )

    with chaos_session([ToolCallFailureFault(mode="empty", tool_name="search")]):
        result1 = search("order #123")
        print(f"  Search result (empty fault): {result1}")

        result2 = refund("123")
        print(f"  Refund result (no fault — different tool): {result2}")

    topo = tracker.topology
    print(f"\n  Topology: {len(topo.nodes)} nodes, {len(topo.edges)} edges")
    for node in topo.nodes:
        print(f"    Node: {node.name} ({node.type})")
    for edge in topo.edges:
        src = next(n.name for n in topo.nodes if n.id == edge.source_id)
        tgt = next(n.name for n in topo.nodes if n.id == edge.target_id)
        print(f"    Edge: {src} → {tgt} ({edge.message_type})")


# ---------------------------------------------------------------------------
# Run all demos
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    demo_tool_failure()
    demo_memory_corruption()
    demo_infinite_loop()
    demo_wrap_tool_with_topology()

    print("\n" + "=" * 60)
    print("All demos complete!")
    print("=" * 60)
