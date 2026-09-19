# Importing a floor plan (`floor_plan_rooms`)

The **Residence** tab draws its plan from the `floor_plan_rooms` config key. JARVIS
uses that plan for more than decoration: `residence_graph.py` derives room
**adjacency** from it so the intrusion investigator can follow a plausible route
inward from a breach point instead of treating every motion zone as equivalent.

## The format JARVIS expects

`floor_plan_rooms` is a map of **floor name → rooms**, where each room is an
axis-aligned box:

```json
{
  "1F": {
    "rooms": [
      { "name": "Living Room", "x": 0,   "y": 0, "w": 400, "h": 300 },
      { "name": "Kitchen",     "x": 400, "y": 0, "w": 300, "h": 300 }
    ],
    "labels": []
  }
}
```

* `x`, `y` are the box's top-left corner; `w`, `h` its width and height. The y
  axis increases **downward** (screen coordinates).
* `name` should match the Home Assistant **area** name (case/spacing-insensitive)
  so motion, which JARVIS knows by area, can be located on the plan.
* Two rooms are treated as adjacent when their boxes touch or nearly touch, so
  keep neighbouring rooms sharing an edge.

### Object vs. stringified string

You do **not** need to double-escape anything. JARVIS accepts `floor_plan_rooms`
as **either** a JSON object **or** a JSON string — `residence_graph._boxes()` and
the panel both `json.loads()` a string and otherwise use the object as-is. The
escaping pain only appears when you hand-edit Home Assistant's stored config,
where the value happens to be persisted as a string. Editing the plan on the
**Residence** tab avoids the escaping entirely.

## Importing from SweetHome3D

`scripts/sweethome3d_to_floorplan.py` turns a SweetHome3D plan into the format
above. SweetHome3D describes a home as walls, doors/windows, furniture and —
**when you draw them** — `room` polygons. The converter turns each room polygon
into its bounding box, grouped by SweetHome3D level (floor).

It accepts three inputs, auto-detected:

* a native **`.sh3d`** file (SweetHome3D's own save file), **recommended**,
* a SweetHome3D **XML** document (`Home.xml` / an XML export),
* a SweetHome3D **JSON** export (`{"home": {...}}`).

```bash
# Straight from the SweetHome3D save file (most reliable):
python3 scripts/sweethome3d_to_floorplan.py "Projet maison 3d.sh3d"

# Or from a JSON export:
python3 scripts/sweethome3d_to_floorplan.py home.json

# Also print a paste-ready, escaped one-line string for the config field:
python3 scripts/sweethome3d_to_floorplan.py "plan.sh3d" --as-config-string

# SweetHome3D units are centimetres; scale down and re-origin to (0,0):
python3 scripts/sweethome3d_to_floorplan.py "plan.sh3d" --scale 0.5 --origin-zero
```

Then paste the JSON onto the Residence tab (or into the `floor_plan_rooms`
config field).

### Prefer the `.sh3d` file over an HTML/plugin export

Some third-party exporters — the **HTML export**, older **ExportToHASS** builds —
emit an empty `room` array even when rooms are drawn. The native `.sh3d` file
always carries the rooms, so point the converter at that. Reading it requires
SweetHome3D's **XML** save format, which is on by default in recent versions; if
you get the "legacy binary format" error, enable **File → Preferences → Save
homes in XML format**, re-save, and try again.

### "No room polygons found"

If the converter reports that no rooms were found, either your SweetHome3D file is
**all walls, doors and furniture with no rooms drawn**, or you fed it an export
that dropped the rooms (see above — use the `.sh3d`). To draw rooms in
SweetHome3D:

* **Plan → Create rooms**, then click each corner, or
* double-click inside a closed set of walls to auto-detect a room.

Name each room to match its Home Assistant **area**, save, and run the converter
again — ideally against the `.sh3d` file itself.
