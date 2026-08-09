"""Tests for LLM transient-error backoff retry (503/429/timeout) in llm_client."""
from __future__ import annotations

import types
from types import SimpleNamespace

import pytest

from app.agents.tools import llm_client


def _patch_ainvoke(monkeypatch, behavior) -> "list[int]":
    """Replace llm.ainvoke (class-level) with a scripted behavior; returns call count holder."""
    calls: list[int] = [0]

    async def scripted_ainvoke(self, messages, **kwargs):
        calls[0] += 1
        return await behavior(self, messages, calls)

    # ChatOpenAI 是 pydantic 模型，实例属性赋值会被拦截，改 patch 类方法
    monkeypatch.setattr(llm_client.ChatOpenAI, "ainvoke", scripted_ainvoke)
    return calls


@pytest.mark.asyncio
async def test_multimodal_retries_on_503_then_succeeds(monkeypatch):
    async def behavior(self, messages, calls):
        if calls[0] == 1:
            raise RuntimeError("InternalServerError: Error code: 503 - {'code': 50508, 'message': 'System is too busy now.'}")
        return SimpleNamespace(content="成功结果")

    calls = _patch_ainvoke(monkeypatch, behavior)
    status_sink: dict = {}
    result = await llm_client._invoke_multimodal_llm("system", "你好", None, "FALLBACK", status_sink=status_sink)

    assert result == "成功结果"
    assert calls[0] == 2  # 1 次失败 + 1 次重试成功
    assert status_sink.get("status") == "success"
    assert status_sink.get("mode") == "multimodal"


@pytest.mark.asyncio
async def test_multimodal_degrades_after_all_503_retries_exhausted(monkeypatch):
    async def behavior(self, messages, calls):
        raise RuntimeError("InternalServerError: Error code: 503 - System is too busy now. Please try again later.")

    calls = _patch_ainvoke(monkeypatch, behavior)
    result = await llm_client._invoke_multimodal_llm("system", "你好", None, "FALLBACK")

    assert result.startswith("[降级模式: LLM不可用]")
    # 多模态块 3 次 + 文本兜底块 3 次
    assert calls[0] == 2 * (1 + llm_client._LLM_TRANSIENT_RETRIES)


@pytest.mark.asyncio
async def test_multimodal_does_not_retry_non_transient_400(monkeypatch):
    async def behavior(self, messages, calls):
        raise RuntimeError("BadRequestError: Error code: 400 - number of input tokens exceeded max_prompt_tokens")

    calls = _patch_ainvoke(monkeypatch, behavior)
    result = await llm_client._invoke_multimodal_llm("system", "你好", None, "FALLBACK")

    assert result.startswith("[降级模式: LLM不可用]")
    # 400 不重试：多模态 1 次 + 文本兜底 1 次 = 2 次
    assert calls[0] == 2


@pytest.mark.asyncio
async def test_multimodal_text_retry_succeeds_after_multimodal_and_text_503(monkeypatch):
    async def behavior(self, messages, calls):
        raise RuntimeError("InternalServerError: Error code: 503 - too busy")

    calls = _patch_ainvoke(monkeypatch, behavior)

    # 多模态 3 次 + 文本 3 次都失败 → 降级
    result = await llm_client._invoke_multimodal_llm("system", "你好", None, "FALLBACK")
    assert result.startswith("[降级模式: LLM不可用]")
    assert calls[0] == 2 * (1 + llm_client._LLM_TRANSIENT_RETRIES)


def test_is_transient_llm_error_classification():
    import httpx

    assert llm_client._is_transient_llm_error(RuntimeError("Error code: 503 - too busy"))
    assert llm_client._is_transient_llm_error(RuntimeError("Error code: 429 - rate limit"))
    assert llm_client._is_transient_llm_error(httpx.ConnectError("refused"))
    assert llm_client._is_transient_llm_error(httpx.ReadTimeout("read"))
    assert not llm_client._is_transient_llm_error(RuntimeError("Error code: 400 - input tokens exceeded"))
    assert not llm_client._is_transient_llm_error(RuntimeError("Error code: 401 - invalid api key"))
