"""Canonical input type values, display labels, and chart colors."""
from __future__ import annotations

MODALITY_ORDER = ("text", "image", "audio", "video")
MODALITY_LABELS = {
    "text": "文本",
    "image": "图像",
    "audio": "音频",
    "video": "视频",
}

INPUT_TYPE_VALUES = (
    "text",
    "image",
    "audio",
    "video",
    "text_image",
    "text_audio",
    "text_video",
    "image_audio",
    "image_video",
    "audio_video",
    "text_image_audio",
    "text_image_video",
    "text_audio_video",
    "image_audio_video",
    "text_image_audio_video",
)

INPUT_TYPE_LABELS = {
    "text": "文本内容",
    "image": "图像内容",
    "audio": "音频内容",
    "video": "视频内容",
    "text_image": "图文混合",
    "text_audio": "文本+音频",
    "text_video": "文本+视频",
    "image_audio": "图像+音频",
    "image_video": "图像+视频",
    "audio_video": "音频+视频",
    "text_image_audio": "文本+图像+音频",
    "text_image_video": "文本+图像+视频",
    "text_audio_video": "文本+音频+视频",
    "image_audio_video": "图像+音频+视频",
    "text_image_audio_video": "文本+图像+音频+视频",
}

LEGACY_INPUT_TYPE_ALIASES = {
    "mixed": "text_image",
    "image_text": "text_image",
    "image_text_mixed": "text_image",
}

INPUT_TYPE_COLORS = {
    "text": "#22C55E",
    "image": "#61D4FF",
    "audio": "#D4FF3C",
    "video": "#FF8A5B",
    "text_image": "#0EA5E9",
    "text_audio": "#84CC16",
    "text_video": "#14B8A6",
    "image_audio": "#A3E635",
    "image_video": "#F97316",
    "audio_video": "#FACC15",
    "text_image_audio": "#8B5CF6",
    "text_image_video": "#EC4899",
    "text_audio_video": "#10B981",
    "image_audio_video": "#F59E0B",
    "text_image_audio_video": "#F43F5E",
}


def canonical_input_type(value: str | None) -> str:
    raw = (value or "").strip().lower().replace(" ", "").replace("-", "_")
    normalized = LEGACY_INPUT_TYPE_ALIASES.get(raw, raw)
    return normalized if normalized in INPUT_TYPE_LABELS else ""


def derive_input_type_from_modalities(modalities: set[str]) -> str:
    ordered = [item for item in MODALITY_ORDER if item in modalities]
    return "_".join(ordered) if ordered else "unknown"


def display_input_type(value: str | None) -> str:
    normalized = canonical_input_type(value)
    if not normalized:
        return (value or "").strip() or "未分类"
    return INPUT_TYPE_LABELS[normalized]


def input_type_color(value: str | None) -> str:
    normalized = canonical_input_type(value)
    return INPUT_TYPE_COLORS.get(normalized, "#7A77FF")
