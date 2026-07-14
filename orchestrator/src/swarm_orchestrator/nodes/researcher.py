"""REQ-1.1: Researcher Node — generate strategy hypotheses."""

from __future__ import annotations

import json
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from swarm_orchestrator.broker.crdt_state import SwarmStateCRDT
from swarm_orchestrator.config import Settings
from swarm_orchestrator.llm_factory import create_llm
from swarm_orchestrator.prompts import RESEARCHER_SYSTEM
from swarm_orchestrator.state import StrategyHypothesis, SwarmState


def researcher_node(state: SwarmState, settings: Settings) -> dict:
    task_id = state.get("task_id") or str(uuid.uuid4())
    llm = create_llm(settings)

    prompt = state.get("user_prompt") or "Design a mean-reversion strategy for liquid US equities."
    response = llm.invoke([
        SystemMessage(content=RESEARCHER_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content)
        hypothesis = StrategyHypothesis.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        hypothesis = StrategyHypothesis(
            name="Generated Strategy",
            description=response.content.strip(),
            symbols=["SPY"],
        )

    crdt = SwarmStateCRDT(settings.redis_url, settings.crdt_node_id or None)
    crdt.update_register(task_id, "hypothesis", hypothesis.model_dump())
    if settings.enable_crdt_sync:
        crdt.publish_for_sync(task_id)

    return {
        "task_id": task_id,
        "hypothesis": hypothesis,
        "iteration_log": [f"[researcher] Hypothesis: {hypothesis.name}"],
    }
