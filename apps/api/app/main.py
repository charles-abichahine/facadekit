"""FacadeKit HTTP API.

    POST /jobs                  submit a brief, get a job id back immediately
    GET  /jobs/{id}             poll status, metrics and the file list
    GET  /jobs/{id}/files/{f}   download schedule.csv / nesting.dxf / panel-map.png
    GET  /catalogues            what can be legalised against
    GET  /healthz               liveness, plus which backends are configured

Submit-and-poll, never a blocking generate call.
"""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.jobs import JobRunner
from facadekit import __version__ as core_version
from facadekit.catalogue import CatalogueError, load_catalogue

app = FastAPI(
    title="FacadeKit API",
    version=core_version,
    description="Legalise a generated facade against a real manufacturer's kit of parts.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

runner = JobRunner(settings)

ALLOWED_FILES = {"schedule.csv", "nesting.dxf", "panel-map.png", "proposal.png", "run.json"}
"""An allowlist, not a path check. Job ids are ours but filenames come from the
URL, and there is no reason for this endpoint to serve anything else."""


class JobRequest(BaseModel):
    brief: str = Field("", max_length=2000)
    catalogue: str | None = Field(None, description="Catalogue filename, e.g. demo.json")
    mask: str | None = Field(None, description="Sample mask filename; skips generation")
    legaliser: str = Field("nearest", description="nearest (baseline) | cp-sat (stub)")
    tolerance_mm: float | None = None
    seed: int = 0


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "version": core_version,
        "generate_backend": settings.generate_backend,
        "storage_backend": runner.storage.backend,
        "default_catalogue": settings.default_catalogue,
    }


@app.get("/catalogues")
def catalogues() -> dict[str, Any]:
    found = []
    for path in sorted(settings.catalogues_dir.glob("*.json")):
        try:
            cat = load_catalogue(path)
        except CatalogueError as e:
            found.append({"file": path.name, "ok": False, "problems": e.problems})
            continue
        found.append(
            {
                "file": path.name,
                "ok": True,
                "system": cat.system,
                "parts": len(cat),
                "kinds": list(cat.kinds),
                "sheet": {"w": cat.sheet.w, "h": cat.sheet.h},
            }
        )
    return {"catalogues": found, "default": settings.default_catalogue}


@app.get("/masks")
def masks() -> dict[str, Any]:
    """The pre-computed sample masks, for running the solver with no generation."""
    return {"masks": sorted(p.name for p in settings.masks_dir.glob("*.png"))}


@app.post("/jobs", status_code=202)
def create_job(req: JobRequest) -> dict[str, Any]:
    if not req.brief.strip() and not req.mask:
        raise HTTPException(422, "give a brief to generate from, or a mask to segment")
    job = runner.submit(
        brief=req.brief.strip(),
        catalogue=req.catalogue,
        mask=req.mask,
        legaliser=req.legaliser,
        tolerance_mm=req.tolerance_mm,
        seed=req.seed,
    )
    return job.public()


@app.get("/jobs")
def list_jobs(limit: int = 20) -> dict[str, Any]:
    return {"jobs": [j.public() for j in runner.recent(min(limit, 100))]}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    return job.public()


@app.get("/jobs/{job_id}/files/{filename}")
def get_job_file(job_id: str, filename: str) -> Response:
    if filename not in ALLOWED_FILES:
        raise HTTPException(404, f"{filename} is not a job output")
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id}")
    if job.status != "done":
        raise HTTPException(409, f"job {job_id} is {job.status}")

    try:
        data = runner.storage.open(f"{job_id}/{filename}")
    except FileNotFoundError:
        raise HTTPException(404, f"{filename} was not produced by job {job_id}") from None

    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if filename.endswith(".dxf"):
        media_type = "image/vnd.dxf"
    headers = {}
    if filename.endswith((".csv", ".dxf")):
        headers["Content-Disposition"] = f'attachment; filename="{job_id}-{filename}"'
    return Response(content=data, media_type=media_type, headers=headers)
