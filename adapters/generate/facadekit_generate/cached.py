"""Serve a pre-made image from storage. The default, and the safety net.

The deployed demo runs on this: no GPU, no API key, no per-image cost, and it
cannot fail in front of a jury. The cost is that it cannot answer a brief
nobody anticipated -- which is exactly the trade-off the explainer records.

Selection is deterministic: the same (prompt, seed) always returns the same
image, so a cached run is still reproducible and still a valid dataset row
(flagged `is_real_generation == False`).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from facadekit_generate.base import GenerationError, GeneratorResult

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "samples" / "facades"


class CachedGenerator:
    name = "cached"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.environ.get("FACADEKIT_CACHE_DIR") or DEFAULT_ROOT)

    def available(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(p for p in self.root.iterdir() if p.suffix.lower() == ".png")

    def generate(self, prompt: str, seed: int = 0) -> GeneratorResult:
        images = self.available()
        if not images:
            raise GenerationError(
                f"no cached images in {self.root}. Run `python data/samples/make_samples.py`, "
                "or point FACADEKIT_CACHE_DIR at a directory of PNGs."
            )

        digest = hashlib.sha256(f"{prompt}|{seed}".encode()).digest()
        chosen = images[int.from_bytes(digest[:8], "big") % len(images)]

        return GeneratorResult(
            png=chosen.read_bytes(),
            backend=self.name,
            prompt=prompt,
            seed=seed,
            provenance={
                "file": chosen.name,
                "root": str(self.root),
                "note": "pre-made placeholder; not generated for this brief",
            },
        )
