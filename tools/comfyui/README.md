# ComfyUI workflows

Copied from **LegoArch** (`hi-em/genai-legoarch`, Charles Abi Chahine and
Emilie El Chidiac, IAAC MaCAD 2025/26) and unchanged so far. They still
generate LEGO, not façades — retargeting them is box 1 of the thesis.

| File | What it is |
|---|---|
| `flux_txt2img.api.json` | API-format FLUX.2 + LoRA text-to-image graph the backend submits |
| `flux_img2img.api.json` | API-format FLUX.2 + LoRA image-to-image graph |
| `FLUX.2_LoRA.source.json` | the editable ComfyUI graph the txt2img API graph was exported from |
| `FLUX.2_img2img_LoRA.source.json` | the editable image-to-image graph |

Deliberately **not** copied: the TRELLIS image→3D graph. FaçadeKit has no 3D
stage — a façade is an elevation, so the pipeline stays 2D.

## Wiring one up locally

`facadekit_generate`'s ComfyUI backend overrides nodes by id:

```bash
FACADEKIT_GENERATE=comfyui
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW=tools/comfyui/flux_txt2img.api.json
COMFYUI_PROMPT_NODE=683      # PrimitiveStringMultiline -> the prompt text
COMFYUI_SEED_NODE=678:662    # RandomNoise
```

Node `684` is a `StringConcatenate` that prepends the LoRA trigger word
(`legoarch` today; it becomes the façade trigger once the new LoRA is trained).
Confirm the ids after any re-export — ComfyUI renumbers freely.

This backend is **never** used by the deployed site. The whole point of the
deployment design is that the demo does not touch Charles's PC.

## The missing piece: no LoRA training config

LegoArch has **no trainer configuration to copy**. `references/legoarch.safetensors`
was trained outside the repo on the 40 product photographs in
`comfyui/legoarch-dataset/`; only the graphs that *use* the adapter were
committed. So the façade LoRA needs a training config written from scratch.

That is a real gap, not an oversight to work around later. Two consequences
worth deciding early:

- If the façade LoRA is trained on **fal.ai's own trainer**, the base model is
  whatever they host (FLUX.1-dev), not the FLUX.2 Klein these graphs use — the
  adapter will not be portable back to this ComfyUI setup.
- If it is trained **locally against FLUX.2 Klein**, these graphs keep working
  unchanged, but the hosted-endpoint route for the live demo closes.

The explainer already reaches the same fork ("retrain on the provider's trainer
rather than porting the FLUX.2 Klein one"). Whichever way it goes, record the
trainer, base model, dataset and hyperparameters *here* so the façade LoRA is
reproducible in a way `legoarch.safetensors` is not.
