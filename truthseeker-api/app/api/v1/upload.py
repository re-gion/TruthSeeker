"""文件上传端点 - 接收文件并存储到 Supabase Storage"""
import uuid
import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional
from app.utils.supabase_client import supabase
from app.config import settings

router = APIRouter()

ALLOWED_MIME = {
    "video/mp4", "video/webm",
    "audio/mpeg", "audio/wav",
    "image/jpeg", "image/png", "image/webp",
    "text/plain",
}
MAX_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
):
    """上传媒体文件到 Supabase Storage，返回可访问 URL"""
    # 验证 MIME 类型
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型: {content_type}")

    # 读取文件内容
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过 500MB 限制")

    # 构建存储路径: {user_id_or_anon}/{uuid}.{ext}
    ext = (file.filename or "file").rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    folder = user_id or "anon"
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
    except Exception:
        file_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/media/{storage_path}"

    return {
        "file_url": file_url,
        "storage_path": storage_path,
        "content_type": content_type,
        "size": len(content),
    }
