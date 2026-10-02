"""Tests for probabilistic beliefs (kernel Phase 6). Pure, no I/O."""
import pytest


@pytest.fixture
def B(load):
    return load("kernel.beliefs")


def test_default_is_uncertain(B):
    b = B.Belief(proposition="door is open")
    assert b.probability == 0.5 and not b.contradicted


def test_supporting_evidence_raises_probability(B):
    b = B.Belief(proposition="p").with_evidence(B.Evidence("sensor", True, weight=1.0))
    assert b.probability > 0.5
    stronger = b.with_evidence(B.Evidence("camera", True, weight=2.0))
    assert stronger.probability > b.probability


def test_refuting_evidence_lowers_probability(B):
    b = B.Belief(proposition="p").with_evidence(B.Evidence("sensor", False, weight=1.5))
    assert b.probability < 0.5


def test_probability_stays_in_open_interval(B):
    b = B.Belief(proposition="p")
    for _ in range(50):
        b = b.with_evidence(B.Evidence("s", True, weight=5.0))
    assert 0.0 < b.probability < 1.0


def test_opposing_evidence_roughly_cancels(B):
    b = (B.Belief(proposition="p")
         .with_evidence(B.Evidence("a", True, weight=2.0))
         .with_evidence(B.Evidence("b", False, weight=2.0)))
    assert abs(b.probability - 0.5) < 1e-6
    assert b.contradicted and b.contradiction_strength() == pytest.approx(1.0)


def test_contradiction_flags(B):
    one_sided = (B.Belief(proposition="p")
                 .with_evidence(B.Evidence("a", True, 1.0))
                 .with_evidence(B.Evidence("b", True, 1.0)))
    assert not one_sided.contradicted and one_sided.contradiction_strength() == 0.0


def test_decay_pulls_toward_half(B):
    b = B.Belief(proposition="p", decay_per_day=1.0)
    b = b.with_evidence(B.Evidence("s", True, weight=3.0))   # log-odds 3.0
    p_before = b.probability
    decayed = b.decayed(now=b.updated_ts + 86400.0)   # one day → log-odds 2.0
    assert 0.5 < decayed.probability < p_before


def test_decay_does_not_overshoot_past_half(B):
    b = B.Belief(proposition="p", decay_per_day=100.0)   # huge pull
    b = b.with_evidence(B.Evidence("s", True, weight=2.0))
    decayed = b.decayed(now=b.updated_ts + 86400.0)
    assert decayed.probability == pytest.approx(0.5)   # clamps at 0.5, never flips


def test_no_decay_when_disabled(B):
    b = B.Belief(proposition="p").with_evidence(B.Evidence("s", True, 3.0))
    assert b.decayed(now=b.updated_ts + 10 * 86400.0).probability == b.probability


def test_seed_from_confidence_roundtrips_direction(B):
    hi = B.seed_from_confidence("p", 0.9)
    lo = B.seed_from_confidence("q", 0.1)
    assert hi.probability == pytest.approx(0.9, abs=1e-6) and hi.supported
    assert lo.probability == pytest.approx(0.1, abs=1e-6) and not lo.supported


def test_to_dict_serialisable(B):
    b = B.Belief(proposition="p").with_evidence(B.Evidence("s", True, 1.0))
    d = b.to_dict()
    assert d["proposition"] == "p" and isinstance(d["evidence"], list)
    assert d["evidence"][0]["source"] == "s"
