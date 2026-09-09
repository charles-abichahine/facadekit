"""Brief -> facade image.

One interface, three backends:

    cached    serve a pre-made image from storage       (default; no GPU, no spend)
    fal       fal.ai hosted FLUX + facade LoRA          (needs FAL_KEY)
    comfyui   a local ComfyUI running your own graph    (Charles's PC only)

Box 1 of the pipeline is deliberately the *least* interesting part of the
thesis (the proposal says so outright: the generator is commodity), so it is
isolated behind this seam and defaults to the backend that costs nothing.

Select with the FACADEKIT_GENERATE environment variable, or pass a name to
`get_generator`.
"""

from facadekit_generate.base import GenerationError, Generator, GeneratorResult
from facadekit_generate.cached import CachedGenerator
from facadekit_generate.comfyui import ComfyUIGenerator
from facadekit_generate.fal import FalGenerator
from facadekit_generate.registry import GENERATORS, get_generator

__all__ = [
    "GenerationError",
    "Generator",
    "GeneratorResult",
    "CachedGenerator",
    "ComfyUIGenerator",
    "FalGenerator",
    "GENERATORS",
    "get_generator",
]
