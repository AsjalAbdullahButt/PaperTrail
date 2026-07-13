"""Storage abstraction for uploaded file bytes.

All file I/O in the app must go through a ``StorageBackend`` instead of
``open()``/``os.path`` directly, so the same code works whether files live on
local disk (dev) or in an S3-compatible bucket (prod, e.g. Cloudflare R2).

Keys follow ``uploads/{user_id}/{uuid}.{ext}`` regardless of backend.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol, runtime_checkable

from .config import settings


class StorageNotFoundError(Exception):
    """Raised by ``get()`` when the requested key does not exist."""


# Rows created before the storage abstraction existed store a bare local disk
# path wrapped as ``legacy://<path>`` (see migration 0007). Those files always
# live on local disk regardless of the currently configured backend, so both
# backends resolve this prefix the same way instead of looking it up remotely.
LEGACY_PREFIX = "legacy://"


def _read_legacy(key: str) -> bytes:
    path = key[len(LEGACY_PREFIX):]
    if not os.path.exists(path):
        raise StorageNotFoundError(key)
    with open(path, "rb") as fh:
        return fh.read()


def _legacy_exists(key: str) -> bool:
    return os.path.exists(key[len(LEGACY_PREFIX):])


def _delete_legacy(key: str) -> None:
    path = key[len(LEGACY_PREFIX):]
    if os.path.exists(path):
        os.remove(path)


@runtime_checkable
class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store data. Returns a URL or key that can be passed back to get()."""
        ...

    def get(self, key: str) -> bytes:
        """Retrieve data. Raises StorageNotFoundError if missing."""
        ...

    def delete(self, key: str) -> None:
        """Delete. Silently succeeds if key does not exist."""
        ...

    def exists(self, key: str) -> bool:
        """Return True if the key exists."""
        ...


class LocalStorage:
    """Stores files under a local root directory (dev default: ``uploads/``).

    ``key`` is a relative path (e.g. ``uploads/{user_id}/{uuid}.pdf``); it is
    joined with ``root`` to form the on-disk path.
    """

    def __init__(self, root: str = "."):
        self.root = root

    def _path(self, key: str) -> str:
        return os.path.join(self.root, key)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return key

    def get(self, key: str) -> bytes:
        if key.startswith(LEGACY_PREFIX):
            return _read_legacy(key)
        path = self._path(key)
        if not os.path.exists(path):
            raise StorageNotFoundError(key)
        with open(path, "rb") as fh:
            return fh.read()

    def delete(self, key: str) -> None:
        if key.startswith(LEGACY_PREFIX):
            return _delete_legacy(key)
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        if key.startswith(LEGACY_PREFIX):
            return _legacy_exists(key)
        return os.path.exists(self._path(key))


class S3Storage:
    """Stores files in an S3-compatible bucket (AWS S3, Cloudflare R2, etc.).

    ``endpoint_url`` should be left ``None`` for real AWS S3, or set to the
    provider's S3-compatible endpoint (e.g. R2's account endpoint).
    """

    def __init__(
        self,
        bucket: str,
        region: str = "auto",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        import boto3

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return key

    def get(self, key: str) -> bytes:
        if key.startswith(LEGACY_PREFIX):
            return _read_legacy(key)
        from botocore.exceptions import ClientError

        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise StorageNotFoundError(key) from exc
            raise
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        if key.startswith(LEGACY_PREFIX):
            return _delete_legacy(key)
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        if key.startswith(LEGACY_PREFIX):
            return _legacy_exists(key)
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                return False
            raise


@lru_cache
def get_storage() -> StorageBackend:
    """Build the configured storage backend (cached for process lifetime)."""
    if settings.storage_backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            access_key=settings.s3_access_key_id or None,
            secret_key=settings.s3_secret_access_key or None,
        )
    return LocalStorage(root=".")


storage = get_storage()
