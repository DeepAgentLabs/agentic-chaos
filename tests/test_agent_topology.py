from agentic_chaos.agents.topology import TopologyTracker
from agentic_chaos.models.agent_topology import AgentEdge, AgentNode, AgentTopology


class TestAgentTopologyModel:
    def test_agent_node_defaults(self) -> None:
        node = AgentNode(name="Planner")
        assert node.id
        assert node.name == "Planner"
        assert node.type == "agent"

    def test_agent_edge_defaults(self) -> None:
        edge = AgentEdge(source_id="a", target_id="b")
        assert edge.id
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.message_type == "call"
        assert edge.timestamp is not None

    def test_agent_topology_empty(self) -> None:
        topo = AgentTopology()
        assert topo.nodes == []
        assert topo.edges == []

    def test_agent_topology_as_json(self) -> None:
        topo = AgentTopology(
            nodes=[AgentNode(name="A"), AgentNode(name="B", type="tool")],
        )
        data = topo.as_json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["name"] == "A"
        assert data["nodes"][1]["type"] == "tool"
        assert data["edges"] == []


class TestTopologyTracker:
    def test_register_node(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        node = tracker.register_node("Planner", type="agent")
        assert node.name == "Planner"
        assert node.type == "agent"
        assert len(tracker.topology.nodes) == 1

    def test_register_node_idempotent(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        n1 = tracker.register_node("Planner")
        n2 = tracker.register_node("Planner")
        assert n1 is n2
        assert len(tracker.topology.nodes) == 1

    def test_register_node_does_not_overwrite_type_on_re_registration(self) -> None:
        """Bug fix: re-registering with a different type must NOT clobber the original."""
        tracker = TopologyTracker(auto_activate=False)
        node = tracker.register_node("search_tool", type="tool")
        assert node.type == "tool"
        same_node = tracker.register_node("search_tool", type="agent")
        assert same_node is node
        assert same_node.type == "tool"  # NOT overwritten

    def test_record_edge_does_not_overwrite_existing_node_type(self) -> None:
        """The docstring example: register as 'tool', then record_edge with default
        target_type='agent' — type must stay 'tool'."""
        tracker = TopologyTracker(auto_activate=False)
        tracker.register_node("search_tool", type="tool")
        tracker.record_edge("Planner", "search_tool", message_type="tool_call")
        search_node = tracker._nodes_by_name["search_tool"]
        assert search_node.type == "tool"  # NOT flipped to "agent"

    def test_set_node_type_explicitly_changes_type(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        tracker.register_node("search", type="tool")
        tracker.set_node_type("search", "agent")
        assert tracker._nodes_by_name["search"].type == "agent"

    def test_set_node_type_raises_for_unregistered_node(self) -> None:
        import pytest

        tracker = TopologyTracker(auto_activate=False)
        with pytest.raises(KeyError, match="not been registered"):
            tracker.set_node_type("ghost", "tool")

    def test_record_edge(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        tracker.register_node("Planner", type="agent")
        tracker.register_node("search", type="tool")
        edge = tracker.record_edge("Planner", "search", message_type="tool_call")

        assert edge.message_type == "tool_call"
        assert len(tracker.topology.edges) == 1
        assert len(tracker.topology.nodes) == 2

    def test_record_edge_auto_registers_nodes(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        tracker.record_edge(
            "Agent1", "Agent2", message_type="handoff", source_type="agent", target_type="agent"
        )

        assert len(tracker.topology.nodes) == 2
        assert len(tracker.topology.edges) == 1
        names = {n.name for n in tracker.topology.nodes}
        assert names == {"Agent1", "Agent2"}

    def test_full_topology_round_trip(self) -> None:
        tracker = TopologyTracker(auto_activate=False)
        tracker.register_node("SupportAgent", type="agent")
        tracker.record_edge(
            "SupportAgent",
            "search_tool",
            message_type="tool_call",
            target_type="tool",
        )
        tracker.record_edge(
            "SupportAgent",
            "refund_api",
            message_type="tool_call",
            target_type="tool",
        )

        topo = tracker.topology
        assert len(topo.nodes) == 3
        assert len(topo.edges) == 2

        data = topo.as_json()
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2
        assert all("id" in n for n in data["nodes"])
        assert all("source_id" in e for e in data["edges"])

    def test_topology_embeds_in_chaos_report(self) -> None:
        from datetime import datetime, timezone

        from agentic_chaos.models import ChaosReport

        tracker = TopologyTracker()
        tracker.record_edge("A", "B", message_type="handoff")

        report = ChaosReport(
            name="agent-test",
            start_time=datetime.now(timezone.utc),
            agent_topology=tracker.topology.as_json(),
        )

        dumped = report.model_dump(mode="json")
        assert dumped["agent_topology"] is not None
        assert len(dumped["agent_topology"]["nodes"]) == 2
        assert len(dumped["agent_topology"]["edges"]) == 1


class TestTopologyTrackerContextvar:
    def test_auto_activate_registers_in_contextvar(self) -> None:
        from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker

        tracker = TopologyTracker()
        assert get_active_tracker() is tracker
        reset_active_tracker()
        assert get_active_tracker() is None

    def test_deactivate_resets_contextvar(self) -> None:
        from agentic_chaos.agents.topology import get_active_tracker

        tracker = TopologyTracker()
        assert get_active_tracker() is tracker
        tracker.deactivate()
        assert get_active_tracker() is None

    def test_context_manager_resets_on_exit(self) -> None:
        from agentic_chaos.agents.topology import get_active_tracker

        with TopologyTracker() as tracker:
            assert get_active_tracker() is tracker
        assert get_active_tracker() is None

    def test_no_leak_across_sequential_trackers(self) -> None:
        from agentic_chaos.agents.topology import get_active_tracker

        tracker1 = TopologyTracker()
        tracker1.register_node("A")
        tracker1.deactivate()

        # Second invocation without a tracker — should see None
        assert get_active_tracker() is None

    def test_auto_activate_false_does_not_register(self) -> None:
        from agentic_chaos.agents.topology import get_active_tracker, reset_active_tracker

        # Ensure clean state
        reset_active_tracker()
        TopologyTracker(auto_activate=False)
        assert get_active_tracker() is None
