"""Tests for the event ledger (kernel Phase 1). Real on-disk SQLite via tmp_path."""
import pytest


@pytest.fixture
def mods(load):
    return load("kernel.ledger"), load("kernel.event")


def _mk(ev_mod, **kw):
    kw.setdefault("type", "state_changed")
    kw.setdefault("source", "ha")
    return ev_mod.JarvisEvent(**kw)


def test_record_buffers_then_flush_persists(mods, tmp_path):
    ledger_mod, ev_mod = mods
    led = ledger_mod.EventLedger(str(tmp_path / "events.db"))
    e = _mk(ev_mod, subject="sensor.door", correlation_id="c1", data={"new": "on"})
    led.record(e)
    assert led.pending() == 1
    assert led.flush() == 1
    assert led.pending() == 0

    rows = led.query_recent()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == e.id and row["type"] == "state_changed"
    assert row["subject"] == "sensor.door" and row["correlation_id"] == "c1"
    assert row["data"] == {"new": "on"}          # round-tripped from JSON
    assert isinstance(row["causality"], list)


def test_flush_empty_is_zero(mods, tmp_path):
    ledger_mod, _ = mods
    led = ledger_mod.EventLedger(str(tmp_path / "events.db"))
    assert led.flush() == 0


def test_query_by_correlation_orders_oldest_first(mods, tmp_path):
    ledger_mod, ev_mod = mods
    led = ledger_mod.EventLedger(str(tmp_path / "events.db"))
    led.record(_mk(ev_mod, correlation_id="chain", ts=100.0, subject="a"))
    led.record(_mk(ev_mod, correlation_id="chain", ts=200.0, subject="b"))
    led.record(_mk(ev_mod, correlation_id="other", ts=150.0, subject="c"))
    led.flush()

    chain = led.query_by_correlation("chain")
    assert [r["subject"] for r in chain] == ["a", "b"]


def test_buffer_cap_drops_oldest(mods, tmp_path):
    ledger_mod, ev_mod = mods
    led = ledger_mod.EventLedger(str(tmp_path / "events.db"), max_buffer=3)
    for i in range(5):
        led.record(_mk(ev_mod, subject=f"s{i}", ts=float(i)))
    assert led.pending() == 3
    assert led.dropped == 2
    led.flush()
    subjects = sorted(r["subject"] for r in led.query_recent())
    assert subjects == ["s2", "s3", "s4"]        # oldest two dropped


def test_duplicate_id_is_ignored(mods, tmp_path):
    ledger_mod, ev_mod = mods
    led = ledger_mod.EventLedger(str(tmp_path / "events.db"))
    e = _mk(ev_mod, subject="dup")
    led.record(e)
    led.flush()
    led.record(e)            # same id again
    led.flush()
    assert len(led.query_recent()) == 1          # INSERT OR IGNORE
