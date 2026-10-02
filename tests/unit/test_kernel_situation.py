"""Tests for the situation manager (kernel Phase 3).

Pure transition logic plus the durable manager against on-disk SQLite (tmp_path).
"""
import pytest


@pytest.fixture
def sm(load):
    return load("kernel.situation")


# ── pure transition table ───────────────────────────────────────────────────────
def test_can_transition_follows_lifecycle(sm):
    assert sm.can_transition(sm.NORMAL, sm.POSSIBLE)
    assert sm.can_transition(sm.POSSIBLE, sm.INVESTIGATING)
    assert sm.can_transition(sm.INVESTIGATING, sm.CONFIRMED)
    assert sm.can_transition(sm.INVESTIGATING, sm.BENIGN)
    assert sm.can_transition(sm.CONFIRMED, sm.RESPONSE)
    assert sm.can_transition(sm.RESPONSE, sm.RESOLVED)
    # disallowed jumps
    assert not sm.can_transition(sm.NORMAL, sm.CONFIRMED)
    assert not sm.can_transition(sm.POSSIBLE, sm.RESPONSE)
    assert not sm.can_transition(sm.RESOLVED, sm.POSSIBLE)  # terminal


def test_is_terminal(sm):
    assert sm.is_terminal(sm.RESOLVED)
    assert not sm.is_terminal(sm.INVESTIGATING)


def test_every_active_state_can_reach_resolved(sm):
    for state in (sm.POSSIBLE, sm.INVESTIGATING, sm.CONFIRMED, sm.RESPONSE, sm.BENIGN):
        assert sm.can_transition(state, sm.RESOLVED), state


# ── Situation value semantics ─────────────────────────────────────────────────
def test_stepped_records_history_and_is_immutable(sm):
    s0 = sm.Situation(kind="intrusion", state=sm.POSSIBLE)
    s1 = s0.stepped(sm.INVESTIGATING, reason="motion", event_id="e1")
    assert s0.state == sm.POSSIBLE and s0.history == ()      # original untouched
    assert s1.state == sm.INVESTIGATING
    assert s1.history[-1]["from"] == sm.POSSIBLE
    assert s1.history[-1]["to"] == sm.INVESTIGATING
    assert s1.history[-1]["reason"] == "motion" and s1.history[-1]["event_id"] == "e1"
    assert s1.id == s0.id and s1.active is True


def test_stepped_rejects_invalid_transition(sm):
    s = sm.Situation(kind="intrusion", state=sm.POSSIBLE)
    with pytest.raises(sm.InvalidTransition):
        s.stepped(sm.RESPONSE)   # POSSIBLE → RESPONSE not allowed


def test_to_from_dict_roundtrip(sm):
    s = sm.Situation(kind="intrusion", state=sm.POSSIBLE, subject="front_door",
                     location="porch", correlation_id="c1", data={"k": 1})
    s = s.stepped(sm.INVESTIGATING, reason="motion")
    again = sm.Situation.from_dict(s.to_dict())
    assert again == s
    assert isinstance(again.history, tuple)


# ── durable manager ───────────────────────────────────────────────────────────
@pytest.fixture
def mgr(sm, tmp_path):
    return sm.SituationManager(str(tmp_path / "situations.db"))


def test_open_persists_and_is_retrievable(sm, mgr):
    s = mgr.open("intrusion", subject="front_door", location="porch",
                 correlation_id="c1", data={"breach": "door"})
    assert s.state == sm.POSSIBLE
    got = mgr.get(s.id)
    assert got is not None
    assert got.kind == "intrusion" and got.subject == "front_door"
    assert got.correlation_id == "c1" and got.data == {"breach": "door"}
    assert got.history[0]["to"] == sm.POSSIBLE and got.history[0]["reason"] == "opened"


def test_transition_persists_new_state(sm, mgr):
    s = mgr.open("intrusion")
    mgr.transition(s.id, sm.INVESTIGATING, reason="motion", event_id="e1")
    mgr.transition(s.id, sm.CONFIRMED, reason="vision")
    got = mgr.get(s.id)
    assert got.state == sm.CONFIRMED
    assert [h["to"] for h in got.history] == [sm.POSSIBLE, sm.INVESTIGATING, sm.CONFIRMED]


def test_transition_rejects_invalid(sm, mgr):
    s = mgr.open("intrusion")
    with pytest.raises(sm.InvalidTransition):
        mgr.transition(s.id, sm.RESPONSE)   # POSSIBLE → RESPONSE
    assert mgr.get(s.id).state == sm.POSSIBLE   # unchanged, nothing persisted


def test_transition_unknown_id_raises(sm, mgr):
    with pytest.raises(KeyError):
        mgr.transition("sit_nope", sm.INVESTIGATING)


def test_open_situations_excludes_resolved_and_filters_kind(sm, mgr):
    a = mgr.open("intrusion", subject="a")
    b = mgr.open("delivery", subject="b")
    c = mgr.open("intrusion", subject="c")
    mgr.resolve(c.id, reason="done")

    intrusion_open = {s.id for s in mgr.open_situations("intrusion")}
    assert intrusion_open == {a.id}            # c resolved, b is a different kind
    all_open = {s.id for s in mgr.open_situations()}
    assert all_open == {a.id, b.id}
    assert mgr.get(c.id).terminal is True


def test_resolve_from_confirmed_path(sm, mgr):
    s = mgr.open("intrusion")
    mgr.transition(s.id, sm.INVESTIGATING)
    mgr.transition(s.id, sm.CONFIRMED)
    mgr.transition(s.id, sm.RESPONSE, reason="alarm")
    final = mgr.resolve(s.id, reason="cleared")
    assert final.state == sm.RESOLVED and final.terminal
    assert mgr.open_situations("intrusion") == []
