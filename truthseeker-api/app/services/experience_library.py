"""Private personal experience library and RAG helpers."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.services.case_rag import embed_text, merge_hybrid_results
from app.agents.tools.llm_client import commander_extract_experience_drafts
from app.utils.supabase_client import supabase


VALID_EXPERIENCE_AGENTS = {"forensics", "osint", "challenger"}
EXPERIENCE_SIMILARITY_THRESHOLD = 0.58


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _tokens(text: str) -> set[str]:
    normalized = text.lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", normalized))
    chars = set(re.findall(r"[\u4e00-\u9fff]", normalized))
    return words | chars


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _target_agents(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [str(item) for item in value]
    else:
        candidates = []
    result: list[str] = []
    for item in candidates:
        agent = item.strip().lower()
        if agent in VALID_EXPERIENCE_AGENTS and agent not in result:
            result.append(agent)
    return result


def _text_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text[:300])
        if len(result) >= limit:
            break
    return result


def normalize_experience_draft(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    agents = _target_agents(raw.get("target_agents") or raw.get("target_agent"))
    title = str(raw.get("title") or "").strip()
    problem_pattern = str(raw.get("problem_pattern") or "").strip()
    recommended_method = str(raw.get("recommended_method") or "").strip()
    if not agents or not title or not problem_pattern or not recommended_method:
        return None
    return {
        "title": title[:120],
        "target_agents": agents,
        "problem_pattern": problem_pattern[:1200],
        "recommended_method": recommended_method[:1600],
        "evidence_to_check": _text_list(raw.get("evidence_to_check")),
        "when_to_escalate": str(raw.get("when_to_escalate") or "").strip()[:800],
        "limitations": str(raw.get("limitations") or "").strip()[:800],
    }


def experience_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("title"),
        item.get("problem_pattern"),
        item.get("recommended_method"),
        "；".join(item.get("evidence_to_check") or []),
        item.get("when_to_escalate"),
        item.get("limitations"),
    ]
    return _normalize_space("\n".join(str(part) for part in parts if part))


def build_content_hash(user_id: str, item: dict[str, Any]) -> str:
    payload = {
        "user_id": user_id,
        "target_agents": item.get("target_agents") or [],
        "text": experience_text(item),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _existing_experiences(client: Any, user_id: str, agents: list[str]) -> list[dict[str, Any]]:
    try:
        resp = client.table("experience_library_entries").select("*").eq("user_id", user_id).eq("status", "active").execute()
    except Exception:
        return []
    rows = resp.data or []
    return [
        row for row in rows
        if isinstance(row, dict) and set(_target_agents(row.get("target_agents"))) & set(agents)
    ]


def _is_duplicate_experience(client: Any, user_id: str, draft: dict[str, Any]) -> bool:
    draft_text = experience_text(draft)
    for row in _existing_experiences(client, user_id, draft["target_agents"]):
        existing_text = experience_text(row)
        if _similarity(draft_text, existing_text) >= EXPERIENCE_SIMILARITY_THRESHOLD:
            return True
    return False


async def build_experience_drafts(
    client: Any = None,
    *,
    user_id: str,
    task_id: str,
    session_id: str,
    messages: list[dict[str, Any]],
    context_payload: dict[str, Any] | None = None,
    summary_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    client = client or supabase
    raw_drafts = await commander_extract_experience_drafts(
        messages=messages,
        context_payload=context_payload or {},
        summary_payload=summary_payload or {},
    )
    drafts: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for raw in raw_drafts or []:
        draft = normalize_experience_draft(raw)
        if not draft:
            continue
        content_hash = build_content_hash(user_id, draft)
        if content_hash in seen_hashes:
            continue
        if _is_duplicate_experience(client, user_id, draft):
            continue
        seen_hashes.add(content_hash)
        draft.update({
            "source_task_id": task_id,
            "source_session_id": session_id,
            "content_hash": content_hash,
        })
        drafts.append(draft)
    return drafts


async def _index_entry(client: Any, entry: dict[str, Any]) -> int:
    text = experience_text(entry)
    embed = await embed_text(text)
    if embed.get("status") != "success":
        return 0
    inserted = 0
    for agent in _target_agents(entry.get("target_agents")):
        chunk_id = f"experience:{entry['id']}:{agent}:{entry['content_hash'][:12]}"
        payload = {
            "entry_id": entry["id"],
            "user_id": entry["user_id"],
            "target_agent": agent,
            "chunk_id": chunk_id,
            "chunk_text": text,
            "title": entry["title"],
            "embedding": embed["embedding"],
            "embedding_model": str(embed.get("model") or settings.EMBEDDING_MODEL),
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "content_hash": entry["content_hash"],
            "indexed_at": _now(),
        }
        client.table("experience_library_rag_chunks").upsert(payload, on_conflict="chunk_id").execute()
        inserted += 1
    return inserted


async def confirm_experience_drafts(
    client: Any = None,
    *,
    user_id: str,
    task_id: str,
    session_id: str,
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    client = client or supabase
    inserted = 0
    indexed_chunks = 0
    entries: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for raw in drafts:
        draft = normalize_experience_draft(raw)
        if not draft:
            continue
        content_hash = build_content_hash(user_id, draft)
        if content_hash in seen_hashes:
            continue
        if _is_duplicate_experience(client, user_id, draft):
            continue
        seen_hashes.add(content_hash)
        entry = {
            **draft,
            "user_id": user_id,
            "source_task_id": task_id,
            "source_session_id": session_id,
            "status": "active",
            "content_hash": content_hash,
            "created_at": _now(),
            "updated_at": _now(),
        }
        resp = client.table("experience_library_entries").insert(entry).execute()
        saved = dict((resp.data or [entry])[0])
        entries.append(saved)
        inserted += 1
        indexed_chunks += await _index_entry(client, saved)
    return {"status": "ok", "inserted": inserted, "indexed_chunks": indexed_chunks, "entries": entries}


def delete_experience(client: Any = None, *, entry_id: str, user_id: str) -> None:
    client = client or supabase
    resp = client.table("experience_library_entries").select("id,user_id").eq("id", entry_id).eq("user_id", user_id).limit(1).execute()
    if not resp.data:
        raise ValueError("experience not found")
    client.table("experience_library_rag_chunks").delete().eq("entry_id", entry_id).eq("user_id", user_id).execute()
    client.table("experience_library_entries").delete().eq("id", entry_id).eq("user_id", user_id).execute()


def _keyword_candidates(client: Any, query: str, *, user_id: str, agent: str, limit: int) -> list[dict[str, Any]]:
    try:
        resp = (
            client.table("experience_library_rag_chunks")
            .select("*")
            .eq("user_id", user_id)
            .eq("target_agent", agent)
            .limit(200)
            .execute()
        )
    except Exception:
        return []
    query_terms = _tokens(query)
    scored = []
    for row in resp.data or []:
        text = " ".join(str(row.get(key) or "") for key in ("title", "chunk_text"))
        terms = _tokens(text)
        overlap = len(query_terms & terms)
        if overlap <= 0:
            continue
        scored.append({**row, "keyword_score": min(1.0, overlap / max(1, min(len(query_terms), 12)))})
    scored.sort(key=lambda item: item.get("keyword_score", 0.0), reverse=True)
    return scored[:limit]


async def experience_rag_search(
    client: Any = None,
    *,
    query: str,
    user_id: str,
    agent: str,
    top_k: int | None = None,
) -> dict[str, Any]:
    client = client or supabase
    top_k = top_k or settings.CASE_RAG_TOP_K
    agent = agent if agent in VALID_EXPERIENCE_AGENTS else "forensics"
    vector_rows: list[dict[str, Any]] = []
    embed = await embed_text(query)
    if embed.get("status") == "success":
        try:
            resp = client.rpc(
                "match_experience_library_rag_chunks",
                {
                    "query_embedding": embed["embedding"],
                    "match_user_id": user_id,
                    "match_agent": agent,
                    "match_count": max(top_k * 3, 8),
                },
            ).execute()
            vector_rows = [
                row for row in (resp.data or [])
                if row.get("user_id") == user_id and row.get("target_agent") == agent
            ]
        except Exception:
            vector_rows = []
    keyword_rows = _keyword_candidates(client, query, user_id=user_id, agent=agent, limit=max(top_k * 3, 8))
    matches = merge_hybrid_results(vector_rows=vector_rows, keyword_rows=keyword_rows, limit=top_k)
    for item in matches:
        item["entry_id"] = item.get("entry_id") or item.get("case_id")
    return {
        "tool": "experience_rag_search",
        "target": agent,
        "status": "success" if matches else "no_match",
        "degraded": embed.get("status") != "success",
        "summary": f"命中 {len(matches)} 条个人经验库条目" if matches else "未命中个人经验库",
        "matches": matches,
        "embedding_model": embed.get("model"),
        "completed_at": _now(),
    }
