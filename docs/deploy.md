# Deploying FacadeKit

Everything needed to put the demo back on the internet alone: every account,
every key, every command, in order.

**Written as we went, September 2026.** Sections marked ⏳ were not done in that
session and are written from the provider's documented flow — expect small
differences in wording.

---

## 0. The shape of it

```
    browser
       │
       ▼
  ┌──────────┐  static, free            ┌──────────────┐  CPU, small
  │  Vercel  │────── /jobs, polling ───▶│    Fly.io    │
  │ apps/web │◀───── CSV DXF PNG ───────│   apps/api   │
  └──────────┘                          └──────┬───────┘
                                               │ only when FACADEKIT_GENERATE=fal
                                               ▼
                                        ┌─────────────┐  GPU, per image
                                        │   fal.ai    │  ⏳ not wired up yet
                                        └─────────────┘
```

The demo never touches Charles's PC. The backend does all the thesis work
(segmentation, legalising, nesting, export) on a cheap CPU host. The one GPU
step is bought per image from a hosted endpoint — and by default is not bought
at all, because the `cached` generator serves pre-made images.

**Default costs nothing.** `FACADEKIT_GENERATE=cached` needs no key and makes no
paid call. Setting it to `fal` is a spending decision and an explicit deploy step.

---

## 1. Accounts

| # | Account | Needed for | Cost | Status |
|---|---|---|---|---|
| 1 | **GitHub** | the repo, CI | free | done — `charles-abichahine` |
| 2 | **Vercel** | frontend hosting | free (Hobby) | ⏳ |
| 3 | **Fly.io** | backend hosting | free allowance; card on file | ⏳ |
| 4 | **fal.ai** | live FLUX generation | per image | ⏳ optional, later |
| 5 | **Cloudflare** | R2 bucket for run artefacts | free tier | ⏳ optional, later |

Sign up for 2 and 3 **with the GitHub account** — it makes both CLIs' login
flows one click, and Vercel can then see the repo directly.

Charles creates every account and pastes every key himself. No key is ever
typed into a chat; all of them live in gitignored `.env` files.

---

## 2. Backend → Fly.io

### 2.1 One-time

```bash
flyctl auth login
```

Fly wants a card on file even for the free allowance. The smallest machine
(`shared-cpu-1x`, 256 MB) is enough for the baseline solver, but **not** enough
to hold SAM weights — see §5.

From the repo root:

```bash
flyctl launch --no-deploy --dockerfile apps/api/Dockerfile --name facadekit-api
```

Answer: **no** to a Postgres database, **no** to Redis, and pick a region near
Barcelona (`cdg` Paris or `mad` Madrid). It writes `fly.toml`.

Check `fly.toml` says `internal_port = 8000` and add a volume only if you want
run artefacts to survive restarts (not needed while the demo is cached-only —
jobs are ephemeral by design).

### 2.2 Configuration

Non-secret settings go in `fly.toml` under `[env]`:

```toml
[env]
  FACADEKIT_GENERATE = "cached"
  STORAGE_BACKEND = "local"
  CORS_ORIGINS = "https://facadekit.vercel.app"
```

`CORS_ORIGINS` must be the **exact** Vercel URL, scheme included, no trailing
slash. Getting this wrong is the single most likely reason the deployed site
loads but every request fails; the browser console will say so explicitly.

Secrets never go in `fly.toml` (it is committed). They go in Fly's own store:

```bash
flyctl secrets set FAL_KEY=... FAL_LORA_URL=...
```

Only needed once §4 is live.

### 2.3 Deploy

```bash
flyctl deploy
```

Fly builds the image on its own remote builder, so local Docker is not
required. Verify:

```bash
curl https://facadekit-api.fly.dev/healthz
```

Expect `{"ok":true,...,"generate_backend":"cached","storage_backend":"local"}`.

### 2.4 Sleeping machines

Fly stops idle machines and cold-starts them on the next request, which shows up
as one slow first load. That is the right trade for a demo. If a jury demo must
be instant, set `min_machines_running = 1` in `fly.toml` shortly before, and put
it back afterwards — it bills continuously.

---

## 3. Frontend → Vercel

### 3.1 Import

At <https://vercel.com/new>, import the `facadekit` repo, then set:

| Field | Value |
|---|---|
| Framework preset | Vite |
| **Root directory** | `apps/web` |
| Build command | `npm run build` (default) |
| Output directory | `dist` (default) |

The root directory is the setting that matters: this is a monorepo and the
default (repo root) has no `package.json` to build.

### 3.2 Environment variable

In **Settings → Environment Variables**, for all environments:

```
VITE_API_URL = https://facadekit-api.fly.dev
```

No trailing slash. Vite inlines `VITE_*` at **build** time, so after changing
it you must **redeploy** — changing the variable alone does nothing to the site
already built.

### 3.3 Deploy and verify

Push to `main`; Vercel builds automatically. Then, on the live URL:

1. the page loads and the catalogue dropdown fills in (that alone proves
   `/catalogues` reached the API and CORS is right);
2. click **Legalise**;
3. the job goes `queued → running → done` and a panel map appears;
4. all three download buttons return files.

If the dropdown is empty, it is CORS or `VITE_API_URL` — check the browser
console, then §2.2.

---

## 4. ⏳ Live generation → fal.ai

Optional. Skip until there is a trained façade LoRA; the demo works without it.

1. Create an account at <https://fal.ai> and add credit.
2. Copy the key from the dashboard.
3. Upload the trained LoRA and copy its URL.
4. Locally: copy `apps/api/.env.example` to `apps/api/.env` and fill in
   `FAL_KEY` and `FAL_LORA_URL`. **`.env` is gitignored — check `git status`
   shows nothing before committing.**
5. On Fly: `flyctl secrets set FAL_KEY=... FAL_LORA_URL=...`
6. Flip the backend: `flyctl secrets set FACADEKIT_GENERATE=fal`

Costs money per image from step 6 onwards. To stop spending, set it back to
`cached` — the site keeps working.

**Open decision first (see `tools/comfyui/README.md`):** fal.ai hosts
FLUX.1-dev, not the FLUX.2 Klein the LegoArch graphs use. Training the façade
LoRA on fal's trainer means it will not load in the local ComfyUI setup, and
vice versa. Decide which side matters before training anything.

---

## 5. ⏳ SAM on the deployed box

The API image ships **without** torch or SAM — they would add gigabytes to a
256 MB machine.

The deployed demo therefore takes the documented fallback: the `cached`
generator serves a pre-made image and the pipeline segments that image's
**pre-computed mask** instead. This is not hidden — it appears as a warning in
`run.json` and on the page:

> no SAM checkpoint; segmented the pre-computed mask banded.png instead of the
> image itself

To run SAM for real, either scale the Fly machine up (`flyctl scale vm
shared-cpu-2x --memory 2048`, which leaves the free allowance and bills), bake
a checkpoint into the image and set `FACADEKIT_SAM_CHECKPOINT`, or buy
segmentation from the same hosted provider as generation. None of this is on the
October critical path.

---

## 6. ⏳ Storage → Cloudflare R2

Run artefacts currently live on the API machine's disk and vanish when it
restarts. Fine for a demo; wrong for a dataset of hundreds of runs.

When the dataset matters:

1. Cloudflare dashboard → **R2** → create a bucket, e.g. `facadekit-runs`.
2. Create an R2 API token (Object Read & Write) and note the access key id,
   secret, and the account-specific S3 endpoint.
3. `flyctl secrets set S3_BUCKET=facadekit-runs S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... STORAGE_BACKEND=s3`
4. Rebuild the API image with the `s3` extra so `boto3` is present.

The code path already exists (`apps/api/app/storage.py`); it refuses to start
with a clear error while `S3_BUCKET` is empty, which is why it is safe to leave
unconfigured.

---

## 7. Redeploy checklist

| Change | What to do |
|---|---|
| backend code | `flyctl deploy` |
| frontend code | push to `main`; Vercel builds |
| `VITE_API_URL` | change it, then **redeploy** — build-time only |
| a secret | `flyctl secrets set ...` (restarts the app) |
| new Vercel URL | update `CORS_ORIGINS` in `fly.toml`, `flyctl deploy` |

## 8. When it breaks

| Symptom | Cause |
|---|---|
| dropdown empty, console shows a CORS error | `CORS_ORIGINS` ≠ the exact Vercel URL |
| every request 404s at `/api/...` | `VITE_API_URL` unset in the Vercel build |
| first request very slow, then fine | Fly cold start (§2.4) |
| job errors with "stub" | `legaliser: cp-sat` was requested; it is not written |
| job warns about a pre-computed mask | expected on the deployed box (§5) |
| `/healthz` says `generate_backend: fal` unexpectedly | a secret is set; you are spending per image |
