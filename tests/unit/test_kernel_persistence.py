"""Tests for the unified SQLite access seam (kernel Phase 0).

Uses a real on-disk SQLite file under pytest's tmp_path; no Home Assistant.
Loaded through the harness `load()` loader so the parent-package import resolves.
"""
import sqlite3

import pytest


@pytest.fixture
def kp(load):
    """The kernel.persistence module, loaded under the synthetic package."""
    return load("kernel/persistence")


def test_connect_opens_usable_connection(kp, tmp_path):
    db = tmp_path / "x.db"
    conn = kp.connect(db)
    try:
        conn.execute("CREATE TABLE t (a INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        assert conn.execute("SELECT a FROM t").fetchone()[0] == 1
    finally:
        conn.close()


def test_connect_as_context_manager_closes(kp, tmp_path):
    db = tmp_path / "x.db"
    with kp.connect(db) as conn:
        conn.execute("CREATE TABLE t (a INTEGER)")
    # ClosingConnection closes on context exit → further use raises.
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_transaction_commits_on_success(kp, tmp_path):
    db = tmp_path / "x.db"
    with kp.transaction(db) as conn:
        conn.execute("CREATE TABLE t (a INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
    # Reopen: the row persisted (committed) and the connection was closed.
    conn2 = kp.connect(db)
    try:
        assert conn2.execute("SELECT a FROM t").fetchone()[0] == 42
    finally:
        conn2.close()


def test_transaction_rolls_back_on_error(kp, tmp_path):
    db = tmp_path / "x.db"
    with kp.connect(db) as c:
        c.execute("CREATE TABLE t (a INTEGER)")
        c.commit()
    with pytest.raises(RuntimeError):
        with kp.transaction(db) as conn:
            conn.execute("INSERT INTO t VALUES (99)")
            raise RuntimeError("boom")
    conn2 = kp.connect(db)
    try:
        assert conn2.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    finally:
        conn2.close()


def test_run_migrations_applies_in_order_and_is_idempotent(kp, tmp_path):
    db = tmp_path / "x.db"
    calls = []

    def m1(conn):
        calls.append("m1")
        conn.execute("CREATE TABLE a (x INTEGER)")

    def m2(conn):
        calls.append("m2")
        conn.execute("CREATE TABLE b (y INTEGER)")

    assert kp.schema_version(db) == 0
    applied = kp.run_migrations(db, [m1, m2])
    assert applied == 2 and calls == ["m1", "m2"]
    assert kp.schema_version(db) == 2

    # Second run applies nothing; migrations don't re-fire.
    applied2 = kp.run_migrations(db, [m1, m2])
    assert applied2 == 0 and calls == ["m1", "m2"]

    # Appending a new migration applies only the new one.
    def m3(conn):
        calls.append("m3")
        conn.execute("CREATE TABLE c (z INTEGER)")

    applied3 = kp.run_migrations(db, [m1, m2, m3])
    assert applied3 == 1 and calls == ["m1", "m2", "m3"]
    assert kp.schema_version(db) == 3


def test_failing_migration_rolls_back_the_batch(kp, tmp_path):
    db = tmp_path / "x.db"

    def ok(conn):
        conn.execute("CREATE TABLE a (x INTEGER)")

    def boom(conn):
        conn.execute("CREATE TABLE b (y INTEGER)")
        raise RuntimeError("bad migration")

    with pytest.raises(RuntimeError):
        kp.run_migrations(db, [ok, boom])

    # Whole batch rolled back: version untouched, table `a` not left behind.
    assert kp.schema_version(db) == 0
    conn = kp.connect(db)
    try:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "a" not in names and "b" not in names
    finally:
        conn.close()
