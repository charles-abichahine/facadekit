"""Load and validate a panel catalogue.

A catalogue is one manufacturer's kit of parts, as JSON:

    {
      "system": "Demo Rainscreen R1",
      "units": "mm",
      "sheet": {"w": 3050, "h": 1220},
      "parts": [
        {"id": "P-0600-0600", "kind": "panel", "w": 600, "h": 600,
         "finish": "natural", "joint": "open-6mm"}
      ]
    }

Validation is strict and collects *every* problem before raising, because a
catalogue is hand-authored and a single-error-at-a-time loop is miserable to
work through. The rule that a part must physically fit on a stock sheet is the
one real fabrication constraint here rather than a schema formality -- it is
what makes "fabricable by construction" mean anything at all.

Provenance: the two-source validation idea ("accept a part only if two
independent sources agree") is carried over from LegoArch's Rebrickable +
LDraw catalogue builder. See tools/legoarch-reference/.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KINDS = ("panel", "window", "corner")
"""Part kinds the legaliser understands. A panel mask is only ever replaced by
a part of a compatible kind."""


class CatalogueError(ValueError):
    """A catalogue is malformed. Carries every problem found, not just the first."""

    def __init__(self, problems: Iterable[str], source: str | None = None) -> None:
        self.problems = list(problems)
        self.source = source
        where = f" in {source}" if source else ""
        joined = "\n  - ".join(self.problems)
        super().__init__(f"{len(self.problems)} problem(s){where}:\n  - {joined}")


@dataclass(frozen=True)
class Part:
    """One orderable item from the manufacturer's catalogue."""

    id: str
    kind: str
    w: float
    h: float
    finish: str
    joint: str

    @property
    def area(self) -> float:
        return self.w * self.h

    def fits_on(self, sheet: Sheet, allow_rotation: bool = True) -> bool:
        if self.w <= sheet.w and self.h <= sheet.h:
            return True
        return allow_rotation and self.h <= sheet.w and self.w <= sheet.h


@dataclass(frozen=True)
class Sheet:
    """A stock sheet the parts are cut from."""

    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass(frozen=True)
class Catalogue:
    system: str
    units: str
    sheet: Sheet
    parts: tuple[Part, ...]
    _by_id: dict[str, Part] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {p.id: p for p in self.parts})

    @property
    def by_id(self) -> dict[str, Part]:
        return dict(self._by_id)

    def get(self, part_id: str) -> Part:
        try:
            return self._by_id[part_id]
        except KeyError:
            raise KeyError(f"no part {part_id!r} in catalogue {self.system!r}") from None

    def of_kind(self, kind: str) -> tuple[Part, ...]:
        return tuple(p for p in self.parts if p.kind == kind)

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({p.kind for p in self.parts}))

    def __len__(self) -> int:
        return len(self.parts)


def _is_positive_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def validate(raw: dict[str, Any], source: str | None = None) -> Catalogue:
    """Turn a parsed JSON object into a Catalogue, or raise CatalogueError."""
    if not isinstance(raw, dict):
        raise CatalogueError(["top level must be a JSON object"], source)

    problems: list[str] = []

    system = raw.get("system")
    if not isinstance(system, str) or not system.strip():
        problems.append("'system' must be a non-empty string")

    units = raw.get("units")
    if units != "mm":
        problems.append(
            f"'units' must be \"mm\" (got {units!r}); everything downstream assumes mm"
        )

    sheet_raw = raw.get("sheet")
    sheet: Sheet | None = None
    if not isinstance(sheet_raw, dict):
        problems.append("'sheet' must be an object with 'w' and 'h'")
    else:
        sw, sh = sheet_raw.get("w"), sheet_raw.get("h")
        if not _is_positive_number(sw) or not _is_positive_number(sh):
            problems.append("'sheet.w' and 'sheet.h' must be positive numbers")
        else:
            sheet = Sheet(float(sw), float(sh))

    parts_raw = raw.get("parts")
    parts: list[Part] = []
    if not isinstance(parts_raw, list) or not parts_raw:
        problems.append("'parts' must be a non-empty list")
    else:
        seen: set[str] = set()
        for i, p in enumerate(parts_raw):
            tag = f"parts[{i}]"
            if not isinstance(p, dict):
                problems.append(f"{tag} must be an object")
                continue

            pid = p.get("id")
            if not isinstance(pid, str) or not pid.strip():
                problems.append(f"{tag}.id must be a non-empty string")
                pid = None
            elif pid in seen:
                problems.append(f"{tag}.id {pid!r} is a duplicate; part ids must be unique")
                pid = None
            else:
                seen.add(pid)
                tag = f"part {pid!r}"

            kind = p.get("kind")
            if kind not in KINDS:
                problems.append(f"{tag}.kind must be one of {list(KINDS)} (got {kind!r})")

            for dim in ("w", "h"):
                if not _is_positive_number(p.get(dim)):
                    problems.append(f"{tag}.{dim} must be a positive number of mm")

            for name in ("finish", "joint"):
                v = p.get(name)
                if not isinstance(v, str) or not v.strip():
                    problems.append(f"{tag}.{name} must be a non-empty string")

            ok = (
                pid is not None
                and kind in KINDS
                and _is_positive_number(p.get("w"))
                and _is_positive_number(p.get("h"))
                and isinstance(p.get("finish"), str)
                and isinstance(p.get("joint"), str)
            )
            if not ok:
                continue

            part = Part(pid, kind, float(p["w"]), float(p["h"]), p["finish"], p["joint"])
            if sheet is not None and not part.fits_on(sheet):
                problems.append(
                    f"part {pid!r} is {part.w:.0f}x{part.h:.0f} mm and does not fit on the "
                    f"{sheet.w:.0f}x{sheet.h:.0f} mm stock sheet in either orientation"
                )
            else:
                parts.append(part)

    if problems:
        raise CatalogueError(problems, source)

    assert sheet is not None
    return Catalogue(system=str(system), units="mm", sheet=sheet, parts=tuple(parts))


def load_catalogue(path: str | Path) -> Catalogue:
    """Read a catalogue JSON file from disk and validate it."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CatalogueError([f"file not found: {path}"], str(path)) from None
    except json.JSONDecodeError as e:
        raise CatalogueError([f"not valid JSON: {e}"], str(path)) from None
    return validate(raw, source=str(path))
