"""文件上传端点 - 接收文件并存储到 Supabase Storage"""
import uuid
import re
import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional
from app.utils.supabase_client import supabase
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_MIME = {
    "video/mp4", "video/webm",
    "audio/mpeg", "audio/wav",
    "image/jpeg", "image/png", "image/webp",
    "text/plain",
}
MAX_SIZE = 500 * 1024 * 1024  # 500MB
CHUNK_SIZE = 1 * 1024 * 1024  # 1MB


def _sanitize_folder(user_id: Optional[str]) -> str:
    """验证并清理 user_id，防止路径遍历攻击"""
    if not user_id:
        return "anon"
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', user_id):
        raise HTTPException(status_code=400, detail="无效的 user_id 格式")
    return user_id


def _safe_ext(filename: Optional[str]) -> str:
    """从文件名安全提取扩展名，只保留字母数字"""
    raw_ext = os.path.splitext(filename or "")[1].lstrip(".")
    return re.sub(r'[^a-zA-Z0-9]', '', raw_ext)[:10] or "bin"


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
):
    """上传媒体文件到 Supabase Storage，返回可访问 URL"""
    # 验证 MIME 类型（基于客户端声明，服务端白名单过滤）
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型: {content_type}")

    # 分块读取，防止 OOM
    chunks = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(status_code=413, detail="文件大小超过 500MB 限制")
        chunks.append(chunk)
    content = b"".join(chunks)

    # 构建存储路径（sanitized）
    folder = _sanitize_folder(user_id)
    ext = _safe_ext(file.filename)
    storage_path = f"{folder}/{uuid.uuid4()}.{ext}"

    try:
        supabase.storage.from_("media").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"存储上传失败: {str(e)}")

    # 生成签名 URL（1小时有效）
    try:
        signed = supabase.storage.from_("media").create_signed_url(storage_path, 3600)
        file_url = signed["signedURL"]
    except Exception as e:
        logger.warning("签名 URL 生成失败，降级为公开 URL: %s", e)
        file_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/media/{storage_path}"

    return {
        "file_url": file_url,
        "storage_path": storage_path,
        "content_type": content_type,
        "size": total,
    }
