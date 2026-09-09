# FacadeKit API. Build context is the repo root, not apps/api -- the image needs
# packages/core and adapters/generate too.
#
#   docker build -f apps/api/Dockerfile -t facadekit-api .
#
# Deliberately CPU-only and deliberately without torch/SAM: the deployed box
# runs the solver and serves files, and buys the one GPU step per image from a
# hosted endpoint (or serves a cached image). See docs/deploy.md.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Manifests first, so a code-only change does not re-resolve dependencies.
COPY packages/core/pyproject.toml packages/core/README.md ./packages/core/
COPY adapters/generate/pyproject.toml adapters/generate/README.md ./adapters/generate/
COPY apps/api/pyproject.toml apps/api/README.md ./apps/api/

COPY packages/core/facadekit ./packages/core/facadekit
COPY adapters/generate/facadekit_generate ./adapters/generate/facadekit_generate
COPY apps/api/app ./apps/api/app

RUN pip install --no-cache-dir \
      ./packages/core \
      ./adapters/generate \
      ./apps/api

# The demo catalogue, the sample masks and the placeholder facades: without
# these the cached generator has nothing to serve.
COPY data ./data

# Run as a non-root user; storage is the only writable path it needs.
RUN useradd --create-home --uid 10001 facadekit \
 && mkdir -p /app/storage \
 && chown -R facadekit:facadekit /app/storage
USER facadekit

ENV STORAGE_DIR=/app/storage \
    CATALOGUES_DIR=/app/data/catalogues \
    MASKS_DIR=/app/data/samples/masks \
    FACADEKIT_CACHE_DIR=/app/data/samples/facades \
    FACADEKIT_GENERATE=cached \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/healthz').read()"

# Shell form so $PORT expands: Fly and Render both inject their own.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
