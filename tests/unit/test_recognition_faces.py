"""Tests for the Household Faces data layer (#140): recognition.recent_faces,
which feeds the panel, and recognition.resident_present, which stands intrusion
monitoring down when a known resident is the face on camera.

Both read the in-memory recognition cache (populated by the MQTT/DoubleTake path)
and the household roster. The cache stores naive-UTC timestamps, so the tests
drive it directly with controlled ages and isolate module-level state."""
from datetime import datetime, timedelta, timezone

import pytest


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def recog(load, tmp_path, monkeypatch):
    """recognition module with an empty cache and an isolated, empty roster."""
    fr = load("face_roster")
    monkeypatch.setattr(fr, "ROSTER_PATH", str(tmp_path / "face_roster.json"))
    fr._loaded = False
    fr._roster = {}

    mod = load("recognition")
    mod._RECOGNITION_CACHE.clear()
    yield mod, fr
    mod._RECOGNITION_CACHE.clear()


def _cache(mod, camera_entity, name, confidence, age_seconds):
    mod._RECOGNITION_CACHE[camera_entity] = {
        "name": name,
        "confidence": confidence,
        "ts": _now() - timedelta(seconds=age_seconds),
        "unknown_count": 0,
    }


# ── recent_faces ──────────────────────────────────────────────────────────────

def test_recent_faces_marks_resident_and_unknown(recog, fake_hass):
    mod, fr = recog
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Sam", 92.0, age_seconds=10)
    _cache(mod, "camera.driveway", "Unknown", 0.0, age_seconds=30)

    rows = mod.recent_faces(fake_hass)
    by_name = {r["name"]: r for r in rows}

    assert by_name["Sam"]["is_resident"] is True
    assert by_name["Sam"]["is_unknown"] is False
    assert by_name["Unknown"]["is_unknown"] is True
    assert by_name["Unknown"]["is_resident"] is False


def test_recent_faces_non_resident_known_face_not_flagged(recog, fake_hass):
    mod, fr = recog
    # Roster has Sam; a recognized-but-unlisted person must not be a resident.
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Quentin", 88.0, age_seconds=5)

    rows = mod.recent_faces(fake_hass)
    assert rows[0]["name"] == "Quentin"
    assert rows[0]["is_resident"] is False
    assert rows[0]["is_unknown"] is False


def test_recent_faces_sorted_newest_first_and_limited(recog, fake_hass):
    mod, _ = recog
    _cache(mod, "camera.a", "Old", 70.0, age_seconds=600)
    _cache(mod, "camera.b", "Mid", 70.0, age_seconds=120)
    _cache(mod, "camera.c", "New", 70.0, age_seconds=5)

    rows = mod.recent_faces(fake_hass, limit=2)
    assert [r["name"] for r in rows] == ["New", "Mid"]
    assert rows[0]["age_seconds"] <= rows[1]["age_seconds"]


def test_recent_faces_drops_stale_cache_entries(recog, fake_hass):
    mod, _ = recog
    # Older than CACHE_MAX_AGE (2h) → excluded.
    _cache(mod, "camera.front_door", "Sam", 90.0,
           age_seconds=int(mod.CACHE_MAX_AGE.total_seconds()) + 60)
    assert mod.recent_faces(fake_hass) == []


def test_recent_faces_empty_when_nothing_seen(recog, fake_hass):
    mod, _ = recog
    assert mod.recent_faces(fake_hass) == []


# ── resident_present ────────────────────────────────────────────────────────────

def test_resident_present_recent_and_confident(recog, fake_hass):
    mod, fr = recog
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Sam", 90.0, age_seconds=30)
    assert mod.resident_present(fake_hass) == "Sam"


def test_resident_present_ignores_stale(recog, fake_hass):
    mod, fr = recog
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Sam", 90.0, age_seconds=10_000)
    assert mod.resident_present(fake_hass) is None


def test_resident_present_ignores_low_confidence(recog, fake_hass):
    mod, fr = recog
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Sam",
           mod.CONFIDENCE_THRESHOLD - 1, age_seconds=10)
    assert mod.resident_present(fake_hass) is None


def test_resident_present_ignores_non_resident(recog, fake_hass):
    mod, fr = recog
    fr.add_resident("Sam")
    _cache(mod, "camera.front_door", "Quentin", 95.0, age_seconds=10)
    assert mod.resident_present(fake_hass) is None


def test_resident_present_none_when_whitelist_empty(recog, fake_hass):
    mod, _ = recog
    # No residents flagged → presence gate is a no-op even with a confident face.
    _cache(mod, "camera.front_door", "Sam", 95.0, age_seconds=10)
    assert mod.resident_present(fake_hass) is None
