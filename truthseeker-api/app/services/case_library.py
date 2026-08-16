"""Public case library helpers."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.services.analysis_persistence import normalize_final_verdict
from app.services.input_types import canonical_input_type
from app.services.text_validation import strip_null_bytes

logger = logging.getLogger(__name__)

CASE_LIBRARY_STATUSES = {"published", "draft", "hidden"}
CASE_LIBRARY_CATEGORIES = {
    "text_generation",
    "image_forgery",
    "image_text_mixed",
    "audio_forgery",
    "video_forgery",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
SIGNED_URL_TOKEN_RE = re.compile(r"([?&](?:token|signature|expires|apikey|access_token)=)[^)\]\s&]+", re.IGNORECASE)
STORAGE_PATH_RE = re.compile(r"\b[a-zA-Z0-9_-]{6,}/tmp[a-zA-Z0-9_.-]+\b")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_case_prompt(case_prompt: str | None) -> str:
    return re.sub(r"\s+", " ", (case_prompt or "").strip())


def build_case_fingerprint(files: list[dict[str, Any]] | None, case_prompt: str | None) -> str:
    """Build global duplicate key from file hashes and normalized case prompt."""
    file_hashes = sorted(
        str(item.get("sha256") or "").strip().lower()
        for item in (files or [])
        if isinstance(item, dict) and str(item.get("sha256") or "").strip()
    )
    payload = {
        "file_hashes": file_hashes,
        "case_prompt": normalize_case_prompt(case_prompt),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def redact_public_text(value: str | None) -> str:
    text = value or ""
    text = EMAIL_RE.sub("[邮箱]", text)
    text = PHONE_RE.sub("[手机号]", text)
    text = ID_CARD_RE.sub("[身份证号]", text)
    text = SIGNED_URL_TOKEN_RE.sub(r"\1[已脱敏]", text)
    text = STORAGE_PATH_RE.sub("[存储路径]", text)
    return text


def _remove_public_key_evidence_sections(markdown: str) -> str:
    lines = (markdown or "").splitlines()
    result: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        is_heading = stripped.startswith("#")
        heading_text = stripped.lstrip("#").strip()
        if is_heading and "关键证据" in heading_text:
            skipping = True
            continue
        if skipping and is_heading:
            skipping = False
        if skipping:
            continue
        if not is_heading and stripped.startswith("关键证据"):
            continue
        result.append(line)
    return "\n".join(result).strip()


def redact_public_markdown(markdown: str | None) -> str:
    return _remove_public_key_evidence_sections(redact_public_text(markdown or ""))


def strip_public_key_evidence_sections(markdown: str | None) -> str:
    return redact_public_markdown(markdown)


def _metadata(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get("metadata") or {}
    return value if isinstance(value, dict) else {}


def _task_files(task: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = _metadata(task)
    raw_files = metadata.get("files") or (task.get("storage_paths") or {}).get("files") or []
    return [dict(item) for item in raw_files if isinstance(item, dict)]


def wants_public_case(task: dict[str, Any] | None) -> bool:
    if not task:
        return False
    metadata = _metadata(task)
    return bool(metadata.get("share_to_casebase"))


def _category_from_modalities(modalities: set[str]) -> str:
    """Map a modality set to a case category.

    Priority for mixed media is video > audio > image; ``image_text_mixed`` is
    reserved for image+text so that audio/video cases are never mislabeled as
    image-text.
    """
    non_text = modalities - {"text"}
    if not non_text:
        return "text_generation"
    if "video" in non_text:
        return "video_forgery"
    if "audio" in non_text:
        return "audio_forgery"
    if "text" in modalities:
        return "image_text_mixed"
    return "image_forgery"


def _derive_media_category(files: list[dict[str, Any]], input_type: str | None = None) -> str:
    modalities = {
        str(item.get("modality") or "").lower()
        for item in files
        if isinstance(item, dict) and item.get("modality")
    }
    if modalities:
        return _category_from_modalities(modalities)
    canonical = canonical_input_type(input_type)
    if not canonical:
        return "text_generation"
    return _category_from_modalities({token for token in canonical.split("_") if token})


def _difficulty(confidence: Any) -> str:
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        return "Medium"
    if score >= 0.85:
        return "High"
    if score >= 0.65:
        return "Medium"
    return "Low"


VERDICT_LABEL_MAP = {
    "forged": "确认伪造",
    "suspicious": "高度可疑",
    "authentic": "内容真实",
    "inconclusive": "无法判定",
}

CATEGORY_LABEL_MAP = {
    "text_generation": "文本生成",
    "image_forgery": "图像伪造",
    "image_text_mixed": "图文混合",
    "audio_forgery": "音频伪造",
    "video_forgery": "视频伪造",
}

# 类别名含"伪造"字样，用于"内容真实/无法判定"案例的兜底标题时需换成中性表述，
# 否则会拼出"图像伪造内容真实案例"这类自相矛盾的文案。
NEUTRAL_MEDIA_LABEL_MAP = {
    "text_generation": "文本检材",
    "image_forgery": "图像检材",
    "image_text_mixed": "图文检材",
    "audio_forgery": "音频检材",
    "video_forgery": "视频检材",
}


def _fallback_title_and_summary(
    verdict: str,
    media_category: str,
    confidence: float | None,
    difficulty: str,
    case_prompt: str | None = None,
) -> tuple[str, str]:
    """Deterministic title/summary.

    Deliberately grounded only in the verdict, media category, and confidence.
    We do NOT extract a "subject" from case_prompt (it is a detection request,
    not case facts), because doing so produced fabricated entities in titles.
    """
    verdict_label = VERDICT_LABEL_MAP.get(verdict, verdict)
    category_label = CATEGORY_LABEL_MAP.get(media_category, media_category)

    # 根据裁决结果和媒体类别决定标题。伪造/可疑用"类别+疑似"，真实/无法判定改用
    # 中性检材词，避免拼出"图像伪造内容真实案例"这类自相矛盾或重复的文案。
    if verdict in {"forged", "suspicious"}:
        if media_category in {"audio_forgery", "video_forgery"}:
            case_type = "疑似合成"
        elif media_category == "image_text_mixed":
            case_type = "疑似伪造"
        else:
            case_type = "疑似 AIGC"
        title = f"{category_label}{case_type}案例"
    else:
        neutral = NEUTRAL_MEDIA_LABEL_MAP.get(media_category, category_label)
        title = f"{neutral}真实性核验案例" if verdict == "authentic" else f"{neutral}研判案例"

    conf_text = f"{confidence * 100:.1f}%" if confidence is not None else "未知"
    summary = f"本案涉及{category_label}类型检材，研判结论为{verdict_label}，综合置信度 {conf_text}。"

    return title, summary


def _coerce_confidence(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_llm_json(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    payload = match.group(0) if match else text
    parsed = json.loads(payload)
    return parsed if isinstance(parsed, dict) else {}


URL_RE = re.compile(r"https?://[^\s)）\]】，。；、\"']+", re.IGNORECASE)
# 中文与字母数字之间不存在 \b 边界（Unicode 下汉字也是 \w），需用显式环视判定域名边界
DOMAIN_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9_-]+\.)+[a-zA-Z]{2,}(?![A-Za-z0-9_.-])")


EMPTY_QUOTES_RE = re.compile(r'""|\'\'|“”|‘’|「」')


def _clean_generated_public_text(value: Any, *, max_chars: int) -> str:
    text = redact_public_text(str(value or ""))
    # 公开案例标题/摘要中不允许出现任何网址或域名（包括钓鱼链接本身）
    text = URL_RE.sub("", text)
    text = DOMAIN_RE.sub("", text)
    # 清理域名/URL 被移除后残留的空引号对
    text = EMPTY_QUOTES_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def _collect_evidence_context(client: Any, task_id: Any) -> dict[str, Any]:
    """Best-effort extraction of grounded case facts from persisted agent snapshots.

    The reports row alone only carries scores/labels; the actual case narrative
    (text content, ASR transcripts, tool conclusions) lives in
    ``analysis_states.result_snapshot``. Returns {} on any failure so callers can
    degrade to the deterministic fallback path.
    """
    if not client or not task_id:
        return {}
    try:
        resp = (
            client.table("analysis_states")
            .select("result_snapshot")
            .eq("task_id", task_id)
            .order("created_at", desc=False)
            .limit(200)
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed to load analysis states for public case %s: %s", task_id, exc)
        return {}

    forensics: dict[str, Any] = {}
    osint: dict[str, Any] = {}
    for row in resp.data or []:
        snapshot = row.get("result_snapshot") if isinstance(row, dict) else None
        if not isinstance(snapshot, dict):
            continue
        if isinstance(snapshot.get("forensics"), dict):
            forensics = snapshot["forensics"]
        if isinstance(snapshot.get("osint"), dict):
            osint = snapshot["osint"]

    context: dict[str, Any] = {}
    forensics_analysis = str(forensics.get("llm_analysis") or "").strip()
    if forensics_analysis:
        context["forensics_analysis"] = redact_public_text(forensics_analysis)[:1600]
    transcripts = []
    for item in forensics.get("audio_transcripts") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            transcripts.append(redact_public_text(text)[:300])
    if transcripts:
        context["audio_transcripts"] = transcripts[:2]
    osint_analysis = str(osint.get("llm_analysis") or "").strip()
    if osint_analysis:
        context["osint_analysis"] = redact_public_text(osint_analysis)[:800]
    return context


async def generate_case_title_and_summary(
    task: dict[str, Any],
    report: dict[str, Any],
    llm: Any | None,
    *,
    client: Any | None = None,
) -> tuple[str, str]:
    """Generate a public-facing title and summary, with deterministic fallback."""
    verdict_payload = normalize_final_verdict(report.get("verdict_payload") or {})
    verdict = report.get("verdict") or verdict_payload.get("verdict") or "inconclusive"
    confidence = _coerce_confidence(report.get("confidence_overall", verdict_payload.get("confidence_overall")))
    files = _task_files(task)
    media_category = _derive_media_category(files, task.get("input_type"))
    difficulty = _difficulty(confidence)
    case_prompt = str(task.get("description") or _metadata(task).get("case_prompt") or "")
    fallback = _fallback_title_and_summary(verdict, media_category, confidence, difficulty, case_prompt)

    if llm is None:
        return fallback

    evidence_context = _collect_evidence_context(client, task.get("id"))
    file_descriptors = [
        {
            "id": f"file-{index}",
            "name": redact_public_text(str(item.get("name") or ""))[:120],
            "modality": item.get("modality") or "unknown",
            "mime_type": item.get("mime_type"),
            "size_bytes": item.get("size_bytes"),
        }
        for index, item in enumerate(files[:5], 1)
    ]
    prompt_payload = {
        "verdict": verdict,
        "verdict_label": VERDICT_LABEL_MAP.get(verdict, verdict),
        "confidence_overall": confidence,
        "media_category": media_category,
        "media_category_label": CATEGORY_LABEL_MAP.get(media_category, media_category),
        "files": file_descriptors,
        "case_request": redact_public_text(case_prompt)[:200],
        "evidence_context": evidence_context,
    }
    prompt = (
        "你是 TruthSeeker 的公开案例编辑。请基于输入生成适合公开案例库展示的标题和摘要。\n"
        "严格要求：\n"
        "1. 标题 10-24 个中文字符，摘要 50-120 个中文字符。\n"
        "2. evidence_context 是取证与情报溯源 Agent 的案情分析，是唯一案情事实来源；"
        "标题和摘要只能引用其中明确出现的主体、实体和情节。\n"
        "3. case_request 只是用户提交的检测诉求，不是案情事实，不得作为标题/摘要的内容来源。\n"
        "4. 禁止编造或脑补输入中不存在的主体与情节（如熟人、亲友、领导、转账等）；"
        "如果 evidence_context 中没有明确主体，标题改用“检材类型+研判结论”的客观描述。\n"
        "5. 摘要面向公众：说明检材类型、关键鉴定依据、研判结论和置信度，可附一句简短防范建议。\n"
        "6. 不得输出邮箱、手机号、身份证号、存储路径或签名 URL；"
        "不得引用任何网址或域名（包括涉案钓鱼域名本身，用“免费托管域名”等描述性说法代替），"
        "确保移除链接后句子依然通顺。\n"
        "只输出 JSON，格式为 {\"title\":\"...\",\"summary\":\"...\"}。\n"
        f"输入：{json.dumps(prompt_payload, ensure_ascii=False)}"
    )
    try:
        response = await llm.ainvoke(prompt)
        content = getattr(response, "content", response)
        parsed = _parse_llm_json(content)
        title = _clean_generated_public_text(parsed.get("title"), max_chars=120)
        summary = _clean_generated_public_text(parsed.get("summary"), max_chars=360)
        if title and summary:
            return title, summary
    except Exception as exc:
        logger.warning("Failed to generate public case title/summary by LLM: %s", exc)

    return fallback


def _safe_file_name(name: Any, index: int) -> str:
    raw = redact_public_text(str(name or f"检材 {index}")).strip()
    if not raw:
        return f"检材 {index}"
    return raw[:120]


def _public_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(files, 1):
        result.append(
            {
                "id": item.get("id") or f"file-{index}",
                "name": _safe_file_name(item.get("name"), index),
                "mime_type": item.get("mime_type"),
                "modality": item.get("modality"),
                "size_bytes": item.get("size_bytes"),
            }
        )
    return result


def _summary_from_report(report: dict[str, Any], verdict: dict[str, Any]) -> str:
    summary = report.get("summary") or verdict.get("analysis_summary") or verdict.get("llm_ruling") or ""
    return redact_public_text(str(summary)).strip()[:360]


def build_markdown_from_report_row(report: dict[str, Any]) -> str:
    verdict = normalize_final_verdict(report.get("verdict_payload") or {})
    lines = [
        "# 公开案例研判报告",
        "",
        f"- 裁决结果：{report.get('verdict') or verdict.get('verdict') or 'inconclusive'}",
    ]
    confidence = report.get("confidence_overall") or verdict.get("confidence_overall")
    safe_confidence = _coerce_confidence(confidence)
    if safe_confidence is not None:
        lines.append(f"- 综合置信度：{safe_confidence * 100:.1f}%")
    summary = report.get("summary") or verdict.get("analysis_summary")
    if summary:
        lines.extend(["", "## 摘要", str(summary)])
    recommendations = report.get("recommendations") or verdict.get("recommendations") or []
    if recommendations:
        lines.extend(["", "## 处置建议"])
        for item in recommendations:
            lines.append(f"- {item}")
    return redact_public_markdown("\n".join(lines))


def build_case_library_entry(
    task: dict[str, Any],
    report: dict[str, Any],
    report_markdown: str,
    *,
    public_title: str | None = None,
    public_summary: str | None = None,
) -> dict[str, Any]:
    files = _task_files(task)
    case_prompt = task.get("description") or _metadata(task).get("case_prompt") or ""
    verdict = normalize_final_verdict(report.get("verdict_payload") or {})
    confidence = report.get("confidence_overall", verdict.get("confidence_overall"))
    title = (
        redact_public_text(public_title).strip()[:120]
        if public_title
        else redact_public_text(str(task.get("title") or "未命名公开案例")).strip()[:120]
    ) or "未命名公开案例"
    summary = (
        redact_public_text(public_summary).strip()[:360]
        if public_summary
        else _summary_from_report(report, verdict)
    )
    public_files = _public_files(files)

    return {
        "task_id": task.get("id"),
        "user_id": task.get("user_id"),
        "status": "published",
        "title": title,
        "media_category": _derive_media_category(files, task.get("input_type")),
        "summary": summary,
        "verdict": report.get("verdict") or verdict.get("verdict") or "inconclusive",
        "confidence_overall": confidence,
        "difficulty": _difficulty(confidence),
        "public_files": public_files,
        "report_markdown": redact_public_markdown(report_markdown),
        "content_fingerprint": build_case_fingerprint(files, case_prompt),
        "published_at": utc_now_iso(),
    }


def find_duplicate_case(client: Any, files: list[dict[str, Any]] | None, case_prompt: str | None) -> dict[str, Any] | None:
    fingerprint = build_case_fingerprint(files, case_prompt)
    if not fingerprint:
        return None
    try:
        resp = (
            client.table("case_library_entries")
            .select("*")
            .eq("status", "published")
            .eq("content_fingerprint", fingerprint)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("Failed to check duplicate public case: %s", exc)
        return None


def public_case_duplicate_metadata(client: Any, files: list[dict[str, Any]] | None, case_prompt: str | None) -> dict[str, Any]:
    duplicate = find_duplicate_case(client, files, case_prompt)
    return {
        "casebase_duplicate": bool(duplicate),
        "casebase_duplicate_case_id": duplicate.get("id") if duplicate else None,
        "casebase_fingerprint": build_case_fingerprint(files, case_prompt),
    }


async def ensure_case_library_entry(
    client: Any,
    task: dict[str, Any] | None,
    report: dict[str, Any] | None,
    report_markdown: str | None = None,
    llm: Any | None = None,
) -> dict[str, Any]:
    """Create public case entry once, returning duplicate/skipped/created status."""
    if not wants_public_case(task):
        return {"status": "skipped", "reason": "not_requested", "entry": None}
    if not report:
        return {"status": "skipped", "reason": "missing_report", "entry": None}

    task = task or {}
    report = report or {}
    files = _task_files(task)
    case_prompt = task.get("description") or _metadata(task).get("case_prompt") or ""
    duplicate = find_duplicate_case(client, files, case_prompt)
    if duplicate:
        return {"status": "duplicate", "entry": duplicate}

    markdown = report_markdown if report_markdown is not None else build_markdown_from_report_row(report)
    title, summary = await generate_case_title_and_summary(task, report, llm, client=client)
    entry = build_case_library_entry(
        task,
        report,
        markdown,
        public_title=title,
        public_summary=summary,
    )
    try:
        # 标题/摘要含 LLM 输出，案情含检材文本；Postgres 不接受 U+0000（22P05）
        resp = client.table("case_library_entries").insert(strip_null_bytes(entry)).execute()
        created = resp.data[0] if resp.data else entry
        return {"status": "created", "entry": created}
    except Exception as exc:
        duplicate = find_duplicate_case(client, files, case_prompt)
        if duplicate:
            return {"status": "duplicate", "entry": duplicate}
        logger.error("Failed to create public case entry for task %s: %s", task.get("id"), exc)
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "entry": None}


def sanitize_case_for_response(row: dict[str, Any], *, include_report: bool = False) -> dict[str, Any]:
    public_files = []
    for item in row.get("public_files") or []:
        if not isinstance(item, dict):
            continue
        public_files.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "mime_type": item.get("mime_type"),
                "modality": item.get("modality"),
                "size_bytes": item.get("size_bytes"),
                "storage_path": None,
            }
        )
    payload = {
        "id": row.get("id"),
        "source_kind": row.get("source_kind") or "public",
        "task_id": row.get("task_id"),
        "title": row.get("title"),
        "media_category": row.get("media_category"),
        "summary": row.get("summary"),
        "verdict": row.get("verdict"),
        "confidence_overall": row.get("confidence_overall"),
        "difficulty": row.get("difficulty"),
        "public_files": public_files,
        "published_at": row.get("published_at"),
    }
    if include_report:
        payload["report_markdown"] = strip_public_key_evidence_sections(row.get("report_markdown") or "")
    return payload


def find_public_file(row: dict[str, Any], file_id: str) -> dict[str, Any] | None:
    for item in row.get("public_files") or []:
        if isinstance(item, dict) and str(item.get("id")) == str(file_id):
            return item
    return None
