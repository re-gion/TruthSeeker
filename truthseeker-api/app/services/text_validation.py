"""Text evidence validation helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


TEXT_ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log"})
TEXT_SAMPLE_BYTES = 64 * 1024
TEXT_MAX_CONTROL_RATIO = float(os.environ.get("TEXT_MAX_CONTROL_RATIO", "0.02"))
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


def strip_null_bytes(value: Any) -> Any:
    """递归剥离字符串中的 NUL（U+0000）字符。

    Postgres 的 text/jsonb 均无法存储 \\u0000（错误码 22P05），一旦载荷里
    混入 NUL，整条 insert/update 会被拒绝。NUL 对检材文本、LLM 输出和
    外部工具结果都没有语义价值，这里在写入前统一移除。
    """
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {key: strip_null_bytes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_null_bytes(item) for item in value]
    return value


def _has_safe_text_extension(filename: str) -> bool:
    return Path(filename or "").suffix.lower() in TEXT_ALLOWED_EXTENSIONS


def _is_mostly_printable(text: str) -> bool:
    if not text:
        return True

    control_count = 0
    for char in text:
        codepoint = ord(char)
        if char in "\t\r\n":
            continue
        if codepoint < 32 or 127 <= codepoint <= 159:
            control_count += 1

    return (control_count / max(len(text), 1)) <= TEXT_MAX_CONTROL_RATIO


def decode_text_bytes(data: bytes, *, max_chars: int | None = None) -> dict[str, str]:
    """Decode uploaded text evidence with the supported encodings.

    Returns UTF-8-ready text plus the detected source encoding name.
    """
    last_error: UnicodeDecodeError | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            # NUL 在 Postgres 中不可存储（22P05），且对文本取证无语义，先剥离再截断
            text = data.decode(encoding).replace("\x00", "")
            if max_chars is not None:
                text = text[:max_chars]
            return {"text": text, "encoding": encoding, "charset": encoding}
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return {"text": "", "encoding": TEXT_ENCODINGS[0], "charset": TEXT_ENCODINGS[0]}


def validate_text_plain_file(path: str, filename: str) -> bool:
    """Reject binary files disguised as text/plain."""
    if not _has_safe_text_extension(filename):
        return False

    with open(path, "rb") as file_obj:
        sample = file_obj.read(TEXT_SAMPLE_BYTES)
    if not sample:
        return True
    if b"\x00" in sample:
        return False

    try:
        decoded = decode_text_bytes(sample)
    except UnicodeDecodeError:
        return False
    return _is_mostly_printable(decoded["text"])
