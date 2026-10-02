"""Tests for the log-only authority↔gate parity bridge (kernel hardening H1)."""
import pytest

from fakes import FakeHass


@pytest.fixture
def ab(load):
    return load("authority_bridge")


def test_agreement_recorded_for_safe_allowed(ab):
    hass = FakeHass()
    # A safe action the gate allowed → engine ALLOW → agreement.
    d = ab.record_control_parity(hass, "light", "turn_on", allowed=True)
    assert d is not None and d.decision == "allow"
    summary = ab.parity_summary(hass)
    assert summary["agree"] == 1 and summary["disagree"] == 0


def test_mismatch_recorded_for_security_allowed(ab):
    hass = FakeHass()
    # The gate let an unlock through (allowed=True) but the engine would CONFIRM
    # (security-sensitive, no identity) → mismatch, logged not enforced.
    ab.record_control_parity(hass, "lock", "unlock", allowed=True)
    s = ab.parity_summary(hass)
    assert s["disagree"] == 1
    assert s["recent_mismatches"][0]["capability"] == "lock.unlock"


def test_gate_hold_matches_engine_confirm(ab):
    hass = FakeHass()
    # Gate held the action (allowed=False → actual CONFIRM); engine also CONFIRM.
    ab.record_control_parity(hass, "lock", "unlock", allowed=False, identity="Sam")
    s = ab.parity_summary(hass)
    assert s["agree"] == 1 and s["disagree"] == 0


def test_tally_accumulates_across_calls(ab):
    hass = FakeHass()
    ab.record_control_parity(hass, "light", "turn_on", allowed=True)
    ab.record_control_parity(hass, "switch", "toggle", allowed=True)
    s = ab.parity_summary(hass)
    assert s["agree"] == 2 and 0.0 <= s["agreement_rate"] <= 1.0


def test_summary_empty_when_nothing_recorded(ab):
    assert ab.parity_summary(FakeHass()) in ({}, {"agree": 0, "disagree": 0,
                                                 "agreement_rate": 1.0,
                                                 "by_capability": {},
                                                 "recent_mismatches": []})


def test_record_accepts_richer_inputs_and_stays_log_only(ab):
    # MCU A4: the bridge threads situation/scope/intent/token/context into the
    # engine request. Still log-only — recording never raises and the gate's
    # outcome is untouched.
    hass = FakeHass()
    d = ab.record_control_parity(
        hass, "light", "turn_on", allowed=True,
        intent="turn on", scope="light.kitchen",
        situation="normal", context={"room": "kitchen"})
    assert d is not None and d.decision == "allow"
    assert ab.parity_summary(hass)["agree"] == 1


def test_token_input_affects_engine_decision(ab, load):
    # Proof the token is actually fed into the decision (A4): a capability token
    # that does NOT grant this action makes the engine DENY (delegation can't
    # escalate) — even though the live gate let it through (allowed=True).
    auth = load("kernel.authority")
    tok = auth.CapabilityToken(holder="friday", capabilities=frozenset({"climate"}))
    hass = FakeHass()
    d = ab.record_control_parity(
        hass, "light", "turn_on", allowed=True, token=tok)
    assert d is not None and d.decision == auth.DENY
    # Still log-only: the mismatch is recorded, nothing is blocked.
    assert ab.parity_summary(hass)["disagree"] == 1
