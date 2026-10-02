"""Integration smoke tests against a real Home Assistant instance (PHACC).

These prove what the unit fakes cannot: that the integration actually sets up
under a real `hass`, registers its services, and tears down cleanly on unload
and reload — the install / setup / reload / unload path. Run locally (or in CI)
where pytest-homeassistant-custom-component is installed; the directory conftest
skips them cleanly when it is absent.

Provider construction is mocked: the integration imports its LLM SDKs lazily, so
once create_provider is stubbed, setup needs no groq/openai/etc. at all.
"""
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "jarvis"

ENTRY_DATA = {
    "api_key": "", "model": "llama3.1", "honorific": "Sir",
    "llm_provider": "ollama", "llm_base_url": "http://localhost:11434/v1",
    "schema_version": 7,
}


class _FakeProvider:
    name = "fake"

    def chat(self, *a, **k):
        return {"text": "", "tool_calls": [], "raw": None}

    def supports_vision(self):
        return False


def _entry():
    return MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options={}, unique_id=DOMAIN)


def _mock_provider():
    return patch("custom_components.jarvis.create_provider", return_value=_FakeProvider())


async def test_config_flow_opens(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"})
    assert result["type"] in ("form", "menu")


async def test_setup_and_unload_lifecycle(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    with _mock_provider():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]
    assert hass.services.has_service(DOMAIN, "analyze_camera")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    assert not hass.services.has_service(DOMAIN, "analyze_camera")


async def test_reload_leaves_integration_loaded(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    with _mock_provider():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.services.has_service(DOMAIN, "analyze_camera")
