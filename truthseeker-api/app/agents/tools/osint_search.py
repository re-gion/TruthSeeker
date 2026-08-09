"""Exa OSINT search adapter with structured degradation."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EXA_TIMEOUT_SECONDS = 20.0
MAX_EXA_QUERIES = 3
EXA_CONNECT_RETRY_DELAYS_SECONDS = (0.5, 1.5)
EXA_CONNECT_MAX_ATTEMPTS = len(EXA_CONNECT_RETRY_DELAYS_SECONDS) + 1
MAX_RESULT_SUMMARY_CHARS = 280
INTERNAL_DIAGNOSTIC_PATTERNS = (
    "VirusTotal 未实际调用",
    "未配置 VirusTotal",
    "结果不可用",
    "工具失败",
    "降级",
    "degraded",
    "mock",
    "whoisxml 查询",
    "virustotal",
    "threat_score=",
    "status=",
)

_DOMAIN_PATTERN = re.compile(
    r"(?<![\w-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?![\w-])",
    re.IGNORECASE,
)
_COMMON_COMPOUND_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.br", "net.br", "org.br",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.au", "net.au", "org.au",
}
_NON_INDEPENDENT_SOURCE_DOMAINS = {"whoisxmlapi.com", "exa.ai"}
_IP_PATTERN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_query(text: str, *, max_length: int = 240) -> str:
    """Remove high-risk personal details and keep only search-worthy clues."""
    cleaned = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text or "")
    cleaned = re.sub(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b", "[phone]", cleaned)
    cleaned = re.sub(r"\b\d{15,19}\b", "[long-number]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]


def _is_internal_diagnostic(text: str) -> bool:
    return any(pattern.lower() in (text or "").lower() for pattern in INTERNAL_DIAGNOSTIC_PATTERNS)


def _is_generic_case_prompt(text: str) -> bool:
    generic_markers = ("请以", "数字取证专家", "判断该图片和文本", "AI 伪造", "局部篡改")
    return sum(1 for marker in generic_markers if marker in (text or "")) >= 2


def _shorten_summary(text: str, *, max_length: int = MAX_RESULT_SUMMARY_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    noisy_markers = ["登录", "注册", "首页", "导航", "探索发现", "用户中心"]
    if sum(1 for marker in noisy_markers if marker in cleaned[:240]) >= 3:
        cleaned = cleaned[:max_length]
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def _normalize_hostname(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
    hostname = (parsed.hostname or "").strip(".")
    if not hostname:
        return ""
    try:
        return ipaddress.ip_address(hostname).compressed.lower()
    except ValueError:
        try:
            return hostname.encode("idna").decode("ascii").lower()
        except UnicodeError:
            return ""


def _ioc_anchors(query: str) -> set[str]:
    """Extract normalized domain/IP anchors used to admit search evidence."""
    anchors: set[str] = set()
    for match in _IP_PATTERN.findall(query or ""):
        try:
            anchors.add(ipaddress.ip_address(match).compressed.lower())
        except ValueError:
            continue
    for match in _DOMAIN_PATTERN.findall(query or ""):
        domain = _normalize_hostname(match)
        if not domain:
            continue
        anchors.add(domain)
        labels = domain.split(".")
        suffix = ".".join(labels[-2:])
        registrable_size = 3 if suffix in _COMMON_COMPOUND_SUFFIXES else 2
        if len(labels) >= registrable_size:
            anchors.add(".".join(labels[-registrable_size:]))
    return anchors


def _contains_anchor(text: str, anchor: str) -> bool:
    return bool(re.search(
        rf"(?<![a-z0-9-]){re.escape(anchor)}(?![a-z0-9-])",
        text,
        flags=re.IGNORECASE,
    ))


def _is_relevant_result(item: dict[str, Any], query: str) -> bool:
    source_host = (urlparse(str(item.get("url") or "")).hostname or "").lower().strip(".")
    if any(
        source_host == domain or source_host.endswith(f".{domain}")
        for domain in _NON_INDEPENDENT_SOURCE_DOMAINS
    ):
        return False
    anchors = _ioc_anchors(query)
    if not anchors:
        return True
    haystack = " ".join(str(item.get(key) or "") for key in ("title", "url", "summary", "text")).lower()
    return any(_contains_anchor(haystack, anchor) for anchor in anchors)


def _result_identity(item: dict[str, Any]) -> str:
    raw_url = str(item.get("url") or "").strip()
    if raw_url:
        parsed = urlparse(raw_url)
        hostname = _normalize_hostname(raw_url)
        query = urlencode(sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
        ))
        return urlunparse((
            parsed.scheme.lower(), hostname, parsed.path.rstrip("/"), "", query, ""
        ))
    return f"{item.get('title', '')}\n{item.get('summary') or item.get('text') or ''}".strip().lower()


async def _post_with_connection_retry(
    client: httpx.AsyncClient,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Retry an idempotent Exa search after transient connection failures."""
    for attempt in range(EXA_CONNECT_MAX_ATTEMPTS):
        try:
            return await client.post(url, **kwargs)
        except httpx.ConnectError:
            if attempt >= EXA_CONNECT_MAX_ATTEMPTS - 1:
                raise
            await asyncio.sleep(EXA_CONNECT_RETRY_DELAYS_SECONDS[attempt])
    raise RuntimeError("unreachable Exa retry state")


def build_deidentified_queries(
    *,
    case_prompt: str,
    threat_indicators: list[str] | None = None,
    urls: list[str] | None = None,
    file_names: list[str] | None = None,
) -> list[str]:
    """Build compact, de-identified search queries for public OSINT."""
    candidates: list[str] = []
    for url in urls or []:
        host = _normalize_hostname(str(url))
        if host:
            candidates.append(f'"{host}" phishing OR scam OR reputation')

    # A concrete URL/domain is the strongest public-search anchor. Mixing in
    # generic risk labels or upstream tool summaries creates unrelated searches
    # (for example a WhoisXML summary finding WhoisXML's own product page).
    if candidates:
        source_candidates = candidates
    else:
        source_candidates = []
        for indicator in threat_indicators or []:
            if isinstance(indicator, str) and not _is_internal_diagnostic(indicator):
                source_candidates.append(indicator)
        for name in file_names or []:
            stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", str(name))
            if stem:
                source_candidates.append(f'"{stem}" AIGC provenance')
        if case_prompt and not _is_generic_case_prompt(case_prompt) and not _is_internal_diagnostic(case_prompt):
            source_candidates.append(case_prompt)

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in source_candidates:
        query = _redact_query(candidate)
        if len(query) < 4 or query in seen:
            continue
        seen.add(query)
        queries.append(query)
        if len(queries) >= MAX_EXA_QUERIES:
            break
    return queries


async def search_osint(queries: list[str], *, num_results: int = 5) -> dict[str, Any]:
    """Search Exa API and return a normalized, non-throwing result."""
    queries = [q for q in queries if isinstance(q, str) and q.strip()]
    if not queries:
        logger.warning("Exa search degraded: no searchable queries after de-identification")
        return {
            "status": "degraded",
            "provider": "exa",
            "queries": [],
            "results": [],
            "reason": "no_searchable_query",
            "retrieved_at": _now(),
        }

    api_key = settings.EXA_API_KEY
    if not api_key:
        logger.warning("Exa search degraded: missing API key")
        return {
            "status": "degraded",
            "provider": "exa",
            "queries": queries,
            "results": [],
            "reason": "missing_api_key",
            "retrieved_at": _now(),
        }

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    rejected_result_count = 0
    duplicate_result_count = 0
    searched_result_count = 0
    failed_query_count = 0
    reason: str | None = None
    seen_results: set[str] = set()
    async with httpx.AsyncClient(timeout=EXA_TIMEOUT_SECONDS) as client:
        for query_index, query in enumerate(queries):
            try:
                resp = await _post_with_connection_retry(
                    client,
                    f"{settings.EXA_BASE_URL.rstrip('/')}/search",
                    headers=headers,
                    json={
                        "query": query,
                        "numResults": num_results,
                        "contents": {"text": {"maxCharacters": MAX_RESULT_SUMMARY_CHARS}},
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                raw_results = payload.get("results") or []
                searched_result_count += len(raw_results)
                for item in raw_results:
                    if not isinstance(item, dict) or not _is_relevant_result(item, query):
                        rejected_result_count += 1
                        continue
                    identity = _result_identity(item)
                    if identity and identity in seen_results:
                        duplicate_result_count += 1
                        continue
                    if identity:
                        seen_results.add(identity)
                    results.append({
                        "title": item.get("title") or item.get("url") or "Exa result",
                        "url": item.get("url"),
                        "summary": _shorten_summary(item.get("summary") or item.get("text") or ""),
                        "score": item.get("score"),
                        "published_date": item.get("publishedDate") or item.get("published_date"),
                        "retrieved_at": _now(),
                        "query": query,
                    })
            except httpx.ConnectError as exc:
                logger.warning("Exa batch connection failed for query '%s': %s", query, exc)
                errors.append(f"{type(exc).__name__}: {exc}")
                failed_query_count += len(queries) - query_index
                reason = "connection_failed"
                break
            except Exception as exc:
                logger.warning("Exa search degraded for query '%s': %s", query, exc)
                errors.append(f"{type(exc).__name__}: {exc}")
                failed_query_count += 1
                reason = reason or "provider_error"

    # A completed search with zero case-specific matches is a valid negative
    # result, not an unavailable/degraded provider. Keep unrelated semantic
    # candidates out of the evidence chain while distinguishing them from API
    # failures such as timeouts, authentication errors, or connection loss.
    status = "partial" if results and errors else "failed" if errors else "success"
    if not results and rejected_result_count and not errors and not reason:
        reason = "no_case_specific_matches"
    elif not results and not errors and not reason:
        reason = "no_results"
    response = {
        "status": status,
        "provider": "exa",
        "queries": queries,
        "results": results[:num_results],
        "errors": errors,
        "failed_query_count": failed_query_count,
        "searched_result_count": searched_result_count,
        "rejected_result_count": rejected_result_count,
        "duplicate_result_count": duplicate_result_count,
        "retrieved_at": _now(),
    }
    if reason:
        response["reason"] = reason
    return response
