"""Regression: camera bus listeners must be @callback (run on the event loop).

A plain lambda/function registered with hass.bus.async_listen is dispatched by HA
to an executor thread; the handlers here call hass.bus.async_fire (a loop-only
API), so off-loop execution trips HA's thread-safety guard (camera.py async_fire,
HA 2026.x). This pins the handlers as loop-safe callbacks.
"""
import sys
import types

import pytest


@pytest.fixture
def cam(load, monkeypatch):
    monkeypatch.setitem(sys.modules, "aiohttp", types.ModuleType("aiohttp"))
    hc = types.ModuleType("homeassistant.components.camera")
    hc.async_get_image = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "homeassistant.components.camera", hc)
    net = types.ModuleType("homeassistant.helpers.network")
    net.get_url = lambda *a, **k: "http://localhost:8123"
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.network", net)
    for sib, fns in {
        "jc.database": {"save_message": lambda *a, **k: None},
        "jc.tts_helper": {"async_announce": lambda *a, **k: None},
        "jc.camera_backends": {"find_backend": lambda *a, **k: None},
    }.items():
        m = types.ModuleType(sib)
        for n, f in fns.items():
            setattr(m, n, f)
        monkeypatch.setitem(sys.modules, sib, m)
    sys.modules.pop("jc.camera", None)
    mod = load("camera")
    yield mod
    sys.modules.pop("jc.camera", None)


class _RecordingBus:
    def __init__(self):
        self.listeners = {}  # event_type -> listener

    def async_listen(self, event_type, listener):
        self.listeners[event_type] = listener
        return lambda: None


class _Hass:
    def __init__(self):
        self.bus = _RecordingBus()


def test_frigate_and_nest_listeners_are_callbacks(cam):
    hass = _Hass()
    cam.register_event_listeners(hass)
    # The two handlers that fire jarvis_camera_event must be loop-safe callbacks.
    for ev in ("frigate_event", "nest_event"):
        listener = hass.bus.listeners.get(ev)
        assert listener is not None, f"no listener registered for {ev}"
        assert getattr(listener, "_hass_callback", False) is True, (
            f"{ev} listener must be @callback so async_fire runs on the loop")


def test_all_expected_event_types_registered(cam):
    hass = _Hass()
    unsubs = cam.register_event_listeners(hass)
    assert "frigate_event" in hass.bus.listeners
    assert "nest_event" in hass.bus.listeners
    assert len(unsubs) >= 2
