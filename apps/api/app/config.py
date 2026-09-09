"""Settings, all from the environment. No secret ever has a default."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _csv_env(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


@dataclass
class Settings:
    # --- where things live -------------------------------------------------
    storage_backend: str = field(default_factory=lambda: os.environ.get("STORAGE_BACKEND", "local"))
    storage_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("STORAGE_DIR", REPO_ROOT / "storage"))
    )
    catalogues_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("CATALOGUES_DIR", REPO_ROOT / "data" / "catalogues")
        )
    )
    masks_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MASKS_DIR", REPO_ROOT / "data" / "samples" / "masks")
        )
    )

    # --- S3 / Cloudflare R2: present but unconfigured until the bucket exists
    s3_bucket: str = field(default_factory=lambda: os.environ.get("S3_BUCKET", ""))
    s3_endpoint: str = field(default_factory=lambda: os.environ.get("S3_ENDPOINT", ""))
    s3_region: str = field(default_factory=lambda: os.environ.get("S3_REGION", "auto"))

    # --- pipeline defaults -------------------------------------------------
    default_catalogue: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_CATALOGUE", "demo.json")
    )
    facade_width_mm: float = field(
        default_factory=lambda: float(os.environ.get("FACADE_WIDTH_MM", "12000"))
    )
    grid_mm: float = field(default_factory=lambda: float(os.environ.get("GRID_MM", "300")))

    # --- generation --------------------------------------------------------
    # "cached" costs nothing and needs no key. Changing this is a spending
    # decision, so it is an explicit deployment step, never a code default.
    generate_backend: str = field(
        default_factory=lambda: os.environ.get("FACADEKIT_GENERATE", "cached")
    )

    # --- http --------------------------------------------------------------
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env("CORS_ORIGINS", "http://localhost:5173")
    )
    max_jobs: int = field(default_factory=lambda: int(os.environ.get("MAX_JOBS", "200")))

    @property
    def catalogue_path(self) -> Path:
        return self.catalogues_dir / self.default_catalogue


settings = Settings()
