"""Where run artefacts go.

Local disk today, S3-compatible (Cloudflare R2) when a bucket exists. The seam
is here so that moving to R2 is a deployment change, not a code change: the job
runner writes through `Storage` and never touches a path directly.

`S3Storage` is written but intentionally not reachable until S3_BUCKET is set --
the brief says leave it unconfigured until the bucket is created.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from app.config import Settings, settings


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    backend: str

    def put_dir(self, prefix: str, source: Path) -> None: ...
    def open(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> Iterator[str]: ...
    def local_path(self, key: str) -> Path | None: ...


class LocalStorage:
    """Files on the box the API runs on. Fine for one instance; not shared."""

    backend = "local"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Keys come from URLs. Refuse anything that escapes the root.
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise StorageError(f"refusing to access {key!r} outside the storage root")
        return target

    def put_dir(self, prefix: str, source: Path) -> None:
        dest = self._resolve(prefix)
        dest.mkdir(parents=True, exist_ok=True)
        for item in Path(source).iterdir():
            if item.is_file():
                shutil.copy2(item, dest / item.name)

    def open(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageError:
            return False

    def list(self, prefix: str) -> Iterator[str]:
        base = self._resolve(prefix)
        if not base.is_dir():
            return
        for item in sorted(base.iterdir()):
            if item.is_file():
                yield item.name

    def local_path(self, key: str) -> Path | None:
        path = self._resolve(key)
        return path if path.is_file() else None


class S3Storage:
    """S3-compatible object storage (Cloudflare R2).

    NOT WIRED UP YET. Needs a bucket, an endpoint and credentials in the API's
    .env, plus `boto3` installed. See docs/deploy.md; until then STORAGE_BACKEND
    stays "local" and this class is never constructed.
    """

    backend = "s3"

    def __init__(self, bucket: str, endpoint: str = "", region: str = "auto") -> None:
        if not bucket:
            raise StorageError(
                "S3_BUCKET is not set. Create the R2 bucket first (docs/deploy.md), "
                "or leave STORAGE_BACKEND=local."
            )
        try:
            import boto3
        except ImportError as e:
            raise StorageError(
                "S3 storage needs boto3: uv pip install -e 'apps/api[s3]'"
            ) from e

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            region_name=region,
        )

    def put_dir(self, prefix: str, source: Path) -> None:
        for item in Path(source).iterdir():
            if item.is_file():
                self.client.upload_file(str(item), self.bucket, f"{prefix}/{item.name}")

    def open(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list(self, prefix: str) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{prefix}/"):
            for obj in page.get("Contents", []):
                yield obj["Key"].rsplit("/", 1)[-1]

    def local_path(self, key: str) -> Path | None:
        return None  # objects are remote; the API streams them instead


def get_storage(config: Settings | None = None) -> Storage:
    config = config or settings
    if config.storage_backend == "s3":
        return S3Storage(config.s3_bucket, config.s3_endpoint, config.s3_region)
    return LocalStorage(config.storage_dir)
