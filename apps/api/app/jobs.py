"""In-process job runner.

Generation takes tens of seconds, so the frontend submits and polls rather than
blocking on one request -- the lesson LegoArch already paid for.

Deliberately small: one worker thread, jobs in a dict, results copied into
storage. It is enough for a single-instance demo and it is the wrong thing the
moment there are two instances, because the dict is per-process. Replacing it
with a real queue (Redis/RQ, or Fly's own) is a deployment change; the API
surface does not move.
"""

from __future__ import annotations

import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.config import Settings, settings
from app.storage import Storage, get_storage
from facadekit.pipeline import PipelineError, RunConfig
from facadekit.pipeline import run as run_pipeline

Status = Literal["queued", "running", "done", "error"]


@dataclass
class Job:
    id: str
    brief: str
    status: Status = "queued"
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    finished_at: str | None = None
    error: str | None = None
    manifest: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "brief": self.brief,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "metrics": self.manifest.get("metrics", {}),
            "method": self.manifest.get("method"),
            "catalogue": self.manifest.get("catalogue"),
            "generator": self.manifest.get("generator"),
            "warnings": self.manifest.get("warnings", []),
            "panels": self.manifest.get("panels"),
            "files": self.files,
        }


class JobRunner:
    def __init__(self, config: Settings | None = None, storage: Storage | None = None) -> None:
        self.config = config or settings
        self.storage = storage or get_storage(self.config)
        # One worker: SAM and CP-SAT are both happier not competing for a
        # small instance's CPU, and the demo runs one image at a time.
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="facadekit")
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    # -- queries -----------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self, limit: int = 20) -> list[Job]:
        with self._lock:
            return [self._jobs[i] for i in reversed(self._order[-limit:])]

    # -- submission --------------------------------------------------------
    def submit(
        self,
        brief: str,
        catalogue: str | None = None,
        mask: str | None = None,
        legaliser: str = "nearest",
        tolerance_mm: float | None = None,
        seed: int = 0,
    ) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], brief=brief)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            # Bounded memory: the oldest job's record goes, its files stay.
            while len(self._order) > self.config.max_jobs:
                self._jobs.pop(self._order.pop(0), None)

        self._pool.submit(
            self._run, job, catalogue, mask, legaliser, tolerance_mm, seed
        )
        return job

    # -- the work ----------------------------------------------------------
    def _generator(self):
        try:
            from facadekit_generate import get_generator
        except ImportError:
            return None
        return get_generator(self.config.generate_backend)

    def _run(
        self,
        job: Job,
        catalogue: str | None,
        mask: str | None,
        legaliser: str,
        tolerance_mm: float | None,
        seed: int,
    ) -> None:
        job.status = "running"
        try:
            catalogue_path = self.config.catalogues_dir / (
                catalogue or self.config.default_catalogue
            )
            mask_path = (self.config.masks_dir / mask) if mask else None

            with tempfile.TemporaryDirectory(prefix=f"facadekit-{job.id}-") as tmp:
                config = RunConfig(
                    brief=job.brief,
                    catalogue_path=catalogue_path,
                    out_dir=tmp,
                    mask_path=mask_path,
                    masks_dir=self.config.masks_dir,
                    facade_width_mm=self.config.facade_width_mm,
                    grid_mm=self.config.grid_mm,
                    legaliser=legaliser,
                    seed=seed,
                    **({"tolerance_mm": tolerance_mm} if tolerance_mm is not None else {}),
                )
                result = run_pipeline(config, self._generator() if mask_path is None else None)

                self.storage.put_dir(job.id, Path(tmp))
                job.files = sorted(p.name for p in Path(tmp).iterdir() if p.is_file())

            job.manifest = result.manifest
            job.status = "done"
        except (PipelineError, NotImplementedError, ValueError) as e:
            job.status = "error"
            job.error = str(e)
        except Exception as e:  # unexpected: still must not take the worker down
            job.status = "error"
            job.error = f"{type(e).__name__}: {e}"
        finally:
            job.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
