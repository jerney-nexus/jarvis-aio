"""Tests for the agency budget (kernel MCU A3)."""
import pytest


@pytest.fixture
def bud(load):
    return load("kernel.budget")


def test_rate_allows_until_cap_then_blocks(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(window_s=3600.0, rates={"action": 3}))
    for i in range(3):
        v = b.check_and_record("action", now=float(i))
        assert v.allowed, i
    # 4th within the window → blocked.
    v = b.check_and_record("action", now=3.0)
    assert not v.allowed and v.reason == bud.RATE_EXCEEDED
    assert b.count("action", now=3.0) == 3      # the blocked one wasn't recorded


def test_sliding_window_frees_slots(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(window_s=100.0, rates={"action": 2}))
    b.check_and_record("action", now=0.0)
    b.check_and_record("action", now=10.0)
    assert not b.allow("action", now=50.0).allowed      # full
    # after the window passes the first event ages out → a slot frees.
    assert b.allow("action", now=101.0).allowed
    assert b.remaining("action", now=101.0) == 1


def test_unlimited_rate_when_cap_zero(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(rates={"action": 0}))
    for i in range(1000):
        assert b.check_and_record("action", now=float(i)).allowed
    assert b.remaining("action", now=0.0) is None


def test_allow_does_not_consume(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(rates={"llm": 1}))
    assert b.allow("llm", now=0.0).allowed
    assert b.allow("llm", now=0.0).allowed          # still allowed — allow() is pure
    b.record("llm", now=0.0)
    assert not b.allow("llm", now=0.0).allowed


def test_retries_cap(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(retries_per_action=2))
    assert b.retries_ok(1).allowed                   # first try
    assert b.retries_ok(3).allowed                   # first + 2 retries
    v = b.retries_ok(4)
    assert not v.allowed and v.reason == bud.RETRIES_EXCEEDED


def test_delegation_depth_cap(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(max_delegation_depth=2))
    assert b.depth_ok(2).allowed
    v = b.depth_ok(3)
    assert not v.allowed and v.reason == bud.DEPTH_EXCEEDED


def test_concurrency_cap(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(max_concurrency={"action": 2}))
    assert b.concurrency_ok("action", in_flight=1).allowed
    v = b.concurrency_ok("action", in_flight=2)
    assert not v.allowed and v.reason == bud.CONCURRENCY_EXCEEDED
    # unknown kind with no configured cap → unlimited
    assert b.concurrency_ok("llm", in_flight=99).allowed


def test_reset(bud):
    b = bud.AgencyBudget(bud.BudgetLimits(rates={"action": 1}))
    b.record("action", now=0.0)
    assert not b.allow("action", now=0.0).allowed
    b.reset("action")
    assert b.allow("action", now=0.0).allowed


def test_default_limits_are_sane(bud):
    b = bud.AgencyBudget()
    assert b.limits.rate_for("action") > 0
    assert b.limits.rate_for("llm") > 0
    assert b.limits.max_delegation_depth > 0
