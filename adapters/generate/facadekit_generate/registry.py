"""Pick a generator by name, defaulting to the one that cannot cost money."""

from __future__ import annotations

import os

from facadekit_generate.base import Generator
from facadekit_generate.cached import CachedGenerator
from facadekit_generate.comfyui import ComfyUIGenerator
from facadekit_generate.fal import FalGenerator

GENERATORS: dict[str, type] = {
    "cached": CachedGenerator,
    "fal": FalGenerator,
    "comfyui": ComfyUIGenerator,
}

DEFAULT = "cached"


def get_generator(name: str | None = None, **kwargs) -> Generator:
    """Resolve a generator: explicit name > FACADEKIT_GENERATE env > cached."""
    chosen = name or os.environ.get("FACADEKIT_GENERATE") or DEFAULT
    try:
        cls = GENERATORS[chosen]
    except KeyError:
        raise KeyError(
            f"unknown generate backend {chosen!r}; available: {sorted(GENERATORS)}"
        ) from None
    return cls(**kwargs)
