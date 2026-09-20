"""Tests for scripts/sweethome3d_to_floorplan.py — SweetHome3D -> floor_plan_rooms."""
import importlib.util
import json
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "sweethome3d_to_floorplan.py"


@pytest.fixture(scope="module")
def conv():
    spec = importlib.util.spec_from_file_location("sh3d_conv", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rooms_become_bounding_boxes(conv):
    home = {"room": [
        {"name": "Living Room", "points": [[0, 0], [400, 0], [400, 300], [0, 300]]},
        {"name": "Kitchen", "points": [[400, 0], [700, 0], [700, 300], [400, 300]]},
    ]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    rooms = {r["name"]: r for r in plan["main"]["rooms"]}
    living = rooms["Living Room"]
    assert (living["x"], living["y"], living["w"], living["h"]) == (0, 0, 400, 300)
    assert "points" not in living   # a plain rectangle needs no polygon override
    assert rooms["Kitchen"]["x"] == 400 and rooms["Kitchen"]["w"] == 300


def test_home_wrapper_and_levels(conv):
    doc = {"home": {
        "level": [{"id": "lvl0", "name": "Ground"}, {"id": "lvl1", "name": "Upstairs"}],
        "room": [
            {"name": "Hall", "level": "lvl0", "points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"name": "Bed", "level": "lvl1", "points": [[0, 0], [20, 0], [20, 20], [0, 20]]},
        ],
    }}
    plan = conv.convert(conv._home(doc), scale=1.0, default_floor="main")
    assert set(plan) == {"Ground", "Upstairs"}
    assert plan["Ground"]["rooms"][0]["name"] == "Hall"
    assert plan["Upstairs"]["rooms"][0]["name"] == "Bed"


def test_scale_and_origin_zero(conv):
    home = {"room": [{"name": "R", "points": [[200, 100], [400, 100], [400, 300], [200, 300]]}]}
    plan = conv.convert(home, scale=0.5, default_floor="main")
    conv._shift_to_origin(plan)
    r = plan["main"]["rooms"][0]
    assert (r["x"], r["y"], r["w"], r["h"]) == (0, 0, 100, 100)
    assert "points" not in r


def test_dict_points_and_auto_names(conv):
    home = {"room": [{"points": [{"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 5}]}]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    assert plan["main"]["rooms"][0]["name"] == "Room 1"


def test_walls_only_export_yields_no_rooms(conv):
    # The shape reported in issue #34: walls/doors/furniture but no room polygons.
    home = {"wall": [{"xStart": 0, "yStart": 0, "xEnd": 100, "yEnd": 0}],
            "doorOrWindow": [{"id": "d1"}], "pieceOfFurniture": [{"id": "f1"}]}
    assert conv.convert(home, scale=1.0, default_floor="main") == {}


def test_degenerate_polygons_skipped(conv):
    home = {"room": [
        {"name": "line", "points": [[0, 0], [10, 0]]},   # < 3 points
        {"name": "ok", "points": [[0, 0], [1, 0], [1, 1]]},
    ]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    names = [r["name"] for r in plan["main"]["rooms"]]
    assert names == ["ok"]


def test_output_matches_floor_plan_rooms_schema(conv):
    """Rectangular rooms keep residence_graph._boxes's bbox keys plus type, and
    omit points since the bbox already describes them exactly."""
    home = {"room": [{"name": "X", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    box = plan["main"]["rooms"][0]
    assert set(box) == {"name", "x", "y", "w", "h", "type"}
    assert box["type"] == "room"
    assert plan["main"]["labels"] == []
    # round-trips through JSON string exactly as the config stores it
    assert json.loads(json.dumps(plan)) == plan


def test_non_rectangular_rooms_keep_their_polygon(conv):
    """A room whose points aren't just its bbox corners keeps the full polygon."""
    home = {"room": [{"name": "L-Shape",
                     "points": [[0, 0], [100, 0], [100, 50], [50, 50], [50, 100], [0, 100]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    box = plan["main"]["rooms"][0]
    assert set(box) == {"name", "x", "y", "w", "h", "type", "points"}
    assert box["points"] == [[0, 0], [100, 0], [100, 50], [50, 50], [50, 100], [0, 100]]


def test_quadrilateral_that_isnt_a_rectangle_keeps_points(conv):
    # 4 points, but not the bbox corners (a trapezoid) -> still a real polygon.
    home = {"room": [{"name": "Trapezoid", "points": [[0, 0], [100, 0], [80, 50], [20, 50]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    assert "points" in plan["main"]["rooms"][0]


def test_rectangle_with_rounding_noise_omits_points(conv):
    # SweetHome3D sometimes stores a corner a hair off due to snapping/rounding
    # (e.g. y=622.96265 vs y=622.9751, a 0.0125 discrepancy) -- still a rectangle.
    home = {"room": [{"name": "Treppe", "points": [
        [743.66797, 622.96265], [743.66797, 392.9751],
        [843.66797, 392.9751], [843.66797, 622.9751],
    ]}]}
    plan = conv.convert(home, scale=1.0, default_floor="main")
    assert "points" not in plan["main"]["rooms"][0]


# ── native .sh3d / XML input (issue #34: HTML/JSON export drops the room array) ──

import io
import zipfile

import pytest as _pytest

_SH3D_XML = """<?xml version='1.0'?>
<home version='7400'>
  <level id='lvl0' name='Ground'/>
  <room level='lvl0' name='Salon'>
    <point x='0' y='0'/><point x='400' y='0'/><point x='400' y='300'/><point x='0' y='300'/>
  </room>
  <room name='Chambre Hugo'>
    <point x='0' y='300'/><point x='350' y='300'/><point x='350' y='600'/><point x='0' y='600'/>
  </room>
  <wall xStart='0' yStart='0' xEnd='400' yEnd='0'/>
</home>"""


def test_parse_xml_home_normalises_rooms_levels_points(conv):
    home = conv._parse_xml_home(_SH3D_XML)
    names = {r["name"] for r in home["room"]}
    assert names == {"Salon", "Chambre Hugo"}
    salon = next(r for r in home["room"] if r["name"] == "Salon")
    assert salon["level"] == "lvl0"
    assert salon["points"][0] == [0.0, 0.0] and salon["points"][2] == [400.0, 300.0]
    # feeds convert() unchanged
    plan = conv.convert(home, scale=1.0, default_floor="main")
    assert plan["Ground"]["rooms"][0]["name"] == "Salon"
    assert plan["main"]["rooms"][0]["name"] == "Chambre Hugo"


def test_load_reads_raw_xml_file(conv, tmp_path):
    p = tmp_path / "Home.xml"
    p.write_text(_SH3D_XML, encoding="utf-8")
    home = conv._home(conv._load(str(p)))
    assert {r["name"] for r in home["room"]} == {"Salon", "Chambre Hugo"}


def _sh3d_bytes(home_entry: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Home", home_entry)
        z.writestr("0", b"fake-resource")
    return buf.getvalue()


def test_load_reads_native_sh3d_zip(conv, tmp_path):
    p = tmp_path / "plan.sh3d"
    p.write_bytes(_sh3d_bytes(_SH3D_XML.encode("utf-8")))
    plan = conv.convert(conv._home(conv._load(str(p))), scale=1.0, default_floor="main")
    assert plan["Ground"]["rooms"][0]["name"] == "Salon"


def test_legacy_binary_sh3d_raises_actionable_error(conv, tmp_path):
    # A .sh3d whose Home entry is Java-serialized binary (no XML) must fail with
    # guidance, not a traceback.
    p = tmp_path / "legacy.sh3d"
    p.write_bytes(_sh3d_bytes(b"\xac\xed\x00\x05sr\x00\x1ecom.eteks.sweethome3d"))
    with _pytest.raises(ValueError) as ei:
        conv._load(str(p))
    assert "XML format" in str(ei.value)


def test_json_path_still_works(conv, tmp_path):
    p = tmp_path / "home.json"
    p.write_text(json.dumps({"home": {"room": [
        {"name": "K", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}}), encoding="utf-8")
    plan = conv.convert(conv._home(conv._load(str(p))), scale=1.0, default_floor="main")
    assert plan["main"]["rooms"][0]["name"] == "K"


# ── floor-key default + rotation (issue #34 follow-up) ───────────────────────

def test_cli_default_floor_key_is_1f(conv, tmp_path, capsys):
    # JARVIS's Residence tab keys floors 1f/2f/bsmt; a plan keyed "main" shows on
    # no tab, so the CLI default floor must be 1f (issue #34).
    p = tmp_path / "home.json"
    p.write_text(json.dumps({"home": {"room": [
        {"name": "R", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}}), encoding="utf-8")
    rc = conv.main([str(p)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["1f"]


def test_convert_uses_given_floor_key(conv):
    home = {"room": [{"name": "R", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    assert list(plan) == ["1f"]


def test_rotate_180_flips_both_axes(conv):
    # Two rooms side by side: after 180° the left one ends up on the right.
    home = {"room": [
        {"name": "Left", "points": [[0, 0], [100, 0], [100, 100], [0, 100]]},
        {"name": "Right", "points": [[100, 0], [300, 0], [300, 100], [100, 100]]},
    ]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    conv._rotate_plan(plan, 180)
    rooms = {r["name"]: r for r in plan["1f"]["rooms"]}
    # widths/heights unchanged
    assert rooms["Left"]["w"] == 100 and rooms["Right"]["w"] == 200
    # order flipped along x: Right (originally at 100) now starts at 0
    assert rooms["Right"]["x"] == 0
    assert rooms["Left"]["x"] == 200
    # re-origined to (0,0)
    assert min(r["x"] for r in plan["1f"]["rooms"]) == 0


def test_rotate_90_swaps_width_and_height(conv):
    home = {"room": [{"name": "Wide", "points": [[0, 0], [400, 0], [400, 100], [0, 100]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    conv._rotate_plan(plan, 90)
    r = plan["1f"]["rooms"][0]
    assert (r["w"], r["h"]) == (100, 400)     # w/h swapped


def test_rotate_zero_is_noop(conv):
    home = {"room": [{"name": "R", "points": [[5, 5], [105, 5], [105, 55], [5, 55]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    before = json.dumps(plan, sort_keys=True)
    conv._rotate_plan(plan, 0)
    assert json.dumps(plan, sort_keys=True) == before


def test_rotate_180_transforms_points(conv):
    home = {"room": [{"name": "R", "points": [[0, 0], [100, 0], [50, 50]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    conv._rotate_plan(plan, 180)
    r = plan["1f"]["rooms"][0]
    assert (r["x"], r["y"], r["w"], r["h"]) == (0, 0, 100, 50)
    assert r["points"] == [[100, 50], [0, 50], [50, 0]]


def test_rotate_90_transforms_points(conv):
    home = {"room": [{"name": "R", "points": [[0, 0], [100, 0], [50, 50]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    conv._rotate_plan(plan, 90)
    r = plan["1f"]["rooms"][0]
    assert (r["x"], r["y"], r["w"], r["h"]) == (0, 0, 50, 100)
    assert r["points"] == [[50, 0], [50, 100], [0, 50]]


def test_shift_to_origin_translates_points(conv):
    home = {"room": [{"name": "R", "points": [[10, 20], [30, 20], [20, 40]]}]}
    plan = conv.convert(home, scale=1.0, default_floor="1f")
    conv._shift_to_origin(plan)
    r = plan["1f"]["rooms"][0]
    assert r["points"] == [[0, 0], [20, 0], [10, 20]]
