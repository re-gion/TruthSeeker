"""Exa OSINT search adapter with structured degradation."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

EXA_TIMEOUT_SECONDS = 20.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_query(text: str, *, max_length: int = 240) -> str:
    """Remove high-risk personal details and keep only search-worthy clues."""
    cleaned = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text or "")
    cleaned = re.sub(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b", "[phone]", cleaned)
    cleaned = re.sub(r"\b\d{15,19}\b", "[long-number]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]


def build_deidentified_queries(
    *,
    case_prompt: str,
    threat_indicators: list[str] | None = None,
    urls: list[str] | None = None,
    file_names: list[str] | None = None,
) -> list[str]:
    """Build compact, de-identified search queries for public OSINT."""
    candidates: list[str] = []
    if case_prompt:
        candidates.append(case_prompt)
    for indicator in threat_indicators or []:
        if isinstance(indicator, str):
            candidates.append(indicator)
    for url in urls or []:
        host = re.sub(r"^https?://", "", str(url)).split("/")[0]
        if host:
            candidates.append(f"{host} security report")
    for name in file_names or []:
        stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", str(name))
        if stem:
            candidates.append(f"{stem} deepfake provenance")

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        query = _redact_query(candidate)
        if len(query) < 4 or query in seen:
            continue
        seen.add(query)
        queries.append(query)
        if len(queries) >= 3:
            break
    return queries


async def search_osint(queries: list[str], *, num_results: int = 5) -> dict[str, Any]:
    """Search Exa API and return a normalized, non-throwing result."""
    queries = [q for q in queries if isinstance(q, str) and q.strip()]
    if not queries:
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
    async with httpx.AsyncClient(timeout=EXA_TIMEOUT_SECONDS) as client:
        for query in queries:
            try:
                resp = await client.post(
                    f"{settings.EXA_BASE_URL.rstrip('/')}/search",
                    headers=headers,
                    json={
                        "query": query,
                        "numResults": num_results,
                        "contents": {"text": {"maxCharacters": 800}},
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("results") or []:
                    results.append({
                        "title": item.get("title") or item.get("url") or "Exa result",
                        "url": item.get("url"),
                        "summary": item.get("text") or item.get("summary") or "",
                        "score": item.get("score"),
                        "published_date": item.get("publishedDate") or item.get("published_date"),
                        "retrieved_at": _now(),
                        "query": query,
                    })
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

    status = "success" if results else "failed" if errors else "degraded"
    return {
        "status": status,
        "provider": "exa",
        "queries": queries,
        "results": results[:num_results],
        "errors": errors,
        "retrieved_at": _now(),
    }
