"""REQ-1.3 / REQ-1.4: Evaluator Node and reflection routing."""

from __future__ import annotations

import json
import time

import pika
from langchain_core.messages import HumanMessage, SystemMessage
from pymongo import MongoClient

from swarm_orchestrator.broker.crdt_state import SwarmStateCRDT
from swarm_orchestrator.broker.rabbitmq import (
    BacktestResultPayload,
    BacktestTaskPayload,
    RESULT_QUEUE,
    declare_topology,
    parse_result,
    publish_task,
)
from swarm_orchestrator.broker.redis_cache import AgentMemoryCache
from swarm_orchestrator.config import Settings
from swarm_orchestrator.llm_factory import create_llm
from swarm_orchestrator.prompts import EVALUATOR_SYSTEM
from swarm_orchestrator.state import BacktestMetrics, BacktestOutcome, SwarmState


def _wait_for_result(channel: pika.adapters.blocking_connection.BlockingChannel, task_id: str, timeout: float) -> BacktestResultPayload | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        method, _, body = channel.basic_get(queue=RESULT_QUEUE, auto_ack=True)
        if method is None:
            time.sleep(0.25)
            continue
        result = parse_result(body)
        if result.task_id == task_id:
            return result
    return None


def submit_and_evaluate_node(state: SwarmState, settings: Settings) -> dict:
    """Publish backtest task, wait for result, evaluate KPIs."""
    cache = AgentMemoryCache(settings.redis_url)

    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    declare_topology(channel)

    hypothesis = state.get("hypothesis")
    task = BacktestTaskPayload(
        task_id=state.get("task_id", ""),
        iteration=state.get("iteration", 0),
        strategy_source=state.get("strategy_source", ""),
        dataset_id=state.get("dataset_id", "sample_spy_ticks"),
        metadata={
            "hypothesis": hypothesis.description if hypothesis else "",
            "symbols": hypothesis.symbols if hypothesis else [],
        },
    )
    publish_task(channel, task)

    task_id = state.get("task_id", "")
    raw = _wait_for_result(channel, task_id, settings.backtest_timeout_sec)
    connection.close()

    if raw is None:
        outcome = BacktestOutcome(task_id=task_id, status="timeout", stderr="Backtest result timeout")
    else:
        metrics = None
        if raw.metrics:
            metrics = BacktestMetrics(**raw.metrics)
        outcome = BacktestOutcome(
            task_id=raw.task_id,
            status=raw.status,  # type: ignore[arg-type]
            metrics=metrics,
            stderr=raw.stderr,
            stdout=raw.stdout,
        )

    approved = False
    reflection = ""

    if outcome.status != "success":
        reflection = f"Execution failed with status={outcome.status}. stderr: {outcome.stderr[:2000]}"
    elif outcome.metrics:
        m = outcome.metrics
        failures = []
        if m.max_drawdown_pct > settings.max_drawdown_pct:
            failures.append(f"Max drawdown {m.max_drawdown_pct:.2f}% exceeds {settings.max_drawdown_pct}%")
        if m.avg_latency_us > settings.max_latency_us:
            failures.append(f"Avg latency {m.avg_latency_us:.2f}µs exceeds {settings.max_latency_us}µs")
        if m.sharpe_ratio < settings.min_sharpe_ratio:
            failures.append(f"Sharpe {m.sharpe_ratio:.2f} below minimum {settings.min_sharpe_ratio}")

        if failures:
            reflection = "; ".join(failures)
        else:
            approved = True

    if not approved and not reflection:
        llm = create_llm(settings)
        eval_input = json.dumps(outcome.model_dump(), indent=2)
        response = llm.invoke([
            SystemMessage(content=EVALUATOR_SYSTEM),
            HumanMessage(content=eval_input),
        ])
        reflection = response.content.strip()

    cache.append_iteration(task_id, {
        "iteration": state.get("iteration", 0),
        "status": outcome.status,
        "notes": reflection or "approved",
        "metrics": outcome.metrics.model_dump() if outcome.metrics else None,
    })

    crdt = SwarmStateCRDT(settings.redis_url, settings.crdt_node_id or None)
    crdt.update_register(task_id, "reflection_notes", reflection)
    crdt.append_iteration(task_id, {
        "iteration": state.get("iteration", 0),
        "status": outcome.status,
        "notes": reflection or "approved",
        "metrics": outcome.metrics.model_dump() if outcome.metrics else None,
    })
    if settings.enable_crdt_sync:
        crdt.publish_for_sync(task_id)

    if approved:
        try:
            client = MongoClient(settings.mongodb_url)
            db = client.get_default_database()
            hypothesis = state.get("hypothesis")
            db.strategies.insert_one({
                "task_id": task_id,
                "hypothesis": hypothesis.model_dump() if hypothesis else None,
                "strategy_source": state.get("strategy_source", ""),
                "metrics": outcome.metrics.model_dump() if outcome.metrics else None,
            })
        except Exception:
            pass

    return {
        "outcome": outcome,
        "approved": approved,
        "reflection_notes": reflection,
        "iteration_log": [f"[evaluator] status={outcome.status} approved={approved}"],
    }


def should_reflect(state: SwarmState) -> str:
    """REQ-1.4: Reflection edge — route back to coder or end."""
    if state.get("approved"):
        return "end"
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "end"
    return "coder"
