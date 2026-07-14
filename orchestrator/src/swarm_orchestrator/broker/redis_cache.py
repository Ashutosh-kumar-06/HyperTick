"""Redis sliding-window agent memory cache (REQ-2.2)."""

from __future__ import annotations

import json
from typing import Any

import redis


class AgentMemoryCache:
  def __init__(self, redis_url: str, window_size: int = 10):
      self._client = redis.from_url(redis_url, decode_responses=True)
      self._window = window_size

  def _key(self, task_id: str) -> str:
      return f"swarm:iterations:{task_id}"

  def append_iteration(self, task_id: str, entry: dict[str, Any]) -> None:
      key = self._key(task_id)
      self._client.rpush(key, json.dumps(entry))
      self._client.ltrim(key, -self._window, -1)
      self._client.expire(key, 86_400)

  def get_history(self, task_id: str) -> list[dict[str, Any]]:
      key = self._key(task_id)
      raw = self._client.lrange(key, 0, -1)
      return [json.loads(item) for item in raw]

  def format_for_prompt(self, task_id: str) -> str:
      history = self.get_history(task_id)
      if not history:
          return ""
      lines = ["Previous iterations (most recent last):"]
      for i, entry in enumerate(history, 1):
          lines.append(f"  [{i}] status={entry.get('status')} notes={entry.get('notes', '')[:200]}")
      return "\n".join(lines)
