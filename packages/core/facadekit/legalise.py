"""Panel masks -> real catalogue parts. The legaliser.

This module is the thesis. Everything else in the package feeds it or writes
down what it decided.

What is here today is the *baseline*: `NearestPartLegaliser` picks, for each
panel independently, the catalogue part whose size is closest. It is greedy,
it has no notion of joints, adjacency, waste or unique-part count, and it is
exactly arm 1 of the three-arm experiment ("what raw generation costs"). It is
useful precisely because it is the thing the real legaliser has to beat.

`CpSatLegaliser` is the real one and is a **stub** -- see its docstring for the
model to be built in October. Any caller can swap between them because both
satisfy the `Legaliser` interface and return the same `LegalisationResult`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from facadekit.catalogue import Catalogue, Part
from facadekit.segment import Panel

DEFAULT_TOLERANCE_MM = 50.0
"""How far a part may be from the panel it replaces and still count as legal.

50 mm is a placeholder chosen to make the demo produce a mix of legal and
illegal panels rather than a uniform wall of either. It is not a fabrication
figure and must be replaced by a real one once a manufacturer's catalogue and
joint tolerances are committed (proposal section 6.3).
"""


@dataclass(frozen=True)
class Assignment:
    """One panel, and the part the legaliser chose for it."""

    panel: Panel
    part: Part | None
    rotated: bool = False
    fit_error_mm: float = float("inf")
    legal: bool = False
    note: str = ""

    @property
    def part_id(self) -> str:
        return self.part.id if self.part else "-"


@dataclass(frozen=True)
class LegalisationResult:
    """What the legaliser decided, plus the numbers the thesis reports."""

    assignments: tuple[Assignment, ...]
    catalogue: Catalogue
    method: str
    solve_time_s: float = 0.0
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def legal_count(self) -> int:
        return sum(1 for a in self.assignments if a.legal)

    @property
    def unique_parts(self) -> int:
        return len({a.part.id for a in self.assignments if a.part})

    def __len__(self) -> int:
        return len(self.assignments)


def _summarise(
    assignments: Sequence[Assignment], catalogue: Catalogue, method: str, elapsed: float
) -> LegalisationResult:
    n = len(assignments)
    errors = [a.fit_error_mm for a in assignments if a.part is not None]
    legal = sum(1 for a in assignments if a.legal)
    metrics = {
        "panels": float(n),
        "legalised": float(legal),
        "legalised_fraction": (legal / n) if n else 0.0,
        "unique_parts": float(len({a.part.id for a in assignments if a.part})),
        "mean_fit_error_mm": (sum(errors) / len(errors)) if errors else 0.0,
        "max_fit_error_mm": max(errors) if errors else 0.0,
        "solve_time_s": elapsed,
    }
    return LegalisationResult(
        assignments=tuple(assignments),
        catalogue=catalogue,
        method=method,
        solve_time_s=elapsed,
        metrics=metrics,
    )


class Legaliser(Protocol):
    """Anything that maps panels onto catalogue parts.

    Kept deliberately narrow: the whole point of the experiment is that three
    very different strategies can be dropped in behind this one call.
    """

    name: str

    def legalise(self, panels: Sequence[Panel], catalogue: Catalogue) -> LegalisationResult: ...


class NearestPartLegaliser:
    """Baseline: independently give each panel the closest part by size.

    Distance is Chebyshev on the two dimensions -- max(|dw|, |dh|) -- because a
    part that is close in width but wildly wrong in height is not "close" in any
    sense a fabricator would accept, and an L2 distance would hide that.

    Rotation is allowed for square-ish rectangular parts, which is free realism:
    a rainscreen cassette can usually be hung either way, and refusing rotation
    would make the baseline artificially bad.
    """

    name = "nearest-part"

    def __init__(
        self,
        tolerance_mm: float = DEFAULT_TOLERANCE_MM,
        allow_rotation: bool = True,
        kinds: Sequence[str] | None = None,
    ) -> None:
        self.tolerance_mm = tolerance_mm
        self.allow_rotation = allow_rotation
        self.kinds = tuple(kinds) if kinds else None

    def _candidates(self, catalogue: Catalogue) -> tuple[Part, ...]:
        if self.kinds is None:
            return catalogue.parts
        return tuple(p for p in catalogue.parts if p.kind in self.kinds)

    def legalise(self, panels: Sequence[Panel], catalogue: Catalogue) -> LegalisationResult:
        started = time.perf_counter()
        candidates = self._candidates(catalogue)
        assignments: list[Assignment] = []

        for panel in panels:
            if not candidates:
                assignments.append(
                    Assignment(panel=panel, part=None, note="catalogue has no usable parts")
                )
                continue

            best: tuple[float, bool, Part] | None = None
            for part in candidates:
                options = [(part.w, part.h, False)]
                if self.allow_rotation and part.w != part.h:
                    options.append((part.h, part.w, True))
                for pw, ph, rotated in options:
                    error = max(abs(pw - panel.w), abs(ph - panel.h))
                    # Ties break towards the un-rotated part, then the smaller
                    # part, so the same catalogue always gives the same answer.
                    key = (error, rotated, part.area, part.id)
                    if best is None or key < (best[0], best[1], best[2].area, best[2].id):
                        best = (error, rotated, part)

            assert best is not None
            error, rotated, part = best
            legal = error <= self.tolerance_mm
            assignments.append(
                Assignment(
                    panel=panel,
                    part=part,
                    rotated=rotated,
                    fit_error_mm=error,
                    legal=legal,
                    note=(
                        ""
                        if legal
                        else f"off by {error:.0f} mm (tolerance {self.tolerance_mm:.0f})"
                    ),
                )
            )

        return _summarise(assignments, catalogue, self.name, time.perf_counter() - started)


class CpSatLegaliser:
    """STUB -- the real legaliser. Not implemented; this is the October work.

    Calling `legalise` raises NotImplementedError on purpose. It exists now so
    that the CLI, the API and the experiment harness are already written against
    the interface the real solver will satisfy, and so that swapping it in is a
    one-line change rather than a refactor.

    The model to build (OR-Tools CP-SAT), per the proposal:

      variables   one integer per panel, indexing the catalogue part assigned to
                  it, plus a boolean per (panel, part) for the linearisation and
                  a boolean per part id for "this SKU is used at all"
      hard        catalogue membership; panel kind must match part kind; joint
                  compatibility between adjacent panels; assigned part must fit
                  the panel opening within the system's joint tolerance; parts
                  must nest onto the stock sheet
      objectives  minimise, in a weighted sum or lexicographically:
                    (a) fidelity loss -- deviation from the segmented panel size
                    (b) sheet waste percentage
                    (c) unique part count (SKUs), which is what actually drives
                        cost in a real facade package
      output      the same LegalisationResult, so every downstream consumer and
                  every metric in the comparison table is unchanged

    Read arxiv.org/abs/2606.09849 (Sketch-to-Layout, CP-SAT on a facade grid)
    before writing the formulation from scratch.
    """

    name = "cp-sat"

    def __init__(self, time_limit_s: float = 30.0, **weights: float) -> None:
        self.time_limit_s = time_limit_s
        self.weights = weights

    def legalise(self, panels: Sequence[Panel], catalogue: Catalogue) -> LegalisationResult:
        raise NotImplementedError(
            "CpSatLegaliser is a stub. The CP-SAT model is the October thesis work; "
            "see the class docstring for the formulation. Use NearestPartLegaliser "
            "(--legaliser nearest) for the baseline pipeline."
        )


LEGALISERS: dict[str, type] = {
    "nearest": NearestPartLegaliser,
    "cp-sat": CpSatLegaliser,
}


def get_legaliser(name: str, **kwargs) -> Legaliser:
    try:
        cls = LEGALISERS[name]
    except KeyError:
        raise KeyError(
            f"unknown legaliser {name!r}; available: {sorted(LEGALISERS)}"
        ) from None
    return cls(**kwargs)
