"""Report hashing helpers for tamper-evident outputs."""
from __future__ import annotations

import hashlib
import json
from typing import Any


SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "file_url",
    "file_urls",
    "invite_token",
    "raw_result",
    "refresh_token",
    "share_token",
    "signed_url",
    "signedurl",
    "token",
}

HASH_FIELDS = (
    "task_id",
    "verdict",
    "confidence_overall",
    "summary",
    "key_evidence",
    "recommendations",
    "verdict_payload",
    "generated_at",
    "share_token",
)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_KEYS:
                continue
            clean[str(key)] = _sanitize(item)
        return clean
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def build_report_hash(report_row: dict[str, Any]) -> str:
    canonical = {field: _sanitize(report_row.get(field)) for field in HASH_FIELDS}
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
