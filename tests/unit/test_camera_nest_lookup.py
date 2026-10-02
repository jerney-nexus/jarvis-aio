"""Tests for camera._nest_device_to_camera — the Nest device → camera entity
lookup, after migrating off the deprecated DeviceRegistry.devices mapping.

Covers both the modern HA iteration (yields DeviceEntry) and the defensive
fallback for cores whose `.devices` iteration yields ids, plus the no-match path.
"""
import sys
import types

import pytest


@pytest.fixture
def cam(load, monkeypatch):
    # camera.py does a bare `import aiohttp`, which isn't in the sandbox; a stub
    # module satisfies the import (aiohttp code paths aren't exercised here).
    if "aiohttp" not in sys.modules:
        monkeypatch.setitem(sys.modules, "aiohttp", types.ModuleType("aiohttp"))
    return load("camera")


class _Dev:
    def __init__(self, id, identifiers):
        self.id = id
        self.identifiers = identifiers


class _Ent:
    def __init__(self, entity_id, device_id, domain):
        self.entity_id = entity_id
        self.device_id = device_id
        self.domain = domain


def _device_registry(devices, *, iter_as_ids=False):
    """A fake DeviceRegistry whose `.devices` iterates like HA's.

    Modern cores yield DeviceEntry objects; `iter_as_ids=True` simulates a core
    that yields device ids, to exercise the defensive normalisation.
    """
    by_id = {d.id: d for d in devices}

    class _Devices:
        def __iter__(self):
            return iter(by_id.keys()) if iter_as_ids else iter(devices)

        def __getitem__(self, key):
            return by_id[key]

    return types.SimpleNamespace(devices=_Devices())


def _entity_registry(entities):
    class _Entities:
        def values(self):
            return list(entities)

    return types.SimpleNamespace(entities=_Entities())


def _patch(cam, monkeypatch, dev_reg, ent_reg):
    monkeypatch.setattr(cam, "dr", types.SimpleNamespace(async_get=lambda h: dev_reg))
    monkeypatch.setattr(cam, "er", types.SimpleNamespace(async_get=lambda h: ent_reg))


def test_nest_lookup_modern_iteration(cam, fake_hass, monkeypatch):
    dev = _Dev("dev1", {("nest", "enterprises/p/devices/ABC123")})
    _patch(cam, monkeypatch,
           _device_registry([dev]),
           _entity_registry([_Ent("camera.front", "dev1", "camera")]))
    assert cam._nest_device_to_camera(fake_hass, "ABC123") == "camera.front"


def test_nest_lookup_legacy_id_iteration(cam, fake_hass, monkeypatch):
    dev = _Dev("dev1", {("nest", "enterprises/p/devices/ABC123")})
    _patch(cam, monkeypatch,
           _device_registry([dev], iter_as_ids=True),
           _entity_registry([_Ent("camera.front", "dev1", "camera")]))
    assert cam._nest_device_to_camera(fake_hass, "ABC123") == "camera.front"


def test_nest_lookup_no_device_match(cam, fake_hass, monkeypatch):
    dev = _Dev("dev1", {("nest", "enterprises/p/devices/ABC123")})
    _patch(cam, monkeypatch,
           _device_registry([dev]),
           _entity_registry([_Ent("camera.front", "dev1", "camera")]))
    assert cam._nest_device_to_camera(fake_hass, "NOPE") is None


def test_nest_lookup_device_without_camera_entity(cam, fake_hass, monkeypatch):
    dev = _Dev("dev1", {("nest", "enterprises/p/devices/ABC123")})
    _patch(cam, monkeypatch,
           _device_registry([dev]),
           _entity_registry([_Ent("sensor.temp", "dev1", "sensor")]))  # no camera
    assert cam._nest_device_to_camera(fake_hass, "ABC123") is None
