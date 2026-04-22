"""Evidence file normalization and routing helpers."""
from __future__ import annotations

from typing import Any, Literal, TypedDict


MAX_EVIDENCE_FILES = 5

# Per-type limits (aligned with Reality Defender API)
_SIZE_LIMITS = {
    "image": 50 * 1024 * 1024,    # 50 MB
    "audio": 20 * 1024 * 1024,    # 20 MB
    "video": 250 * 1024 * 1024,   # 250 MB
    "text": 5 * 1024 * 1024,      # 5 MB
}
MAX_EVIDENCE_FILE_SIZE = 250 * 1024 * 1024  # global upper bound

EvidenceModality = Literal["video", "audio", "image", "text"]


class UploadedEvidenceFile(TypedDict, total=False):
    id: str
    name: str
    mime_type: str
    size_bytes: int
    modality: EvidenceModality
    storage_path: str
    file_url: str


def infer_modality(mime_type: str, name: str = "") -> EvidenceModality:
    normalized = (mime_type or "").lower()
    filename = name.lower()

    if normalized.startswith("video/"):
        return "video"
    if normalized.startswith("audio/"):
        return "audio"
    if normalized.startswith("image/"):
        return "image"
    if normalized == "text/plain" or filename.endswith(".txt"):
        return "text"

    raise ValueError(f"Unsupported evidence file type: {mime_type or name}")


def normalize_uploaded_files(raw_files: list[dict[str, Any]] | None) -> list[UploadedEvidenceFile]:
    files = raw_files or []
    if len(files) > MAX_EVIDENCE_FILES:
        raise ValueError(f"最多支持 {MAX_EVIDENCE_FILES} 个检材文件")

    normalized: list[UploadedEvidenceFile] = []
    for index, item in enumerate(files, start=1):
        name = str(item.get("name") or item.get("filename") or f"file-{index}").strip()
        mime_type = str(item.get("mime_type") or item.get("mimeType") or item.get("content_type") or "").strip()
        size_bytes = int(item.get("size_bytes") or item.get("size") or 0)
        modality_val = item.get("modality") or infer_modality(mime_type, name)
        size_limit = _SIZE_LIMITS.get(modality_val, MAX_EVIDENCE_FILE_SIZE)
        if size_bytes > size_limit:
            limit_mb = size_limit // (1024 * 1024)
            raise ValueError(f"{name} 超过 {limit_mb}MB（{modality_val} 类型上限）")

        storage_path = str(item.get("storage_path") or item.get("storagePath") or "").strip()
        file_url = str(item.get("file_url") or item.get("fileUrl") or "").strip()
        modality = modality_val

        normalized_item: UploadedEvidenceFile = {
            "id": str(item.get("id") or f"file-{index}"),
            "name": name,
            "mime_type": mime_type,
            "size_bytes": max(size_bytes, 0),
            "modality": modality,  # type: ignore[typeddict-item]
            "storage_path": storage_path,
        }
        if file_url:
            normalized_item["file_url"] = file_url
        normalized.append(normalized_item)

    return normalized


def require_evidence_files(files: list[UploadedEvidenceFile]) -> bool:
    return len(files) > 0


def derive_input_type(files: list[UploadedEvidenceFile]) -> str:
    modalities = {item["modality"] for item in files}
    if len(modalities) == 1:
        return next(iter(modalities))
    return "mixed"


def build_agent_file_views(files: list[UploadedEvidenceFile]) -> dict[str, Any]:
    media_files = [item for item in files if item["modality"] in ("video", "audio", "image")]
    text_files = [item for item in files if item["modality"] == "text"]

    return {
        "forensics": media_files,
        "osint": text_files + media_files,
        "primary_forensics": media_files[0] if media_files else None,
        "primary_osint": text_files[0] if text_files else (media_files[0] if media_files else None),
    }


def build_input_files(files: list[UploadedEvidenceFile]) -> dict[str, Any]:
    views = build_agent_file_views(files)
    primary = views["primary_forensics"] or views["primary_osint"]
    primary_url = primary.get("file_url") or primary.get("storage_path") if primary else "mock://default"

    return {
        "primary": primary_url,
        "files": files,
        "forensics": views["forensics"],
        "osint": views["osint"],
    }
