"""上传端点传输层韧性：瞬时传输错误有限重试，服务端明确拒绝快速清晰失败。"""
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from storage3.exceptions import StorageApiError

from app.api.v1 import upload as upload_module


class _FakeBucket:
    def __init__(self, failures: list[Exception]):
        self.failures = failures
        self.calls: list[dict] = []

    def upload(self, path, f, file_options=None):
        self.calls.append(
            {"path": path, "file_options": dict(file_options or {}), "size": len(f.read())}
        )
        if self.failures:
            raise self.failures.pop(0)

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://example.com/{path}?sig=1"}


class _FakeStorage:
    def __init__(self, failures: list[Exception]):
        self.bucket = _FakeBucket(failures)

    def from_(self, name):
        return self.bucket


class _FakeSupabase:
    def __init__(self, failures: list[Exception]):
        self.storage = _FakeStorage(failures)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(upload_module, "UPLOAD_RETRY_DELAY_SECONDS", 0.01)
    app = FastAPI()
    app.include_router(upload_module.router, prefix="/upload")
    return TestClient(app)


def _post_file(client):
    return client.post(
        "/upload/",
        files={"file": ("note.txt", b"hello truthseeker", "text/plain")},
        data={"user_id": "tester"},
    )


def test_transient_transport_error_retried_then_succeeds(client, monkeypatch):
    fake = _FakeSupabase(
        [httpx.RemoteProtocolError("<StreamReset stream_id:1, error_code:1, remote_reset:True>")]
    )
    monkeypatch.setattr(upload_module, "supabase", fake)

    resp = _post_file(client)

    assert resp.status_code == 200
    assert len(fake.storage.bucket.calls) == 2
    # 首次不带 upsert，重试带 upsert 防止服务端已写入导致重复报错
    assert not fake.storage.bucket.calls[0]["file_options"].get("upsert")
    assert fake.storage.bucket.calls[1]["file_options"].get("upsert") == "true"
    # content-type 必须用连字符键覆盖 storage3 默认值
    assert fake.storage.bucket.calls[0]["file_options"].get("content-type") == "text/plain; charset=utf-8"


def test_transport_error_exhausted_returns_500(client, monkeypatch):
    fake = _FakeSupabase([httpx.RemoteProtocolError("reset")] * upload_module.UPLOAD_MAX_ATTEMPTS)
    monkeypatch.setattr(upload_module, "supabase", fake)

    resp = _post_file(client)

    assert resp.status_code == 500
    assert len(fake.storage.bucket.calls) == upload_module.UPLOAD_MAX_ATTEMPTS


def test_storage_413_maps_to_clear_400_without_retry(client, monkeypatch):
    fake = _FakeSupabase(
        [StorageApiError("Object exceeded the maximum allowed size", "413", 413)]
    )
    monkeypatch.setattr(upload_module, "supabase", fake)

    resp = _post_file(client)

    assert resp.status_code == 400
    assert "上限" in resp.json()["detail"]
    assert len(fake.storage.bucket.calls) == 1


def test_storage_other_api_error_returns_500_without_retry(client, monkeypatch):
    fake = _FakeSupabase([StorageApiError("Forbidden", "403", 403)])
    monkeypatch.setattr(upload_module, "supabase", fake)

    resp = _post_file(client)

    assert resp.status_code == 500
    assert len(fake.storage.bucket.calls) == 1
