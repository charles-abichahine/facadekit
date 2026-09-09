"""Shared fixtures.

`repo_root` walks up from the test file rather than assuming a working
directory, so `pytest` works from anywhere and from CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def demo_catalogue_path(repo_root: Path) -> Path:
    path = repo_root / "data" / "catalogues" / "demo.json"
    if not path.is_file():
        pytest.skip(f"demo catalogue missing at {path}")
    return path


@pytest.fixture(scope="session")
def sample_mask(repo_root: Path) -> Path:
    path = repo_root / "data" / "samples" / "masks" / "banded.png"
    if not path.is_file():
        pytest.skip("sample masks missing; run python data/samples/make_samples.py")
    return path


@pytest.fixture
def tiny_catalogue(tmp_path: Path) -> Path:
    """A two-part catalogue, small enough to reason about by hand."""
    data = {
        "system": "Test system",
        "units": "mm",
        "sheet": {"w": 2000, "h": 1000},
        "parts": [
            {"id": "A-600", "kind": "panel", "w": 600, "h": 600,
             "finish": "natural", "joint": "open-6mm"},
            {"id": "A-1200", "kind": "panel", "w": 1200, "h": 600,
             "finish": "natural", "joint": "open-6mm"},
        ],
    }
    path = tmp_path / "tiny.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def hand_drawn_mask(tmp_path: Path) -> Path:
    """A 2 x 2 mask drawn here in the test, not loaded from the repo.

    100 px = 1200 mm at the widths this is used with, so the four panels are
    nominally 600 x 600 mm before the joint is taken off. Deliberately
    hand-placed so the expected panel count and geometry are obvious from
    reading the test rather than from trusting a committed PNG.
    """
    img = Image.new("L", (200, 200), 0)
    draw = ImageDraw.Draw(img)
    for cx in (0, 100):
        for cy in (0, 100):
            draw.rectangle([cx + 4, cy + 4, cx + 96, cy + 96], fill=255)
    path = tmp_path / "hand-drawn.png"
    img.save(path)
    return path
