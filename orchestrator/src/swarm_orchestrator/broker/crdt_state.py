"""CRDT-based distributed agent state for multi-node orchestration."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import redis


@dataclass
class LWWRegister:
    """Last-Writer-Wins register CRDT."""

    value: Any = None
    timestamp: float = 0.0
    node_id: str = ""

    def merge(self, other: LWWRegister) -> LWWRegister:
        if other.timestamp > self.timestamp:
            return LWWRegister(other.value, other.timestamp, other.node_id)
        if other.timestamp == self.timestamp and other.node_id > self.node_id:
            return LWWRegister(other.value, other.timestamp, other.node_id)
        return self

    def set(self, value: Any, node_id: str) -> LWWRegister:
        return LWWRegister(value, time.time(), node_id)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "timestamp": self.timestamp, "node_id": self.node_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LWWRegister:
        return cls(data.get("value"), float(data.get("timestamp", 0)), data.get("node_id", ""))


@dataclass
class ORSet:
    """Observed-Remove Set CRDT for iteration log entries."""

    elements: dict[str, str] = field(default_factory=dict)  # uid -> payload json
    tombstones: set[str] = field(default_factory=set)

    def add(self, payload: dict[str, Any]) -> str:
        uid = str(uuid.uuid4())
        self.elements[uid] = json.dumps(payload)
        return uid

    def merge(self, other: ORSet) -> ORSet:
        merged_elements = dict(self.elements)
        merged_elements.update(other.elements)
        tombstones = self.tombstones | other.tombstones
        for uid in tombstones:
            merged_elements.pop(uid, None)
        return ORSet(merged_elements, tombstones)

    def values(self) -> list[dict[str, Any]]:
        return [json.loads(v) for uid, v in sorted(self.elements.items()) if uid not in self.tombstones]

    def to_dict(self) -> dict[str, Any]:
        return {"elements": self.elements, "tombstones": list(self.tombstones)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ORSet:
        return cls(dict(data.get("elements", {})), set(data.get("tombstones", [])))


@dataclass
class GCounter:
    """Grow-only counter CRDT for distributed iteration counts."""

    counts: dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str, amount: int = 1) -> None:
        self.counts[node_id] = self.counts.get(node_id, 0) + amount

    def value(self) -> int:
        return sum(self.counts.values())

    def merge(self, other: GCounter) -> GCounter:
        merged = dict(self.counts)
        for node_id, count in other.counts.items():
            merged[node_id] = max(merged.get(node_id, 0), count)
        return GCounter(merged)

    def to_dict(self) -> dict[str, int]:
        return dict(self.counts)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> GCounter:
        return GCounter(dict(data))


class SwarmStateCRDT:
    """Redis-backed CRDT state store for distributed LangGraph nodes."""

    def __init__(self, redis_url: str, node_id: str | None = None):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"

    def _key(self, task_id: str) -> str:
        return f"swarm:crdt:{task_id}"

    def load(self, task_id: str) -> dict[str, Any]:
        raw = self._client.get(self._key(task_id))
        if not raw:
            return self._empty_state()
        return json.loads(raw)

    def save(self, task_id: str, state: dict[str, Any]) -> None:
        self._client.set(self._key(task_id), json.dumps(state), ex=86_400)

    def _empty_state(self) -> dict[str, Any]:
        return {
            "hypothesis": LWWRegister().to_dict(),
            "strategy_source": LWWRegister().to_dict(),
            "reflection_notes": LWWRegister().to_dict(),
            "iteration_log": ORSet().to_dict(),
            "iteration_counter": GCounter().to_dict(),
        }

    def merge_remote(self, task_id: str, remote_state: dict[str, Any]) -> dict[str, Any]:
        local = self.load(task_id)

        merged = {
            "hypothesis": LWWRegister.from_dict(local["hypothesis"])
            .merge(LWWRegister.from_dict(remote_state.get("hypothesis", {})))
            .to_dict(),
            "strategy_source": LWWRegister.from_dict(local["strategy_source"])
            .merge(LWWRegister.from_dict(remote_state.get("strategy_source", {})))
            .to_dict(),
            "reflection_notes": LWWRegister.from_dict(local["reflection_notes"])
            .merge(LWWRegister.from_dict(remote_state.get("reflection_notes", {})))
            .to_dict(),
            "iteration_log": ORSet.from_dict(local["iteration_log"])
            .merge(ORSet.from_dict(remote_state.get("iteration_log", {})))
            .to_dict(),
            "iteration_counter": GCounter.from_dict(local["iteration_counter"])
            .merge(GCounter.from_dict(remote_state.get("iteration_counter", {})))
            .to_dict(),
        }
        self.save(task_id, merged)
        return merged

    def update_register(self, task_id: str, field: str, value: Any) -> None:
        state = self.load(task_id)
        reg = LWWRegister.from_dict(state.get(field, {})).set(value, self.node_id)
        state[field] = reg.to_dict()
        self.save(task_id, state)

    def append_iteration(self, task_id: str, entry: dict[str, Any]) -> None:
        state = self.load(task_id)
        or_set = ORSet.from_dict(state["iteration_log"])
        or_set.add(entry)
        state["iteration_log"] = or_set.to_dict()

        counter = GCounter.from_dict(state["iteration_counter"])
        counter.increment(self.node_id)
        state["iteration_counter"] = counter.to_dict()

        self.save(task_id, state)

    def get_iteration_count(self, task_id: str) -> int:
        state = self.load(task_id)
        return GCounter.from_dict(state["iteration_counter"]).value()

    def format_iteration_log(self, task_id: str) -> str:
        state = self.load(task_id)
        entries = ORSet.from_dict(state["iteration_log"]).values()
        if not entries:
            return ""
        lines = ["CRDT iteration log (merged across nodes):"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"  [{i}] status={entry.get('status')} notes={str(entry.get('notes', ''))[:200]}")
        return "\n".join(lines)

    def publish_for_sync(self, task_id: str, channel: str = "swarm:crdt:sync") -> None:
        """Broadcast local CRDT state for peer merge."""
        state = self.load(task_id)
        payload = json.dumps({"task_id": task_id, "node_id": self.node_id, "state": state})
        self._client.publish(channel, payload)

    def subscribe_sync(self, task_id: str, channel: str = "swarm:crdt:sync") -> None:
        """Merge state from pub/sub peers (blocking one-shot for simplicity)."""
        pubsub = self._client.pubsub()
        pubsub.subscribe(channel)
        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            if data.get("task_id") != task_id:
                continue
            if data.get("node_id") == self.node_id:
                continue
            self.merge_remote(task_id, data["state"])
            break
        pubsub.unsubscribe(channel)
        pubsub.close()
