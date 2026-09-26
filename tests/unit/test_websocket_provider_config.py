from __future__ import annotations

import importlib
import importlib.util
import datetime
import pathlib
import sys
import types


def _load_websocket_module():
    comp = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "jarvis"
    sys.modules.pop("jc.websocket", None)

    ws_api = types.ModuleType("homeassistant.components.websocket_api")
    ws_api.websocket_command = lambda schema: (lambda func: func)
    ws_api.async_response = lambda func: func
    ws_api.async_register_command = lambda hass, func: None
    sys.modules["homeassistant.components.websocket_api"] = ws_api
    import homeassistant.components as ha_components

    ha_components.websocket_api = ws_api

    spec = importlib.util.spec_from_file_location("jc.websocket", comp / "websocket.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jc.websocket"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Conn:
    def __init__(self):
        self.result = None
        self.error = None

    def send_result(self, msg_id, payload):
        self.result = (msg_id, payload)

    def send_error(self, msg_id, code, message):
        self.error = (msg_id, code, message)


async def test_configured_providers_require_custom_endpoint(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    ha_secrets = importlib.import_module("jc.ha_secrets")
    values = {
        "llm_provider": "custom",
        "custom_base_url": "",
        "ollama_base_url": "",
        "llm_base_url": "",
    }
    monkeypatch.setattr(websocket, "_runtime_opt", lambda hass, entry, key, default=None: values.get(key, default))

    async def _no_key(hass, provider):
        return ""

    monkeypatch.setattr(ha_secrets, "async_get_provider_key", _no_key)

    configured = await websocket._configured_providers(fake_hass, object())
    assert "custom" not in configured


async def test_configured_providers_allow_selected_ollama_default_endpoint(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    ha_secrets = importlib.import_module("jc.ha_secrets")
    values = {
        "llm_provider": "ollama",
        "ollama_base_url": "",
        "llm_base_url": "",
    }
    monkeypatch.setattr(websocket, "_runtime_opt", lambda hass, entry, key, default=None: values.get(key, default))

    async def _no_key(hass, provider):
        return ""

    monkeypatch.setattr(ha_secrets, "async_get_provider_key", _no_key)

    configured = await websocket._configured_providers(fake_hass, object())
    assert "ollama" in configured


async def test_configured_providers_do_not_leak_legacy_url_to_unselected_ollama(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    ha_secrets = importlib.import_module("jc.ha_secrets")
    values = {
        "llm_provider": "custom",
        "custom_base_url": "http://gpu.local:11434/v1",
        "ollama_base_url": "",
        "llm_base_url": "http://gpu.local:11434/v1",
    }
    monkeypatch.setattr(websocket, "_runtime_opt", lambda hass, entry, key, default=None: values.get(key, default))

    async def _no_key(hass, provider):
        return ""

    monkeypatch.setattr(ha_secrets, "async_get_provider_key", _no_key)

    configured = await websocket._configured_providers(fake_hass, object())
    assert "ollama" not in configured


async def test_configured_providers_do_not_leak_legacy_url_to_unselected_custom(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    ha_secrets = importlib.import_module("jc.ha_secrets")
    values = {
        "llm_provider": "ollama",
        "custom_base_url": "",
        "ollama_base_url": "http://gpu.local:11434/v1",
        "llm_base_url": "http://gpu.local:11434/v1",
    }
    monkeypatch.setattr(websocket, "_runtime_opt", lambda hass, entry, key, default=None: values.get(key, default))

    async def _no_key(hass, provider):
        return ""

    monkeypatch.setattr(ha_secrets, "async_get_provider_key", _no_key)

    configured = await websocket._configured_providers(fake_hass, object())
    assert "custom" not in configured


async def test_fetch_models_uses_resolved_api_key_in_auth_header(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    seen = {}

    class _Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return ""

        async def json(self):
            return {"data": [{"id": "gpt-4o-mini"}]}

    class _Session:
        def get(self, url, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return _Response()

    class _Timeout:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        sys.modules["homeassistant.helpers.aiohttp_client"],
        "async_get_clientsession",
        lambda hass: _Session(),
    )
    sys.modules["async_timeout"] = types.SimpleNamespace(timeout=lambda seconds: _Timeout())

    models = await websocket._fetch_models(fake_hass, "openai", "sk-openai", "")

    assert models == ["gpt-4o-mini"]
    assert seen["url"] == "https://api.openai.com/v1/models"
    assert seen["headers"]["Authorization"] == "Bearer " + "sk-openai"


async def test_fetch_models_gemini_uses_genai_sdk(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    captured = {}

    class _Models:
        def list(self):
            return [
                types.SimpleNamespace(
                    name="models/gemini-3.1-flash-lite",
                    supported_actions=["generateContent"],
                ),
                types.SimpleNamespace(
                    name="models/gemini-embedding-001",
                    supported_actions=["embedContent"],
                ),
            ]

    def _client(**kwargs):
        captured["client"] = kwargs
        return types.SimpleNamespace(models=_Models())

    genai = types.SimpleNamespace(Client=_client)
    google = types.ModuleType("google")
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)

    models = await websocket._fetch_models(fake_hass, "gemini", "AIza-key", "")

    assert captured["client"] == {"api_key": "AIza-key"}
    assert models == ["gemini-3.1-flash-lite"]


async def test_fetch_models_custom_uses_models_endpoint_without_v1_suffix(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    seen = {}

    class _Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self):
            return ""

        async def json(self):
            return {"data": [{"id": "custom-model"}]}

    class _Session:
        def get(self, url, headers=None):
            seen["url"] = url
            seen["headers"] = headers or {}
            return _Response()

    class _Timeout:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        sys.modules["homeassistant.helpers.aiohttp_client"],
        "async_get_clientsession",
        lambda hass: _Session(),
    )
    sys.modules["async_timeout"] = types.SimpleNamespace(timeout=lambda seconds: _Timeout())

    models = await websocket._fetch_models(fake_hass, "custom", "sk-custom", "https://host/openai")

    assert models == ["custom-model"]
    assert seen["url"] == "https://host/openai/models"
    assert seen["headers"]["Authorization"] == "Bearer " + "sk-custom"


async def test_ws_update_config_refreshes_live_clients(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    jarvis_config = importlib.import_module("jc.jarvis_config")
    observer = importlib.import_module("jc.observer")
    llm_provider = importlib.import_module("jc.llm_provider")
    entry = type("Entry", (), {"entry_id": "entry-1", "data": {}, "options": {}})()
    fake_hass.config_entries.async_entries = lambda domain: [entry]
    fake_hass.data = {websocket.DOMAIN: {entry.entry_id: {}}}
    conn = _Conn()
    persisted = []
    refreshed = {"main": 0, "observer": 0}

    monkeypatch.setattr(jarvis_config, "set_many", lambda updates: persisted.append(dict(updates)))
    async def _refresh_main(hass, entry):
        refreshed["main"] += 1
    async def _refresh_observer(hass, updates=None):
        refreshed["observer"] += 1
    monkeypatch.setattr(llm_provider, "async_refresh_main_client", _refresh_main)
    monkeypatch.setattr(observer, "is_running", lambda: True)
    monkeypatch.setattr(observer, "refresh_tier_providers", _refresh_observer)

    await websocket.ws_update_config(fake_hass, conn, {"id": 7, "key": "llm_provider", "value": "openai"})

    assert conn.error is None
    assert conn.result == (7, {"key": "llm_provider", "value": "openai"})
    assert fake_hass.data[websocket.DOMAIN][entry.entry_id]["runtime_config"]["llm_provider"] == "openai"
    assert persisted == [{"llm_provider": "openai"}]
    assert refreshed == {"main": 1, "observer": 1}


async def test_ws_update_config_marks_review_provider_as_explicit_opt_in(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    jarvis_config = importlib.import_module("jc.jarvis_config")
    observer = importlib.import_module("jc.observer")
    entry = type("Entry", (), {"entry_id": "entry-1", "data": {}, "options": {}})()
    fake_hass.config_entries.async_entries = lambda domain: [entry]
    fake_hass.data = {websocket.DOMAIN: {entry.entry_id: {}}}
    conn = _Conn()
    persisted = []
    refreshes = []

    monkeypatch.setattr(jarvis_config, "set_many", lambda updates: persisted.append(dict(updates)))
    monkeypatch.setattr(observer, "is_running", lambda: True)
    async def _refresh_observer(hass, updates=None):
        refreshes.append(dict(updates or {}))
    monkeypatch.setattr(observer, "refresh_tier_providers", _refresh_observer)

    await websocket.ws_update_config(fake_hass, conn, {"id": 8, "key": "review_provider", "value": "gemini"})

    runtime = fake_hass.data[websocket.DOMAIN][entry.entry_id]["runtime_config"]
    assert conn.error is None
    assert conn.result == (8, {"key": "review_provider", "value": "gemini"})
    assert runtime["review_provider"] == "gemini"
    assert runtime["review_enabled"] is True
    assert persisted == [{"review_provider": "gemini", "review_enabled": True}]
    assert refreshes == [{"review_provider": "gemini", "review_enabled": True}]


def test_get_observer_stats_aggregates_activity_and_cognition(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    import time

    state = types.SimpleNamespace(
        running=True,
        classifier_timestamps=[time.time() - 10, time.time() - 4000],
        hass=fake_hass,
    )
    observer = types.SimpleNamespace(
        _STATE=state,
        _effective_rate_limit=lambda: 12,
        _cognition_enabled=lambda: False,
        _cognition_threshold=lambda: 0.75,
    )
    cognition = types.SimpleNamespace(
        stats=lambda: {
            "entities_tracked": 4,
            "events_seen": 9,
            "anomalies_escalated": 2,
            "predictable": 3,
            "routines": 5,
            "presence_routines": 1,
        },
        presence_status=lambda hass: ["person.alex"],
    )
    monkeypatch.setitem(sys.modules, "jc.observer", observer)
    monkeypatch.setattr(sys.modules["jc"], "observer", observer, raising=False)
    monkeypatch.setitem(sys.modules, "jc.cognition", cognition)
    monkeypatch.setattr(sys.modules["jc"], "cognition", cognition, raising=False)

    recent = [
        {"was_spoken": True, "message": "event flagged", "source": "observer"},
        {"was_spoken": False, "message": "not worth announcing"},
        {"was_spoken": True, "message": "normal event"},
    ]
    result = websocket._get_observer_stats(
        recent,
        {"learned_patterns": 7, "cloud_calls": 2},
    )

    assert result["running"] is True
    assert result["calls_last_hour"] == 1
    assert result["rate_limit"] == 12
    assert (result["events_24h"], result["flagged_24h"]) == (3, 1)
    assert (result["dropped_24h"], result["spoken_24h"]) == (1, 2)
    assert result["cognition_enabled"] is False
    assert result["cognition_threshold"] == 0.75
    assert result["cog_entities"] == 4
    assert result["cog_presence"] == 1
    assert result["presence"] == ["person.alex"]
    assert result["learned_patterns"] == 7
    assert result["cloud_calls"] == 2


def test_get_observer_stats_loads_recent_activity_when_not_supplied(monkeypatch):
    websocket = _load_websocket_module()
    calls = []
    recent = [{"was_spoken": True, "message": "flagged event"}]
    database = types.ModuleType("jc.database")
    database.get_recent_activity = lambda **kwargs: calls.append(kwargs) or recent
    observer = types.SimpleNamespace(
        _STATE=types.SimpleNamespace(running=False, hass=None),
        _effective_rate_limit=lambda: 30,
        _cognition_enabled=lambda: True,
        _cognition_threshold=lambda: 0.6,
    )
    cognition = types.SimpleNamespace(
        stats=lambda: {},
        presence_status=lambda hass: [],
    )
    monkeypatch.setitem(sys.modules, "jc.database", database)
    monkeypatch.setitem(sys.modules, "jc.observer", observer)
    monkeypatch.setattr(sys.modules["jc"], "observer", observer, raising=False)
    monkeypatch.setitem(sys.modules, "jc.cognition", cognition)
    monkeypatch.setattr(sys.modules["jc"], "cognition", cognition, raising=False)

    result = websocket._get_observer_stats()

    assert calls == [{"hours": 24, "limit": 500}]
    assert result["events_24h"] == 1
    assert result["flagged_24h"] == 1
    assert result["spoken_24h"] == 1


async def test_async_get_observer_stats_fetches_activity_and_passes_reasoning(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    activity = [{"message": "recent event"}]
    reasoning = {"learned_patterns": 3}
    calls = []

    def _get_recent_activity(hours, limit):
        calls.append((hours, limit))
        return activity

    database = types.ModuleType("jc.database")
    database.get_recent_activity = _get_recent_activity
    monkeypatch.setitem(sys.modules, "jc.database", database)
    monkeypatch.setattr(websocket, "_get_reasoning_stats", lambda: reasoning)
    monkeypatch.setattr(
        websocket,
        "_get_observer_stats",
        lambda recent, reasoning_stats: (recent, reasoning_stats),
    )

    result = await websocket._async_get_observer_stats(fake_hass)

    assert calls == [(24, 500)]
    assert result == (activity, reasoning)


async def test_get_area_sparklines_parses_and_downsamples_recorder_states(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    calls = {}
    raw = {
        "sensor.room_temperature": [
            {"state": "18.5"},
            types.SimpleNamespace(state="19.0"),
            {"state": "unknown"},
            {"state": "21.5"},
            {"state": "22.0"},
        ],
        "sensor.room_humidity": [
            {"state": "45"},
            {"state": "46.5"},
        ],
    }

    class _RecorderInstance:
        async def async_add_executor_job(self, func):
            return func()

    def _get_significant_states(hass, start, end, entity_ids, **kwargs):
        calls.update({
            "start": start,
            "end": end,
            "entity_ids": entity_ids,
            "kwargs": kwargs,
        })
        return raw

    recorder = types.ModuleType("homeassistant.components.recorder")
    recorder.get_instance = lambda hass: _RecorderInstance()
    recorder.history = types.SimpleNamespace(get_significant_states=_get_significant_states)
    components = sys.modules["homeassistant.components"]
    monkeypatch.setattr(components, "__path__", [], raising=False)
    monkeypatch.setattr(components, "recorder", recorder, raising=False)
    monkeypatch.setitem(sys.modules, "homeassistant.components.recorder", recorder)

    result = await websocket._get_area_sparklines(
        fake_hass,
        {
            "living": {
                "temp": "sensor.room_temperature",
                "humidity": "sensor.room_humidity",
            },
            "empty": {"temp": "sensor.no_history", "humidity": None},
        },
        hours=3,
        points=2,
    )

    assert result == {
        "living": {"temp": [18.5, 21.5], "humidity": [45.0, 46.5]},
    }
    assert calls["entity_ids"] == [
        "sensor.no_history",
        "sensor.room_humidity",
        "sensor.room_temperature",
    ]
    assert calls["end"] - calls["start"] == datetime.timedelta(hours=3)
    assert calls["kwargs"] == {"minimal_response": True, "no_attributes": True}


async def test_get_area_sparklines_returns_empty_without_entities(fake_hass):
    websocket = _load_websocket_module()

    result = await websocket._get_area_sparklines(
        fake_hass, {"living": {"temp": None, "humidity": None}}
    )

    assert result == {}


async def test_get_area_sparklines_handles_recorder_failure(fake_hass, monkeypatch):
    websocket = _load_websocket_module()

    class _RecorderInstance:
        async def async_add_executor_job(self, func):
            raise RuntimeError("recorder unavailable")

    recorder = types.ModuleType("homeassistant.components.recorder")
    recorder.get_instance = lambda hass: _RecorderInstance()
    recorder.history = types.SimpleNamespace(get_significant_states=lambda *a, **k: {})
    components = sys.modules["homeassistant.components"]
    monkeypatch.setattr(components, "__path__", [], raising=False)
    monkeypatch.setattr(components, "recorder", recorder, raising=False)
    monkeypatch.setitem(sys.modules, "homeassistant.components.recorder", recorder)

    result = await websocket._get_area_sparklines(
        fake_hass, {"living": {"temp": "sensor.room_temperature"}}
    )

    assert result == {}


async def test_ws_get_activity_log_formats_entries_and_falls_back_on_bad_timestamp(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    calls = []
    entries = [
        {
            "timestamp": "2026-04-23T05:30:00",
            "urgency": "high",
            "entity_id": "binary_sensor.front_door",
            "message": "Front door opened",
            "source": "observer",
        },
        {
            "timestamp": "bad timestamp",
            "source": "briefing",
            "message": "Morning summary",
        },
    ]
    database = types.ModuleType("jc.database")

    def _get_recent_activity(*, hours, limit):
        calls.append((hours, limit))
        return entries

    database.get_recent_activity = _get_recent_activity
    monkeypatch.setitem(sys.modules, "jc.database", database)
    connection = _Conn()

    await websocket.ws_get_activity_log(
        fake_hass, connection, {"id": 12, "hours": 6, "limit": 8}
    )

    assert calls == [(6, 8)]
    assert connection.error is None
    assert connection.result == (12, {
        "entries": [
            {
                "ts": "05:30",
                "urgency": "high",
                "tag": "FRONT_DOOR",
                "msg": "Front door opened",
                "source": "observer",
            },
            {
                "ts": "bad t",
                "urgency": "low",
                "tag": "BRIEFING",
                "msg": "Morning summary",
                "source": "briefing",
            },
        ],
    })


async def test_ws_get_activity_log_reports_database_error(fake_hass, monkeypatch):
    websocket = _load_websocket_module()
    database = types.ModuleType("jc.database")

    def _raise(*args, **kwargs):
        raise RuntimeError("activity store unavailable")

    database.get_recent_activity = _raise
    monkeypatch.setitem(sys.modules, "jc.database", database)
    connection = _Conn()

    await websocket.ws_get_activity_log(
        fake_hass, connection, {"id": 13, "hours": 24, "limit": 50}
    )

    assert connection.result is None
    assert connection.error == (
        13, "activity_log_failed", "activity store unavailable"
    )


def test_get_runtime_json_obeys_config_precedence_and_json_fallback(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    entry = types.SimpleNamespace(entry_id="entry-1")
    fake_hass.data = {
        websocket.DOMAIN: {
            entry.entry_id: {
                "runtime_config": {
                    "runtime_json": '{"source": "runtime"}',
                    "runtime_dict": {"source": "runtime"},
                    "invalid_runtime": "{",
                },
            },
        },
    }
    persistent = {
        "persistent_json": '{"source": "persistent"}',
        "invalid_persistent": "not-json",
    }
    options = {"options_json": '["entry option"]', "invalid_options": "["}
    jarvis_config = types.ModuleType("jc.jarvis_config")
    jarvis_config.get = lambda key: persistent.get(key)
    monkeypatch.setitem(sys.modules, "jc.jarvis_config", jarvis_config)
    monkeypatch.setattr(sys.modules["jc"], "jarvis_config", jarvis_config, raising=False)
    monkeypatch.setattr(
        websocket,
        "_entry_opt",
        lambda entry, key, default=None: options.get(key, default),
    )

    assert websocket._get_runtime_json(fake_hass, entry, "runtime_json", None) == {
        "source": "runtime",
    }
    assert websocket._get_runtime_json(fake_hass, entry, "runtime_dict", None) == {
        "source": "runtime",
    }
    assert websocket._get_runtime_json(fake_hass, entry, "persistent_json", None) == {
        "source": "persistent",
    }
    assert websocket._get_runtime_json(fake_hass, entry, "options_json", None) == [
        "entry option",
    ]
    assert websocket._get_runtime_json(fake_hass, entry, "invalid_persistent", None) == "not-json"
    assert websocket._get_runtime_json(fake_hass, entry, "invalid_options", "fallback") == "fallback"
    assert websocket._get_runtime_json(fake_hass, entry, "invalid_runtime", "fallback") == "fallback"
    assert websocket._get_runtime_json(fake_hass, None, "missing", "fallback") == "fallback"


def test_get_runtime_str_obeys_runtime_persistent_and_options_precedence(
    fake_hass, monkeypatch,
):
    websocket = _load_websocket_module()
    entry = types.SimpleNamespace(entry_id="entry-2")
    fake_hass.data = {
        websocket.DOMAIN: {
            entry.entry_id: {"runtime_config": {"value": 0}},
        },
    }
    persistent = {"persistent_value": 12}
    options = {"option_value": False}
    jarvis_config = types.ModuleType("jc.jarvis_config")
    jarvis_config.get = lambda key: persistent.get(key)
    monkeypatch.setitem(sys.modules, "jc.jarvis_config", jarvis_config)
    monkeypatch.setattr(sys.modules["jc"], "jarvis_config", jarvis_config, raising=False)
    monkeypatch.setattr(
        websocket,
        "_entry_opt",
        lambda entry, key, default=None: options.get(key, default),
    )

    assert websocket._get_runtime_str(fake_hass, entry, "value", "default") == "0"
    assert websocket._get_runtime_str(fake_hass, entry, "persistent_value", "default") == "12"
    assert websocket._get_runtime_str(fake_hass, entry, "option_value", "default") == "False"
    assert websocket._get_runtime_str(fake_hass, None, "missing", "default") == "default"


def test_format_uptime_handles_seconds_minutes_hours_and_days():
    websocket = _load_websocket_module()

    assert websocket._format_uptime(59.9) == "59s"
    assert websocket._format_uptime(60) == "1m 0s"
    assert websocket._format_uptime(3600) == "1h 0m"
    assert websocket._format_uptime(86400) == "1d 0h"


def test_downsample_preserves_small_inputs_and_evenly_selects_large_inputs():
    websocket = _load_websocket_module()
    values = [float(value) for value in range(10)]

    assert websocket._downsample(values[:2], 2) == values[:2]
    assert websocket._downsample(values, 0) == values
    assert websocket._downsample(values, 3) == [0.0, 3.0, 6.0]
