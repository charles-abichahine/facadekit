# FacadeKit

**Legalising generated façades against a real kit of parts.**
MaCAD thesis · Charles Abi Chahine · tutor Gabriella Rossi · IAAC, Oct–Dec 2026

You type a façade brief. A model draws it. A solver forces the drawing to obey a
real panel manufacturer's catalogue. The output is a **panel schedule, a nesting
layout and cut files** — not a render.

```
brief → image → panel masks → CATALOGUE PARTS → sheets → CSV · DXF · PNG
        FLUX     SAM           the legaliser     nesting   + run.json
        ·······borrowed······  ······────── the thesis ──────······
```

The graded contribution is the **legaliser**, the **labelled dataset** it produces
as a side effect (one `run.json` per run), and the **comparison** between
constrained and unconstrained generation.

---

## Status: skeleton

The pipeline runs end to end, but on placeholders. Nothing here is a result yet.

| | State |
|---|---|
| `catalogue.py`, `segment.py`, `export.py`, `pipeline.py`, `cli.py` | working |
| `legalise.py` → `NearestPartLegaliser` | **baseline** — nearest part by size, nothing else |
| `legalise.py` → `CpSatLegaliser` | **stub** — raises; this is the October work |
| `nest.py` | **stub** — naive shelf packing; its waste % is a ceiling, not a result |
| `data/catalogues/demo.json` | **self-authored**, not a real product |
| images in `data/samples/` | **placeholders**, no FLUX output, no façade LoRA trained |

Two numbers to distrust: the **50 mm legalisation tolerance is invented**, and any
waste figure comes from the naive packer. Both change the headline percentages.

---

## Run it

Python 3.11+.

```bash
uv venv --python 3.11 .venv
uv pip install -e "packages/core[dev]" -e adapters/generate
```

No image, no GPU, straight into the solver — this is October's working mode:

```bash
facadekit run --mask data/samples/masks/banded.png -c data/catalogues/demo.json -o out/banded
```

Writes `schedule.csv`, `nesting.dxf`, `panel-map.png` and `run.json`.

Validate a catalogue on its own with `facadekit check data/catalogues/demo.json`.
The web app and API are in `apps/`; see [docs/deploy.md](docs/deploy.md).

---

## Credits

Solo thesis, but descended from **LegoArch** (`hi-em/genai-legoarch`), built by
**Charles Abi Chahine and Emilie El Chidiac** for IAAC MaCAD 2025/26. A new
repository, not a fork — but the debt is specific:

- `tools/comfyui/` — the FLUX + LoRA graphs, copied unchanged.
- `tools/legoarch-reference/` — LegoArch's catalogue code, kept as reference and
  never imported. `facadekit/catalogue.py` is written fresh but owes it the
  two-source validation idea.
- The shape of the whole thing: generate, discretise, legalise against a real
  catalogue, verify, export a parts list.

Not carried over: the legolizer, TRELLIS, the voxeliser, the gravity check.

## Licence

MIT for the original work — see [LICENSE](LICENSE). **Not MIT:** the copied files
under `tools/`, which are co-owned with Emilie El Chidiac and carry no licence.
