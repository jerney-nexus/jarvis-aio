"""MCU Phase A — control_device golden path: the control_device tool is being
migrated onto the kernel contract one stage at a time (WorldModel → … → Outcome
→ Event), authority staying log-only. These tests pin each stage's real wiring.

8.30.0 — world_model (parity): control_device reads its pre-action context
snapshot through the kernel WorldModel facade, not a bare states.get."""
import json
import sys
import types

import pytest

if "homeassistant.helpers.llm" not in sys.modules:
    _llm = types.ModuleType("homeassistant.helpers.llm")
    _llm.async_get_api = lambda *a, **k: None
    sys.modules["homeassistant.helpers.llm"] = _llm


@pytest.fixture
def agent(load):
    return load("agent")


# ── 8.30.0: WorldModel is the pre-action context authority ───────────────────

async def test_previous_state_comes_from_worldmodel_snapshot(agent, fake_hass):
    """The result's previous_state is the snapshot state read via WorldModel."""
    fake_hass.states.set("light.den", "off")
    out = await agent._exec_control_device(
        fake_hass, {"entity_id": "light.den", "action": "turn_on"})
    await fake_hass.drain()
    res = json.loads(out)
    assert res["success"] is True
    assert res["previous_state"] == "off"


async def test_area_surfaced_from_worldmodel(agent, fake_hass):
    """WorldModel resolves the entity's area; control_device surfaces it."""
    fake_hass.states.set("light.den", "off", area="den")
    out = await agent._exec_control_device(
        fake_hass, {"entity_id": "light.den", "action": "turn_on"})
    await fake_hass.drain()
    res = json.loads(out)
    assert res["area"] == "den"


async def test_context_read_routes_through_worldmodel(agent, fake_hass, load, monkeypatch):
    """Prove the path uses WorldModel.device (not a raw states.get) for context:
    a patched facade returning a distinct snapshot shows up in the result."""
    wm_mod = load("kernel.world_model")
    sentinel = {"entity_id": "light.den", "domain": "light",
                "name": "Den", "state": "SENTINEL_PREV", "area": "SENTINEL_AREA",
                "attributes": {}}
    monkeypatch.setattr(wm_mod.WorldModel, "device", lambda self, eid: sentinel)
    fake_hass.states.set("light.den", "off")
    out = await agent._exec_control_device(
        fake_hass, {"entity_id": "light.den", "action": "turn_on"})
    await fake_hass.drain()
    res = json.loads(out)
    assert res["previous_state"] == "SENTINEL_PREV"
    assert res["area"] == "SENTINEL_AREA"


async def test_missing_entity_still_errors(agent, fake_hass):
    """No state and no snapshot → the not-found error is preserved."""
    out = await agent._exec_control_device(
        fake_hass, {"entity_id": "light.ghost", "action": "turn_on"})
    assert "not found" in out
