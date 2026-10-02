"""Executable JARVIS Constitution (MCU audit A2).

docs/JARVIS_CONSTITUTION.md states the invariants JARVIS must never violate.
Documentation drifts; tests don't. Each test here *attempts the violation* of a
named invariant and asserts the responsible kernel primitive blocks it. If one of
these fails, an invariant has been broken — treat it as a release blocker, not a
flaky test.
"""
import pytest


@pytest.fixture
def K(load):
    return {
        "priority": load("kernel.priority"),
        "authority": load("kernel.authority"),
        "plan": load("kernel.plan"),
        "correlation": load("kernel.correlation"),
    }


# ── PERSONALITY_NEVER_OVERRIDES_SAFETY ───────────────────────────────────────
def test_personality_never_overrides_safety(K):
    pri = K["priority"]
    # Attempt: let a personality concern override a safety one.
    assert pri.may_override(pri.PERSONALITY, pri.LIFE_SAFETY) is False
    assert pri.may_override(pri.PERSONALITY, pri.SECURITY) is False
    # And no lower tier ever overrides a strictly higher one.
    for i, hi in enumerate(pri.ORDER):
        for lo in pri.ORDER[i + 1:]:
            assert pri.may_override(lo, hi) is False, (lo, hi)


# ── NO_DELEGATION_ESCALATION ─────────────────────────────────────────────────
def test_delegation_cannot_escalate_capabilities(K):
    auth = K["authority"]
    parent = auth.CapabilityToken(holder="sam", capabilities=frozenset({"light"}))
    # Attempt: derive a child that grants a capability the parent never held.
    child = parent.derive("friday", ["light", "lock.unlock"])
    assert "lock.unlock" not in child.capabilities      # narrowed, not escalated
    assert child.grants("light") and not child.grants("lock.unlock")


def test_delegated_child_never_outlives_parent(K):
    auth = K["authority"]
    parent = auth.CapabilityToken(holder="sam", capabilities=frozenset({"*"}),
                                  expires_at=100.0)
    # Attempt: give the child a longer TTL than the parent's remaining life.
    child = parent.derive("friday", ["light"], ttl=10_000.0, now=0.0)
    assert child.expires_at <= parent.expires_at


def test_authorize_denies_token_without_capability(K):
    auth = K["authority"]
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"light"}))
    req = auth.AuthorityRequest(capability="lock.unlock", actor="friday",
                                token=tok, identity="sam")
    assert auth.authorize(req).denied


# ── AUTONOMY_IS_REVOCABLE (expiry + revocation) ──────────────────────────────
def test_expired_token_is_denied(K):
    auth = K["authority"]
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"*"}),
                               expires_at=50.0)
    req = auth.AuthorityRequest(capability="light.turn_on", actor="friday",
                                token=tok, identity="sam", now=100.0)
    assert auth.authorize(req).denied


def test_revoked_token_is_denied(K):
    auth = K["authority"]
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"*"}))
    req = auth.AuthorityRequest(capability="light.turn_on", actor="friday",
                                token=tok, identity="sam",
                                revoked=frozenset({tok.token_id}))
    assert auth.authorize(req).denied


# ── SECURITY_REQUIRES_AUTHORITY ──────────────────────────────────────────────
def test_security_capability_never_silently_allowed(K):
    auth = K["authority"]
    # No identified requester → a security action must DENY, never ALLOW.
    anon = auth.AuthorityRequest(capability="lock.unlock", identity=None)
    assert auth.authorize(anon).denied
    # Even with an identity it is CONFIRM, never a silent ALLOW.
    named = auth.AuthorityRequest(capability="lock.unlock", identity="sam")
    assert auth.authorize(named).needs_confirmation
    assert not auth.authorize(named).allowed


# ── FAIL_CLOSED ──────────────────────────────────────────────────────────────
def test_authority_fails_closed_on_policy_error(K):
    auth = K["authority"]

    def _boom(_req):
        raise RuntimeError("policy exploded")

    req = auth.AuthorityRequest(capability="light.turn_on", identity="sam")
    assert auth.authorize(req, policy=_boom).denied


# ── VERIFY_AFTER_ACT ─────────────────────────────────────────────────────────
def test_action_whose_postcondition_fails_is_not_done(K):
    plan = K["plan"]
    step = plan.Step(action="light.turn_on", postconditions=("is_on",))
    p = plan.Plan(goal="light on", steps=(step,))
    # run_step "succeeds" but the postcondition never holds → must NOT be DONE.
    report = plan.execute_plan(
        p, run_step=lambda s: True, check=lambda cond, s: False)
    assert report.ok is False
    assert report.outcomes[0].status == plan.VERIFY_FAILED


# ── IDEMPOTENCY_REQUIRED ─────────────────────────────────────────────────────
def test_completed_idempotency_key_is_not_re_executed(K):
    plan = K["plan"]
    step = plan.Step(action="lock.lock", idempotency_key="lock-front-door")
    p = plan.Plan(goal="lock up", steps=(step,))
    ran = []
    report = plan.execute_plan(
        p, run_step=lambda s: ran.append(s.action) or True,
        completed={"lock-front-door"})
    assert ran == []                                  # never double-acted
    assert report.outcomes[0].status == plan.SKIPPED


# ── CORRELATION_REQUIRED ─────────────────────────────────────────────────────
def test_correlation_scope_propagates(K):
    corr = K["correlation"]
    assert corr.current() is None
    with corr.scope("evt-123"):
        assert corr.current() == "evt-123"
    assert corr.current() is None                     # restored on exit
