# LegoArch catalogue code — reference only

Copied verbatim from **LegoArch** (`hi-em/genai-legoarch`, Charles Abi Chahine
and Emilie El Chidiac, IAAC MaCAD 2025/26). **Nothing here is imported by
FaçadeKit.** It is kept so the lineage of `facadekit/catalogue.py` is visible
and auditable rather than asserted.

| File | Originally |
|---|---|
| `build_catalog.py` | `scripts/build_catalog.py` |
| `catalog_loader.py` | `backend/app/catalog/__init__.py` |
| `test_catalog.py` | `backend/tests/test_catalog.py` |

## What transferred, and what did not

The **code** does not transfer: it is LEGO all the way down — Rebrickable CSV
dumps, LDraw colour codes, stud/plate geometry, per-part colour availability.
A façade catalogue has none of those.

The **method** transfers, and it is the part worth keeping:

- **Two-source validation.** LegoArch accepts a colour only if Rebrickable and
  LDraw agree on its code *and* its name, and drops it loudly otherwise. The
  façade equivalent is accepting a part only if the manufacturer's published
  size table and its technical datasheet agree.
- **Prove availability, do not assume it.** A (part, colour) pair was allowed
  only if a real element existed in `elements.csv`. A façade part should
  likewise be allowed only if the manufacturer actually sells that size in that
  finish — which is what makes "fabricable by construction" a claim rather than
  a hope.
- **Degrade loudly, not silently.** The loader returns `None` and falls back to
  a built-in palette when the catalogue is missing. `facadekit.catalogue` takes
  the opposite line and refuses to load a bad catalogue at all, collecting every
  problem in one pass — a wrong catalogue silently accepted would corrupt every
  number in the thesis.

`facadekit/catalogue.py` is written fresh against the FaçadeKit schema and owes
this code the third point by inversion and the first two directly.

## Not copied

The split-and-merge legolizer, TRELLIS, the voxeliser, the gravity/stability
check and the LDraw exporter. Per the proposal: *read it, do not port it* — its
job is done by CP-SAT with real objectives, and façades are elevations, so
there is no mesh and no gravity.
