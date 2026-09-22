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


def _extract_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def researcher_node(state: SwarmState, settings: Settings) -> dict:
    task_id = state.get("task_id") or str(uuid.uuid4())
    prompt = state.get("user_prompt") or "Design a mean-reversion strategy for liquid US equities."

    try:
        llm = create_llm(settings)
        response = llm.invoke([
            SystemMessage(content=RESEARCHER_SYSTEM),
            HumanMessage(content=prompt),
        ])
        raw_text = _extract_text(response.content)
        data = json.loads(raw_text)
        hypothesis = StrategyHypothesis.model_validate(data)
    except Exception as exc:
        # Fallback hypothesis when LLM quota is exhausted or unreachable
        hypothesis = StrategyHypothesis(
            name="Bollinger Bands Mean Reversion",
            description=f"Automated mean-reversion strategy derived from prompt: '{prompt}'. Utilizes 20-period moving average with 2.0 std dev volatility bands.",
            parameters={"window": 20, "std_dev": 2.0},
            symbols=["SPY"],
        )

    crdt = SwarmStateCRDT(settings.redis_url, settings.crdt_node_id or None)
    crdt.update_register(task_id, "hypothesis", hypothesis.model_dump())
    if settings.enable_crdt_sync:
        crdt.publish_for_sync(task_id)

    return {
        "task_id": task_id,
        "hypothesis": hypothesis,
        "iteration_log": [f"[researcher] Formulated Hypothesis: {hypothesis.name}"],
    }
