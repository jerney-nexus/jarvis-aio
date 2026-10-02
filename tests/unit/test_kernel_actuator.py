"""Tests for the universal actuator contract (kernel MCU A5)."""
import pytest


@pytest.fixture
def act(load):
    return load("kernel.actuator")


def test_minimal_request_has_sensible_defaults(act):
    r = act.ActuatorRequest(capability="light.turn_on")
    assert r.capability == "light.turn_on"
    assert r.target == "" and r.params == {}
    assert r.actor == "jarvis"            # default actor
    assert r.id.startswith("act_") and r.ts > 0


def test_full_request_round_trips_to_dict(act):
    r = act.ActuatorRequest(
        capability="lock.unlock", target="lock.front",
        params={"code": "x"}, actor="friday", identity="sam",
        intent="let the dog walker in", situation="away",
        correlation_id="evt-1", causation_id="evt-0",
        idempotency_key="lock.front:unlock", expected_outcome="unlocked")
    d = r.to_dict()
    assert d["capability"] == "lock.unlock" and d["target"] == "lock.front"
    assert d["intent"] == "let the dog walker in"
    assert d["idempotency_key"] == "lock.front:unlock"
    assert d["expected_outcome"] == "unlocked"


def test_build_helper(act):
    r = act.build_actuator_request(
        "light.turn_on", target="light.kitchen", params={"brightness_pct": 50},
        intent="turn on", correlation_id="c1", idempotency_key="light.kitchen:turn_on")
    assert isinstance(r, act.ActuatorRequest)
    assert r.target == "light.kitchen" and r.params["brightness_pct"] == 50
    assert r.correlation_id == "c1"


def test_build_helper_rejects_unknown_field(act):
    with pytest.raises(TypeError):
        act.build_actuator_request("light.turn_on", nonsense_field=1)


def test_requests_get_unique_ids(act):
    a = act.ActuatorRequest(capability="x")
    b = act.ActuatorRequest(capability="x")
    assert a.id != b.id


def test_outcome_model(act):
    o = act.ActuatorOutcome(request_id="act_1", status=act.VERIFIED,
                            observed="off")
    assert o.status == act.VERIFIED and o.observed == "off"
    # The lifecycle distinguishes "service returned success" from "world verified".
    assert act.EXECUTED != act.VERIFIED
    assert set(["requested", "executed", "observed", "verified",
                "mismatch", "failed"]) == {
        act.REQUESTED, act.EXECUTED, act.OBSERVED, act.VERIFIED,
        act.MISMATCH, act.FAILED}
