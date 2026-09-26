"""Backup/restore of JARVIS state — archive, wipe, restore round-trip."""
import importlib.util
import os
from pathlib import Path

import pytest

COMP = Path(__file__).resolve().parents[2] / "custom_components" / "jarvis"


def _load_backup():
    spec = importlib.util.spec_from_file_location("jarvis_backup", COMP / "backup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


backup = _load_backup()


def test_backup_restore_roundtrip(tmp_path):
    cfg = str(tmp_path)
    os.makedirs(os.path.join(cfg, "jarvis"))
    with open(os.path.join(cfg, "jarvis", "knowledge.db"), "w") as file:
        file.write("KNOW")
    with open(os.path.join(cfg, "jarvis.db"), "w") as file:
        file.write("FTS")
    os.makedirs(os.path.join(cfg, "jarvis_memory"))
    with open(os.path.join(cfg, "jarvis_memory", "chroma.sqlite3"), "w") as file:
        file.write("CHROMA")

    arc = backup.create_backup(cfg)
    assert os.path.exists(arc) and arc.endswith(".tar.gz")

    # wipe, then restore the latest backup
    os.remove(os.path.join(cfg, "jarvis", "knowledge.db"))
    os.remove(os.path.join(cfg, "jarvis.db"))
    used = backup.restore_backup(cfg)
    assert used == arc
    with open(os.path.join(cfg, "jarvis", "knowledge.db")) as file:
        assert file.read() == "KNOW"
    with open(os.path.join(cfg, "jarvis.db")) as file:
        assert file.read() == "FTS"
    with open(os.path.join(cfg, "jarvis_memory", "chroma.sqlite3")) as file:
        assert file.read() == "CHROMA"


def test_restore_no_backup_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup.restore_backup(str(tmp_path))
