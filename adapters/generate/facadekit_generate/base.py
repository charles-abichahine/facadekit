"""The one interface every generator satisfies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class GenerationError(RuntimeError):
    """A backend could not produce an image. Message is shown to the user."""


@dataclass(frozen=True)
class GeneratorResult:
    """PNG bytes plus enough provenance to reproduce the run.

    `provenance` is what makes a run a dataset row rather than a picture: which
    backend, which model, which seed. Every experiment arm depends on being
    able to say where an image came from.
    """

    png: bytes
    backend: str
    prompt: str
    seed: int
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def is_real_generation(self) -> bool:
        """False for cached/placeholder images. Never report a cached run as generated."""
        return self.backend not in ("cached",)


@runtime_checkable
class Generator(Protocol):
    name: str

    def generate(self, prompt: str, seed: int = 0) -> GeneratorResult: ...
