"""RabbitMQ consumer — consumes backtest_tasks, spawns sandbox workers, publishes results."""

from __future__ import annotations

import json
import sys

import pika

from swarm_consumer.config import ConsumerSettings
from swarm_consumer.sandbox import SandboxRunner

EXCHANGE = "trading_swarm_exchange"
TASK_QUEUE = "backtest_tasks"
RESULT_QUEUE = "backtest_results"
ROUTING_TASK = "backtest.task"
ROUTING_RESULT = "backtest.result"


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=TASK_QUEUE, durable=True)
    channel.queue_declare(queue=RESULT_QUEUE, durable=True)
    channel.queue_bind(queue=TASK_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_TASK)
    channel.queue_bind(queue=RESULT_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_RESULT)


def handle_task(body: bytes, runner: SandboxRunner, channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    payload = json.loads(body)
    task_id = payload["task_id"]
    metadata = payload.get("metadata", {})

    result = runner.run_backtest(
        strategy_source=payload["strategy_source"],
        dataset_id=payload["dataset_id"],
        commission_bps=metadata.get("commission_bps", 1.0),
        slippage_bps=metadata.get("slippage_bps", 0.5),
    )

    response = {
        "task_id": task_id,
        "status": result["status"],
        "metrics": result.get("metrics"),
        "stderr": result.get("stderr", ""),
        "stdout": result.get("stdout", ""),
        "exit_code": result.get("exit_code", 0),
    }

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=ROUTING_RESULT,
        body=json.dumps(response),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )


def main() -> None:
    settings = ConsumerSettings()
    runner = SandboxRunner(settings)
    instance = settings.consumer_instance_id or "consumer-local"

    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    declare_topology(channel)
    channel.basic_qos(prefetch_count=settings.rabbitmq_prefetch)

    def callback(ch, method, properties, body):
        try:
            handle_task(body, runner, ch)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            print(f"[{instance}] Task handler error: {exc}", file=sys.stderr)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=TASK_QUEUE, on_message_callback=callback)
    print(f"[{instance}] Consumer listening on backtest_tasks (prefetch={settings.rabbitmq_prefetch})...", flush=True)
    channel.start_consuming()


if __name__ == "__main__":
    main()
