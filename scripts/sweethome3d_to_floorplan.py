#!/usr/bin/env python3
"""Convert a SweetHome3D plan into JARVIS `floor_plan_rooms` JSON.

The Residence tab stores its plan under the `floor_plan_rooms` config key as

    {"<floor>": {"rooms": [{"name", "x", "y", "w", "h"}, ...], "labels": [...]}}

(see `custom_components/jarvis/residence_graph.py`, which reads it to derive
room adjacency). SweetHome3D, by contrast, describes a home as a set of wall
segments, doors/windows, furniture and — when you draw them — `room` polygons.
This helper reads a SweetHome3D plan and emits every room in the shape JARVIS
expects: the room's exact polygon (`points`) alongside its axis-aligned
bounding box (`x`/`y`/`w`/`h`, still needed by `residence_graph.py` for room
adjacency), so you can paste the result straight into the config instead of
hand-escaping JSON.

Accepted inputs (auto-detected):
  * a native **.sh3d** file (SweetHome3D's own save file — a ZIP whose ``Home``
    entry is XML when "Save homes in XML format" is enabled),
  * a SweetHome3D **XML** document (``Home.xml`` / an XML export),
  * a SweetHome3D **JSON** export (``{"home": {...}}``).

The .sh3d / XML path matters because some third-party exporters (the HTML
export, older ExportToHASS builds) drop the `room` array even when rooms are
drawn. The native file always carries the rooms, so pointing this tool at the
`.sh3d` you already have is the most reliable route.

Usage
-----
    # Straight from the SweetHome3D save file:
    python3 scripts/sweethome3d_to_floorplan.py "Projet maison 3d.sh3d"

    # From a JSON export, pretty plan to stdout:
    python3 scripts/sweethome3d_to_floorplan.py home.json

    # From stdin, and also a paste-ready escaped string for the config field:
    cat home.json | python3 scripts/sweethome3d_to_floorplan.py - --as-config-string

    # Scale SweetHome3D centimetres down and shift the plan to a (0,0) origin:
    python3 scripts/sweethome3d_to_floorplan.py home.json --scale 0.5 --origin-zero

Notes
-----
* SweetHome3D uses centimetres with y increasing downward, the same axis
  convention JARVIS's plan uses, so no axis flip is needed. `--scale` just
  rescales the numbers; adjacency is scale-independent (the touch test uses a
  gap proportional to the coordinates).
* Rooms are grouped by SweetHome3D level (floor) when the plan defines levels;
  otherwise everything lands on a single floor (`--floor`, default "1f" — the
  Residence tab's floor keys are 1f / 2f / bsmt, so a plan keyed anything else
  shows on no floor tab).
* `--rotate 90|180|270` turns the whole plan clockwise if it imports mirrored or
  rotated relative to the house model (180 swaps front/back and left/right).
* If the plan contains no `room` polygons — a SweetHome3D file can be all walls
  and furniture with no rooms drawn — there is nothing to convert. Draw rooms in
  SweetHome3D first (Plan menu -> Create rooms, or double-click inside a closed
  set of walls to auto-detect one), save, and run this again.

Exit code 0 = at least one room converted, 1 = nothing to convert / bad input.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Optional


def _read_bytes(source: str) -> bytes:
    if source == "-":
        return sys.stdin.buffer.read()
    with open(source, "rb") as f:
        return f.read()


def _looks_like_xml(raw: bytes) -> bool:
    head = raw.lstrip()[:256].lower()
    return head.startswith(b"<?xml") or b"<home" in head


def _xml_home_from_sh3d(data: bytes) -> Optional[str]:
    """Return the XML text of the home from a .sh3d ZIP, or None if the archive
    has no XML home entry (e.g. it was saved in the legacy binary format)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None
    names = zf.namelist()
    # SweetHome3D stores the home as an entry named "Home"; try it first, then
    # any *.xml entry, then anything else that happens to look like XML.
    ordered = ([n for n in names if n == "Home"]
               + [n for n in names if n.lower().endswith(".xml")]
               + names)
    seen: set[str] = set()
    for name in ordered:
        if name in seen:
            continue
        seen.add(name)
        try:
            raw = zf.read(name)
        except Exception:
            continue
        if _looks_like_xml(raw):
            return raw.decode("utf-8", "replace")
    return None


def _parse_xml_home(text: str) -> dict:
    """Normalise a SweetHome3D XML home into the same dict shape the JSON path
    produces: ``{"level": [{id, name}], "room": [{name, level, points:[[x,y]]}]}``."""
    root = ET.fromstring(text)
    levels: list[dict] = []
    for lvl in root.iter("level"):
        lid = lvl.get("id") or lvl.get("name") or str(len(levels))
        levels.append({"id": lid, "name": lvl.get("name") or lid})
    rooms: list[dict] = []
    for rm in root.iter("room"):
        pts: list[list[float]] = []
        for pt in rm.findall("point"):
            x_text = pt.get("x")
            y_text = pt.get("y")
            if x_text is None or y_text is None:
                continue
            try:
                pts.append([float(x_text), float(y_text)])
            except (TypeError, ValueError):
                continue
        rooms.append({"name": rm.get("name") or "",
                      "level": rm.get("level"), "points": pts})
    return {"level": levels, "room": rooms}


def _load(source: str) -> Any:
    """Read the source and return either a parsed JSON document or a normalised
    home dict (for .sh3d / XML input). Both are accepted by ``_home``."""
    data = _read_bytes(source)
    if data[:2] == b"PK":            # ZIP magic → a .sh3d save file
        xml = _xml_home_from_sh3d(data)
        if xml is None:
            raise ValueError(
                "this .sh3d file has no XML home entry — it was saved in "
                "SweetHome3D's legacy binary format, which this tool can't read. "
                "In SweetHome3D, turn on File → Preferences → 'Save homes "
                "in XML format', re-save the file, and run this again (or pass the "
                "JSON export instead).")
        return _parse_xml_home(xml)
    if _looks_like_xml(data):        # a raw Home.xml / XML export
        return _parse_xml_home(data.decode("utf-8", "replace"))
    return json.loads(data.decode("utf-8", "replace").lstrip("﻿"))


def _home(doc: Any) -> dict:
    """Unwrap the SweetHome3D home object from common export shapes."""
    if isinstance(doc, dict):
        if isinstance(doc.get("home"), dict):
            return doc["home"]
        return doc
    raise ValueError("expected a JSON object at the top level")


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _points(room: dict) -> list[tuple[float, float]]:
    """Pull [x, y] vertices from a SweetHome3D room, tolerant of shapes."""
    raw = room.get("points")
    if raw is None:
        raw = room.get("sPoints") or room.get("point")
    pts: list[tuple[float, float]] = []
    for p in _as_list(raw):
        try:
            if isinstance(p, dict):
                pts.append((float(p["x"]), float(p["y"])))
            else:  # [x, y] pair
                pts.append((float(p[0]), float(p[1])))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return pts


def _level_names(home: dict) -> dict[str, str]:
    """{level_id: level_name} for grouping rooms onto floors."""
    names: dict[str, str] = {}
    for i, lvl in enumerate(_as_list(home.get("level"))):
        if not isinstance(lvl, dict):
            continue
        lid = str(lvl.get("id", i))
        names[lid] = str(lvl.get("name") or lid).strip() or lid
    return names


def convert(home: dict, *, scale: float, default_floor: str) -> dict[str, dict]:
    level_names = _level_names(home)
    plan: dict[str, dict] = {}
    auto = 0
    for room in _as_list(home.get("room") or home.get("rooms")):
        if not isinstance(room, dict):
            continue
        pts = _points(room)
        if len(pts) < 3:
            continue  # not a polygon
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0 = min(xs), min(ys)
        auto += 1
        name = str(room.get("name") or "").strip() or f"Room {auto}"
        floor = level_names.get(str(room.get("level")), default_floor)
        box = {
            "name": name,
            "x": round(x0 * scale, 2),
            "y": round(y0 * scale, 2),
            "w": round((max(xs) - x0) * scale, 2),
            "h": round((max(ys) - y0) * scale, 2),
            "type": "room",
            # exact SweetHome3D polygon; the frontend prefers this over the bbox above
            "points": [[round(px * scale, 2), round(py * scale, 2)] for px, py in pts],
        }
        plan.setdefault(floor, {"rooms": [], "labels": []})["rooms"].append(box)
    return plan


def _shift_to_origin(plan: dict[str, dict]) -> None:
    """Translate all rooms so the top-left of the whole plan sits at (0, 0)."""
    boxes = [r for f in plan.values() for r in f["rooms"]]
    if not boxes:
        return
    dx = min(r["x"] for r in boxes)
    dy = min(r["y"] for r in boxes)
    for r in boxes:
        r["x"] = round(r["x"] - dx, 2)
        r["y"] = round(r["y"] - dy, 2)
        if r.get("points"):
            r["points"] = [[round(px - dx, 2), round(py - dy, 2)] for px, py in r["points"]]


def _rotate_plan(plan: dict[str, dict], degrees: int) -> None:
    """Rotate the whole plan clockwise by 0/90/180/270°, keeping every room
    axis-aligned, then re-origin to (0, 0). Use it when the imported plan comes
    out mirrored/rotated relative to the house model on the Residence tab —
    180° swaps front↔back and left↔right at once."""
    deg = degrees % 360
    if deg == 0:
        return
    for floor in plan.values():
        for r in floor["rooms"]:
            x, y, w, h = r["x"], r["y"], r["w"], r["h"]
            if deg == 180:
                nx, ny, nw, nh = -(x + w), -(y + h), w, h
            elif deg == 90:            # clockwise
                nx, ny, nw, nh = -(y + h), x, h, w
            else:                      # 270 clockwise = 90 counter-clockwise
                nx, ny, nw, nh = y, -(x + w), h, w
            r["x"], r["y"], r["w"], r["h"] = round(nx, 2), round(ny, 2), round(nw, 2), round(nh, 2)
            if r.get("points"):
                # same rotation as the bbox above, applied per vertex
                if deg == 180:
                    rot = lambda px, py: (-px, -py)
                elif deg == 90:
                    rot = lambda px, py: (-py, px)
                else:
                    rot = lambda px, py: (py, -px)
                r["points"] = [[round(nx_, 2), round(ny_, 2)] for nx_, ny_ in (rot(px, py) for px, py in r["points"])]
    _shift_to_origin(plan)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source",
                    help="SweetHome3D .sh3d file, XML, or JSON export (- for stdin)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="multiply every coordinate (default 1.0; SweetHome3D units are cm)")
    ap.add_argument("--floor", default="1f",
                    help="floor key for rooms with no SweetHome3D level (default: 1f — "
                         "JARVIS's Residence tab uses 1f / 2f / bsmt)")
    ap.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0,
                    help="rotate the whole plan clockwise by this many degrees "
                         "(180 fixes a plan that comes out with front/back and left/right swapped)")
    ap.add_argument("--origin-zero", action="store_true",
                    help="translate the plan so its top-left corner is (0, 0)")
    ap.add_argument("--as-config-string", action="store_true",
                    help="also print the escaped one-line JSON string to paste into floor_plan_rooms")
    args = ap.parse_args(argv)

    try:
        home = _home(_load(args.source))
    except (OSError, ValueError, json.JSONDecodeError, ET.ParseError) as e:
        print(f"error: could not read SweetHome3D plan: {e}", file=sys.stderr)
        return 1

    plan = convert(home, scale=args.scale, default_floor=args.floor)
    if args.rotate:
        _rotate_plan(plan, args.rotate)
    if args.origin_zero:
        _shift_to_origin(plan)

    total = sum(len(f["rooms"]) for f in plan.values())
    if not total:
        print(
            "error: no room polygons found in this SweetHome3D plan.\n"
            "A file that is only walls, doors and furniture has no rooms to import,\n"
            "and some exporters (HTML export, older ExportToHASS builds) drop the\n"
            "room array even when rooms exist. Two things to check:\n"
            "  1. In SweetHome3D, make sure rooms are actually drawn (Plan menu ->\n"
            "     Create rooms, or double-click inside a closed set of walls).\n"
            "  2. Feed this tool the native .sh3d file (or its XML) rather than an\n"
            "     HTML/JSON export — the native file always carries the rooms.\n"
            "Then run this again.",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.as_config_string:
        print("\n# Paste this value into the floor_plan_rooms config field:", file=sys.stderr)
        print(json.dumps(json.dumps(plan, ensure_ascii=False)))
    print(f"# converted {total} room(s) across {len(plan)} floor(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
