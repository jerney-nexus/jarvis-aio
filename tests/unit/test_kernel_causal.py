"""Tests for causal learning (kernel Phase 7). Pure, no I/O."""
import pytest


@pytest.fixture
def C(load):
    return load("kernel.causal")


def _feed(C, model, cause, effect, trials):
    """trials: list of (cause_present, effect_present)."""
    for cp, ep in trials:
        model.observe(cause, effect, cause_present=cp, effect_present=ep)
    return model.get(cause, effect)


def test_perfect_cause_has_high_positive_confidence(C):
    m = C.CausalModel()
    # Effect always with cause, never without.
    h = _feed(C, m, "door_open", "cold", [(True, True)] * 20 + [(False, False)] * 20)
    assert h.delta_p == pytest.approx(1.0)
    assert h.confidence > 0.8 and h.direction == "causes"


def test_no_relationship_is_near_zero(C):
    m = C.CausalModel()
    # Effect equally likely with and without the cause.
    trials = [(True, True), (True, False), (False, True), (False, False)] * 10
    h = _feed(C, m, "x", "y", trials)
    assert abs(h.delta_p) < 1e-9
    assert h.confidence == pytest.approx(0.0) and h.direction == "none"


def test_preventive_cause_is_negative(C):
    m = C.CausalModel()
    # Cause suppresses the effect.
    h = _feed(C, m, "heater_on", "cold", [(True, False)] * 20 + [(False, True)] * 20)
    assert h.delta_p == pytest.approx(-1.0)
    assert h.confidence < -0.8 and h.direction == "prevents"


def test_small_sample_is_shrunk(C):
    m = C.CausalModel()
    # Perfect contrast but only 2 trials → confidence well below |delta_p|=1.
    h = _feed(C, m, "c", "e", [(True, True), (False, False)])
    assert h.delta_p == pytest.approx(1.0)
    assert 0.0 < h.confidence < 0.5   # shrinkage toward 0


def test_confidence_zero_without_both_sides(C):
    m = C.CausalModel()
    # Only ever observed the cause present → P(E|¬C) undefined → confidence 0.
    h = _feed(C, m, "c", "e", [(True, True)] * 10)
    assert h.p_effect_given_not_cause is None
    assert h.confidence == 0.0


def test_observe_accumulates_contingency(C):
    m = C.CausalModel()
    h = _feed(C, m, "c", "e", [(True, True), (True, False), (False, True), (False, False)])
    assert (h.n11, h.n10, h.n01, h.n00) == (1, 1, 1, 1)
    assert h.trials == 4


def test_ranked_orders_by_abs_confidence(C):
    m = C.CausalModel()
    _feed(C, m, "strong", "e", [(True, True)] * 30 + [(False, False)] * 30)
    _feed(C, m, "weak", "e", [(True, True), (True, False), (False, True), (False, False)] * 3)
    ranked = m.ranked()
    assert ranked[0].cause == "strong"
    strong_only = m.ranked(min_abs_confidence=0.5)
    assert [h.cause for h in strong_only] == ["strong"]


def test_model_confidence_accessor(C):
    m = C.CausalModel()
    assert m.confidence("missing", "e") == 0.0   # unknown hypothesis → 0
    _feed(C, m, "c", "e", [(True, True)] * 20 + [(False, False)] * 20)
    assert m.confidence("c", "e") > 0.8
