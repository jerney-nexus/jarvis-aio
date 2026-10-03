#!/usr/bin/env python3
"""Behavioral kernel-coverage matrix (MCU audit follow-up P0.5).

`kernel_adoption.py` answers *"does a live module reference a kernel primitive?"*
That is necessary but not sufficient: a module can `from .kernel import authorize`
and still have actuators that bypass Authority. The external MCU audit asked the
sharper question —

    "what fraction of behaviour-bearing paths actually pass through the kernel
     contract (Event → WorldModel → Situation → Authority → Plan → Verify →
     Outcome)?"

This script makes that measurable. For each behaviour-bearing *path* (the ways
JARVIS acts on the home) it declares, per pipeline contract, how far that path is
wired onto the kernel — ``none / shadow / parity / full`` — and the script
verifies every non-``none`` claim against a piece of **evidence** that must be
present in the path's source (so the matrix cannot drift into optimistic
fiction). It prints a single honest coverage percentage.

    python3 scripts/kernel_coverage.py             # the matrix + coverage %
    python3 scripts/kernel_coverage.py --check      # + fail on evidence drift
    python3 scripts/kernel_coverage.py --markdown    # the KERNEL_COVERAGE table

The number is deliberately low today — most paths are still legacy. That is the
truth the audit wanted surfaced, and the gate keeps it honest as paths migrate.
Keep ``_PATHS`` the single source of truth; raise a cell's stage only when the
real execution path reaches that stage, and update the evidence with it.
"""
from __future__ import annotations

import pathlib
import sys

# Pipeline contracts, in order (the MCU "spine").
_CONTRACTS = ["event", "world_model", "situation", "authority", "plan",
              "verify", "outcome"]

# How much each stage counts toward coverage.
_WEIGHT = {"none": 0.0, "shadow": 1 / 3, "parity": 2 / 3, "full": 1.0}
_ICON = {"none": "·", "shadow": "◐", "parity": "◑", "full": "●"}


# Behaviour-bearing paths → the module file that carries the path, and the
# declared stage + evidence per contract. A contract absent from "contracts"
# is "none" (the path does not pass through that kernel contract yet).
_PATHS: dict[str, dict] = {
    "control_device": {
        "module": "agent.py",
        "contracts": {
            # 8.30.0 (MCU Phase A): the pre-action context snapshot is read
            # through the WorldModel facade. Parity, not full — the post-action
            # verify/read-back still reads raw HA state.
            "world_model": {"stage": "parity", "evidence": "WorldModel"},
            # H1: logs the Phase-4 engine decision vs the live confirm-gate.
            "authority": {"stage": "parity", "evidence": "authority_bridge"},
            # v6.38 verify-after-act for deterministic targets.
            "verify": {"stage": "full", "evidence": "_verify_control"},
            # 8.31.0 (MCU Phase A): the verify step produces the canonical
            # ActuatorOutcome (requested→executed→observed→verified) as the
            # path's real outcome record — the audit's point 18.
            "outcome": {"stage": "full", "evidence": "ActuatorOutcome"},
            # 8.32.0 (MCU Phase A): the actuation is published as a canonical
            # JarvisEvent on the bus (ledger records it). Parity, not full — it
            # enters the event stream but no cognitive consumer reacts yet.
            "event": {"stage": "parity", "evidence": "from_actuation"},
        },
    },
    # Uses only the legacy policy confirmation gate — no kernel contract yet.
    "bulk_control": {"module": "agent.py", "contracts": {}},
    # Legacy in-agent executor; the kernel planner (kernel.plan) is not adopted.
    "execute_plan": {"module": "agent.py", "contracts": {}},
    # Intrusion mirrors its lifecycle into the kernel Situation state machine.
    "intrusion": {
        "module": "intrusion.py",
        "contracts": {
            "situation": {"stage": "parity", "evidence": "situation"},
        },
    },
    "goals": {"module": "goals.py", "contracts": {}},
    "proactive": {"module": "proactive_audio.py", "contracts": {}},
    "friday": {"module": "agent.py", "contracts": {}},
    "homer": {"module": "agent.py", "contracts": {}},
}


def _component_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "jarvis"


def _stage(path: str, contract: str) -> str:
    return _PATHS[path]["contracts"].get(contract, {}).get("stage", "none")


def scan() -> dict[str, dict]:
    """Return per-path per-contract stages (the declared matrix)."""
    return {
        path: {c: _stage(path, c) for c in _CONTRACTS}
        for path in _PATHS
    }


def coverage_pct(rows: dict[str, dict] | None = None) -> float:
    rows = rows or scan()
    total = len(_PATHS) * len(_CONTRACTS)
    got = sum(_WEIGHT.get(stage, 0.0)
              for contracts in rows.values() for stage in contracts.values())
    return round(100.0 * got / total, 1) if total else 0.0


def drift() -> list[str]:
    """Problems: a declared non-``none`` cell whose evidence is absent from the
    path's source, an unknown contract name, or a missing module file."""
    comp = _component_dir()
    problems: list[str] = []
    for path, spec in _PATHS.items():
        src_path = comp / spec["module"]
        text = src_path.read_text() if src_path.exists() else None
        if text is None:
            problems.append(f"{path}: module {spec['module']} not found")
            continue
        for contract, cell in spec["contracts"].items():
            if contract not in _CONTRACTS:
                problems.append(f"{path}: unknown contract '{contract}'")
                continue
            if cell["stage"] != "none":
                ev = cell.get("evidence")
                if not ev or ev not in text:
                    problems.append(
                        f"{path}.{contract}: declared '{cell['stage']}' but "
                        f"evidence {ev!r} not found in {spec['module']}")
    return problems


def render_markdown(rows: dict[str, dict] | None = None) -> str:
    rows = rows or scan()
    header = "| Path | " + " | ".join(_CONTRACTS) + " |"
    sep = "| --- " * (len(_CONTRACTS) + 1) + "|"
    lines = [header, sep]
    for path in _PATHS:
        cells = " | ".join(f"{_ICON[rows[path][c]]}" for c in _CONTRACTS)
        lines.append(f"| `{path}` | {cells} |")
    lines.append("")
    lines.append(f"**Kernel coverage: {coverage_pct(rows)}%** "
                 "(· none ◐ shadow ◑ parity ● full)")
    return "\n".join(lines)


def render_table(rows: dict[str, dict] | None = None) -> str:
    rows = rows or scan()
    width = max(len(p) for p in _PATHS)
    out = ["  " + "path".ljust(width) + "  " + " ".join(c[:4] for c in _CONTRACTS)]
    for path in _PATHS:
        cells = " ".join(_ICON[rows[path][c]].center(4) for c in _CONTRACTS)
        out.append("  " + path.ljust(width) + "  " + cells)
    return "\n".join(out)


def main(argv: list[str]) -> int:
    rows = scan()
    if "--markdown" in argv:
        print(render_markdown(rows))
    else:
        print("Behavioral kernel-coverage "
              "(· none  ◐ shadow  ◑ parity  ● full)\n")
        print(render_table(rows))
        print(f"\n  coverage: {coverage_pct(rows)}% of behaviour-bearing "
              "path × contract cells are kernel-wired")

    if "--check" in argv:
        problems = drift()
        if problems:
            print("\nDRIFT:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print("\ncoverage matrix OK — every declared stage has live evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
