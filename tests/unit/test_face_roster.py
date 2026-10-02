"""Tests for the household resident whitelist (#140) — a JARVIS-native
'who is a resident' flag layered on backend face recognition. Matching is
name-normalized (case/space-insensitive) and the list persists to JSON."""
import json

import pytest


@pytest.fixture
def fr(load, tmp_path, monkeypatch):
    mod = load("face_roster")
    monkeypatch.setattr(mod, "ROSTER_PATH", str(tmp_path / "face_roster.json"))
    mod._loaded = False
    mod._roster = {}
    return mod


def test_add_and_is_resident_normalizes(fr):
    assert fr.add_resident("Sam") is True
    assert fr.add_resident("Sam") is False          # already present → not new
    assert fr.is_resident("sam") is True            # case-insensitive
    assert fr.is_resident("  SAM  ") is True         # whitespace-insensitive
    assert fr.is_resident("Quentin") is False
    assert fr.residents() == ["Sam"]


def test_remove(fr):
    fr.add_resident("Eliana")
    assert fr.remove_resident("eliana") is True     # normalized match removes it
    assert fr.remove_resident("eliana") is False    # already gone
    assert fr.residents() == []


def test_blank_names_ignored(fr):
    assert fr.add_resident("") is False
    assert fr.add_resident("   ") is False
    assert fr.residents() == []


def test_persists_across_reload(fr):
    fr.add_resident("Sam")
    fr.add_resident("Lee")
    # Simulate a fresh process: drop in-memory state, reload from disk.
    fr._loaded = False
    fr._roster = {}
    assert sorted(fr.residents()) == ["Lee", "Sam"]


def test_on_disk_format_is_a_plain_list(fr):
    fr.add_resident("Sam")
    with open(fr.ROSTER_PATH) as f:
        data = json.load(f)
    assert isinstance(data, list) and "Sam" in data


def test_tolerates_legacy_dict_file(fr):
    # An older {normalized: display} map should still load.
    with open(fr.ROSTER_PATH, "w") as f:
        json.dump({"sam_smith": "Sam Smith"}, f)
    fr._loaded = False
    fr._roster = {}
    assert fr.is_resident("Sam Smith") is True
    assert fr.residents() == ["Sam Smith"]
