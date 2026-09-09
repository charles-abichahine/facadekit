"""API round-trip: submit a job, poll it, download the three files."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TIMEOUT_S = 60.0


def _wait(job_id: str) -> dict:
    """Poll until the job leaves the queue. This is what the frontend does."""
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        body = client.get(f"/jobs/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.1)
    pytest.fail(f"job {job_id} did not finish within {TIMEOUT_S:.0f}s")


def test_healthz_reports_its_backends():
    body = client.get("/healthz").json()
    assert body["ok"] is True
    # The deployed default must never be a backend that can spend money.
    assert body["generate_backend"] == "cached"


def test_catalogues_are_listed_and_valid():
    body = client.get("/catalogues").json()
    assert body["catalogues"], "no catalogues found on disk"
    for cat in body["catalogues"]:
        assert cat["ok"], f"{cat['file']} is invalid: {cat.get('problems')}"


def test_masks_are_listed():
    assert client.get("/masks").json()["masks"]


def test_job_round_trip_from_a_mask():
    submitted = client.post("/jobs", json={"mask": "banded.png", "brief": "test"})
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]

    body = _wait(job_id)
    assert body["status"] == "done", body.get("error")
    assert body["panels"] > 0
    assert 0 < body["metrics"]["legalised_fraction"] <= 1
    assert set(body["files"]) >= {"schedule.csv", "nesting.dxf", "panel-map.png"}

    # ezdxf writes CRLF on Windows and LF on Linux, so normalise the first few
    # bytes before matching rather than pinning the test to one platform.
    for name, prefix in [
        ("schedule.csv", b"panel_id,"),
        ("nesting.dxf", b"  0\nSECTION"),
        ("panel-map.png", b"\x89PNG"),
    ]:
        r = client.get(f"/jobs/{job_id}/files/{name}")
        assert r.status_code == 200, name
        head = r.content[:64].replace(b"\r\n", b"\n")
        assert head.startswith(prefix), f"{name} does not look like a {name.split('.')[-1]}"


def test_job_from_a_brief_uses_the_cached_generator():
    submitted = client.post("/jobs", json={"brief": "a six-storey office facade"})
    body = _wait(submitted.json()["id"])
    assert body["status"] == "done", body.get("error")
    assert body["generator"] == "cached"
    # The cached path cannot segment the image itself, and must say so.
    assert any("pre-computed mask" in w for w in body["warnings"])


def test_empty_request_is_rejected():
    assert client.post("/jobs", json={"brief": "   "}).status_code == 422


def test_unknown_job_is_404():
    assert client.get("/jobs/deadbeef").status_code == 404


def test_arbitrary_files_are_not_served():
    job_id = client.post("/jobs", json={"mask": "banded.png"}).json()["id"]
    _wait(job_id)
    for name in ("../../.env", "secrets.txt", "..%2F.env"):
        assert client.get(f"/jobs/{job_id}/files/{name}").status_code == 404


def test_cp_sat_stub_surfaces_as_a_job_error():
    submitted = client.post("/jobs", json={"mask": "banded.png", "legaliser": "cp-sat"})
    body = _wait(submitted.json()["id"])
    assert body["status"] == "error"
    assert "stub" in body["error"]
