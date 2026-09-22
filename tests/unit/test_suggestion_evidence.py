"""Tests for the enriched suggestion review loop (v6.80.0) — the evidence that
makes a suggestion reviewable instead of a leap of faith. Covers the explainer
(pure), the schema/persistence of evidence, and the panel wiring."""
import json
import pathlib

import pytest

COMP = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "jarvis"


@pytest.fixture
def pa(load):
    return load("pattern_analyzer")


# ── the explainer: pattern details → human "why" ─────────────────────────────

def test_time_routine_explanation(pa):
    out = pa.explain_suggestion(
        "time_routine",
        {"hour": 18, "state": "on", "consistency": 0.87, "person": "Sam"}, 26)
    assert "18:00" in out["headline"]
    joined = " ".join(out["evidence"]).lower()
    assert "26 times" in joined
    assert "87%" in joined
    assert "sam" in joined


def test_repeated_command_explanation(pa):
    out = pa.explain_suggestion(
        "repeated_command", {"command": "lights off", "hour": 23}, 14)
    joined = " ".join(out["evidence"]).lower()
    assert "14" in joined
    assert "lights off" in joined
    assert "23:00" in joined


def test_sequence_explanation(pa):
    out = pa.explain_suggestion(
        "sequence", {"first": "door opens", "then": "hall light on",
                     "window_seconds": 30}, 9)
    joined = " ".join(out["evidence"]).lower()
    assert "door opens" in joined and "hall light on" in joined


def test_sequence_explanation_from_stored_dicts(pa):
    # Production stores trigger/action as {entity, state} dicts (not first/then
    # strings). The card must render human phrases — never a raw "{'entity': ...}"
    # dict — and describe what the automation would DO.
    out = pa.explain_suggestion(
        "sequence",
        {"trigger": {"entity": "binary_sensor.front_door", "state": "on"},
         "action": {"entity": "light.hallway", "state": "on"}}, 40)
    joined = " ".join(out["evidence"])
    assert "{'entity'" not in joined and "{\"entity\"" not in joined
    assert "turn on" in joined.lower()
    assert "hallway" in joined.lower()


def test_sequence_explanation_marks_non_actionable_correlation(pa):
    # Two camera "idle" states just co-occur — there is no device action to
    # automate, so the card must say so rather than imply an outcome.
    out = pa.explain_suggestion(
        "sequence",
        {"trigger": {"entity": "camera.front_door", "state": "idle"},
         "action": {"entity": "camera.hall", "state": "idle"}}, 3315)
    joined = " ".join(out["evidence"]).lower()
    assert "{'entity'" not in joined
    assert "no device action to automate" in joined


def test_unknown_pattern_type_is_safe(pa):
    out = pa.explain_suggestion("something_new", {}, 5)
    assert out["headline"]
    assert out["evidence"]


def test_explainer_never_raises_on_junk(pa):
    for bad in (None, {}, {"hour": "xx"}, {"consistency": None}):
        out = pa.explain_suggestion("time_routine", bad, 0)
        assert "headline" in out and "evidence" in out


def test_explainer_is_pure_no_exceptions_on_missing_keys(pa):
    # temp_pref with no target, presence with nothing
    assert pa.explain_suggestion("temp_pref", {}, 3)["evidence"]
    assert pa.explain_suggestion("presence", {}, 4)["evidence"]


# ── evidence is persisted and surfaced ───────────────────────────────────────

def test_suggestions_schema_has_evidence_columns():
    cc = (COMP / "cognitive_core.py").read_text()
    # fresh-DB schema
    assert "pattern_type TEXT" in cc
    assert "entity_ids TEXT" in cc
    assert "details TEXT" in cc
    # migration for existing DBs
    assert 'ALTER TABLE suggestions ADD COLUMN' in cc


def test_insert_stores_evidence():
    pa_src = (COMP / "pattern_analyzer.py").read_text()
    assert "pattern_type, entity_ids, details" in pa_src
    assert "json.dumps(pattern.entity_ids" in pa_src
    assert "json.dumps(pattern.details" in pa_src


def test_websocket_surfaces_why():
    ws = (COMP / "websocket.py").read_text()
    assert "explain_suggestion" in ws
    assert "why_headline" in ws
    assert "evidence" in ws
    assert '"pattern_type"' in ws


def test_panel_renders_evidence():
    panel = (COMP / "frontend" / "jarvis-panel.js").read_text()
    assert "why_headline" in panel
    assert "What JARVIS observed" in panel
    assert "sug-ev" in panel
    assert "Create automation" in panel


def test_panel_actions_still_wired():
    # the rich card must keep the classes the action handler binds to
    panel = (COMP / "frontend" / "jarvis-panel.js").read_text()
    assert "sug-approve" in panel
    assert "sug-dismiss" in panel
    assert "sug-yaml-btn" in panel
