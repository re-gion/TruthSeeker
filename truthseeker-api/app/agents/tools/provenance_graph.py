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


def _build_file_citations(evidence_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    citations: list[dict[str, Any]] = []
    file_citation_ids: dict[str, str] = {}
    for index, item in enumerate(evidence_files or [], 1):
        file_id = str(item.get("id") or f"file-{index}")
        citation_id = f"file:{file_id}"
        citations.append({
            "id": citation_id,
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

    for tool_result in forensics_result.get("tool_results") or []:
        if not isinstance(tool_result, dict):
            continue
        tool = tool_result.get("tool", "tool")
        target = tool_result.get("target", "")
        node_id = _stable_id("finding", f"{tool}:{target}:{tool_result.get('status')}")
        _append_node(nodes, seen_nodes, {
            "id": node_id,
            "type": "finding",
            "label": f"{tool} {tool_result.get('status', 'unknown')}",
            "confidence": _clamp_score(tool_result.get("confidence"), 0.55),
            "metadata": {
                "tool": tool,
                "status": tool_result.get("status"),
                "target": target,
                "summary": tool_result.get("summary"),
                "degraded": tool_result.get("degraded", False),
            },
        })
        if evidence_files:
            artifact_ref = f"artifact:{evidence_files[0].get('id') or 'file-1'}"
            _append_edge(edges, seen_edges, {
                "source": node_id,
                "target": artifact_ref,
                "type": "derived_from",
                "model_inferred": False,
            })

    for index, result in enumerate(osint_result.get("search_results") or [], 1):
        if not isinstance(result, dict):
            continue
        url = result.get("url") or f"osint-result-{index}"
        citation_id = _stable_id("url", url)
        citations.append({
            "id": citation_id,
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

    claim_seed = osint_result.get("model_claims") or []
    if not claim_seed:
        for indicator in (osint_result.get("threat_indicators") or [])[:5]:
            claim_seed.append({
                "label": str(indicator),
                "confidence": osint_result.get("confidence", 0.5),
                "citation_ids": [],
            })

    for index, claim in enumerate(claim_seed, 1):
        if not isinstance(claim, dict):
            continue
        label = str(claim.get("label") or claim.get("text") or f"模型声明 {index}")
        claim_id = str(claim.get("id") or _stable_id("claim", label))
        citation_ids = [cid for cid in claim.get("citation_ids", []) if cid]
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
