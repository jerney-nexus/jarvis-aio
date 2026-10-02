"""Tests for the authority / capability engine (kernel Phase 4). Pure, no I/O."""
import pytest


@pytest.fixture
def auth(load):
    return load("kernel.authority")


def _req(auth, capability, **kw):
    return auth.AuthorityRequest(capability=capability, **kw)


# ── sensitivity classification ────────────────────────────────────────────────
def test_sensitivity_tiers(auth):
    assert auth.sensitivity("announce") == auth.SAFE
    assert auth.sensitivity("camera.analyze") == auth.SAFE
    assert auth.sensitivity("light.turn_on") == auth.SENSITIVE
    assert auth.sensitivity("mode.set") == auth.SENSITIVE
    assert auth.sensitivity("lock.lock") == auth.SENSITIVE
    assert auth.sensitivity("lock.unlock") == auth.SECURITY
    assert auth.sensitivity("alarm_control_panel.alarm_disarm") == auth.SECURITY
    assert auth.sensitivity("intrusion.dismiss") == auth.SECURITY


def test_unknown_capability_is_sensitive_not_safe(auth):
    assert auth.sensitivity("totally.unknown") == auth.SENSITIVE


def test_longest_prefix_wins(auth):
    # lock.unlock (SECURITY) must win over the lock.lock (SENSITIVE) sibling.
    assert auth.sensitivity("lock.unlock") == auth.SECURITY


# ── default policy ────────────────────────────────────────────────────────────
def test_safe_capability_allowed(auth):
    d = auth.authorize(_req(auth, "announce"))
    assert d.allowed and d.decision == auth.ALLOW


def test_sensitive_allowed_when_confident(auth):
    d = auth.authorize(_req(auth, "light.turn_on", confidence=0.9))
    assert d.allowed


def test_sensitive_confirm_when_low_confidence(auth):
    d = auth.authorize(_req(auth, "light.turn_on", confidence=0.2))
    assert d.needs_confirmation and d.decision == auth.CONFIRM


def test_security_requires_confirmation_with_identity(auth):
    d = auth.authorize(_req(auth, "lock.unlock", identity="Sam", confidence=1.0))
    assert d.needs_confirmation


def test_security_denied_without_identity(auth):
    d = auth.authorize(_req(auth, "alarm_control_panel.alarm_disarm", identity=None))
    assert d.denied


# ── capability tokens: no escalation by delegation ────────────────────────────
def test_token_denies_ungranted_capability(auth):
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"announce"}))
    d = auth.authorize(_req(auth, "light.turn_on", actor="friday", token=tok))
    assert d.denied and "does not grant" in d.reason


def test_token_allows_granted_capability(auth):
    tok = auth.CapabilityToken(
        holder="friday", capabilities=frozenset({"light.turn_on"}))
    d = auth.authorize(_req(auth, "light.turn_on", actor="friday", token=tok, confidence=1.0))
    assert d.allowed


def test_wildcard_token_grants_all(auth):
    root = auth.CapabilityToken(holder="jarvis", capabilities=frozenset({"*"}))
    assert root.grants("anything.at.all")
    d = auth.authorize(_req(auth, "light.turn_on", actor="jarvis", token=root, confidence=1.0))
    assert d.allowed


def test_derive_narrows_and_cannot_widen(auth):
    root = auth.CapabilityToken(
        holder="jarvis", capabilities=frozenset({"announce", "light.turn_on"}))
    child = root.derive("friday", {"light.turn_on", "lock.unlock"})
    # lock.unlock was NOT in the parent → intersection drops it (no escalation).
    assert child.capabilities == frozenset({"light.turn_on"})
    assert child.issuer == "jarvis"
    assert not child.grants("lock.unlock")


def test_derive_from_wildcard_grants_requested(auth):
    root = auth.CapabilityToken(holder="jarvis", capabilities=frozenset({"*"}))
    child = root.derive("homer", {"announce", "light.turn_on"})
    assert child.capabilities == frozenset({"announce", "light.turn_on"})


def test_token_cannot_reach_security_even_if_granted(auth):
    # Even with the capability in its token, a security action still needs
    # explicit authority (CONFIRM/DENY), never a silent allow.
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"lock.unlock"}))
    d = auth.authorize(_req(auth, "lock.unlock", actor="friday", token=tok, identity="Sam"))
    assert d.needs_confirmation


# ── fail closed ───────────────────────────────────────────────────────────────
def test_policy_error_fails_closed(auth):
    def _boom(req):
        raise RuntimeError("policy bug")
    d = auth.authorize(_req(auth, "announce"), policy=_boom)
    assert d.denied and "policy error" in d.reason


# ── 8.13.0: token expiry / revocation + parity tracker ──────────────────────────
def test_expired_token_denied(auth):
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"light.turn_on"}),
                               expires_at=100.0)
    d = auth.authorize(_req(auth, "light.turn_on", actor="friday", token=tok,
                            confidence=1.0, now=200.0))
    assert d.denied and "expired" in d.reason


def test_unexpired_token_allowed(auth):
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"light.turn_on"}),
                               expires_at=1000.0)
    d = auth.authorize(_req(auth, "light.turn_on", actor="friday", token=tok,
                            confidence=1.0, now=200.0))
    assert d.allowed


def test_revoked_token_denied(auth):
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"light.turn_on"}))
    d = auth.authorize(_req(auth, "light.turn_on", actor="friday", token=tok,
                            confidence=1.0, revoked=frozenset({tok.token_id})))
    assert d.denied and "revoked" in d.reason


def test_derive_ttl_never_outlives_parent(auth):
    parent = auth.CapabilityToken(holder="jarvis", capabilities=frozenset({"*"}),
                                  expires_at=1000.0)
    # ttl would push past the parent's expiry → clamped to the parent's.
    child = parent.derive("friday", {"light.turn_on"}, ttl=5000.0, now=0.0)
    assert child.expires_at == 1000.0
    # a shorter ttl wins
    child2 = parent.derive("friday", {"light.turn_on"}, ttl=100.0, now=0.0)
    assert child2.expires_at == 100.0


def test_derive_assigns_new_token_id(auth):
    parent = auth.CapabilityToken(holder="jarvis", capabilities=frozenset({"*"}))
    child = parent.derive("friday", {"light.turn_on"})
    assert child.token_id != parent.token_id


def test_parity_tracks_agreement(auth):
    p = auth.AuthorityParity()
    allow = auth.authorize(_req(auth, "announce"))
    assert p.record(allow, auth.ALLOW) is True
    sec = auth.authorize(_req(auth, "lock.unlock", identity="Sam"))   # CONFIRM
    assert p.record(sec, auth.ALLOW) is False   # engine would gate; actual allowed
    assert p.agree == 1 and p.disagree == 1
    assert p.agreement_rate == 0.5
    s = p.summary()
    assert s["recent_mismatches"][0]["capability"] == "lock.unlock"
    assert s["by_capability"]["announce"] == [1, 0]
