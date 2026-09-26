"""Tests for reminder database connection setup."""
import sys
import types
from unittest.mock import MagicMock

import pytest

if "homeassistant.helpers.event" not in sys.modules:
    event_module = types.ModuleType("homeassistant.helpers.event")
    event_module.async_track_time_interval = MagicMock()
    sys.modules["homeassistant.helpers.event"] = event_module


@pytest.mark.parametrize("failing_operation", ["executescript", "commit"])
def test_connect_closes_connection_when_setup_fails(
    load, tmp_path, monkeypatch, failing_operation
):
    reminders = load("reminders")
    connection = MagicMock()
    setup_error = reminders.sqlite3.OperationalError("setup failed")
    getattr(connection, failing_operation).side_effect = setup_error
    monkeypatch.setattr(reminders, "DB_PATH", tmp_path / "reminders.db")
    monkeypatch.setattr(
        reminders.sqlite3, "connect", MagicMock(return_value=connection)
    )

    with pytest.raises(reminders.sqlite3.OperationalError, match="setup failed"):
        reminders._connect()

    connection.close.assert_called_once_with()