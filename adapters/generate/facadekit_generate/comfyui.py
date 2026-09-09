"""A local ComfyUI running your own graph. Charles's PC only.

Submits an API-format workflow JSON, overrides the prompt/seed nodes by id,
polls /history until the run finishes, then downloads the output image.

Adapted from LegoArch's `backend/app/comfy_client.py` (Charles Abi Chahine and
Emilie El Chidiac, IAAC MaCAD 2025/26) -- the submit-and-poll shape and the
"override nodes by id" approach are theirs. The graphs themselves live in
tools/comfyui/.

This backend is never used by the deployed site: the whole point of the
deployment diagram in the explainer is that the demo does not touch this PC.
"""

from __future__ import annotations

import copy
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from facadekit_generate.base import GenerationError, GeneratorResult

DEFAULT_URL = "http://127.0.0.1:8188"
POLL_INTERVAL_S = 1.0
DEFAULT_TIMEOUT_S = 300.0


class ComfyUIGenerator:
    name = "comfyui"

    def __init__(
        self,
        url: str | None = None,
        workflow: str | Path | None = None,
        prompt_node: str | None = None,
        seed_node: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.url = (url or os.environ.get("COMFYUI_URL") or DEFAULT_URL).rstrip("/")
        self.workflow_path = Path(
            workflow or os.environ.get("COMFYUI_WORKFLOW") or ""
        )
        self.prompt_node = prompt_node or os.environ.get("COMFYUI_PROMPT_NODE", "")
        self.seed_node = seed_node or os.environ.get("COMFYUI_SEED_NODE", "")
        self.timeout_s = timeout_s

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.URLError as e:
            raise GenerationError(
                f"could not reach ComfyUI at {self.url}: {e}. Is it running?"
            ) from e

    def _get(self, path: str) -> dict:
        try:
            with urllib.request.urlopen(f"{self.url}{path}", timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.URLError as e:
            raise GenerationError(f"could not reach ComfyUI at {self.url}: {e}") from e

    def _load_workflow(self) -> dict:
        if not self.workflow_path or not self.workflow_path.is_file():
            raise GenerationError(
                "COMFYUI_WORKFLOW must point at an API-format workflow JSON "
                "(see tools/comfyui/)."
            )
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))

    def generate(self, prompt: str, seed: int = 0) -> GeneratorResult:
        graph = copy.deepcopy(self._load_workflow())

        if self.prompt_node:
            if self.prompt_node not in graph:
                raise GenerationError(
                    f"COMFYUI_PROMPT_NODE={self.prompt_node!r} is not a node in "
                    f"{self.workflow_path.name}"
                )
            graph[self.prompt_node].setdefault("inputs", {})["text"] = prompt
        if self.seed_node and self.seed_node in graph:
            graph[self.seed_node].setdefault("inputs", {})["seed"] = seed

        submitted = self._post("/prompt", {"prompt": graph})
        prompt_id = submitted.get("prompt_id")
        if not prompt_id:
            raise GenerationError(f"ComfyUI rejected the workflow: {submitted}")

        deadline = time.monotonic() + self.timeout_s
        while True:
            history = self._get(f"/history/{prompt_id}")
            if prompt_id in history:
                break
            if time.monotonic() > deadline:
                raise GenerationError(f"ComfyUI run timed out after {self.timeout_s:.0f}s")
            time.sleep(POLL_INTERVAL_S)

        outputs = history[prompt_id].get("outputs", {})
        for node_output in outputs.values():
            for image in node_output.get("images", []):
                query = urllib.parse.urlencode(
                    {
                        "filename": image["filename"],
                        "subfolder": image.get("subfolder", ""),
                        "type": image.get("type", "output"),
                    }
                )
                with urllib.request.urlopen(f"{self.url}/view?{query}", timeout=60) as r:
                    png = r.read()
                return GeneratorResult(
                    png=png,
                    backend=self.name,
                    prompt=prompt,
                    seed=seed,
                    provenance={
                        "workflow": self.workflow_path.name,
                        "prompt_id": str(prompt_id),
                        "filename": image["filename"],
                    },
                )

        raise GenerationError(f"ComfyUI run {prompt_id} produced no images")
