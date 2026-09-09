# facadekit-api

FastAPI wrapper around `facadekit.pipeline`. Submit-and-poll, never a blocking
generate call.

| Route | Does |
|---|---|
| `POST /jobs` | submit a brief (or a sample mask), returns a job id immediately |
| `GET /jobs/{id}` | status, metrics, warnings, file list |
| `GET /jobs/{id}/files/{name}` | `schedule.csv`, `nesting.dxf`, `panel-map.png`, `proposal.png`, `run.json` |
| `GET /catalogues` | catalogues on disk, each validated |
| `GET /masks` | pre-computed sample masks |
| `GET /healthz` | liveness + which backends are configured |

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

Config is entirely environment variables — see `.env.example`. No secret has a
default, and the generate backend defaults to `cached`, which cannot spend money.

The job runner keeps jobs in a dict in one process. That is correct for a
single-instance demo and wrong for two instances; swapping it for a real queue
does not move the API surface.
