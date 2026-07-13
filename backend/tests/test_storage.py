"""Unit tests for the storage abstraction (backend/app/storage.py)."""
from __future__ import annotations

import pytest

from app.storage import (
    LEGACY_PREFIX,
    LocalStorage,
    S3Storage,
    StorageNotFoundError,
)


# ------------------------------- LocalStorage ----------------------------- #
def test_local_storage_put_get_roundtrip(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    key = "uploads/user1/abc123.pdf"
    returned = store.put(key, b"hello world", content_type="application/pdf")
    assert returned == key
    assert store.get(key) == b"hello world"


def test_local_storage_creates_nested_directories(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    store.put("uploads/deep/nested/user/file.txt", b"data")
    assert (tmp_path / "uploads" / "deep" / "nested" / "user" / "file.txt").exists()


def test_local_storage_get_missing_raises(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    with pytest.raises(StorageNotFoundError):
        store.get("uploads/does/not/exist.pdf")


def test_local_storage_exists(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    key = "uploads/user1/file.txt"
    assert store.exists(key) is False
    store.put(key, b"data")
    assert store.exists(key) is True


def test_local_storage_delete(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    key = "uploads/user1/file.txt"
    store.put(key, b"data")
    assert store.exists(key) is True
    store.delete(key)
    assert store.exists(key) is False


def test_local_storage_delete_missing_key_is_silent(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    store.delete("uploads/never/existed.txt")  # must not raise


def test_local_storage_legacy_key_reads_raw_path(tmp_path):
    """Pre-migration rows store a bare disk path wrapped as legacy://<path>;
    it must resolve straight to that path, ignoring the configured root."""
    real_path = tmp_path / "old_upload.pdf"
    real_path.write_bytes(b"legacy bytes")
    store = LocalStorage(root=str(tmp_path / "unrelated_root"))
    key = LEGACY_PREFIX + str(real_path)
    assert store.exists(key) is True
    assert store.get(key) == b"legacy bytes"
    store.delete(key)
    assert not real_path.exists()


def test_local_storage_legacy_key_missing_raises(tmp_path):
    store = LocalStorage(root=str(tmp_path))
    key = LEGACY_PREFIX + str(tmp_path / "nope.pdf")
    with pytest.raises(StorageNotFoundError):
        store.get(key)


# --------------------------------- S3Storage ------------------------------ #
@pytest.fixture()
def moto_s3():
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        import boto3

        bucket = "papertrail-test-bucket"
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=bucket)
        yield bucket


def test_s3_storage_put_get_roundtrip(moto_s3):
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    key = "uploads/user1/abc123.pdf"
    returned = store.put(key, b"hello world", content_type="application/pdf")
    assert returned == key
    assert store.get(key) == b"hello world"


def test_s3_storage_get_missing_raises(moto_s3):
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    with pytest.raises(StorageNotFoundError):
        store.get("uploads/does/not/exist.pdf")


def test_s3_storage_exists(moto_s3):
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    key = "uploads/user1/file.txt"
    assert store.exists(key) is False
    store.put(key, b"data")
    assert store.exists(key) is True


def test_s3_storage_delete(moto_s3):
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    key = "uploads/user1/file.txt"
    store.put(key, b"data")
    store.delete(key)
    assert store.exists(key) is False


def test_s3_storage_delete_missing_key_is_silent(moto_s3):
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    store.delete("uploads/never/existed.txt")  # must not raise (S3 semantics)


def test_s3_storage_legacy_key_reads_raw_path(moto_s3, tmp_path):
    real_path = tmp_path / "old_upload.pdf"
    real_path.write_bytes(b"legacy bytes")
    store = S3Storage(bucket=moto_s3, region="us-east-1")
    key = LEGACY_PREFIX + str(real_path)
    assert store.exists(key) is True
    assert store.get(key) == b"legacy bytes"
