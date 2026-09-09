"""fal.ai hosted FLUX + facade LoRA.

Costs money per image. Never the default: it is reached only when
FACADEKIT_GENERATE=fal is set explicitly, and it refuses to run without a key
rather than silently falling back, so a spend can never happen by accident.

Setup (all of it done by Charles, none of it by the code):
    1. create an account at fal.ai and add credit
    2. put the key in apps/api/.env as  FAL_KEY=...     (.env is gitignored)
    3. upload the trained facade LoRA and put its URL in FAL_LORA_URL
See docs/deploy.md.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from facadekit_generate.base import GenerationError, GeneratorResult

DEFAULT_MODEL = "fal-ai/flux-lora"
QUEUE_HOST = "https://queue.fal.run"
POLL_INTERVAL_S = 2.0
DEFAULT_TIMEOUT_S = 180.0


class FalGenerator:
    name = "fal"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        lora_url: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.api_key = api_key or os.environ.get("FAL_KEY", "")
        self.model = model or os.environ.get("FAL_MODEL", DEFAULT_MODEL)
        self.lora_url = lora_url or os.environ.get("FAL_LORA_URL", "")
        self.timeout_s = timeout_s

    def _request(self, url: str, payload: dict | None = None) -> dict:
        if not self.api_key:
            raise GenerationError(
                "FAL_KEY is not set. Add it to apps/api/.env (see docs/deploy.md) or "
                "use FACADEKIT_GENERATE=cached, which needs no key and costs nothing."
            )
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Key {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:400]
            raise GenerationError(f"fal.ai returned {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise GenerationError(f"could not reach fal.ai: {e.reason}") from e

    def generate(self, prompt: str, seed: int = 0) -> GeneratorResult:
        payload: dict = {"prompt": prompt, "seed": seed, "image_size": "landscape_4_3"}
        if self.lora_url:
            payload["loras"] = [{"path": self.lora_url, "scale": 0.9}]

        submitted = self._request(f"{QUEUE_HOST}/{self.model}", payload)
        status_url = submitted.get("status_url")
        response_url = submitted.get("response_url")
        if not status_url or not response_url:
            raise GenerationError(f"unexpected fal.ai submit response: {submitted}")

        deadline = time.monotonic() + self.timeout_s
        while True:
            status = self._request(status_url)
            state = status.get("status")
            if state == "COMPLETED":
                break
            if state in ("FAILED", "CANCELLED"):
                raise GenerationError(f"fal.ai job {state.lower()}: {status}")
            if time.monotonic() > deadline:
                raise GenerationError(f"fal.ai job timed out after {self.timeout_s:.0f}s")
            time.sleep(POLL_INTERVAL_S)

        result = self._request(response_url)
        images = result.get("images") or []
        if not images or not images[0].get("url"):
            raise GenerationError(f"fal.ai returned no image: {result}")

        image_url = images[0]["url"]
        try:
            with urllib.request.urlopen(image_url, timeout=60) as r:
                png = r.read()
        except urllib.error.URLError as e:
            raise GenerationError(f"could not download the generated image: {e.reason}") from e

        return GeneratorResult(
            png=png,
            backend=self.name,
            prompt=prompt,
            seed=seed,
            provenance={
                "model": self.model,
                "lora": self.lora_url or "(none)",
                "image_url": image_url,
            },
        )
