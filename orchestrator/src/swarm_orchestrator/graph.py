"""LangGraph orchestration graph (REQ-1.1–1.4)."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from swarm_orchestrator.config import Settings
from swarm_orchestrator.nodes.coder import coder_node
from swarm_orchestrator.nodes.evaluator import should_reflect, submit_and_evaluate_node
from swarm_orchestrator.nodes.researcher import researcher_node
from swarm_orchestrator.state import SwarmState


def build_graph(settings: Settings | None = None):
    settings = settings or Settings()

    graph = StateGraph(SwarmState)

    graph.add_node("researcher", partial(researcher_node, settings=settings))
    graph.add_node("coder", partial(coder_node, settings=settings))
    graph.add_node("evaluator", partial(submit_and_evaluate_node, settings=settings))

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "coder")
    graph.add_edge("coder", "evaluator")
    graph.add_conditional_edges("evaluator", should_reflect, {"coder": "coder", "end": END})

    return graph.compile()
