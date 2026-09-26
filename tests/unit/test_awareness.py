"""Tests for awareness — JARVIS's first-person recollection of recent camera
events. Covers the pure ranking/phrasing core (no DB, no hass) and the guarded
``reflect`` reader against a real on-disk pattern DB.
"""
import sqlite3
from datetime import datetime

import pytest

from jc.sqlite_utils import ClosingConnection


@pytest.fixture
def aw(load):
    return load("awareness")


def _rows(*specs):
    """specs: (entity_id, label, person, hour, day_of_week, ts)."""
    out = []
    for eid, label, person, hour, dow, ts in specs:
        out.append({
            "entity_id": eid, "new_state": label, "person": person,
            "hour": hour, "day_of_week": dow, "timestamp": ts,
        })
    return out


# ── ranking ───────────────────────────────────────────────────────────────────
def test_rank_groups_and_thresholds(aw):
    rows = _rows(
        ("camera_event.front_door", "person", "Sam", 18, 1, "2026-09-20T18:00:00"),
        ("camera_event.front_door", "person", "Sam", 18, 2, "2026-09-21T18:05:00"),
        ("camera_event.driveway", "vehicle", "unknown", 17, 1, "2026-09-20T17:00:00"),
    )
    ranked = aw.rank_observations(rows, min_occurrences=2)
    # driveway seen once → below threshold; front_door person Sam kept.
    assert len(ranked) == 1
    obs = ranked[0]
    assert obs["entity_id"] == "camera_event.front_door"
    assert obs["label"] == "person" and obs["person"] == "Sam"
    assert obs["count"] == 2
    assert obs["modal_hour"] == 18


def test_rank_orders_by_regularity_then_recency(aw):
    rows = _rows(
        ("camera_event.a", "person", "unknown", 8, 1, "2026-09-19T08:00:00"),
        ("camera_event.a", "person", "unknown", 8, 2, "2026-09-20T08:00:00"),
        ("camera_event.b", "vehicle", "unknown", 9, 1, "2026-09-19T09:00:00"),
        ("camera_event.b", "vehicle", "unknown", 9, 2, "2026-09-20T09:00:00"),
        ("camera_event.b", "vehicle", "unknown", 9, 3, "2026-09-21T09:00:00"),
    )
    ranked = aw.rank_observations(rows, min_occurrences=2)
    assert [o["entity_id"] for o in ranked] == ["camera_event.b", "camera_event.a"]


def test_rank_separates_by_person(aw):
    rows = _rows(
        ("camera_event.hall", "person", "Sam", 7, 1, "2026-09-20T07:00:00"),
        ("camera_event.hall", "person", "Sam", 7, 2, "2026-09-21T07:00:00"),
        ("camera_event.hall", "person", "Alex", 22, 1, "2026-09-20T22:00:00"),
        ("camera_event.hall", "person", "Alex", 22, 2, "2026-09-21T22:00:00"),
    )
    ranked = aw.rank_observations(rows, min_occurrences=2)
    people = {o["person"] for o in ranked}
    assert people == {"Sam", "Alex"}


def test_rank_ignores_malformed_rows(aw):
    rows = [
        {"entity_id": "", "new_state": "person"},
        {"entity_id": "camera_event.x", "new_state": ""},
        {"new_state": "person"},
        {"entity_id": "camera_event.x", "new_state": "person",
         "hour": "notanint", "day_of_week": None, "person": "Sam",
         "timestamp": "2026-09-21T10:00:00"},
        {"entity_id": "camera_event.x", "new_state": "person",
         "hour": 10, "day_of_week": 1, "person": "Sam",
         "timestamp": "2026-09-21T10:05:00"},
    ]
    ranked = aw.rank_observations(rows, min_occurrences=2)
    assert len(ranked) == 1 and ranked[0]["count"] == 2


# ── phrasing ────────────────────────────────────────────────────────────────
def test_compose_named_person(aw):
    obs = [{"entity_id": "camera_event.front_door", "label": "person",
            "person": "Sam", "count": 6, "modal_hour": 18,
            "hours": [18, 18, 18, 18, 18, 18], "days": [0, 1, 2, 3, 4],
            "last_ts": "z"}]
    text = aw.compose_reflection(obs)
    assert "Sam" in text and "the front door" in text
    assert "around 6pm" in text and "on weekdays" in text
    assert text.startswith("- ")


def test_compose_vehicle_generic(aw):
    obs = [{"entity_id": "camera_event.driveway", "label": "vehicle",
            "person": "unknown", "count": 4, "modal_hour": 19,
            "hours": [19, 19, 19, 19], "days": [5, 6, 5, 6], "last_ts": "z"}]
    text = aw.compose_reflection(obs)
    assert "a vehicle" in text and "the driveway" in text
    assert "on weekends" in text


def test_compose_empty_is_blank(aw):
    assert aw.compose_reflection([]) == ""


def test_compose_respects_max_lines(aw):
    obs = [{"entity_id": f"camera_event.c{i}", "label": "activity",
            "person": "unknown", "count": 3, "modal_hour": 12,
            "hours": [12], "days": [], "last_ts": "z"} for i in range(10)]
    text = aw.compose_reflection(obs, max_lines=3)
    assert text.count("\n") == 2  # 3 lines


def test_hour_phrase_edges(aw):
    assert aw._hour_phrase(0) == "around midnight"
    assert aw._hour_phrase(12) == "around noon"
    assert aw._hour_phrase(9) == "around 9am"
    assert aw._hour_phrase(23) == "around 11pm"
    assert aw._hour_phrase(None) == ""
    assert aw._hour_phrase(99) == ""


# ── reflect: guarded DB reader ────────────────────────────────────────────────
def _make_db(path, rows):
    with sqlite3.connect(path, factory=ClosingConnection) as conn:
        conn.execute("""CREATE TABLE state_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, entity_id TEXT,
            domain TEXT, old_state TEXT, new_state TEXT, area_id TEXT,
            hour INTEGER, day_of_week INTEGER, triggered_by TEXT,
            person TEXT, person_confidence REAL)""")
        conn.executemany(
            "INSERT INTO state_changes (timestamp, entity_id, domain, new_state,"
            " area_id, hour, day_of_week, person) VALUES (?,?,?,?,?,?,?,?)", rows)


def test_reflect_reads_recent_camera_rows(aw, tmp_path):
    db = tmp_path / "patterns.db"
    now = datetime.now()
    ts = now.isoformat()
    _make_db(str(db), [
        (ts, "camera_event.front_door", "camera_event", "person", "", 18, 1, "Sam"),
        (ts, "camera_event.front_door", "camera_event", "person", "", 18, 2, "Sam"),
        # a non-camera row must be ignored
        (ts, "light.kitchen", "light", "on", "", 18, 1, "unknown"),
    ])
    text = aw.reflect(db_path=str(db))
    assert "Sam" in text and "the front door" in text


def test_reflect_skips_old_rows(aw, tmp_path):
    db = tmp_path / "patterns.db"
    old = "2000-01-01T00:00:00"
    _make_db(str(db), [
        (old, "camera_event.front_door", "camera_event", "person", "", 18, 1, "Sam"),
        (old, "camera_event.front_door", "camera_event", "person", "", 18, 2, "Sam"),
    ])
    assert aw.reflect(db_path=str(db)) == ""


def test_reflect_missing_db_is_blank(aw, tmp_path):
    assert aw.reflect(db_path=str(tmp_path / "nope.db")) == ""
