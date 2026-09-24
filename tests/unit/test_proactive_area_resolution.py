"""jarvis.speak area resolution — id / name / alias / slug tolerance (issue #77)."""
import sys
import types

import pytest


class _Area:
    def __init__(self, id, name, aliases=()):
        self.id = id
        self.name = name
        self.aliases = set(aliases)


def _norm(s):  # faithful to HA: casefold + collapse whitespace
    return " ".join(str(s or "").casefold().split())


class _AreaReg:
    def __init__(self, areas):
        self._areas = areas
        self._by_id = {a.id: a for a in areas}

    def async_get_area(self, area_id):
        return self._by_id.get(area_id)

    def async_get_area_by_name(self, name):  # HA matches the canonical name only
        n = _norm(name)
        return next((a for a in self._areas if _norm(a.name) == n), None)

    def async_list_areas(self):
        return list(self._areas)


@pytest.fixture
def pa(load, monkeypatch):
    areas = [
        _Area("01HULID", "Office"),                       # name only, id is a ULID
        _Area("lr", "Living Room", aliases={"Lounge"}),   # has an alias
        _Area("study_id", "Study", aliases={"Home Office"}),
    ]
    helpers = sys.modules.setdefault(
        "homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    ar = types.ModuleType("homeassistant.helpers.area_registry")
    ar.async_get = lambda hass: _AreaReg(areas)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.area_registry", ar)
    monkeypatch.setattr(helpers, "area_registry", ar, raising=False)
    # proactive_audio also imports config_validation and helpers.event at module
    # level; the core harness doesn't stub those, so supply minimal fakes.
    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.string, cv.boolean = str, bool
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.config_validation", cv)
    monkeypatch.setattr(helpers, "config_validation", cv, raising=False)
    ev = types.ModuleType("homeassistant.helpers.event")
    ev.async_call_later = lambda *a, **k: (lambda: None)
    ev.async_track_time_interval = lambda *a, **k: (lambda: None)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", ev)
    monkeypatch.setattr(helpers, "event", ev, raising=False)
    if "homeassistant.exceptions" not in sys.modules:
        exc = types.ModuleType("homeassistant.exceptions")
        class HomeAssistantError(Exception): ...
        exc.HomeAssistantError = HomeAssistantError
        monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exc)
    return load("proactive_audio")


def test_exact_area_id(pa):
    assert pa._resolve_area_id(None, "01HULID") == "01HULID"


def test_canonical_name_case_insensitive(pa):
    # "office" resolves to the area named "Office" via HA's own name matcher.
    assert pa._resolve_area_id(None, "office") == "01HULID"


def test_alias_resolves(pa):
    # "home office" is an alias of "Study" — HA's name matcher misses it, the
    # slug/alias fallback catches it (issue #77).
    assert pa._resolve_area_id(None, "home office") == "study_id"
    assert pa._resolve_area_id(None, "lounge") == "lr"


def test_underscore_and_spacing_variants(pa):
    assert pa._resolve_area_id(None, "living_room") == "lr"
    assert pa._resolve_area_id(None, "Living   Room") == "lr"


def test_unknown_area_returns_none(pa):
    assert pa._resolve_area_id(None, "garage") is None
    assert pa._resolve_area_id(None, "") is None


def test_known_area_labels_for_diagnostics(pa):
    assert pa._known_area_labels(None) == ["Living Room", "Office", "Study"]
