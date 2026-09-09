"""The legaliser: baseline behaviour, and that the CP-SAT stub stays a stub."""

from __future__ import annotations

import pytest

from facadekit.catalogue import load_catalogue
from facadekit.legalise import (
    CpSatLegaliser,
    NearestPartLegaliser,
    get_legaliser,
)
from facadekit.segment import Panel


def _panel(w: float, h: float, i: int = 1) -> Panel:
    return Panel(id=f"PNL-{i:03d}", x=0, y=0, w=w, h=h)


def test_exact_match_is_legal_with_zero_error(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    result = NearestPartLegaliser().legalise([_panel(600, 600)], cat)
    a = result.assignments[0]
    assert a.part.id == "A-600"
    assert a.fit_error_mm == 0
    assert a.legal


def test_near_miss_inside_tolerance_is_legal(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    result = NearestPartLegaliser(tolerance_mm=50).legalise([_panel(630, 600)], cat)
    assert result.assignments[0].legal
    assert result.assignments[0].fit_error_mm == 30


def test_beyond_tolerance_is_illegal_but_still_assigned(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    result = NearestPartLegaliser(tolerance_mm=50).legalise([_panel(900, 600)], cat)
    a = result.assignments[0]
    assert not a.legal
    assert a.part is not None, "the baseline still reports its best guess"
    assert "off by" in a.note


def test_rotation_is_used_when_it_fits_better(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    result = NearestPartLegaliser().legalise([_panel(600, 1200)], cat)
    a = result.assignments[0]
    assert a.part.id == "A-1200"
    assert a.rotated
    assert a.fit_error_mm == 0


def test_rotation_can_be_refused(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    result = NearestPartLegaliser(allow_rotation=False).legalise([_panel(600, 1200)], cat)
    assert not result.assignments[0].rotated


def test_kind_filter_restricts_candidates(demo_catalogue_path):
    cat = load_catalogue(demo_catalogue_path)
    result = NearestPartLegaliser(kinds=["panel"]).legalise([_panel(1200, 1500)], cat)
    # Without the filter the 1200x1500 window would win outright.
    assert result.assignments[0].part.kind == "panel"


def test_metrics_are_reported(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    panels = [_panel(600, 600, 1), _panel(1200, 600, 2), _panel(5000, 5000, 3)]
    result = NearestPartLegaliser(tolerance_mm=50).legalise(panels, cat)
    m = result.metrics
    assert m["panels"] == 3
    assert m["legalised"] == 2
    assert m["legalised_fraction"] == pytest.approx(2 / 3)
    assert result.unique_parts == 2
    assert m["max_fit_error_mm"] > 0


def test_the_same_input_always_gives_the_same_answer(tiny_catalogue):
    cat = load_catalogue(tiny_catalogue)
    panels = [_panel(610, 590, i) for i in range(5)]
    first = NearestPartLegaliser().legalise(panels, cat)
    second = NearestPartLegaliser().legalise(panels, cat)
    assert [a.part_id for a in first.assignments] == [a.part_id for a in second.assignments]


def test_cp_sat_is_still_a_stub(tiny_catalogue):
    """Guards the honesty of the README: if this ever passes, the stub shipped."""
    cat = load_catalogue(tiny_catalogue)
    with pytest.raises(NotImplementedError, match="stub"):
        CpSatLegaliser().legalise([_panel(600, 600)], cat)


def test_registry_resolves_names():
    assert isinstance(get_legaliser("nearest"), NearestPartLegaliser)
    with pytest.raises(KeyError):
        get_legaliser("does-not-exist")
