"""Nesting and the three output files."""

from __future__ import annotations

import csv

import ezdxf

from facadekit.catalogue import load_catalogue
from facadekit.export import write_all, write_panel_map, write_schedule
from facadekit.legalise import NearestPartLegaliser
from facadekit.nest import nest
from facadekit.segment import Panel


def _legalised(catalogue_path, panels):
    cat = load_catalogue(catalogue_path)
    return cat, NearestPartLegaliser().legalise(panels, cat)


def test_every_part_gets_placed(tiny_catalogue):
    panels = [Panel(id=f"PNL-{i:03d}", x=0, y=0, w=600, h=600) for i in range(10)]
    cat, result = _legalised(tiny_catalogue, panels)
    nested = nest(result, cat)
    assert nested.unplaced == ()
    assert sum(len(s.placements) for s in nested.sheets) == 10


def test_a_part_that_only_fits_rotated_is_turned_for_cutting(demo_catalogue_path):
    """The 1200 x 1500 window is taller than the 1220 mm sheet; it must lie down."""
    panels = [Panel(id="PNL-001", x=0, y=0, w=1200, h=1500)]
    cat, result = _legalised(demo_catalogue_path, panels)
    nested = nest(result, cat)
    assert nested.unplaced == ()
    assert nested.sheets[0].placements[0].rotated


def test_placements_stay_inside_the_sheet(demo_catalogue_path, sample_mask):
    from facadekit.segment import read_mask

    panels = read_mask(sample_mask, facade_width_mm=12000, grid_mm=300)
    cat, result = _legalised(demo_catalogue_path, panels)
    nested = nest(result, cat)
    for sheet in nested.sheets:
        for p in sheet.placements:
            assert p.x >= 0 and p.y >= 0
            assert p.x + p.w <= cat.sheet.w + 1e-6
            assert p.y + p.h <= cat.sheet.h + 1e-6


def test_waste_is_a_sane_percentage(tiny_catalogue):
    panels = [Panel(id=f"PNL-{i:03d}", x=0, y=0, w=600, h=600) for i in range(7)]
    cat, result = _legalised(tiny_catalogue, panels)
    nested = nest(result, cat)
    assert 0 <= nested.waste_pct < 100


def test_schedule_has_one_row_per_panel(tmp_path, tiny_catalogue):
    panels = [Panel(id=f"PNL-{i:03d}", x=0, y=0, w=600, h=600) for i in range(1, 4)]
    _, result = _legalised(tiny_catalogue, panels)
    path = write_schedule(result, tmp_path / "schedule.csv")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 3
    assert rows[0]["panel_id"] == "PNL-001"
    assert rows[0]["part_id"] == "A-600"
    assert rows[0]["legal"] == "yes"


def test_dxf_is_readable_and_in_millimetres(tmp_path, tiny_catalogue):
    panels = [Panel(id="PNL-001", x=0, y=0, w=600, h=600)]
    cat, result = _legalised(tiny_catalogue, panels)
    paths = write_all(result, nest(result, cat), tmp_path)
    doc = ezdxf.readfile(paths.dxf)
    assert doc.header["$INSUNITS"] == 4  # millimetres
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert {"SHEET", "CUT", "ELEVATION"} <= layers


def test_panel_map_is_a_png(tmp_path, tiny_catalogue):
    from PIL import Image

    panels = [Panel(id="PNL-001", x=0, y=0, w=600, h=600)]
    _, result = _legalised(tiny_catalogue, panels)
    path = write_panel_map(result, tmp_path / "map.png")
    with Image.open(path) as im:
        assert im.format == "PNG"
        assert im.width > 0 and im.height > 0


def test_empty_result_does_not_crash_the_panel_map(tmp_path, tiny_catalogue):
    _, result = _legalised(tiny_catalogue, [])
    assert write_panel_map(result, tmp_path / "empty.png").is_file()
