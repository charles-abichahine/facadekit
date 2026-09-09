# facadekit-generate

Box 1 of the pipeline — brief → façade image — behind one seam, so the rest of
FacadeKit never learns where the picture came from.

```python
from facadekit_generate import get_generator
result = get_generator().generate("a six-storey office façade", seed=7)
result.png              # PNG bytes
result.is_real_generation  # False for cached placeholders
```

| Backend | `FACADEKIT_GENERATE` | Needs | Costs |
|---|---|---|---|
| Cached | `cached` *(default)* | a directory of PNGs | nothing |
| fal.ai | `fal` | `FAL_KEY`, optional `FAL_LORA_URL` | per image |
| ComfyUI | `comfyui` | a local ComfyUI + `COMFYUI_WORKFLOW` | a GPU |

**The default cannot spend money.** `fal` is reached only when
`FACADEKIT_GENERATE=fal` is set explicitly, and it refuses to run without a key
rather than falling back silently. Keys go in `apps/api/.env`, which is
gitignored — see `docs/deploy.md`.

Stdlib only: every backend talks HTTP over `urllib`, so the deployed CPU box
does not grow a dependency for a call it will usually not make.

The ComfyUI client's submit-and-poll shape is adapted from LegoArch
(`backend/app/comfy_client.py`, Charles Abi Chahine and Emilie El Chidiac).
