"""Tests for feedback-loop detection (kernel hardening H3)."""
import pytest


@pytest.fixture
def ld(load):
    return load("kernel.loop_detect")


def test_single_fire_is_not_a_loop(ld):
    d = ld.LoopDetector()
    v = d.record("light.turn_on:bed", now=0.0)
    assert not v.looping and v.reason == ld.NONE and v.count == 1
    assert not bool(v)


def test_repetition_within_window_flags_loop(ld):
    d = ld.LoopDetector(window_s=10.0, max_repeats=3)
    assert not d.record("a", now=0.0).looping
    assert not d.record("a", now=1.0).looping
    v = d.record("a", now=2.0)
    assert v.looping and v.reason == ld.REPETITION and v.count == 3
    assert bool(v)


def test_spacing_out_fires_avoids_repetition(ld):
    d = ld.LoopDetector(window_s=10.0, max_repeats=3)
    # Each fire is outside the window of the previous ones → count stays low.
    for t in (0.0, 20.0, 40.0):
        v = d.record("a", now=t)
        assert not v.looping, t
        assert v.count == 1


def test_cooldown_holds_after_loop(ld):
    d = ld.LoopDetector(window_s=10.0, max_repeats=2, cooldown_s=30.0)
    d.record("a", now=0.0)
    v = d.record("a", now=1.0)
    assert v.looping and v.reason == ld.REPETITION
    # Next firing within cooldown → cooling_down, not a fresh loop flag.
    v2 = d.record("a", now=5.0)
    assert not v2.looping and v2.cooling_down and v2.reason == ld.COOLDOWN
    assert bool(v2)
    assert d.cooling_down("a", now=5.0)


def test_cooldown_expires(ld):
    d = ld.LoopDetector(window_s=10.0, max_repeats=2, cooldown_s=30.0)
    d.record("a", now=0.0)
    d.record("a", now=1.0)  # loop → cooldown until 31.0
    assert d.cooling_down("a", now=20.0)
    assert not d.cooling_down("a", now=31.0)
    # After cooldown a fresh firing is counted normally again.
    v = d.record("a", now=40.0)
    assert not v.looping and not v.cooling_down


def test_self_trigger_via_cause_chain(ld):
    d = ld.LoopDetector(max_repeats=99)  # isolate causal path from repetition
    # Action A fires and emits event e1.
    d.record("A", now=0.0, cause=None, event_id="e1")
    # Action B reacts to e1 and emits e2.
    d.record("B", now=1.0, cause="e1", event_id="e2")
    # Action A reacts to e2 → traces back A→e1→...→A: self-trigger loop.
    v = d.record("A", now=2.0, cause="e2", event_id="e3")
    assert v.looping and v.reason == ld.SELF_TRIGGER


def test_unrelated_cause_is_not_self_trigger(ld):
    d = ld.LoopDetector(max_repeats=99)
    d.record("A", now=0.0, cause=None, event_id="e1")
    d.record("B", now=1.0, cause="e1", event_id="e2")
    # C reacts to e2 but C never produced e1/e2 → not a self-trigger.
    v = d.record("C", now=2.0, cause="e2", event_id="e3")
    assert not v.looping


def test_chain_depth_bounds_the_walk(ld):
    d = ld.LoopDetector(max_repeats=99, chain_depth=2)
    # Build a long chain A(e0) → x1(e1) → x2(e2) → x3(e3), then A reacts to e3.
    d.record("A", now=0.0, cause=None, event_id="e0")
    d.record("x1", now=1.0, cause="e0", event_id="e1")
    d.record("x2", now=2.0, cause="e1", event_id="e2")
    d.record("x3", now=3.0, cause="e2", event_id="e3")
    # The A producer is 4 hops back but chain_depth=2 → not traced (bounded).
    v = d.record("A", now=4.0, cause="e3", event_id="e4")
    assert not v.looping


def test_reset_clears_state(ld):
    d = ld.LoopDetector(max_repeats=2, cooldown_s=30.0)
    d.record("a", now=0.0)
    d.record("a", now=1.0)  # loop → cooldown
    d.reset("a")
    assert not d.cooling_down("a", now=2.0)
    v = d.record("a", now=2.0)
    assert v.count == 1 and not v.looping


def test_reset_all(ld):
    d = ld.LoopDetector(max_repeats=2)
    d.record("a", now=0.0)
    d.record("b", now=0.0)
    d.reset()
    assert d.record("a", now=1.0).count == 1
    assert d.record("b", now=1.0).count == 1


def test_emitted_map_is_bounded(ld):
    d = ld.LoopDetector(max_repeats=99)
    d._max_emitted = 4
    for i in range(10):
        d.record(f"k{i}", now=float(i), event_id=f"e{i}")
    # The map was cleared at least once; it never grew unbounded.
    assert len(d._emitted) <= 4
