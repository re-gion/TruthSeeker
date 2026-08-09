"""检材下载传输层韧性：瞬时 TLS/连接错误有限重试，服务端明确拒绝快速失败。

与 tests/test_upload_resilience.py 对称：上传端已有重试，下载端缺同样保护时，
代理/网络抖动造成的间歇性 ConnectError 会导致文本/媒体检材读不到而降级。
"""
import httpx
import pytest

from app.services import evidence_access as module


class _FakeAsyncClient:
    """按调用次数弹出结果的 httpx.AsyncClient 替身。"""

    def __init__(self, outcomes: list):
        self.outcomes = list(outcomes)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, *args, **kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, httpx.Response):
            outcome.request = httpx.Request("GET", str(url))
        return outcome


class _FakeBucket:
    def __init__(self, failures: list[Exception], payload: bytes = b"hello evidence"):
        self.failures = list(failures)
        self.payload = payload
        self.calls = 0

    def download(self, path):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return self.payload


class _FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, name):
        return self._bucket


class _FakeSupabase:
    def __init__(self, bucket):
        self.storage = _FakeStorage(bucket)


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    monkeypatch.setattr(module, "DOWNLOAD_RETRY_DELAY_SECONDS", 0.01)


async def _download(reference, **kwargs):
    return await module.download_evidence_bytes(reference, **kwargs)


@pytest.mark.asyncio
async def test_http_transport_error_retried_then_succeeds(monkeypatch):
    """HTTP URL 首次连接中断，重试后成功返回内容。"""
    client = _FakeAsyncClient([
        httpx.ConnectError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"),
        httpx.Response(200, content=b"notice text", headers={"content-disposition": 'attachment; filename="notice.txt"'}),
    ])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    content, filename = await _download("https://example.com/evidence/notice.txt")

    assert content == b"notice text"
    assert filename == "notice.txt"
    assert len(client.outcomes) == 0


@pytest.mark.asyncio
async def test_http_retry_exhausted_raises_last_error(monkeypatch):
    """重试耗尽后抛出最后一次传输错误，让调用方走降级。"""
    err = httpx.ConnectError("connection refused")
    client = _FakeAsyncClient([err] * module.DOWNLOAD_MAX_ATTEMPTS)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(httpx.ConnectError):
        await _download("https://example.com/evidence/notice.txt")


@pytest.mark.asyncio
async def test_http_status_error_not_retried(monkeypatch):
    """服务端明确拒绝（如 404）属于业务失败，不消耗重试次数。"""
    client = _FakeAsyncClient([httpx.Response(404, content=b"not found")])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(httpx.HTTPStatusError):
        await _download("https://example.com/evidence/missing.txt")
    assert len(client.outcomes) == 0


@pytest.mark.asyncio
async def test_storage_transport_error_retried_then_succeeds(monkeypatch):
    """Supabase storage 下载首次连接中断，重试后成功返回内容。"""
    bucket = _FakeBucket([httpx.ConnectError("tls reset")], payload=b"storage text")
    monkeypatch.setattr(module, "supabase", _FakeSupabase(bucket))

    content, filename = await _download("uploads/evidence/notice.txt")

    assert content == b"storage text"
    assert filename == "notice.txt"
    assert bucket.calls == 2


@pytest.mark.asyncio
async def test_mock_reference_skips_network():
    """mock:// 引用不发起网络请求。"""
    content, filename = await _download("mock://case/notice.txt")
    assert content == b""
    assert filename == "notice.txt"
