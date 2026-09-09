"""`facadekit` on the command line.

    facadekit run --brief "a six-storey office facade, deep reveals" \
                  --catalogue data/catalogues/demo.json --out out/demo

    facadekit run --mask data/samples/masks/banded.png \
                  --catalogue data/catalogues/demo.json --out out/banded

    facadekit check data/catalogues/demo.json

The `--mask` form is October's working mode: no image, no GPU, straight into
the solver. The `--brief` form needs a generate backend and defaults to the
cached one, which costs nothing.
"""

from __future__ import annotations

from pathlib import Path

import typer

from facadekit.catalogue import CatalogueError, load_catalogue
from facadekit.legalise import DEFAULT_TOLERANCE_MM
from facadekit.pipeline import (
    DEFAULT_FACADE_WIDTH_MM,
    DEFAULT_GRID_MM,
    PipelineError,
    RunConfig,
)
from facadekit.pipeline import (
    run as run_pipeline,
)

app = typer.Typer(
    add_completion=False,
    help="Legalise a facade against a real manufacturer's kit of parts.",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MASKS_DIR = REPO_ROOT / "data" / "samples" / "masks"


def _load_generator(name: str | None):
    """Import the generate adapter lazily; it is an optional sibling package."""
    try:
        from facadekit_generate import get_generator
    except ImportError:
        return None
    return get_generator(name)


@app.command()
def run(
    catalogue: Path = typer.Option(..., "--catalogue", "-c", help="Catalogue JSON."),
    out: Path = typer.Option(..., "--out", "-o", help="Output directory."),
    brief: str = typer.Option("", "--brief", "-b", help="Text brief for the facade."),
    mask: Path | None = typer.Option(
        None, "--mask", "-m", help="Skip generation; segment this mask PNG directly."
    ),
    generate: str | None = typer.Option(
        None, "--generate", help="Backend: cached (default) | fal | comfyui."
    ),
    legaliser: str = typer.Option(
        "nearest", "--legaliser", "-l", help="nearest (baseline) | cp-sat (stub)."
    ),
    tolerance_mm: float = typer.Option(
        DEFAULT_TOLERANCE_MM, "--tolerance", help="Max size error still counted as legal."
    ),
    facade_width_mm: float = typer.Option(
        DEFAULT_FACADE_WIDTH_MM, "--facade-width", help="Real width of the elevation, mm."
    ),
    facade_height_mm: float | None = typer.Option(
        None, "--facade-height", help="Real height, mm. Defaults to the image aspect."
    ),
    grid_mm: float = typer.Option(DEFAULT_GRID_MM, "--grid", help="Snap panel edges to this grid."),
    seed: int = typer.Option(0, "--seed", help="Generation seed."),
) -> None:
    """Run the pipeline and write schedule.csv, nesting.dxf and panel-map.png."""
    if not brief and mask is None:
        raise typer.BadParameter("give a --brief to generate from, or a --mask to segment.")

    generator = None if mask is not None else _load_generator(generate)
    if mask is None and generator is None:
        raise typer.BadParameter(
            "no generate adapter installed. Either pass --mask, or install it:\n"
            "    uv pip install -e adapters/generate"
        )

    config = RunConfig(
        brief=brief,
        catalogue_path=catalogue,
        out_dir=out,
        mask_path=mask,
        masks_dir=DEFAULT_MASKS_DIR,
        facade_width_mm=facade_width_mm,
        facade_height_mm=facade_height_mm,
        grid_mm=grid_mm,
        legaliser=legaliser,
        tolerance_mm=tolerance_mm,
        seed=seed,
    )

    try:
        result = run_pipeline(config, generator)
    except (PipelineError, CatalogueError, NotImplementedError) as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None

    m = result.legalisation.metrics
    typer.secho(f"\n{result.catalogue.system}", bold=True)
    typer.echo(f"  method        {result.legalisation.method}")
    typer.echo(f"  panels        {len(result.panels)}")
    typer.echo(
        f"  legalised     {result.legalisation.legal_count}/{len(result.panels)} "
        f"({100 * m['legalised_fraction']:.0f}%)"
    )
    typer.echo(f"  unique parts  {result.legalisation.unique_parts}")
    typer.echo(f"  max fit error {m['max_fit_error_mm']:.0f} mm")
    typer.echo(
        f"  sheets        {result.nesting.sheet_count} "
        f"({result.nesting.waste_pct:.1f}% waste, {result.nesting.method})"
    )
    for w in result.warnings:
        typer.secho(f"  warning: {w}", fg=typer.colors.YELLOW)

    typer.secho("\nwrote", bold=True)
    for label, path in result.exports.as_dict().items():
        typer.echo(f"  {label:<11} {path}")
    typer.echo(f"  {'manifest':<11} {result.out_dir / 'run.json'}")


@app.command()
def check(catalogue: Path = typer.Argument(..., help="Catalogue JSON to validate.")) -> None:
    """Validate a catalogue and print a summary. Exit 1 if it is malformed."""
    try:
        cat = load_catalogue(catalogue)
    except CatalogueError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None

    typer.secho(f"{cat.system}  OK", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  sheet  {cat.sheet.w:.0f} x {cat.sheet.h:.0f} mm")
    typer.echo(f"  parts  {len(cat)} across {len(cat.kinds)} kinds")
    for kind in cat.kinds:
        items = cat.of_kind(kind)
        typer.echo(f"    {kind:<8} {len(items):>2}  " + ", ".join(p.id for p in items[:4])
                   + (" ..." if len(items) > 4 else ""))


if __name__ == "__main__":
    app()
