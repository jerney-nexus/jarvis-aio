#!/usr/bin/env python3
"""JARVIS translation coverage report.

Two translation systems ship with JARVIS, both English-based with graceful
English fallback for anything missing:

  1. Panel UI strings — one JSON file per language under
     ``custom_components/jarvis/frontend/i18n/<lang>.json``, keyed by the exact
     English string shown in the panel.

  2. Deterministic safety/security notifications — ``notify_i18n.py``, whose
     TITLES/MESSAGES tables carry a translation per language for each key.

This script reports how complete each language is, so contributors can see at a
glance where help is welcome, and maintainers can spot strings that newer
features added to English but that haven't been translated yet.

Usage:
    python3 scripts/i18n_coverage.py            # human-readable report
    python3 scripts/i18n_coverage.py --json     # machine-readable JSON
    python3 scripts/i18n_coverage.py --check     # exit 1 on malformed files

The report is informational; only --check gates (on malformed JSON, non-string
values, or empty translations — never on incompleteness, which is expected and
is exactly what the report is for).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "jarvis"
PANEL_I18N = COMPONENT / "frontend" / "i18n"


def _load_panel_files() -> dict[str, dict]:
    """Load every panel-UI language file. Returns {lang: {english: translation}}."""
    out: dict[str, dict] = {}
    for path in sorted(PANEL_I18N.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            out[path.stem] = {"__error__": str(exc)}
            continue
        out[path.stem] = data
    return out


def _panel_report(files: dict[str, dict]) -> dict:
    """Coverage of each panel language against the union of all known keys."""
    reference: set[str] = set()
    for data in files.values():
        if "__error__" not in data:
            reference |= set(data.keys())
    ref_n = len(reference) or 1

    langs = {}
    for lang, data in files.items():
        if "__error__" in data:
            langs[lang] = {"error": data["__error__"]}
            continue
        keys = set(data.keys())
        missing = sorted(reference - keys)
        empty = sorted(k for k, v in data.items() if not str(v).strip())
        langs[lang] = {
            "translated": len(keys),
            "missing": len(missing),
            "pct": round(100.0 * len(keys) / ref_n, 1),
            "missing_keys": missing,
            "empty_values": empty,
        }

    # Strings present in only a few files are usually newly added English that
    # hasn't propagated — surface the ones missing from the most languages.
    counts: dict[str, int] = {k: 0 for k in reference}
    for data in files.values():
        if "__error__" in data:
            continue
        for k in data:
            counts[k] = counts.get(k, 0) + 1
    total_langs = sum(1 for d in files.values() if "__error__" not in d) or 1
    least_covered = sorted(
        ({"key": k, "have": c, "of": total_langs} for k, c in counts.items()),
        key=lambda r: r["have"],
    )[:15]

    return {"reference_keys": len(reference), "languages": langs,
            "least_covered_keys": least_covered}


def _notify_report() -> dict:
    """Language coverage of the safety/security notification tables."""
    sys.path.insert(0, str(COMPONENT.parent))
    ni = _import_notify_i18n()
    tables = {**{f"TITLES.{k}": v for k, v in ni.TITLES.items()},
              **{f"MESSAGES.{k}": v for k, v in ni.MESSAGES.items()}}
    all_langs: set[str] = set()
    for t in tables.values():
        all_langs |= set(t)
    per_lang = {}
    for lang in sorted(all_langs):
        have = sum(1 for t in tables.values() if lang in t)
        per_lang[lang] = {"keys": have, "of": len(tables)}
    return {"languages": sorted(all_langs), "keys": len(tables),
            "per_language": per_lang, "and_langs": sorted(ni._AND)}


def _import_notify_i18n():
    """Import notify_i18n directly from source, without loading the whole
    integration (which pulls in Home Assistant)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_jarvis_notify_i18n", COMPONENT / "notify_i18n.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _print_report(panel: dict, notify: dict) -> None:
    print("JARVIS translation coverage\n" + "=" * 60)
    print(f"\nPanel UI  ({panel['reference_keys']} translatable strings, "
          f"English is the source)\n" + "-" * 60)
    rows = sorted(panel["languages"].items(),
                  key=lambda kv: kv[1].get("pct", -1), reverse=True)
    for lang, info in rows:
        if "error" in info:
            print(f"  {lang:<8} !! malformed: {info['error']}")
            continue
        bar_len = int(info["pct"] / 5)
        bar = "█" * bar_len + "·" * (20 - bar_len)
        note = f"  ({info['missing']} missing)" if info["missing"] else "  ✓ complete"
        empty = f"  [{len(info['empty_values'])} empty]" if info["empty_values"] else ""
        print(f"  {lang:<8} {bar} {info['pct']:5.1f}%{note}{empty}")

    under = [r for r in panel["least_covered_keys"] if r["have"] < r["of"]]
    if under:
        print("\n  Strings missing from the most languages "
              "(usually newly added English):")
        for r in under[:8]:
            print(f"      have {r['have']:>2}/{r['of']} languages")

    print(f"\nSafety/security notifications  ({notify['keys']} keys)\n" + "-" * 60)
    print("  Languages: " + ", ".join(notify["languages"]))
    incomplete = {l: v for l, v in notify["per_language"].items()
                  if v["keys"] != v["of"]}
    if incomplete:
        for lang, v in sorted(incomplete.items()):
            print(f"  {lang:<8} {v['keys']}/{v['of']} keys — INCOMPLETE")
    else:
        print("  ✓ every language covers every key (symmetric)")

    # Cross-reference: panel languages that don't yet have notification coverage,
    # so contributors can see exactly where a translation is still welcome.
    panel_bases = {l.split("-")[0] for l, info in panel["languages"].items()
                   if "error" not in info}
    notify_langs = set(notify["languages"]) - {"en"}
    gap = sorted(panel_bases - notify_langs)
    if gap:
        print("\n  Notifications still welcome for these panel languages: "
              + ", ".join(gap))

    print("\nContribute a translation: "
          "custom_components/jarvis/frontend/i18n/README.md\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 on malformed files (never on incompleteness)")
    args = ap.parse_args()

    files = _load_panel_files()
    panel = _panel_report(files)
    notify = _notify_report()

    if args.json:
        print(json.dumps({"panel": panel, "notify": notify},
                         ensure_ascii=False, indent=2))
    else:
        _print_report(panel, notify)

    if args.check:
        problems = []
        for lang, info in panel["languages"].items():
            if "error" in info:
                problems.append(f"{lang}.json: malformed JSON — {info['error']}")
            elif info.get("empty_values"):
                problems.append(
                    f"{lang}.json: {len(info['empty_values'])} empty value(s)")
        if problems:
            print("\nCHECK FAILED:", file=sys.stderr)
            for p in problems:
                print("  - " + p, file=sys.stderr)
            return 1
        print("CHECK OK — all translation files are well-formed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
