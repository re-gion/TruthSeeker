from __future__ import annotations

import httpx
import pytest

from app.agents.tools import osint_search
from app.agents.nodes import osint as osint_node_module


CASE_URL = "http://halifax.co.uk.account.security.update.moroba.com.br"
CASE_HOST = "halifax.co.uk.account.security.update.moroba.com.br"


def test_case_url_query_excludes_tool_summaries_and_generic_risk_labels():
    queries = osint_search.build_deidentified_queries(
        case_prompt="",
        urls=[CASE_URL],
        threat_indicators=[
            "WhoisXML 查询完成: moroba.com.br，注册时间=2025-08-01，注册商=Example Registrar",
            "文本社工诱导风险高 (52.0%)",
            "要求核验身份或敏感个人信息",
        ],
        file_names=["案例3-文本-客服通知.txt", "案例3-图片-客服通知.jpg"],
    )

    assert queries == [f'"{CASE_HOST}" phishing OR scam OR reputation']


def test_case_url_query_uses_parsed_hostname_not_userinfo():
    queries = osint_search.build_deidentified_queries(
        case_prompt="",
        urls=["https://trusted.co.uk@evil.example/reset"],
    )

    assert queries == ['"evil.example" phishing OR scam OR reputation']


def test_exa_node_timeout_covers_all_queries_and_connection_retries():
    assert osint_node_module.EXA_BATCH_TIMEOUT_SECONDS >= (
        osint_search.EXA_TIMEOUT_SECONDS
        * osint_search.MAX_EXA_QUERIES
        * osint_search.EXA_CONNECT_MAX_ATTEMPTS
    )


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _MixedRelevanceClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return _Response({
            "results": [
                {
                    "title": "WHOIS API product page",
                    "url": "https://www.whoisxmlapi.com/whois-api",
                    "text": "Bulk WHOIS lookup and domain intelligence products.",
                    "score": 0.99,
                },
                {
                    "title": "Suspicious moroba.com.br subdomain report",
                    "url": "https://independent.example/report/moroba.com.br",
                    "text": f"Observed phishing host {CASE_HOST} in an account-reset lure.",
                    "score": 0.71,
                },
            ]
        })


@pytest.mark.asyncio
async def test_search_osint_discards_results_without_case_specific_anchor(monkeypatch):
    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _MixedRelevanceClient)

    result = await osint_search.search_osint(
        [f'"{CASE_HOST}" phishing OR scam OR reputation']
    )

    assert result["status"] == "success"
    assert [item["url"] for item in result["results"]] == [
        "https://independent.example/report/moroba.com.br"
    ]
    assert result["rejected_result_count"] == 1


class _ConnectFailureClient(_MixedRelevanceClient):
    calls = 0

    async def post(self, *args, **kwargs):
        type(self).calls += 1
        request = httpx.Request("POST", "https://api.exa.ai/search")
        raise httpx.ConnectError("connection reset", request=request)


class _ProviderSelfPageClient(_MixedRelevanceClient):
    async def post(self, *args, **kwargs):
        return _Response({
            "results": [{
                "title": f"WHOIS lookup for {CASE_HOST}",
                "url": "https://www.whoisxmlapi.com/whois-api",
                "text": f"Use our API to investigate {CASE_HOST}.",
            }]
        })


@pytest.mark.asyncio
async def test_search_osint_rejects_upstream_tool_provider_self_pages(monkeypatch):
    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _ProviderSelfPageClient)

    result = await osint_search.search_osint(
        [f'"{CASE_HOST}" phishing OR scam OR reputation']
    )

    assert result["status"] == "success"
    assert result["reason"] == "no_case_specific_matches"
    assert result["results"] == []
    assert result["searched_result_count"] == 1
    assert result["rejected_result_count"] == 1

    settled = await osint_node_module._settle_tool(
        tool="exa_search",
        target=f'"{CASE_HOST}" phishing OR scam OR reputation',
        coro=osint_search.search_osint(
            [f'"{CASE_HOST}" phishing OR scam OR reputation']
        ),
        timeout=5.0,
    )

    assert settled["status"] == "success"
    assert settled["degraded"] is False
    assert "搜索完成" in settled["summary"]
    assert "未发现与本案 IOC 直接匹配" in settled["summary"]


@pytest.mark.parametrize(
    ("query", "result_url", "result_text", "expected_result_count", "expected_reason"),
    [
        (
            f'"{CASE_HOST}" phishing',
            "https://independent.example/report/notmoroba.com.br",
            "Report about notmoroba.com.br only.",
            0,
            "no_case_specific_matches",
        ),
        (
            '"203.0.113.17" phishing',
            "https://independent.example/ip/203.0.113.17",
            "Observed 203.0.113.17 in phishing traffic.",
            1,
            None,
        ),
        (
            '"203.0.113.17" phishing',
            "https://independent.example/ip/198.51.100.8",
            "Unrelated IP report.",
            0,
            "no_case_specific_matches",
        ),
    ],
)
@pytest.mark.asyncio
async def test_search_osint_matches_ioc_on_token_boundaries(
    monkeypatch, query, result_url, result_text, expected_result_count, expected_reason
):
    class _Client(_MixedRelevanceClient):
        async def post(self, *args, **kwargs):
            return _Response({"results": [{
                "title": "Independent report",
                "url": result_url,
                "text": result_text,
            }]})

    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _Client)

    result = await osint_search.search_osint([query])

    assert result["status"] == "success"
    assert len(result["results"]) == expected_result_count
    assert result.get("reason") == expected_reason


class _TransientConnectClient(_MixedRelevanceClient):
    calls = 0

    async def post(self, *args, **kwargs):
        type(self).calls += 1
        if type(self).calls == 1:
            request = httpx.Request("POST", "https://api.exa.ai/search")
            raise httpx.ConnectError("connection reset", request=request)
        return _Response({
            "results": [{
                "title": "Independent phishing report",
                "url": "https://independent.example/report/moroba.com.br",
                "text": f"Observed {CASE_HOST} in a credential phishing lure.",
            }]
        })


class _RepeatedTransientConnectClient(_TransientConnectClient):
    calls = 0

    async def post(self, *args, **kwargs):
        type(self).calls += 1
        if type(self).calls < 3:
            request = httpx.Request("POST", "https://api.exa.ai/search")
            raise httpx.ConnectError(
                "[SSL: UNEXPECTED_EOF_WHILE_READING]",
                request=request,
            )
        return _Response({
            "results": [{
                "title": "Independent phishing report",
                "url": "https://independent.example/report/moroba.com.br",
                "text": f"Observed {CASE_HOST} in a credential phishing lure.",
            }]
        })


@pytest.mark.asyncio
async def test_search_osint_retries_one_transient_connection_failure(monkeypatch):
    _TransientConnectClient.calls = 0
    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _TransientConnectClient)

    result = await osint_search.search_osint(
        [f'"{CASE_HOST}" phishing OR scam OR reputation']
    )

    assert result["status"] == "success"
    assert len(result["results"]) == 1
    assert result["errors"] == []
    assert _TransientConnectClient.calls == 2


@pytest.mark.asyncio
async def test_search_osint_survives_two_consecutive_tls_connect_failures(monkeypatch):
    _RepeatedTransientConnectClient.calls = 0
    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _RepeatedTransientConnectClient)

    result = await osint_search.search_osint(
        [f'"{CASE_HOST}" phishing OR scam OR reputation']
    )

    assert result["status"] == "success"
    assert len(result["results"]) == 1
    assert result["errors"] == []
    assert _RepeatedTransientConnectClient.calls == 3


@pytest.mark.asyncio
async def test_search_osint_circuit_breaks_after_batch_connection_failure(monkeypatch):
    _ConnectFailureClient.calls = 0
    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _ConnectFailureClient)

    result = await osint_search.search_osint([
        f'"{CASE_HOST}" phishing OR scam OR reputation',
        '"moroba.com.br" malware',
    ])

    assert result["status"] == "failed"
    assert result["reason"] == "connection_failed"
    assert result["failed_query_count"] == 2
    assert len(result["errors"]) == 1
    assert _ConnectFailureClient.calls == osint_search.EXA_CONNECT_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_search_osint_preserves_provider_error_when_other_results_are_rejected(monkeypatch):
    class _Client(_MixedRelevanceClient):
        calls = 0

        async def post(self, *args, **kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                return _Response({"results": [{
                    "title": "Unrelated product",
                    "url": "https://unrelated.example/product",
                    "text": "No case IOC here.",
                }]})
            raise httpx.ReadError(
                "upstream reset",
                request=httpx.Request("POST", "https://api.exa.ai/search"),
            )

    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _Client)

    result = await osint_search.search_osint([
        f'"{CASE_HOST}" phishing',
        '"second.example" phishing',
    ])

    assert result["status"] == "failed"
    assert result["reason"] == "provider_error"


@pytest.mark.asyncio
async def test_search_osint_deduplicates_same_source_across_queries(monkeypatch):
    class _Client(_MixedRelevanceClient):
        async def post(self, *args, **kwargs):
            return _Response({"results": [{
                "title": "Independent report",
                "url": "https://independent.example/report/moroba?utm_source=exa",
                "text": f"Observed {CASE_HOST} and moroba.com.br in phishing traffic.",
            }]})

    monkeypatch.setattr(osint_search.settings, "EXA_API_KEY", "test-key")
    monkeypatch.setattr(osint_search.httpx, "AsyncClient", _Client)

    result = await osint_search.search_osint([
        f'"{CASE_HOST}" phishing',
        '"moroba.com.br" reputation',
    ])

    assert result["status"] == "success"
    assert len(result["results"]) == 1
    assert result["duplicate_result_count"] == 1
