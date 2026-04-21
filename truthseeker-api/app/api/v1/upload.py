"""文件上传端点 — Supabase Storage + 签名 URL"""
import logging
import os
import re
import tempfile
from pathlib import Path

import filetype
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.services.audit_log import record_audit_event
from app.services.evidence_files import infer_modality
from app.services.text_validation import validate_text_plain_file

logger = logging.getLogger(__name__)

router = APIRouter()
supabase = None


def _get_supabase():
    global supabase
    if supabase is None:
        from app.utils.supabase_client import supabase as active_supabase

        supabase = active_supabase
    return supabase

# 安全：MIME 白名单（不可变集合）
ALLOWED_MIME = frozenset({
    "video/mp4", "video/webm",
    "audio/mpeg", "audio/wav",
    "image/jpeg", "image/png", "image/webp",
    "text/plain",
})

# Magic bytes → 真实 MIME 映射（仅校验二进制格式，text/plain 无固定 magic）
MAGIC_MIME_MAP: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"RIFF": "audio/wav",       # RIFF...WAVE
    b"\x1a\x45\xdf\xa5": "video/webm",  # EBML/Matroska/WebM
}


def _magic_mime(header: bytes) -> str | None:
    """通过文件头 magic bytes 推断真实 MIME 类型"""
    for magic, mime in MAGIC_MIME_MAP.items():
        if header.startswith(magic):
            return mime
    return None


def _sanitize_folder(name: str) -> str:
    """清理 user_id 防止路径穿越，未认证用户使用 anon 以匹配 RLS 策略"""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    if not clean or len(clean) > 64 or clean == "anonymous":
        return "anon"
    return clean


def _safe_ext(filename: str) -> str:
    """提取安全文件扩展名"""
    raw_ext = Path(filename).suffix.lstrip(".")
    safe = re.sub(r"[^a-zA-Z0-9]", "", raw_ext)[:10]
    return safe or "bin"


def _verify_file_type(tmp_path: str, declared_mime: str, filename: str = "") -> str | None:
    """
    校验文件真实类型。优先用 filetype 库，回退到 magic bytes。
    返回真实 MIME，若不匹配白名单则返回 None。
    """
    # filetype 库仅读取头部，不会加载整个文件
    kind = filetype.guess(tmp_path)
    if kind is not None:
        return kind.mime if kind.mime in ALLOWED_MIME else None

    # 回退：手动 magic bytes 检测
    with open(tmp_path, "rb") as f:
        header = f.read(32)
    if not header:
        # 空文件 — 仅允许 text/plain
        return "text/plain" if declared_mime == "text/plain" and validate_text_plain_file(tmp_path, filename) else None

    detected = _magic_mime(header)
    if detected:
        return detected if detected in ALLOWED_MIME else None

    # 无法识别的二进制文件 — 拒绝
    if declared_mime == "text/plain":
        return "text/plain" if validate_text_plain_file(tmp_path, filename) else None

    return None


MAX_SIZE = 500 * 1024 * 1024  # 500 MB


@router.post("/")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
):
    # 1. 客户端声明 MIME 校验
    if file.content_type not in ALLOWED_MIME:
        return JSONResponse(
            {"detail": f"不支持的文件类型：{file.content_type}"},
            status_code=400,
        )

    # 2. 写入临时文件（流式，内存友好）
    request_user_id = getattr(request.state, "user_id", None)
    effective_user_id = request_user_id or "anonymous"
    folder = _sanitize_folder(effective_user_id)
    ext = _safe_ext(file.filename or "upload")
    tmp_path: str | None = None

    try:
        total = 0
        with tempfile.NamedTemporaryFile(
            suffix=f".{ext}", delete=False, dir=tempfile.gettempdir(),
        ) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SIZE:
                    # 超限立即中止
                    os.unlink(tmp_path)
                    tmp_path = None
                    return JSONResponse(
                        {"detail": "文件大小不能超过 500MB"},
                        status_code=400,
                    )
                tmp.write(chunk)

        # 3. Magic bytes 校验（U-1 修复）
        real_mime = _verify_file_type(tmp_path, file.content_type, file.filename or "upload")
        if real_mime is None:
            logger.warning(
                "File type mismatch: declared=%s, real=unknown, user=%s",
                file.content_type, folder,
            )
            return JSONResponse(
                {"detail": "文件真实类型与声明不符或不被支持"},
                status_code=400,
            )

        # 4. 上传到 Supabase Storage
        from storage3.types import FileOptions

        storage_path = f"{folder}/{os.path.basename(tmp_path)}"
        with open(tmp_path, "rb") as f:
            _get_supabase().storage.from_("media").upload(
                storage_path, f, file_options=FileOptions(content_type=real_mime),
            )

        # 5. 生成签名 URL（有效 24 小时，U-5 修复）
        try:
            signed = _get_supabase().storage.from_("media").create_signed_url(
                storage_path, 86400,
            )
            file_url = signed.get("signedURL") or signed.get("signedUrl")
            if not file_url:
                raise ValueError("Empty signed URL response")
        except Exception as e:
            logger.error("Failed to create signed URL: %s", e)
            return JSONResponse(
                {"detail": "文件已存储但无法生成访问链接，请稍后重试"},
                status_code=500,
            )

        modality = infer_modality(real_mime, file.filename or "upload")
        record_audit_event(
            action="upload",
            user_id=effective_user_id,
            metadata={
                "name": file.filename,
                "mime_type": real_mime,
                "size_bytes": total,
                "modality": modality,
                "storage_path": storage_path,
            },
        )

        return {
            "id": os.path.basename(storage_path),
            "name": file.filename or os.path.basename(storage_path),
            "mime_type": real_mime,
            "size_bytes": total,
            "modality": modality,
            "file_url": file_url,
            "storage_path": storage_path,
        }

    except Exception as e:
        logger.error("Upload failed: %s", e)
        # U-6 修复：不泄露内部错误
        return JSONResponse(
            {"detail": "文件上传失败，请稍后重试"},
            status_code=500,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
