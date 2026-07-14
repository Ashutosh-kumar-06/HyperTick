"""RabbitMQ task/result brokerage (REQ-2.1)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pika
from pydantic import BaseModel, Field


EXCHANGE = "trading_swarm_exchange"
TASK_QUEUE = "backtest_tasks"
RESULT_QUEUE = "backtest_results"
ROUTING_TASK = "backtest.task"
ROUTING_RESULT = "backtest.result"


class BacktestTaskPayload(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    iteration: int = 0
    strategy_source: str
    strategy_filename: str = "strategy.cpp"
    dataset_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacktestResultPayload(BaseModel):
    task_id: str
    status: str
    metrics: dict[str, Any] | None = None
    stderr: str = ""
    stdout: str = ""
    exit_code: int = 0


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=TASK_QUEUE, durable=True)
    channel.queue_declare(queue=RESULT_QUEUE, durable=True)
    channel.queue_bind(queue=TASK_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_TASK)
    channel.queue_bind(queue=RESULT_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_RESULT)


def publish_task(channel: pika.adapters.blocking_connection.BlockingChannel, payload: BacktestTaskPayload) -> None:
    declare_topology(channel)
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=ROUTING_TASK,
        body=payload.model_dump_json(),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )


def publish_result(channel: pika.adapters.blocking_connection.BlockingChannel, payload: BacktestResultPayload) -> None:
    declare_topology(channel)
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=ROUTING_RESULT,
        body=payload.model_dump_json(),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )


def parse_result(body: bytes) -> BacktestResultPayload:
    return BacktestResultPayload.model_validate(json.loads(body))
