"""Tests for the deterministic briefing fallback (briefing._plain_briefing, v6.97.0)."""
import pytest


@pytest.fixture
def b(load):
    return load("briefing")


def test_reads_the_gathered_facts(b):
    out = b._plain_briefing("Good morning", "sir",
                            ["It is Monday.", "Weather: 45F.", "At home: Sam."])
    assert out.startswith("Good morning, sir.")
    assert "Weather: 45F." in out and "At home: Sam." in out


def test_empty_context_says_nothing_notable(b):
    assert "Nothing notable" in b._plain_briefing("Good evening", "sir", [])


def test_skips_blank_lines(b):
    out = b._plain_briefing("Good afternoon", "sir", ["", "  ", "Calendar: Dentist at 09:00."])
    assert out == "Good afternoon, sir. Calendar: Dentist at 09:00."


# ── greeting instruction: localize instead of forcing an English string (#79) ──
import types as _types


def _hass(lang):
    return _types.SimpleNamespace(config=_types.SimpleNamespace(language=lang))


def test_greeting_instruction_english_pins_exact_greeting(b, monkeypatch):
    monkeypatch.setattr(b, "_time_greeting", lambda: "Good evening")
    assert b._greeting_instruction(_hass("en"), "sir") == "Begin with 'Good evening, sir.' "


def test_greeting_instruction_absent_language_is_english(b, monkeypatch):
    monkeypatch.setattr(b, "_time_greeting", lambda: "Good morning")
    assert b._greeting_instruction(_hass(None), "sir") == "Begin with 'Good morning, sir.' "


def test_greeting_instruction_non_english_asks_for_equivalent(b, monkeypatch):
    monkeypatch.setattr(b, "_time_greeting", lambda: "Good evening")
    out = b._greeting_instruction(_hass("de"), "Sir")
    # No forced English greeting string that would fight the language directive.
    assert "Begin with 'Good evening, Sir.'" not in out
    assert "German equivalent of 'Good evening'" in out
    assert "continue in German" in out
