"""End to end: a hand-drawn mask in, three files out.

This is the test the brief calls for. It runs the real pipeline -- no mocks
below `run()` -- and asserts on the artefacts a fabricator would receive.
"""

from __future__ import annotations

import csv
import json

import ezdxf
import pytest

from facadekit.pipeline import PipelineError, RunConfig, run


def test_end_to_end_on_a_hand_drawn_mask(tmp_path, hand_drawn_mask, demo_catalogue_path):
    out = tmp_path / "run"
    result = run(
        RunConfig(
            catalogue_path=demo_catalogue_path,
            out_dir=out,
            mask_path=hand_drawn_mask,
            facade_width_mm=2400,
            grid_mm=300,
        )
    )

    # 2 x 2 mask, snapped to the module -> four 1200 x 1200 panels, all of which
    # the demo catalogue stocks exactly.
    assert len(result.panels) == 4
    assert result.legalisation.legal_count == 4
    assert result.legalisation.unique_parts == 1
    assert result.legalisation.metrics["max_fit_error_mm"] == 0

    for path in (out / "schedule.csv", out / "nesting.dxf", out / "panel-map.png"):
        assert path.is_file(), f"{path.name} was not written"
        assert path.stat().st_size > 0

    rows = list(csv.DictReader((out / "schedule.csv").open(encoding="utf-8")))
    assert len(rows) == 4
    assert {r["part_id"] for r in rows} == {"RS-1200-1200"}

    doc = ezdxf.readfile(out / "nesting.dxf")
    assert len(list(doc.modelspace())) > 0


def test_run_writes_a_dataset_row(tmp_path, hand_drawn_mask, demo_catalogue_path):
    """The labelled dataset is a side effect of running, not a separate step."""
    out = tmp_path / "run"
    run(
        RunConfig(
            catalogue_path=demo_catalogue_path,
            out_dir=out,
            mask_path=hand_drawn_mask,
            facade_width_mm=2400,
            grid_mm=300,
        )
    )
    manifest = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert manifest["panels"] == 4
    assert manifest["method"] == "nearest-part"
    for key in ("legalised_fraction", "unique_parts", "waste_pct", "sheets"):
        assert key in manifest["metrics"], f"{key} missing from the dataset row"
    assert manifest["catalogue"]["system"]

    # A row must record the settings that produced it. tolerance_mm in
    # particular sets legalised_fraction directly, and is currently an invented
    # number -- an unrecorded one makes the row incomparable and unreproducible.
    for key in ("seed", "grid_mm", "tolerance_mm", "facade_width_mm"):
        assert key in manifest["settings"], f"{key} missing from the dataset row"
    assert manifest["settings"]["grid_mm"] == 300

    # Paths must mean the same thing on another machine.
    assert "\\" not in (manifest["mask"] or ""), "mask path is not portable"
    assert manifest["files"]["schedule"] == "schedule.csv"


def test_irregular_mask_does_not_fully_legalise(tmp_path, sample_mask, demo_catalogue_path):
    """The committed irregular sample must leave work for the CP-SAT legaliser.

    If this ever reaches 100%, the sample stopped being a meaningful test of the
    solver and the demo would overstate the baseline.
    """
    result = run(
        RunConfig(
            catalogue_path=demo_catalogue_path,
            out_dir=tmp_path / "run",
            mask_path=sample_mask,
            facade_width_mm=12000,
            grid_mm=300,
        )
    )
    fraction = result.legalisation.metrics["legalised_fraction"]
    assert 0.3 < fraction < 1.0, f"expected a partial legalisation, got {fraction:.0%}"


def test_missing_mask_is_a_clear_error(tmp_path, demo_catalogue_path):
    with pytest.raises(PipelineError, match="mask not found"):
        run(
            RunConfig(
                catalogue_path=demo_catalogue_path,
                out_dir=tmp_path,
                mask_path=tmp_path / "nope.png",
            )
        )


def test_no_mask_and_no_generator_is_a_clear_error(tmp_path, demo_catalogue_path):
    with pytest.raises(PipelineError, match="nothing to segment"):
        run(RunConfig(catalogue_path=demo_catalogue_path, out_dir=tmp_path))


def test_blank_mask_is_a_clear_error(tmp_path, demo_catalogue_path):
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("L", (100, 100), 0).save(blank)
    with pytest.raises(PipelineError, match="no panels found"):
        run(
            RunConfig(
                catalogue_path=demo_catalogue_path, out_dir=tmp_path, mask_path=blank
            )
        )
