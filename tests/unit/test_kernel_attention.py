"""Tests for attention / interruption arbitration (kernel Phase 6). Pure."""
import pytest


@pytest.fixture
def A(load):
    return load("kernel.attention")


def _req(A, priority, category="info"):
    return A.AttentionRequest(category=category, priority=priority)


def test_normal_allowed_with_budget(A):
    d = A.arbitrate(_req(A, A.NORMAL), A.AttentionContext(budget_remaining=1.0))
    assert d.allowed


def test_critical_overrides_quiet_shush_budget(A):
    ctx = A.AttentionContext(budget_remaining=0.0, quiet_hours=True, shushed=True,
                             recent_interruptions=99)
    d = A.arbitrate(_req(A, A.CRITICAL), ctx)
    assert d.allowed


def test_duplicate_suppressed_even_if_critical(A):
    d = A.arbitrate(_req(A, A.CRITICAL), A.AttentionContext(duplicate=True))
    assert d.decision == A.SUPPRESS


def test_shush_suppresses_non_critical(A):
    d = A.arbitrate(_req(A, A.HIGH), A.AttentionContext(shushed=True))
    assert d.decision == A.SUPPRESS


def test_quiet_hours_defers_below_high(A):
    assert A.arbitrate(_req(A, A.NORMAL), A.AttentionContext(quiet_hours=True)).decision == A.DEFER
    # HIGH breaks through quiet hours
    assert A.arbitrate(_req(A, A.HIGH), A.AttentionContext(quiet_hours=True)).allowed


def test_exhausted_budget_defers_non_high(A):
    assert A.arbitrate(_req(A, A.NORMAL), A.AttentionContext(budget_remaining=0.0)).decision == A.DEFER
    assert A.arbitrate(_req(A, A.HIGH), A.AttentionContext(budget_remaining=0.0)).allowed


def test_too_many_recent_defers_low_importance(A):
    ctx = A.AttentionContext(recent_interruptions=3, max_recent=3)
    assert A.arbitrate(_req(A, A.NORMAL), ctx).decision == A.DEFER
    assert A.arbitrate(_req(A, A.HIGH), ctx).allowed   # HIGH still gets through
