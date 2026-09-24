"""Tests for panel_register — guard panel removal so absent panels don't warn (#78)."""
import sys
import types

import pytest


def _install_frontend_stubs():
    """panel_register imports frontend/panel_custom/http, which the core test
    harness doesn't stub. Install minimal fakes so the module imports."""
    comps = sys.modules.setdefault(
        "homeassistant.components", types.ModuleType("homeassistant.components"))

    frontend = types.ModuleType("homeassistant.components.frontend")
    frontend.DATA_PANELS = "frontend_panels"
    frontend.async_remove_panel = lambda hass, url_path, **kw: None
    comps.frontend = frontend
    sys.modules["homeassistant.components.frontend"] = frontend

    panel_custom = types.ModuleType("homeassistant.components.panel_custom")
    async def _register(*a, **k):
        return None
    panel_custom.async_register_panel = _register
    comps.panel_custom = panel_custom
    sys.modules["homeassistant.components.panel_custom"] = panel_custom

    http = types.ModuleType("homeassistant.components.http")
    class StaticPathConfig:
        def __init__(self, *a, **k): ...
    http.StaticPathConfig = StaticPathConfig
    sys.modules["homeassistant.components.http"] = http


class _Hass:
    def __init__(self, panels):
        self.data = {"frontend_panels": dict(panels)}


@pytest.fixture
def pr(load):
    _install_frontend_stubs()
    module = load("panel_register")
    # Record every real removal so we can assert the guard never calls HA for
    # an absent panel (which is exactly what emits the "unknown panel" warning).
    calls: list = []

    def _rm(hass, url_path, **kw):
        calls.append(url_path)
        (hass.data.get("frontend_panels") or {}).pop(url_path, None)

    module.frontend.async_remove_panel = _rm
    module._calls = calls
    return module


def test_remove_skipped_when_panel_absent(pr):
    hass = _Hass({})  # nothing registered
    pr._remove_panel_if_present(hass, "jarvis")
    pr._remove_panel_if_present(hass, "jarvis-command")
    assert pr._calls == []  # never touched HA -> no "unknown panel" warning


def test_remove_called_when_panel_present(pr):
    hass = _Hass({"jarvis": object()})
    pr._remove_panel_if_present(hass, "jarvis")
    assert pr._calls == ["jarvis"]


def test_unregister_guarded_when_absent(pr):
    pr.async_unregister_panel(_Hass({}))
    assert pr._calls == []


def test_unregister_removes_when_present(pr):
    pr.async_unregister_panel(_Hass({"jarvis": object()}))
    assert pr._calls == ["jarvis"]
