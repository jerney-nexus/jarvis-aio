"""Regression: conversation store must tolerate concurrent access.

Without a busy-timeout + WAL, a reader hitting the DB while the observer/agent
writes raised "database is locked" immediately (database.py:71 connect and :224
activity-log read). These pin the concurrency pragmas and the behaviour.
"""
import sqlite3

import pytest


@pytest.fixture
def db(load, tmp_path, monkeypatch):
    mod = load("database")
    monkeypatch.setattr(mod, "DB_PATH", tmp_path / "conversations.db")
    return mod


def test_connect_enables_wal_and_busy_timeout(db):
    conn = db._connect()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
    finally:
        conn.close()


def test_read_while_write_transaction_open_does_not_lock(db):
    # Simulate the real contention: one connection holds an open write
    # transaction while another reads. Pre-WAL/busy-timeout this raised
    # "database is locked"; now the reader waits (WAL) and succeeds.
    writer = db._connect()
    reader = db._connect()
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "INSERT INTO activity_log (timestamp, message) VALUES (?, ?)",
            ("2026-10-02T00:00:00", "hello"),
        )
        # Reader on a separate connection — must not raise under WAL.
        rows = reader.execute("SELECT COUNT(*) FROM activity_log").fetchall()
        assert rows[0][0] in (0, 1)  # sees committed state (0 until writer commits)
        writer.commit()
        assert reader.execute(
            "SELECT COUNT(*) FROM activity_log").fetchone()[0] == 1
    finally:
        writer.close()
        reader.close()


def test_connect_is_reusable_across_calls(db):
    # Opening, using and closing repeatedly must stay lock-free (the activity
    # feed + diagnostics each open their own short-lived connection).
    for i in range(5):
        conn = db._connect()
        try:
            conn.execute(
                "INSERT INTO activity_log (timestamp, message) VALUES (?, ?)",
                (f"2026-10-02T00:00:0{i}", f"m{i}"),
            )
            conn.commit()
        finally:
            conn.close()
    conn = db._connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0] == 5
    finally:
        conn.close()


def test_health_ok_after_fix(db):
    assert db.health() == {"ok": True, "error": ""}
