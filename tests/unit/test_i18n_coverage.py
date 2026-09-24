"""The translation-coverage tool (scripts/i18n_coverage.py) doubles as a guard:
panel language files must be valid JSON with no empty values, and the
safety-notification tables must stay symmetric across languages.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "i18n_coverage.py"


@pytest.fixture(scope="module")
def cov():
    spec = importlib.util.spec_from_file_location("i18n_coverage", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_panel_files_are_wellformed_with_no_empty_values(cov):
    files = cov._load_panel_files()
    assert files, "no panel i18n files found"
    report = cov._panel_report(files)
    assert report["reference_keys"] > 0
    for lang, info in report["languages"].items():
        assert "error" not in info, f"{lang}.json is malformed"
        assert not info["empty_values"], f"{lang}.json has empty translations"


def test_notification_tables_are_symmetric(cov):
    notify = cov._notify_report()
    assert "en" in notify["languages"]
    for lang, v in notify["per_language"].items():
        assert v["keys"] == v["of"], f"notify_i18n: {lang} is missing keys"
    # every notification language also has a list-join conjunction
    assert set(notify["languages"]) <= set(notify["and_langs"])
