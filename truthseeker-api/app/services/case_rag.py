"""Public case-library RAG indexing and retrieval helpers."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.services.builtin_cases import list_builtin_cases
from app.services.case_library import redact_public_markdown
from app.utils.supabase_client import supabase

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150
VECTOR_WEIGHT = 0.75
KEYWORD_WEIGHT = 0.25


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _tokenize(text: str) -> set[str]:
    return {
        item.lower()
        for item in re.findall(r"[\w\u4e00-\u9fff]{2,}", text or "")
        if len(item.strip()) >= 2
    }


def build_chunk_hash(source_kind: str, case_id: str, text: str) -> str:
    payload = {
        "source_kind": source_kind,
        "case_id": case_id,
        "text": _normalize_space(text),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def chunk_markdown(
    markdown: str,
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[dict[str, Any]]:
    """Chunk markdown by sections, then split long sections with overlap."""
    text = redact_public_markdown(markdown or "").strip()
    if not text:
        return []

    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())

    chunks: list[dict[str, Any]] = []
    for section in sections:
        if len(section) <= max_chars:
            chunks.append({"chunk_index": len(chunks), "text": section})
            continue
        start = 0
        while start < len(section):
            end = min(start + max_chars, len(section))
            chunk_text = section[start:end].strip()
            if chunk_text:
                chunks.append({"chunk_index": len(chunks), "text": chunk_text})
            if end >= len(section):
                break
            start = max(end - overlap_chars, start + 1)
    return chunks


async def embed_text(text: str) -> dict[str, Any]:
    """Call the configured OpenAI-compatible embeddings endpoint.

    Defaults are set for SiliconFlow Qwen/Qwen3-VL-Embedding-8B. The API key is
    intentionally independent from Kimi chat settings.
    """
    if not settings.CASE_RAG_ENABLED:
        return {"status": "disabled", "embedding": None, "error": "CASE_RAG_ENABLED=false"}
    if not settings.EMBEDDING_API_KEY:
        return {"status": "failed", "embedding": None, "error": "missing EMBEDDING_API_KEY"}

    base_url = settings.EMBEDDING_BASE_URL.rstrip("/")
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": text,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
    }
    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url}/embeddings", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        embedding = ((data.get("data") or [{}])[0] or {}).get("embedding")
        if not isinstance(embedding, list):
            return {"status": "failed", "embedding": None, "error": "embedding response missing data[0].embedding"}
        if len(embedding) != settings.EMBEDDING_DIMENSIONS:
            return {
                "status": "failed",
                "embedding": None,
                "error": f"embedding dimensions mismatch: got {len(embedding)}, expected {settings.EMBEDDING_DIMENSIONS}",
            }
        return {
            "status": "success",
            "embedding": [float(item) for item in embedding],
            "model": settings.EMBEDDING_MODEL,
            "dimensions": settings.EMBEDDING_DIMENSIONS,
        }
    except Exception as exc:
        return {"status": "failed", "embedding": None, "error": f"{type(exc).__name__}: {exc}"}


def merge_hybrid_results(
    *,
    vector_rows: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in vector_rows:
        chunk_id = str(row.get("chunk_id") or row.get("id") or "")
        if not chunk_id:
            continue
        item = dict(row)
        item["chunk_id"] = chunk_id
        item["vector_score"] = max(0.0, min(1.0, float(row.get("similarity", row.get("vector_score", 0.0)) or 0.0)))
        item.setdefault("keyword_score", 0.0)
        by_id[chunk_id] = item
    for row in keyword_rows:
        chunk_id = str(row.get("chunk_id") or row.get("id") or "")
        if not chunk_id:
            continue
        item = by_id.setdefault(chunk_id, dict(row))
        item["chunk_id"] = chunk_id
        item["keyword_score"] = max(0.0, min(1.0, float(row.get("keyword_score", 0.0) or 0.0)))
        item.setdefault("vector_score", 0.0)
        for key, value in row.items():
            item.setdefault(key, value)

    merged: list[dict[str, Any]] = []
    for item in by_id.values():
        item["score"] = round(float(item.get("vector_score", 0.0)) * VECTOR_WEIGHT + float(item.get("keyword_score", 0.0)) * KEYWORD_WEIGHT, 6)
        text = str(item.get("snippet") or item.get("chunk_text") or "")
        item["snippet"] = _normalize_space(text)[:280]
        merged.append(item)
    merged.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return merged[: max(limit, 1)]


def _keyword_candidates(client: Any, query: str, *, category: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
    try:
        query_obj = client.table("case_library_rag_chunks").select("*")
        if category:
            query_obj = query_obj.eq("media_category", category)
        resp = query_obj.limit(200).execute()
        rows = resp.data or []
    except Exception as exc:
        logger.warning("Case RAG keyword candidate query failed: %s", exc)
        return []

    query_terms = _tokenize(query)
    scored: list[dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get(key) or "") for key in ("title", "chunk_text", "summary"))
        terms = _tokenize(text)
        if not terms:
            continue
        overlap = len(query_terms & terms)
        score = overlap / max(1, min(len(query_terms), 12))
        if score <= 0 and query.strip() not in text:
            continue
        scored.append({**row, "keyword_score": min(1.0, max(score, 0.1))})
    scored.sort(key=lambda item: item.get("keyword_score", 0.0), reverse=True)
    return scored[:limit]


def build_rag_query(
    *,
    agent: str,
    case_prompt: str = "",
    input_type: str = "",
    evidence_files: list[dict[str, Any]] | None = None,
    tool_summaries: list[str] | None = None,
) -> str:
    file_bits = [
        f"{item.get('name', '检材')} {item.get('modality', '')} {item.get('mime_type', '')}"
        for item in (evidence_files or [])[:5]
        if isinstance(item, dict)
    ]
    return _normalize_space(
        "\n".join([
            f"agent={agent}",
            f"input_type={input_type}",
            f"case_prompt={case_prompt}",
            "files=" + "；".join(file_bits),
            "tool_summaries=" + "；".join(tool_summaries or []),
        ])
    )[:4000]


async def case_rag_search(
    client: Any = None,
    *,
    query: str,
    agent: str,
    category: str | None = None,
    top_k: int | None = None,
) -> dict[str, Any]:
    started_at = _now()
    top_k = top_k or settings.CASE_RAG_TOP_K
    if not settings.CASE_RAG_ENABLED:
        return {
            "tool": "case_rag_search",
            "target": agent,
            "status": "disabled",
            "degraded": True,
            "summary": "公开案例 RAG 已禁用",
            "matches": [],
            "started_at": started_at,
            "completed_at": _now(),
        }

    embed = await embed_text(query)
    if embed.get("status") != "success":
        return {
            "tool": "case_rag_search",
            "target": agent,
            "status": "degraded",
            "degraded": True,
            "summary": f"公开案例 RAG 不可用: {embed.get('error') or embed.get('status')}",
            "matches": [],
            "started_at": started_at,
            "completed_at": _now(),
        }

    client = client or supabase
    vector_rows: list[dict[str, Any]] = []
    try:
        resp = client.rpc(
            "match_case_library_rag_chunks",
            {
                "query_embedding": embed["embedding"],
                "match_count": max(top_k * 3, 8),
                "filter_category": category,
            },
        ).execute()
        vector_rows = resp.data or []
    except Exception as exc:
        logger.warning("Case RAG vector query failed: %s", exc)

    keyword_rows = _keyword_candidates(client, query, category=category, limit=max(top_k * 3, 8))
    matches = merge_hybrid_results(vector_rows=vector_rows, keyword_rows=keyword_rows, limit=top_k)
    status = "success" if matches else "no_match"
    return {
        "tool": "case_rag_search",
        "target": agent,
        "status": status,
        "degraded": False,
        "summary": f"命中 {len(matches)} 个公开案例 RAG 片段" if matches else "未命中相似公开案例",
        "matches": matches,
        "embedding_model": embed.get("model"),
        "started_at": started_at,
        "completed_at": _now(),
    }


def _case_to_chunks(row: dict[str, Any], *, source_kind: str) -> list[dict[str, Any]]:
    case_id = str(row.get("id") or row.get("case_id") or "")
    markdown = row.get("report_markdown") or ""
    rows: list[dict[str, Any]] = []
    for chunk in chunk_markdown(markdown):
        text = chunk["text"]
        content_hash = build_chunk_hash(source_kind, case_id, text)
        rows.append({
            "source_kind": source_kind,
            "case_id": case_id,
            "chunk_id": f"{source_kind}:{case_id}:{chunk['chunk_index']}:{content_hash[:12]}",
            "chunk_index": chunk["chunk_index"],
            "title": row.get("title") or "未命名公开案例",
            "media_category": row.get("media_category") or "text_generation",
            "verdict": row.get("verdict") or "inconclusive",
            "difficulty": row.get("difficulty") or "Medium",
            "chunk_text": text,
            "snippet": _normalize_space(text)[:280],
            "content_hash": content_hash,
            "published_at": row.get("published_at"),
            "metadata": {"task_id": row.get("task_id")},
        })
    return rows


async def index_case_record(client: Any, row: dict[str, Any], *, source_kind: str) -> dict[str, Any]:
    chunks = _case_to_chunks(row, source_kind=source_kind)
    indexed = 0
    errors: list[str] = []
    for chunk in chunks:
        embed = await embed_text(chunk["chunk_text"])
        if embed.get("status") != "success":
            errors.append(str(embed.get("error") or embed.get("status")))
            continue
        payload = {
            **chunk,
            "embedding": embed["embedding"],
            "embedding_model": str(embed.get("model") or settings.EMBEDDING_MODEL),
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "indexed_at": _now(),
        }
        try:
            client.table("case_library_rag_chunks").upsert(payload, on_conflict="chunk_id").execute()
            indexed += 1
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    return {"case_id": row.get("id"), "source_kind": source_kind, "chunks": len(chunks), "indexed": indexed, "errors": errors[:5]}


async def rebuild_case_rag_index(client: Any = None, *, include_builtin: bool = True, include_public: bool = True) -> dict[str, Any]:
    client = client or supabase
    results: list[dict[str, Any]] = []
    if include_builtin:
        for row in list_builtin_cases():
            results.append(await index_case_record(client, row, source_kind="builtin"))
    if include_public:
        resp = client.table("case_library_entries").select("*").eq("status", "published").execute()
        for row in resp.data or []:
            results.append(await index_case_record(client, row, source_kind="public"))
    return {
        "status": "completed",
        "case_count": len(results),
        "indexed_chunks": sum(int(item.get("indexed") or 0) for item in results),
        "results": results,
    }
