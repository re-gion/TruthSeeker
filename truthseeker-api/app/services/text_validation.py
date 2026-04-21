"""Text evidence validation helpers."""
from __future__ import annotations

from pathlib import Path


TEXT_ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log"})
TEXT_SAMPLE_BYTES = 64 * 1024
TEXT_MAX_CONTROL_RATIO = 0.02
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


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

    for encoding in TEXT_ENCODINGS:
        try:
            text = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        return _is_mostly_printable(text)

    return False
