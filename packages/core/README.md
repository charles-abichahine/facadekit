# facadekit (core)

The Python package the thesis lives in. Brief → image → panel masks →
**catalogue parts** → sheets → CSV/DXF/PNG.

| Module | Does | State |
|---|---|---|
| `catalogue.py` | load + validate a manufacturer catalogue JSON | working |
| `segment.py` | mask PNG → panels; SAM image → panels | mask path working, SAM optional |
| `legalise.py` | panels → catalogue parts | **baseline only** — CP-SAT is a stub |
| `nest.py` | parts → stock sheets, waste % | **stub** — naive shelf packing |
| `export.py` | schedule CSV, nesting DXF, panel map PNG | working |
| `cli.py` | `facadekit run` | working |

Install (from the repo root):

```bash
uv pip install -e "packages/core[dev]"
```

Optional extras: `[solver]` for OR-Tools (the October CP-SAT work), `[segment]`
for SAM + torch. Neither is needed to run the baseline pipeline.

See the repository README for what "stub" means here and which numbers may be
quoted as results.
