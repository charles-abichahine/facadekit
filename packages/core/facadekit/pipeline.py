"""One run of the whole pipeline, end to end.

Lives here rather than in the CLI so that the command line and the API drive
exactly the same code. Any divergence between "what I ran locally" and "what
the demo did" would poison the experiment.

The generator is injected, not imported: core stays independent of
`adapters/generate`, which is what lets the deployed API swap FLUX for a cached
image without core knowing or caring.

Every run writes `run.json` -- the dataset row. The proposal's second
deliverable is a labelled dataset of generated facades, and it is produced as a
side effect of running the pipeline at all, not by a separate export step.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from facadekit import __version__
from facadekit.catalogue import Catalogue, load_catalogue
from facadekit.export import ExportPaths, write_all
from facadekit.legalise import DEFAULT_TOLERANCE_MM, LegalisationResult, get_legaliser
from facadekit.nest import NestResult, nest
from facadekit.segment import Panel, read_mask, segment_image

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_FACADE_WIDTH_MM = 12000.0
DEFAULT_GRID_MM = 300.0
"""Structural grid the panel edges snap to. 300 mm is a common facade module and
divides every panel size in the demo catalogue; a real catalogue brings its own."""


class SupportsGenerate(Protocol):
    name: str

    def generate(self, prompt: str, seed: int = 0) -> Any: ...


class PipelineError(RuntimeError):
    """The run could not complete. Message is safe to show a user."""


@dataclass
class RunConfig:
    brief: str = ""
    catalogue_path: str | Path = ""
    out_dir: str | Path = "out"
    mask_path: str | Path | None = None
    masks_dir: str | Path | None = None
    facade_width_mm: float = DEFAULT_FACADE_WIDTH_MM
    facade_height_mm: float | None = None
    grid_mm: float = DEFAULT_GRID_MM
    legaliser: str = "nearest"
    tolerance_mm: float = DEFAULT_TOLERANCE_MM
    seed: int = 0


def _portable(path: Path | None) -> str | None:
    """A path that means the same thing on another machine.

    Relative to the repo root where possible, always forward slashes. Rows
    written on Windows and on the Linux deploy box have to be joinable in one
    dataset; "data\\samples\\masks\\banded.png" and "data/samples/masks/banded.png"
    are not the same string.
    """
    if path is None:
        return None
    path = Path(path)
    try:
        path = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        pass  # outside the repo (a tmpdir, an absolute mask): keep as given
    return path.as_posix()


@dataclass
class RunResult:
    out_dir: Path
    catalogue: Catalogue
    panels: tuple[Panel, ...]
    legalisation: LegalisationResult
    nesting: NestResult
    exports: ExportPaths
    config: RunConfig | None = None
    image_path: Path | None = None
    mask_path: Path | None = None
    generator: str = "none"
    warnings: list[str] = field(default_factory=list)

    @property
    def manifest(self) -> dict[str, Any]:
        """The dataset row for this run.

        `settings` is not bookkeeping. The legalisation tolerance is currently an
        invented number (see legalise.DEFAULT_TOLERANCE_MM) and it directly sets
        `legalised_fraction`; a row that does not record which tolerance produced
        it cannot be compared with another row, and cannot be reproduced.
        """
        c = self.config or RunConfig()
        return {
            "facadekit_version": __version__,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "catalogue": {
                "system": self.catalogue.system,
                "parts": len(self.catalogue),
                "sheet": asdict(self.catalogue.sheet),
            },
            "generator": self.generator,
            "brief": c.brief,
            "image": self.image_path.name if self.image_path else None,
            "mask": _portable(self.mask_path),
            "method": self.legalisation.method,
            "settings": {
                "seed": c.seed,
                "grid_mm": c.grid_mm,
                "tolerance_mm": c.tolerance_mm,
                "facade_width_mm": c.facade_width_mm,
                "facade_height_mm": c.facade_height_mm,
            },
            "panels": len(self.panels),
            "metrics": {**self.legalisation.metrics, **self.nesting.metrics},
            "files": self.exports.as_dict(),
            "warnings": self.warnings,
        }


def _resolve_mask(
    config: RunConfig, generator: SupportsGenerate | None, out: Path, warnings: list[str]
) -> tuple[Path, Path | None, str]:
    """Return (mask_path, image_path, generator_name).

    Three routes, in order of preference:
      1. an explicit --mask: no generation at all (October's working mode)
      2. generate an image, then SAM it (needs the segment extra + a checkpoint)
      3. generate an image, then use its pre-computed paired mask (deployed demo)
    """
    if config.mask_path:
        mask = Path(config.mask_path)
        if not mask.is_file():
            raise PipelineError(f"mask not found: {mask}")
        return mask, None, "none"

    if generator is None:
        raise PipelineError(
            "nothing to segment: pass a --mask, or configure a generate backend."
        )

    try:
        generated = generator.generate(config.brief, config.seed)
    except Exception as e:  # backends raise their own typed errors
        raise PipelineError(f"generation failed ({generator.name}): {e}") from e

    image_path = out / "proposal.png"
    image_path.write_bytes(generated.png)

    checkpoint = os.environ.get("FACADEKIT_SAM_CHECKPOINT")
    if checkpoint:
        try:
            segment_image(
                image_path,
                facade_width_mm=config.facade_width_mm,
                facade_height_mm=config.facade_height_mm,
                grid_mm=config.grid_mm,
                checkpoint=checkpoint,
            )
            return image_path, image_path, generator.name
        except (ImportError, ValueError) as e:
            warnings.append(f"SAM unavailable, fell back to a pre-computed mask: {e}")

    # Fallback: the paired hand-drawn mask for this cached image.
    paired_name = (generated.provenance or {}).get("file")
    masks_dir = Path(config.masks_dir) if config.masks_dir else None
    if paired_name and masks_dir and (masks_dir / paired_name).is_file():
        warnings.append(
            f"no SAM checkpoint; segmented the pre-computed mask {paired_name} instead of "
            "the image itself"
        )
        return masks_dir / paired_name, image_path, generator.name

    raise PipelineError(
        "cannot segment: no SAM checkpoint (FACADEKIT_SAM_CHECKPOINT) and no pre-computed "
        f"mask for {paired_name or 'the generated image'} in {masks_dir or '(no masks dir)'}. "
        "Pass --mask to run the solver directly on a mask."
    )


def run(config: RunConfig, generator: SupportsGenerate | None = None) -> RunResult:
    """Brief (or mask) in, CSV + DXF + PNG out."""
    if not config.catalogue_path:
        raise PipelineError("a catalogue is required")

    out = Path(config.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    catalogue = load_catalogue(config.catalogue_path)
    mask_path, image_path, generator_name = _resolve_mask(config, generator, out, warnings)

    panels = read_mask(
        mask_path,
        facade_width_mm=config.facade_width_mm,
        facade_height_mm=config.facade_height_mm,
        grid_mm=config.grid_mm,
    )
    if not panels:
        raise PipelineError(
            f"no panels found in {mask_path}. Masks are read as light = panel, "
            "dark = joint; check the image is not inverted."
        )

    legaliser = get_legaliser(config.legaliser, tolerance_mm=config.tolerance_mm)
    legalisation = legaliser.legalise(panels, catalogue)
    nesting = nest(legalisation, catalogue)
    exports = write_all(legalisation, nesting, out)

    result = RunResult(
        out_dir=out,
        catalogue=catalogue,
        panels=tuple(panels),
        legalisation=legalisation,
        nesting=nesting,
        exports=exports,
        config=config,
        image_path=image_path,
        mask_path=Path(mask_path),
        generator=generator_name,
        warnings=warnings,
    )
    (out / "run.json").write_text(
        json.dumps(result.manifest, indent=2), encoding="utf-8"
    )
    return result
