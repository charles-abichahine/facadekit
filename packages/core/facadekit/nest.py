"""Parts -> stock sheets, and a waste percentage.

STUB. This is a first-fit-decreasing shelf packer: sort the parts tall-first,
lay them left to right on a shelf, start a new shelf when the row is full,
start a new sheet when the shelves are. It is the standard naive baseline and
it is here so the pipeline produces a nesting layout and a waste number today.

It is *not* the thesis nesting. The real one is a CP-SAT / cutting-stock model
(or OpenNest / Deepnest as the baseline to beat, per the proposal). The waste
figure this produces is a ceiling, not a result: quote it as "naive shelf
packing" wherever it appears, never as FacadeKit's waste number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from facadekit.catalogue import Catalogue, Sheet
from facadekit.legalise import LegalisationResult

KERF_MM = 0.0
"""Blade/cutter width. Zero until a real machine is chosen; a real kerf makes
every part effectively larger and is a genuine source of waste."""


@dataclass(frozen=True)
class Placement:
    """One part placed on one sheet, in sheet coordinates (mm from bottom-left)."""

    panel_id: str
    part_id: str
    x: float
    y: float
    w: float
    h: float
    rotated: bool = False

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass
class NestedSheet:
    index: int
    sheet: Sheet
    placements: list[Placement] = field(default_factory=list)

    @property
    def used_area(self) -> float:
        return sum(p.area for p in self.placements)

    @property
    def waste_fraction(self) -> float:
        if self.sheet.area <= 0:
            return 0.0
        return 1.0 - (self.used_area / self.sheet.area)


@dataclass(frozen=True)
class NestResult:
    sheets: tuple[NestedSheet, ...]
    method: str
    unplaced: tuple[str, ...] = ()

    @property
    def sheet_count(self) -> int:
        return len(self.sheets)

    @property
    def used_area(self) -> float:
        return sum(s.used_area for s in self.sheets)

    @property
    def stock_area(self) -> float:
        return sum(s.sheet.area for s in self.sheets)

    @property
    def waste_fraction(self) -> float:
        if self.stock_area <= 0:
            return 0.0
        return 1.0 - (self.used_area / self.stock_area)

    @property
    def waste_pct(self) -> float:
        return 100.0 * self.waste_fraction

    @property
    def metrics(self) -> dict[str, float]:
        return {
            "sheets": float(self.sheet_count),
            "waste_pct": self.waste_pct,
            "used_area_mm2": self.used_area,
            "stock_area_mm2": self.stock_area,
            "unplaced": float(len(self.unplaced)),
        }


def nest(result: LegalisationResult, catalogue: Catalogue | None = None) -> NestResult:
    """Pack every assigned part onto stock sheets (naive shelf packing)."""
    catalogue = catalogue or result.catalogue
    sheet = catalogue.sheet

    items: list[tuple[str, str, float, float]] = []
    unplaced: list[str] = []
    for a in result.assignments:
        if a.part is None:
            unplaced.append(a.panel.id)
            continue
        w, h = (a.part.h, a.part.w) if a.rotated else (a.part.w, a.part.h)
        items.append((a.panel.id, a.part.id, w + KERF_MM, h + KERF_MM))

    # Tall-first, then wide-first: the classic FFD ordering for shelf packing.
    items.sort(key=lambda it: (-it[3], -it[2]))

    sheets: list[NestedSheet] = []
    cursor_x = 0.0
    shelf_y = 0.0
    shelf_h = 0.0

    def new_sheet() -> NestedSheet:
        nonlocal cursor_x, shelf_y, shelf_h
        cursor_x, shelf_y, shelf_h = 0.0, 0.0, 0.0
        s = NestedSheet(index=len(sheets), sheet=sheet)
        sheets.append(s)
        return s

    current = new_sheet()

    for panel_id, part_id, w, h in items:
        turned = False
        if w > sheet.w or h > sheet.h:
            # How a part sits on the elevation and how it sits on the sheet are
            # different decisions: a 1200 x 1500 window only fits a 1220 mm
            # sheet on its side. Turn it for cutting.
            #
            # This is safe only while finishes have no grain direction. A
            # brushed or directional finish makes rotation a real constraint,
            # and the CP-SAT nester will have to carry it as one.
            if h <= sheet.w and w <= sheet.h:
                w, h, turned = h, w, True
            else:
                unplaced.append(panel_id)
                continue

        if cursor_x + w > sheet.w:  # shelf full -> next shelf
            shelf_y += shelf_h
            cursor_x, shelf_h = 0.0, 0.0
        if shelf_y + h > sheet.h:  # sheet full -> next sheet
            current = new_sheet()

        current.placements.append(
            Placement(
                panel_id=panel_id, part_id=part_id,
                x=cursor_x, y=shelf_y, w=w, h=h, rotated=turned,
            )
        )
        cursor_x += w
        shelf_h = max(shelf_h, h)

    if sheets and not sheets[-1].placements:
        sheets.pop()

    return NestResult(sheets=tuple(sheets), method="shelf-ffd (stub)", unplaced=tuple(unplaced))
