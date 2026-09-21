"""Tests for camera_learning — turning camera perception into learnable events.

Covers label normalisation, the synthetic entity id, the per-(location,label)
dedup window, and that a detection is recorded through the Cognitive Core's
state_logger as a force-included row (so the pattern miner sees it) — with a
fake core injected so no Home Assistant is needed.
"""
import sys
import types

import pytest


@pytest.fixture
def cl(load):
    return load("camera_learning")


def _fake_core(monkeypatch):
    """Inject a fake jc.cognitive_core with a recording state_logger; return it."""
    class _Logger:
        def __init__(self):
            self.calls = []

        def log_state_change(self, entity_id, old_state, new_state, **kw):
            self.calls.append((entity_id, new_state, kw))

    class _Core:
        running = True

        def __init__(self):
            self.state_logger = _Logger()

    mod = types.ModuleType("jc.cognitive_core")
    mod._CORE = _Core()
    monkeypatch.setitem(sys.modules, "jc.cognitive_core", mod)
    return mod


# ── normalisation ─────────────────────────────────────────────────────────────
def test_normalize_label_maps_semantic_classes(cl):
    assert cl.normalize_label("person") == "person"
    assert cl.normalize_label("Face") == "person"
    assert cl.normalize_label("CAR") == "vehicle"
    assert cl.normalize_label("truck") == "vehicle"
    assert cl.normalize_label("dog") == "animal"
    assert cl.normalize_label("package") == "package"
    assert cl.normalize_label("motion") == "activity"


def test_normalize_label_vision_categories(cl):
    # vision-analysis judgment["category"] values
    assert cl.normalize_label("delivery") == "package"
    assert cl.normalize_label("mail") == "package"
    assert cl.normalize_label("known_resident") == "person"
    assert cl.normalize_label("vehicle") == "vehicle"


def test_normalize_label_skips_nonevents(cl):
    # "empty"/"other"/"unknown" mean nothing happened → never recorded
    for skip in ("empty", "other", "unknown", "none", "quiet"):
        assert cl.normalize_label(skip) is None


def test_normalize_label_unknown_is_activity_empty_is_none(cl):
    assert cl.normalize_label("someweirdclass") == "activity"
    assert cl.normalize_label("") is None
    assert cl.normalize_label(None) is None


def test_synthetic_entity_id_slugs_location(cl):
    assert cl.synthetic_entity_id("Front Yard") == "camera_event.front_yard"
    assert cl.synthetic_entity_id("front-door/cam") == "camera_event.front_door_cam"
    assert cl.synthetic_entity_id("") == "camera_event.unknown"


# ── dedup window ──────────────────────────────────────────────────────────────
def test_deduper_collapses_within_window(cl):
    d = cl._Deduper(window_s=300)
    assert d.should_record(("a", "person"), 1000) is True
    assert d.should_record(("a", "person"), 1100) is False     # within 300s
    assert d.should_record(("a", "person"), 1300) is True      # window elapsed
    assert d.should_record(("a", "vehicle"), 1100) is True     # different label
    assert d.should_record(("b", "person"), 1100) is True      # different place


# ── recording path ────────────────────────────────────────────────────────────
def test_record_writes_forced_learnable_row_and_dedupes(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    ok = cl.record_camera_event(
        object(), camera_entity="camera.front_door", label="person",
        source="frigate", now=1000.0)
    assert ok is True
    calls = core._CORE.state_logger.calls
    assert len(calls) == 1
    entity_id, new_state, kw = calls[0]
    assert entity_id == "camera_event.front_door"
    assert new_state == "person"
    assert kw.get("force_include") is True
    assert kw.get("triggered_by") == "camera:frigate"
    # same place+label inside the window → no second row
    assert cl.record_camera_event(
        object(), camera_entity="camera.front_door", label="person",
        now=1100.0) is False
    assert len(calls) == 1


def test_record_skips_when_core_absent(cl, monkeypatch):
    mod = types.ModuleType("jc.cognitive_core")
    mod._CORE = None
    monkeypatch.setitem(sys.modules, "jc.cognitive_core", mod)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    assert cl.record_camera_event(
        object(), camera_entity="camera.x", label="person") is False


def test_record_skips_empty_label(cl, monkeypatch):
    _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    assert cl.record_camera_event(
        object(), camera_entity="camera.x", label="") is False


def test_on_camera_event_reads_bus_payload(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 40.0)

    class _Ev:
        data = {"entity_id": "camera.driveway", "label": "car",
                "source": "frigate", "confidence": 91}

    cl.on_camera_event(object(), _Ev())
    calls = core._CORE.state_logger.calls
    assert len(calls) == 1
    assert calls[0][0] == "camera_event.driveway" and calls[0][1] == "vehicle"


# ── confidence floor ──────────────────────────────────────────────────────────
def test_confidence_below_floor_is_dropped(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 40.0)
    assert cl.record_camera_event(
        object(), camera_entity="camera.x", label="person", confidence=25) is False
    assert core._CORE.state_logger.calls == []


def test_confidence_at_or_above_floor_records(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 40.0)
    assert cl.record_camera_event(
        object(), camera_entity="camera.x", label="person", confidence=40) is True
    assert len(core._CORE.state_logger.calls) == 1


def test_missing_confidence_is_not_filtered(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 99.0)
    # No confidence supplied (e.g. Nest motion, or vision path) → recorded.
    assert cl.record_camera_event(
        object(), camera_entity="camera.x", label="person") is True
    assert len(core._CORE.state_logger.calls) == 1


# ── per-resident attribution ──────────────────────────────────────────────────
def test_person_event_stamps_recognized_resident(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 0.0)
    # Fake recognition: a known resident seen at this camera.
    rec = types.ModuleType("jc.recognition")
    rec.last_seen_at = lambda hass, cam: {"name": "Sam", "confidence": 88.0}
    monkeypatch.setitem(sys.modules, "jc.recognition", rec)
    monkeypatch.setattr(sys.modules["jc"], "recognition", rec, raising=False)

    assert cl.record_camera_event(
        object(), camera_entity="camera.front_door", label="person") is True
    entity_id, new_state, kw = core._CORE.state_logger.calls[0]
    assert new_state == "person"
    assert kw.get("person") == "Sam"
    assert kw.get("person_confidence") == 88.0


def test_non_person_event_is_not_attributed(cl, monkeypatch):
    core = _fake_core(monkeypatch)
    monkeypatch.setattr(cl, "_DEDUPER", cl._Deduper())
    monkeypatch.setattr(cl, "_min_confidence", lambda: 0.0)
    # recognition shouldn't even be consulted for a vehicle, but make it loud if it is
    rec = types.ModuleType("jc.recognition")
    rec.last_seen_at = lambda hass, cam: {"name": "Sam", "confidence": 88.0}
    monkeypatch.setitem(sys.modules, "jc.recognition", rec)
    monkeypatch.setattr(sys.modules["jc"], "recognition", rec, raising=False)

    cl.record_camera_event(object(), camera_entity="camera.driveway", label="car")
    _, new_state, kw = core._CORE.state_logger.calls[0]
    assert new_state == "vehicle"
    assert kw.get("person") == "unknown"
