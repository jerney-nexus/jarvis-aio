"""Tests for the emergency / priority hierarchy (kernel hardening H2)."""
import pytest


@pytest.fixture
def pri(load):
    return load("kernel.priority")


def test_order_is_highest_first(pri):
    assert pri.ORDER[0] == pri.LIFE_SAFETY
    assert pri.ORDER[-1] == pri.PERSONALITY
    ranks = [pri.rank(t) for t in pri.ORDER]
    assert ranks == sorted(ranks, reverse=True)


def test_rank_unknown_tier_is_lowest(pri):
    assert pri.rank("nonsense") == 0
    assert pri.rank(pri.CONVENIENCE) > 0


def test_is_safety(pri):
    assert pri.is_safety(pri.LIFE_SAFETY)
    assert pri.is_safety(pri.SECURITY)
    assert not pri.is_safety(pri.PROPERTY)
    assert not pri.is_safety(pri.CONVENIENCE)
    assert not pri.is_safety(pri.PERSONALITY)


def test_outranks(pri):
    assert pri.outranks(pri.LIFE_SAFETY, pri.SECURITY)
    assert pri.outranks(pri.SECURITY, pri.CONVENIENCE)
    assert not pri.outranks(pri.CONVENIENCE, pri.SECURITY)
    assert not pri.outranks(pri.HOUSEHOLD, pri.HOUSEHOLD)


def test_winner_prefers_higher_and_ties_to_first(pri):
    assert pri.winner(pri.SECURITY, pri.CONVENIENCE) == pri.SECURITY
    assert pri.winner(pri.CONVENIENCE, pri.SECURITY) == pri.SECURITY
    # Tie resolves to the first argument (caller order).
    assert pri.winner(pri.HOUSEHOLD, pri.HOUSEHOLD) == pri.HOUSEHOLD


def test_personality_never_overrides_safety(pri):
    # The core invariant from the audit.
    assert not pri.may_override(pri.PERSONALITY, pri.LIFE_SAFETY)
    assert not pri.may_override(pri.PERSONALITY, pri.SECURITY)
    # Personality is the lowest tier: it may arbitrate only with itself, never
    # override anything higher (safety included).
    assert pri.may_override(pri.PERSONALITY, pri.PERSONALITY)
    assert not pri.may_override(pri.PERSONALITY, pri.CONVENIENCE)


def test_may_override_is_rank_ordered(pri):
    assert pri.may_override(pri.LIFE_SAFETY, pri.SECURITY)
    assert pri.may_override(pri.SECURITY, pri.SECURITY)  # equal may override
    assert not pri.may_override(pri.CONVENIENCE, pri.PROPERTY)


def test_lower_tier_never_overrides_strictly_higher(pri):
    for i, hi in enumerate(pri.ORDER):
        for lo in pri.ORDER[i + 1:]:
            assert not pri.may_override(lo, hi), (lo, hi)
            assert pri.may_override(hi, lo), (hi, lo)
