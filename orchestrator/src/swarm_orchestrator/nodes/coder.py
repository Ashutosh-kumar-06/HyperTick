"""REQ-1.2: Coder Node — generate C++ strategy conforming to StrategyInterface.hpp."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from swarm_orchestrator.broker.crdt_state import SwarmStateCRDT
from swarm_orchestrator.broker.redis_cache import AgentMemoryCache
from swarm_orchestrator.config import Settings
from swarm_orchestrator.llm_factory import create_llm
from swarm_orchestrator.prompts import CODER_SYSTEM
from swarm_orchestrator.state import SwarmState


def _strip_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def coder_node(state: SwarmState, settings: Settings) -> dict:
    task_id = state.get("task_id", "")
    crdt = SwarmStateCRDT(settings.redis_url, settings.crdt_node_id or None)
    if settings.enable_crdt_sync:
        crdt.subscribe_sync(task_id)

    cache = AgentMemoryCache(settings.redis_url)
    history = crdt.format_iteration_log(task_id) or cache.format_for_prompt(task_id)

    llm = create_llm(settings)

    hypothesis_text = ""
    hypothesis = state.get("hypothesis")
    if hypothesis:
        hypothesis_text = hypothesis.model_dump_json(indent=2)

    reflection = ""
    if state.get("reflection_notes"):
        reflection = f"\n\nFix these issues from the evaluator:\n{state['reflection_notes']}"
    outcome = state.get("outcome")
    if outcome and outcome.stderr:
        reflection += f"\n\nCompiler/runtime stderr:\n{outcome.stderr[:4000]}"

    response = llm.invoke([
        SystemMessage(content=CODER_SYSTEM),
        HumanMessage(content=f"{history}\n\nHypothesis:\n{hypothesis_text}{reflection}"),
    ])

    source = _strip_fences(response.content)
    iteration = state.get("iteration", 0)

    crdt.update_register(task_id, "strategy_source", source)
    crdt.append_iteration(task_id, {
        "iteration": iteration,
        "status": "coded",
        "notes": f"Generated strategy for {hypothesis.name if hypothesis else 'unknown'}",
    })
    if settings.enable_crdt_sync:
        crdt.publish_for_sync(task_id)

    cache.append_iteration(task_id, {
        "iteration": iteration,
        "status": "coded",
        "notes": f"Generated strategy for {hypothesis.name if hypothesis else 'unknown'}",
    })

    return {
        "strategy_source": source,
        "iteration": iteration + 1,
        "iteration_log": [f"[coder] Iteration {iteration + 1} source generated ({len(source)} bytes)"],
    }
