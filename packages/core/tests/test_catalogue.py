"""Catalogue loading and validation."""

from __future__ import annotations

import json

import pytest

from facadekit.catalogue import CatalogueError, Part, Sheet, load_catalogue, validate

GOOD = {
    "system": "S",
    "units": "mm",
    "sheet": {"w": 3050, "h": 1220},
    "parts": [
        {"id": "P1", "kind": "panel", "w": 600, "h": 600, "finish": "f", "joint": "j"},
    ],
}


def test_loads_the_demo_catalogue(demo_catalogue_path):
    cat = load_catalogue(demo_catalogue_path)
    assert len(cat) > 0
    assert cat.units == "mm"
    assert "panel" in cat.kinds
    # The brief asks for a window part; the pipeline has no window handling
    # without one, so this is a real requirement, not decoration.
    assert cat.of_kind("window"), "demo catalogue must contain at least one window part"


def test_every_demo_part_fits_its_sheet(demo_catalogue_path):
    cat = load_catalogue(demo_catalogue_path)
    for part in cat.parts:
        assert part.fits_on(cat.sheet), f"{part.id} does not fit the stock sheet"


def test_accepts_a_minimal_catalogue():
    cat = validate(GOOD)
    assert cat.system == "S"
    assert cat.get("P1").w == 600


def test_reports_every_problem_at_once():
    bad = {
        "system": "",
        "units": "inches",
        "sheet": {"w": 0, "h": 1220},
        "parts": [{"id": "", "kind": "roof", "w": -1, "h": 0, "finish": "", "joint": ""}],
    }
    with pytest.raises(CatalogueError) as e:
        validate(bad)
    # The point of collecting problems is that one pass shows all of them.
    assert len(e.value.problems) >= 6


def test_rejects_duplicate_part_ids():
    raw = json.loads(json.dumps(GOOD))
    raw["parts"].append(dict(raw["parts"][0]))
    with pytest.raises(CatalogueError, match="duplicate"):
        validate(raw)


def test_rejects_a_part_too_big_for_the_sheet():
    raw = json.loads(json.dumps(GOOD))
    raw["parts"][0].update({"w": 4000, "h": 4000})
    with pytest.raises(CatalogueError, match="does not fit"):
        validate(raw)


def test_accepts_a_part_that_only_fits_rotated():
    raw = json.loads(json.dumps(GOOD))
    raw["parts"][0].update({"w": 1200, "h": 1500})  # 1500 > sheet.h, but < sheet.w
    assert len(validate(raw)) == 1


def test_rejects_non_mm_units():
    raw = json.loads(json.dumps(GOOD))
    raw["units"] = "m"
    with pytest.raises(CatalogueError, match="mm"):
        validate(raw)


def test_missing_file_is_a_catalogue_error(tmp_path):
    with pytest.raises(CatalogueError, match="not found"):
        load_catalogue(tmp_path / "nope.json")


def test_malformed_json_is_a_catalogue_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CatalogueError, match="not valid JSON"):
        load_catalogue(path)


def test_part_rotation_fit():
    sheet = Sheet(3050, 1220)
    tall = Part("T", "window", 1200, 1500, "f", "j")
    assert not tall.fits_on(sheet, allow_rotation=False)
    assert tall.fits_on(sheet, allow_rotation=True)
