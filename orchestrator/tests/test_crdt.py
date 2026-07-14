"""Tests for CRDT merge semantics."""

from swarm_orchestrator.broker.crdt_state import GCounter, LWWRegister, ORSet


def test_lww_register_merge():
    a = LWWRegister("old", 1.0, "node-a")
    b = LWWRegister("new", 2.0, "node-b")
    assert a.merge(b).value == "new"


def test_or_set_merge():
    left = ORSet()
    uid = left.add({"status": "coded"})
    right = ORSet()
    right.elements[uid] = left.elements[uid]
    merged = left.merge(right)
    assert len(merged.values()) == 1


def test_gcounter_merge():
    a = GCounter({"node-a": 3})
    b = GCounter({"node-b": 2, "node-a": 5})
    assert a.merge(b).value() == 7
