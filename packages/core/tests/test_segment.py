"""Mask -> panels."""

from __future__ import annotations

from facadekit.segment import read_mask, snap


def test_reads_four_panels_from_a_hand_drawn_mask(hand_drawn_mask):
    panels = read_mask(hand_drawn_mask, facade_width_mm=2400)
    assert len(panels) == 4


def test_panel_geometry_matches_the_drawing(hand_drawn_mask):
    # 200 px wide -> 2400 mm, so 12 mm/px. PIL rectangle() is inclusive at both
    # ends, so a [4, 96] box is 93 px = 1116 mm.
    panels = read_mask(hand_drawn_mask, facade_width_mm=2400)
    for p in panels:
        assert p.w == 1116
        assert p.h == 1116
    assert panels[0].x == 48  # 4 px inset
    assert panels[0].y == 48


def test_grid_snapping_pulls_panels_onto_the_module(hand_drawn_mask):
    panels = read_mask(hand_drawn_mask, facade_width_mm=2400, grid_mm=300)
    for p in panels:
        assert p.w == 1200
        assert p.h == 1200
        assert p.x % 300 == 0
        assert p.y % 300 == 0


def test_panels_are_numbered_in_reading_order(hand_drawn_mask):
    panels = read_mask(hand_drawn_mask, facade_width_mm=2400)
    assert [p.id for p in panels] == ["PNL-001", "PNL-002", "PNL-003", "PNL-004"]
    # top row before bottom row
    assert panels[0].y == panels[1].y
    assert panels[2].y > panels[0].y


def test_explicit_height_overrides_the_image_aspect(hand_drawn_mask):
    square = read_mask(hand_drawn_mask, facade_width_mm=2400)
    squashed = read_mask(hand_drawn_mask, facade_width_mm=2400, facade_height_mm=1200)
    assert squashed[0].h == square[0].h / 2


def test_min_area_drops_specks(hand_drawn_mask):
    assert read_mask(hand_drawn_mask, facade_width_mm=2400, min_area_px=100_000) == []


def test_reads_the_committed_sample_mask(sample_mask):
    panels = read_mask(sample_mask, facade_width_mm=12000, grid_mm=300)
    assert len(panels) > 50
    assert all(p.w > 0 and p.h > 0 for p in panels)


def test_snap():
    assert snap(1104, 300) == 1200
    assert snap(1040, 300) == 900
    assert snap(1104, 0) == 1104  # a zero grid is "do not snap"
