"""Image -> panel masks.

Two ways in, one way out. Both produce a list of `Panel` rectangles in
millimetres, measured from the top-left of the elevation:

    read_mask(...)     a hand-drawn mask PNG -> panels        (no ML, always available)
    segment_image(...) a generated facade PNG -> panels       (SAM, optional extra)

October's solver work only needs the first one. `segment_image` imports torch
and segment-anything lazily so that neither the tests, the CI runner, nor the
deployed CPU box has to carry a multi-gigabyte ML stack to run the pipeline.

Mask convention
---------------
A mask PNG is read as: *light pixels are panel material, dark pixels are the
joint between panels*. Each connected light region becomes one panel, described
by its bounding box. That is deliberately crude -- it is the input the solver
is graded on, not a contribution in itself.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Panel:
    """A panel-shaped hole in the elevation, waiting to be assigned a real part.

    Coordinates are millimetres from the top-left of the elevation, x to the
    right and y downwards -- image order, so nothing has to be flipped between
    here and the panel map. `export` flips y once, on the way into DXF.
    """

    id: str
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def _label_components(binary: np.ndarray, connectivity: int = 4) -> tuple[np.ndarray, int]:
    """Label connected True regions. Iterative BFS -- no scipy/opencv dependency.

    Written out rather than pulled in because it is twenty lines and the
    alternative is putting opencv on the critical path of every install.
    """
    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    if connectivity == 8:
        offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    current = 0
    for sy in range(h):
        for sx in range(w):
            if not binary[sy, sx] or labels[sy, sx]:
                continue
            current += 1
            labels[sy, sx] = current
            queue = deque([(sy, sx)])
            while queue:
                cy, cx = queue.popleft()
                for dy, dx in offsets:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = current
                        queue.append((ny, nx))
    return labels, current


def snap(value: float, grid_mm: float) -> float:
    """Snap one millimetre value to the nearest grid line."""
    if grid_mm <= 0:
        return value
    return round(value / grid_mm) * grid_mm


def read_mask(
    path: str | Path,
    facade_width_mm: float,
    facade_height_mm: float | None = None,
    grid_mm: float = 0.0,
    threshold: int = 128,
    min_area_px: int = 64,
) -> list[Panel]:
    """Turn a hand-drawn mask PNG into panels.

    `facade_width_mm` sets the scale: the image width maps onto that many
    millimetres. If `facade_height_mm` is None the image aspect ratio is kept.
    `grid_mm` > 0 snaps every edge to a structural grid, which is what makes
    the panels legalisable at all -- unsnapped bounding boxes off a raster
    almost never match a catalogue size.
    """
    path = Path(path)
    with Image.open(path) as im:
        arr = np.asarray(im.convert("L"))

    px_h, px_w = arr.shape
    mm_per_px_x = facade_width_mm / px_w
    mm_per_px_y = (
        facade_height_mm / px_h if facade_height_mm is not None else mm_per_px_x
    )

    labels, count = _label_components(arr >= threshold)

    panels: list[Panel] = []
    for label in range(1, count + 1):
        ys, xs = np.nonzero(labels == label)
        if ys.size < min_area_px:
            continue
        x0, x1 = xs.min(), xs.max() + 1
        y0, y1 = ys.min(), ys.max() + 1

        mm_x, mm_y = x0 * mm_per_px_x, y0 * mm_per_px_y
        mm_w, mm_h = (x1 - x0) * mm_per_px_x, (y1 - y0) * mm_per_px_y

        if grid_mm > 0:
            mm_x, mm_y = snap(mm_x, grid_mm), snap(mm_y, grid_mm)
            mm_w, mm_h = max(grid_mm, snap(mm_w, grid_mm)), max(grid_mm, snap(mm_h, grid_mm))

        # float() not np.float64: these end up in JSON and in the CSV.
        panels.append(Panel(id="", x=float(mm_x), y=float(mm_y), w=float(mm_w), h=float(mm_h)))

    # Reading order: top-to-bottom, then left-to-right, so panel ids match how
    # a person scans an elevation and a schedule row is findable on the drawing.
    panels.sort(key=lambda p: (round(p.y, 3), round(p.x, 3)))
    return [Panel(id=f"PNL-{i + 1:03d}", x=p.x, y=p.y, w=p.w, h=p.h) for i, p in enumerate(panels)]


def segment_image(
    path: str | Path,
    facade_width_mm: float,
    facade_height_mm: float | None = None,
    grid_mm: float = 0.0,
    checkpoint: str | Path | None = None,
    model_type: str = "vit_b",
) -> list[Panel]:
    """Segment a generated facade image into panels with SAM.

    Requires the `segment` extra (`pip install -e packages/core[segment]`) and a
    SAM checkpoint. Raises a plain ImportError with install instructions when
    the stack is absent, because the deployed demo is expected to hit this path
    and fall back to pre-computed masks rather than crash obscurely.
    """
    try:
        import cv2  # noqa: F401
        import torch  # noqa: F401
        from segment_anything import SamAutomaticMaskGenerator, sam_model_registry
    except ImportError as e:  # pragma: no cover - exercised only with the extra installed
        raise ImportError(
            "SAM segmentation needs the 'segment' extra:\n"
            "    uv pip install -e packages/core[segment]\n"
            "and a SAM checkpoint (see docs/deploy.md). For a CPU-only host use "
            "pre-computed masks with read_mask() instead."
        ) from e

    if checkpoint is None:
        raise ValueError("segment_image needs a SAM checkpoint path (see docs/deploy.md)")

    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"))

    sam = sam_model_registry[model_type](checkpoint=str(checkpoint))
    generator = SamAutomaticMaskGenerator(sam)
    raw_masks = generator.generate(rgb)

    px_h, px_w = rgb.shape[:2]
    mm_per_px_x = facade_width_mm / px_w
    mm_per_px_y = facade_height_mm / px_h if facade_height_mm is not None else mm_per_px_x

    panels: list[Panel] = []
    for m in raw_masks:
        x0, y0, bw, bh = m["bbox"]
        mm_x, mm_y = x0 * mm_per_px_x, y0 * mm_per_px_y
        mm_w, mm_h = bw * mm_per_px_x, bh * mm_per_px_y
        if grid_mm > 0:
            mm_x, mm_y = snap(mm_x, grid_mm), snap(mm_y, grid_mm)
            mm_w, mm_h = max(grid_mm, snap(mm_w, grid_mm)), max(grid_mm, snap(mm_h, grid_mm))
        panels.append(Panel(id="", x=mm_x, y=mm_y, w=mm_w, h=mm_h))

    panels.sort(key=lambda p: (round(p.y, 3), round(p.x, 3)))
    return [Panel(id=f"PNL-{i + 1:03d}", x=p.x, y=p.y, w=p.w, h=p.h) for i, p in enumerate(panels)]
