"""Write the three files a fabricator actually consumes.

    schedule.csv    one row per panel: id, part, size, position, legal?
    nesting.dxf     stock sheets with the parts laid out on them, ready to cut
    panel-map.png   the elevation redrawn as coloured, labelled catalogue parts

The DXF is the only one with a hard external dependency (ezdxf). Everything is
millimetres; DXF y runs upwards, so the elevation is flipped once here and
nowhere else.
"""

from __future__ import annotations

import colorsys
import csv
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from facadekit.legalise import LegalisationResult
from facadekit.nest import NestResult

SHEET_GAP_MM = 200.0
"""Space left between stock sheets in the nesting DXF, so the cut lines of one
sheet are never mistaken for another's."""


@dataclass(frozen=True)
class ExportPaths:
    schedule: Path
    dxf: Path
    panel_map: Path

    def as_dict(self) -> dict[str, str]:
        """Just the filenames: the directory is the caller's business, and an
        absolute path from one machine is meaningless in another's dataset."""
        return {
            "schedule": self.schedule.name,
            "dxf": self.dxf.name,
            "panel_map": self.panel_map.name,
        }


def _colour_for(part_id: str) -> tuple[int, int, int]:
    """A stable, well-spread colour per part id.

    Hash-to-hue rather than a fixed palette: the number of distinct parts is a
    property of the catalogue and the solver, not something to cap here.
    """
    h = (hash(part_id) % 997) / 997.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.45, 0.92)
    return int(r * 255), int(g * 255), int(b * 255)


def write_schedule(result: LegalisationResult, path: str | Path) -> Path:
    """Panel schedule CSV -- the document a fabricator quotes from."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "panel_id", "part_id", "kind", "part_w_mm", "part_h_mm",
                "finish", "joint", "rotated", "x_mm", "y_mm",
                "panel_w_mm", "panel_h_mm", "fit_error_mm", "legal", "note",
            ]
        )
        for a in result.assignments:
            p = a.panel
            w.writerow(
                [
                    p.id,
                    a.part.id if a.part else "",
                    a.part.kind if a.part else "",
                    f"{a.part.w:.1f}" if a.part else "",
                    f"{a.part.h:.1f}" if a.part else "",
                    a.part.finish if a.part else "",
                    a.part.joint if a.part else "",
                    "yes" if a.rotated else "no",
                    f"{p.x:.1f}", f"{p.y:.1f}", f"{p.w:.1f}", f"{p.h:.1f}",
                    "" if a.part is None else f"{a.fit_error_mm:.1f}",
                    "yes" if a.legal else "no",
                    a.note,
                ]
            )
    return path


def write_dxf(result: LegalisationResult, nested: NestResult, path: str | Path) -> Path:
    """Cut file: every stock sheet with its parts, plus the elevation for reference.

    Layers: SHEET (stock outline), CUT (the actual part outlines -- this is what
    a machine reads), TEXT (part labels), ELEVATION (the facade as legalised, so
    the file is self-explanatory when opened cold).
    """
    import ezdxf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    msp = doc.modelspace()

    doc.layers.add("SHEET", color=8)
    doc.layers.add("CUT", color=1)
    doc.layers.add("TEXT", color=2)
    doc.layers.add("ELEVATION", color=5)

    def rect(x0: float, y0: float, w: float, h: float, layer: str) -> None:
        msp.add_lwpolyline(
            [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
            close=True,
            dxfattribs={"layer": layer},
        )

    # --- nesting: sheets laid out left to right -----------------------------
    offset = 0.0
    for s in nested.sheets:
        rect(offset, 0.0, s.sheet.w, s.sheet.h, "SHEET")
        msp.add_text(
            f"SHEET {s.index + 1}  {s.sheet.w:.0f}x{s.sheet.h:.0f}  "
            f"waste {100 * s.waste_fraction:.1f}%",
            height=40,
            dxfattribs={"layer": "TEXT"},
        ).set_placement((offset, s.sheet.h + 60))
        for pl in s.placements:
            rect(offset + pl.x, pl.y, pl.w, pl.h, "CUT")
            msp.add_text(
                f"{pl.panel_id} {pl.part_id}",
                height=24,
                dxfattribs={"layer": "TEXT"},
            ).set_placement((offset + pl.x + 20, pl.y + 20))
        offset += s.sheet.w + SHEET_GAP_MM

    # --- elevation, placed above the sheets ---------------------------------
    if result.assignments:
        facade_h = max(a.panel.y + a.panel.h for a in result.assignments)
        sheets_h = max((s.sheet.h for s in nested.sheets), default=0.0)
        base_y = sheets_h + 800.0
        for a in result.assignments:
            p = a.panel
            # image y is downwards, DXF y is upwards: flip once, here.
            rect(p.x, base_y + (facade_h - p.y - p.h), p.w, p.h, "ELEVATION")
            msp.add_text(
                a.part_id,
                height=min(60, max(18, p.h / 6)),
                dxfattribs={"layer": "TEXT"},
            ).set_placement((p.x + 20, base_y + (facade_h - p.y - p.h) + 20))

    doc.saveas(path)
    return path


def write_panel_map(
    result: LegalisationResult,
    path: str | Path,
    width_px: int = 1200,
    margin_px: int = 40,
    label: bool = True,
) -> Path:
    """The elevation redrawn as catalogue parts: one colour per part, labelled.

    Illegal panels get a red outline, so the picture answers "did it legalise?"
    at a glance rather than only in the CSV.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not result.assignments:
        Image.new("RGB", (width_px, 200), "white").save(path)
        return path

    facade_w = max(a.panel.x + a.panel.w for a in result.assignments)
    facade_h = max(a.panel.y + a.panel.h for a in result.assignments)
    scale = (width_px - 2 * margin_px) / facade_w if facade_w else 1.0
    height_px = int(facade_h * scale) + 2 * margin_px

    img = Image.new("RGB", (width_px, height_px), (247, 246, 241))
    draw = ImageDraw.Draw(img)

    for a in result.assignments:
        p = a.panel
        x0 = margin_px + p.x * scale
        y0 = margin_px + p.y * scale
        x1 = x0 + p.w * scale
        y1 = y0 + p.h * scale

        fill = _colour_for(a.part_id) if a.part else (225, 225, 225)
        outline = (40, 44, 52) if a.legal else (184, 67, 46)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=3 if a.legal else 5)

        if label and (x1 - x0) > 46 and (y1 - y0) > 22:
            draw.text((x0 + 6, y0 + 5), a.panel.id, fill=(28, 32, 40))
            draw.text((x0 + 6, y0 + 17), a.part_id, fill=(28, 32, 40))

    m = result.metrics
    draw.text(
        (margin_px, 12),
        f"{result.method}  |  {result.legal_count}/{len(result)} legalised  |  "
        f"{result.unique_parts} unique parts  |  max error "
        f"{m.get('max_fit_error_mm', 0):.0f} mm",
        fill=(102, 106, 115),
    )
    img.save(path)
    return path


def write_all(
    result: LegalisationResult, nested: NestResult, out_dir: str | Path
) -> ExportPaths:
    """Write all three deliverables into `out_dir`."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return ExportPaths(
        schedule=write_schedule(result, out / "schedule.csv"),
        dxf=write_dxf(result, nested, out / "nesting.dxf"),
        panel_map=write_panel_map(result, out / "panel-map.png"),
    )
