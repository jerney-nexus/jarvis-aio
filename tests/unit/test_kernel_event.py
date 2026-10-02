"""Tests for the canonical JarvisEvent (kernel Phase 0).

Pure-unit: no Home Assistant, no I/O. Loaded through the harness `load()` loader
(like the rest of the suite) so the real package __init__ is never triggered. The
adapters are exercised against small fakes that mimic a real HA Event's shape.
"""
import dataclasses

import pytest


@pytest.fixture
def ke(load):
    """The kernel.event module, loaded under the synthetic package."""
    return load("kernel/event")


def test_defaults_are_generated_and_unique(ke):
    a = ke.JarvisEvent(type="x", source="test")
    b = ke.JarvisEvent(type="x", source="test")
    assert a.id and b.id and a.id != b.id
    assert isinstance(a.ts, float) and a.ts > 0
    assert a.data == {} and a.causality == () and a.correlation_id is None
    assert a.confidence == 1.0 and a.importance == 0.5


def test_distinct_data_defaults_not_shared(ke):
    a = ke.JarvisEvent(type="x", source="test")
    b = ke.JarvisEvent(type="x", source="test")
    assert a.data is not b.data  # default_factory, not a shared mutable default


def test_event_is_frozen(ke):
    e = ke.JarvisEvent(type="x", source="test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.type = "y"


def test_to_dict_from_dict_roundtrip(ke):
    e = ke.JarvisEvent(
        type="t", source="s", subject="sensor.door", location="hall",
        data={"k": 1}, confidence=0.9, importance=0.7,
        causality=("p1", "p2"), correlation_id="corr-1",
    )
    d = e.to_dict()
    assert isinstance(d["causality"], list)  # JSON-friendly
    again = ke.JarvisEvent.from_dict(d)
    assert again == e
    assert again.causality == ("p1", "p2")  # restored as a tuple


def test_from_dict_ignores_unknown_keys(ke):
    e = ke.JarvisEvent.from_dict(
        {"type": "t", "source": "s", "bogus": "nope", "extra": 123})
    assert e.type == "t" and e.source == "s"


def test_evolve_and_derivation_helpers(ke):
    base = ke.JarvisEvent(type="t", source="s")
    parent = ke.JarvisEvent(type="p", source="s")
    evolved = base.evolve(importance=0.9)
    assert evolved.importance == 0.9 and base.importance == 0.5  # original intact
    assert evolved.id == base.id  # evolve keeps identity unless overridden

    chained = base.caused_by(parent, "manual-id")
    assert chained.causality == (parent.id, "manual-id")
    assert base.causality == ()  # frozen-safe: original unchanged

    tagged = base.with_correlation("corr-9")
    assert tagged.correlation_id == "corr-9" and base.correlation_id is None


# ── Adapter fakes ──────────────────────────────────────────────────────────────
class _FakeState:
    def __init__(self, state, attributes=None):
        self.state = state
        self.attributes = attributes or {}


class _FakeContext:
    def __init__(self, cid):
        self.id = cid


class _FakeEvent:
    def __init__(self, data, context=None, time_fired=None):
        self.data = data
        self.context = context
        self.time_fired = time_fired


def test_from_state_changed_full(ke):
    ev = _FakeEvent(
        data={
            "entity_id": "binary_sensor.front_door",
            "old_state": _FakeState("off"),
            "new_state": _FakeState("on", {"area_id": "porch", "device_class": "door"}),
        },
        context=_FakeContext("ctx-123"),
    )
    je = ke.from_state_changed(ev)
    assert je.type == ke.EVENT_STATE_CHANGED and je.source == "ha"
    assert je.subject == "binary_sensor.front_door"
    assert je.location == "porch"
    assert je.data["old"] == "off" and je.data["new"] == "on"
    assert je.data["attributes"]["device_class"] == "door"
    assert je.correlation_id == "ctx-123"
    assert je.importance == 0.3


def test_from_state_changed_tolerates_missing_pieces(ke):
    je = ke.from_state_changed(
        _FakeEvent(data={"entity_id": "light.x", "new_state": None}))
    assert je.subject == "light.x"
    assert je.data["new"] is None and je.data["old"] is None
    assert je.location is None and je.correlation_id is None
    assert isinstance(je.ts, float)


def test_from_camera_analysis(ke):
    je = ke.from_camera_analysis(
        "camera.porch", "a parcel on the step",
        objects=["box"], confidence=0.8, location="porch")
    assert je.type == ke.EVENT_CAMERA_ANALYSIS and je.source == "camera"
    assert je.subject == "camera.porch" and je.location == "porch"
    assert je.data == {"description": "a parcel on the step", "objects": ["box"]}
    assert je.confidence == 0.8


def test_from_voice_turn(ke):
    je = ke.from_voice_turn(
        "turn on the kitchen light", speaker="Sam", intent="light.on")
    assert je.type == ke.EVENT_VOICE_TURN and je.source == "voice"
    assert je.subject == "Sam"
    assert je.data == {"text": "turn on the kitchen light", "intent": "light.on"}
