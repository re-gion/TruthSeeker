"""Provenance graph builder for TruthSeeker OSINT and final reports."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


NODE_TYPES = {"artifact", "entity", "source", "evidence", "finding", "claim", "event", "agent", "verdict"}
EDGE_TYPES = {
    "extracted_from",
    "mentions",
    "derived_from",
    "supports",
    "refutes",
    "contradicts",
    "reviewed_by",
    "before",
    "after",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def _clamp_score(value: Any, fallback: float = 0.5) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return fallback


def _append_node(nodes: list[dict[str, Any]], seen: set[str], node: dict[str, Any]) -> None:
    node_type = node.get("type")
    if node_type not in NODE_TYPES:
        node["type"] = "entity"
    node_id = str(node.get("id") or _stable_id(str(node["type"]), node.get("label", "")))
    if node_id in seen:
        return
    node["id"] = node_id
    nodes.append(node)
    seen.add(node_id)


def _append_edge(edges: list[dict[str, Any]], seen: set[str], edge: dict[str, Any]) -> None:
    edge_type = edge.get("type")
    if edge_type not in EDGE_TYPES:
        edge["type"] = "derived_from"
    edge_id = str(edge.get("id") or _stable_id("edge", f"{edge.get('source')}:{edge.get('target')}:{edge['type']}"))
    if edge_id in seen:
        return
    edge["id"] = edge_id
    edges.append(edge)
    seen.add(edge_id)


def _evidence_file_label(item: dict[str, Any], index: int) -> str:
    return str(item.get("name") or item.get("storage_path") or f"检材 {index}")


def _append_citation(citations: list[dict[str, Any]], seen: set[str], citation: dict[str, Any]) -> str:
    citation_id = str(citation.get("id") or _stable_id("citation", citation))
    if citation_id in seen:
        return citation_id
    citation["id"] = citation_id
    citations.append(citation)
    seen.add(citation_id)
    return citation_id


def _build_file_citations(evidence_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    file_citation_ids: dict[str, str] = {}
    for index, item in enumerate(evidence_files or [], 1):
        file_id = str(item.get("id") or f"file-{index}")
        citation_id = f"file:{file_id}"
        _append_citation(citations, seen, {
            "id": citation_id,
            "source_kind": "uploaded_file",
            "source_name": "上传检材",
            "retrieved_at": _now(),
            "summary": _evidence_file_label(item, index),
            "file_hash": item.get("sha256") or item.get("hash"),
            "metadata": {
                "modality": item.get("modality"),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
                "storage_path": item.get("storage_path"),
            },
        })
        file_citation_ids[file_id] = citation_id
    return citations, file_citation_ids


def _tool_label(tool_result: dict[str, Any]) -> str:
    tool = str(tool_result.get("tool") or "tool")
    status = str(tool_result.get("status") or "unknown")
    return f"{tool} {status}"


def _tool_citation_id(tool_result: dict[str, Any]) -> str:
    return _stable_id(
        "tool",
        {
            "tool": tool_result.get("tool"),
            "target": tool_result.get("target"),
            "status": tool_result.get("status"),
            "summary": tool_result.get("summary"),
        },
    )


def _append_tool_result_citation(citations: list[dict[str, Any]], seen: set[str], tool_result: dict[str, Any]) -> str:
    tool = str(tool_result.get("tool") or "tool")
    return _append_citation(citations, seen, {
        "id": _tool_citation_id(tool_result),
        "source_kind": "tool_result",
        "source_name": tool,
        "retrieved_at": tool_result.get("retrieved_at") or _now(),
        "summary": tool_result.get("summary") or _tool_label(tool_result),
        "metadata": {
            "tool": tool,
            "target": tool_result.get("target"),
            "status": tool_result.get("status"),
            "confidence": tool_result.get("confidence"),
            "degraded": tool_result.get("degraded", False),
            "provider": (tool_result.get("result") or {}).get("provider") if isinstance(tool_result.get("result"), dict) else None,
        },
    })


def _rag_source_kind(tool_name: str, match: dict[str, Any]) -> str | None:
    explicit = str(match.get("source_kind") or "").strip().lower()
    if explicit in {"case_rag", "experience_rag"}:
        return explicit
    if tool_name == "case_rag_search":
        return "case_rag"
    if tool_name == "experience_rag_search":
        return "experience_rag"
    return None


def _append_rag_match_citations(
    citations: list[dict[str, Any]],
    seen: set[str],
    *,
    tool_name: str,
    matches: list[dict[str, Any]],
) -> list[str]:
    citation_ids: list[str] = []
    for index, match in enumerate(matches or [], 1):
        if not isinstance(match, dict):
            continue
        source_kind = _rag_source_kind(tool_name, match)
        if not source_kind:
            continue
        raw_id = (
            match.get("chunk_id")
            or match.get("case_id")
            or match.get("entry_id")
            or f"{tool_name}:{index}:{match.get('title')}"
        )
        citation_id = _stable_id(source_kind, raw_id)
        citation_ids.append(_append_citation(citations, seen, {
            "id": citation_id,
            "source_kind": source_kind,
            "source_name": match.get("title") or ("公开案例 RAG" if source_kind == "case_rag" else "个人经验 RAG"),
            "retrieved_at": match.get("retrieved_at") or _now(),
            "summary": match.get("snippet") or match.get("chunk_text") or match.get("summary") or "",
            "metadata": {
                "case_id": match.get("case_id"),
                "entry_id": match.get("entry_id"),
                "chunk_id": match.get("chunk_id"),
                "score": match.get("score", match.get("similarity")),
                "tool": tool_name,
            },
        }))
    return citation_ids


def _append_tool_finding(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
    seen_edges: set[str],
    citations: list[dict[str, Any]],
    seen_citations: set[str],
    tool_result: dict[str, Any],
    root_event_id: str,
    artifact_ref: str | None = None,
) -> list[str]:
    tool = str(tool_result.get("tool") or "tool")
    target = str(tool_result.get("target") or "")
    tool_citation_id = _append_tool_result_citation(citations, seen_citations, tool_result)
    rag_citation_ids = _append_rag_match_citations(
        citations,
        seen_citations,
        tool_name=tool,
        matches=[item for item in (tool_result.get("matches") or []) if isinstance(item, dict)],
    )
    citation_ids = [tool_citation_id, *rag_citation_ids]
    node_id = _stable_id("finding", f"{tool}:{target}:{tool_result.get('status')}")
    _append_node(nodes, seen_nodes, {
        "id": node_id,
        "type": "finding",
        "label": _tool_label(tool_result),
        "confidence": _clamp_score(tool_result.get("confidence"), 0.55),
        "citation_ids": citation_ids,
        "metadata": {
            "tool": tool,
            "status": tool_result.get("status"),
            "target": target,
            "summary": tool_result.get("summary"),
            "degraded": tool_result.get("degraded", False),
        },
    })
    _append_edge(edges, seen_edges, {
        "source": node_id,
        "target": artifact_ref or root_event_id,
        "type": "derived_from" if artifact_ref else "supports",
        "citation_ids": citation_ids,
        "model_inferred": False,
    })
    return citation_ids


def build_provenance_graph(
    *,
    task_id: str,
    evidence_files: list[dict[str, Any]] | None = None,
    forensics_result: dict[str, Any] | None = None,
    osint_result: dict[str, Any] | None = None,
    challenger_feedback: dict[str, Any] | None = None,
    final_verdict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a hybrid entity/PROV/claim-evidence-challenge graph.

    The graph intentionally allows model-inferred relationships, but every such edge
    is tagged with ``model_inferred=True`` so the UI cannot present it as external fact.
    """
    evidence_files = evidence_files or []
    forensics_result = forensics_result or {}
    osint_result = osint_result or {}
    challenger_feedback = challenger_feedback or {}
    final_verdict = final_verdict or {}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    citations, file_citation_ids = _build_file_citations(evidence_files)
    seen_citations: set[str] = {str(item.get("id")) for item in citations if item.get("id")}
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()

    root_event_id = f"event:{task_id}:analysis"
    _append_node(nodes, seen_nodes, {
        "id": root_event_id,
        "type": "event",
        "label": "TruthSeeker 分析任务",
        "confidence": 1.0,
        "metadata": {"task_id": task_id},
    })

    for index, item in enumerate(evidence_files, 1):
        file_id = str(item.get("id") or f"file-{index}")
        artifact_id = f"artifact:{file_id}"
        _append_node(nodes, seen_nodes, {
            "id": artifact_id,
            "type": "artifact",
            "label": _evidence_file_label(item, index),
            "confidence": 1.0,
            "citation_ids": [file_citation_ids.get(file_id)],
            "metadata": {
                "modality": item.get("modality"),
                "mime_type": item.get("mime_type"),
                "size_bytes": item.get("size_bytes"),
            },
        })
        _append_edge(edges, seen_edges, {
            "source": artifact_id,
            "target": root_event_id,
            "type": "extracted_from",
            "citation_ids": [file_citation_ids.get(file_id)],
            "model_inferred": False,
        })

    first_artifact_ref = None
    if evidence_files:
        first_artifact_ref = f"artifact:{evidence_files[0].get('id') or 'file-1'}"

    for tool_result in forensics_result.get("tool_results") or []:
        if not isinstance(tool_result, dict):
            continue
        _append_tool_finding(
            nodes=nodes,
            edges=edges,
            seen_nodes=seen_nodes,
            seen_edges=seen_edges,
            citations=citations,
            seen_citations=seen_citations,
            tool_result=tool_result,
            root_event_id=root_event_id,
            artifact_ref=first_artifact_ref,
        )

    for index, result in enumerate(osint_result.get("search_results") or [], 1):
        if not isinstance(result, dict):
            continue
        url = result.get("url") or f"osint-result-{index}"
        citation_id = _stable_id("url", url)
        _append_citation(citations, seen_citations, {
            "id": citation_id,
            "source_kind": "external_source",
            "source_name": result.get("title") or "Exa 搜索结果",
            "url": result.get("url"),
            "retrieved_at": result.get("retrieved_at") or _now(),
            "summary": result.get("summary") or result.get("text") or "",
        })
        source_id = _stable_id("source", url)
        _append_node(nodes, seen_nodes, {
            "id": source_id,
            "type": "source",
            "label": result.get("title") or str(url),
            "confidence": _clamp_score(result.get("score"), 0.6),
            "citation_ids": [citation_id],
            "metadata": {"url": result.get("url"), "published_date": result.get("published_date")},
        })
        _append_edge(edges, seen_edges, {
            "source": source_id,
            "target": root_event_id,
            "type": "mentions",
            "citation_ids": [citation_id],
            "model_inferred": False,
        })

    osint_tool_citation_ids: list[str] = []
    for tool_result in osint_result.get("tool_results") or []:
        if not isinstance(tool_result, dict):
            continue
        osint_tool_citation_ids.extend(_append_tool_finding(
            nodes=nodes,
            edges=edges,
            seen_nodes=seen_nodes,
            seen_edges=seen_edges,
            citations=citations,
            seen_citations=seen_citations,
            tool_result=tool_result,
            root_event_id=root_event_id,
        ))

    claim_seed = osint_result.get("model_claims") or []
    if not claim_seed:
        for indicator in (osint_result.get("threat_indicators") or [])[:5]:
            claim_seed.append({
                "label": str(indicator),
                "confidence": osint_result.get("confidence", 0.5),
                "citation_ids": [],
            })

    source_citation_ids = [
        cid
        for node in nodes
        if node.get("type") == "source"
        for cid in (node.get("citation_ids") or [])
        if cid
    ]
    fallback_claim_citation_ids = list(dict.fromkeys([
        *source_citation_ids,
        *osint_tool_citation_ids,
    ]))[:6]

    for index, claim in enumerate(claim_seed, 1):
        if not isinstance(claim, dict):
            continue
        label = str(claim.get("label") or claim.get("text") or f"模型声明 {index}")
        claim_id = str(claim.get("id") or _stable_id("claim", label))
        citation_ids = [cid for cid in claim.get("citation_ids", []) if cid] or fallback_claim_citation_ids
        model_inferred = len(citation_ids) == 0
        _append_node(nodes, seen_nodes, {
            "id": claim_id if claim_id.startswith("claim:") else f"claim:{claim_id}",
            "type": "claim",
            "label": label,
            "confidence": _clamp_score(claim.get("confidence"), 0.5),
            "citation_ids": citation_ids,
            "model_inferred": model_inferred,
        })
        source_candidates = [node["id"] for node in nodes if node.get("type") == "source"]
        source_id = source_candidates[0] if source_candidates else root_event_id
        _append_edge(edges, seen_edges, {
            "source": source_id,
            "target": claim_id if claim_id.startswith("claim:") else f"claim:{claim_id}",
            "type": "supports",
            "citation_ids": citation_ids,
            "model_inferred": model_inferred,
            "explanation": "无外部引用的声明来自模型综合推理" if model_inferred else "声明由外部来源支持",
        })

    challenger_id = "agent:challenger"
    _append_node(nodes, seen_nodes, {
        "id": challenger_id,
        "type": "agent",
        "label": "逻辑质询 Agent",
        "confidence": _clamp_score(challenger_feedback.get("quality_score"), 0.5),
    })
    for issue in challenger_feedback.get("issues_found") or []:
        if not isinstance(issue, dict):
            continue
        issue_id = _stable_id("claim", issue.get("description"))
        _append_node(nodes, seen_nodes, {
            "id": issue_id,
            "type": "claim",
            "label": issue.get("description") or issue.get("type") or "质询问题",
            "confidence": 0.6,
            "model_inferred": True,
            "metadata": {"severity": issue.get("severity"), "type": issue.get("type")},
        })
        _append_edge(edges, seen_edges, {
            "source": issue_id,
            "target": challenger_id,
            "type": "reviewed_by",
            "model_inferred": True,
        })

    if final_verdict:
        verdict_id = "verdict:final"
        _append_node(nodes, seen_nodes, {
            "id": verdict_id,
            "type": "verdict",
            "label": final_verdict.get("verdict_cn") or final_verdict.get("verdict") or "最终裁决",
            "confidence": _clamp_score(final_verdict.get("confidence"), 0.5),
            "metadata": {"verdict": final_verdict.get("verdict")},
        })
        _append_edge(edges, seen_edges, {
            "source": challenger_id,
            "target": verdict_id,
            "type": "reviewed_by",
            "model_inferred": False,
        })

    cited_edges = [edge for edge in edges if edge.get("citation_ids")]
    model_edges = [edge for edge in edges if edge.get("model_inferred")]
    quality = {
        "completeness": _clamp_score(min(1.0, (len(nodes) + len(edges)) / 12.0), 0.0),
        "citation_coverage": round(len(cited_edges) / max(1, len(edges)), 4),
        "model_inferred_ratio": round(len(model_edges) / max(1, len(edges)), 4),
        "model_inferred_edges": len(model_edges),
        "challenger_quality_score": _clamp_score(challenger_feedback.get("quality_score"), 0.0),
        "review": {
            "issue_count": challenger_feedback.get("issue_count", 0),
            "high_severity_count": challenger_feedback.get("high_severity_count", 0),
        },
    }

    return {
        "schema_version": "truthseeker.provenance_graph.v1",
        "task_id": task_id,
        "nodes": nodes,
        "edges": edges,
        "citations": citations,
        "quality": quality,
        "generated_at": _now(),
    }
