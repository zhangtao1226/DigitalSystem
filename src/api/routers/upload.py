# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : upload.py
# @Time     : 2026/4/20 9:35
# @Desc     : 上传文件

import os
import uuid
import mimetypes
from pathlib import Path
from pydoc import describe
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import unquote

from fastapi.responses import FileResponse
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Form

from src.core.settings import settings
from src.utils.LoggerDetector import logger


ALLOWED_MIME_TYPES = [
    "image/png",
    "image/jpg",
    "image/jpeg",
    "image/bmp",
    "image/tiff",
]

MAX_FILE_SIZE = 1024 * 1024 * 20

if len(os.getenv("SERVICER_SAVE_PATH")) == 0:
    UPLOAD_DIR = settings.server_save_path
else:
    UPLOAD_DIR = os.getenv("SERVICER_SAVE_PATH")

router = APIRouter()

def _validate_image(file: UploadFile) -> str:
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件类型: {mime}",
        )

    ext = mimetypes.guess_extension(mime) or Path(file.filename or "img").suffix
    if ext in (".jpe", "jfif"):
        ext = ".jpg"

    return ext

def _build_save_path(image_name, target_path) -> Path:
    date_dir = Path(UPLOAD_DIR) / target_path
    date_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date_dir}/{image_name}"
    return date_dir / filename


@router.post("/image", summary="上传单个图片")
async def upload_image(file: UploadFile = File(...), target_path: str = Form(None)):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大({len(content) / 1024 /1024:.1f}MB), 最大允许 20MB"
        )
    save_path = _build_save_path(file.filename, target_path)
    save_path.write_bytes(content)
    logger.info(f"[API-上传图片] file: {file.filename}, target_path: {target_path}")
    return {
        "code": 0,
        "message": "上传成功",
        "data": {
            "original_filename": file.filename,
            "file_path": str(save_path)
        }
    }

@router.post("/images/batch", summary="批量上传图片")
async def upload_images_batch(files: list[UploadFile] = File(...), target_path: str = Form(None)):
    results = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"{file.filename} 文件过大 ({len(content) / 1024 /1024:.1f}MB)"
                )
            save_path = _build_save_path(file.filename, target_path)
            save_path.write_bytes(content)
            results.append({
                "original_filename": file.filename,
                "file_path": str(save_path),
                "save_path": str(save_path)
            })
        except HTTPException as e:
            errors.append({"filename": file.filename, "error": e.detail})

    return {
        "code": 0,
        "message": f"成功上传 {len(results)} 张, 失败 ({len(errors)})",
        "data":{
            "success": results,
            "failed": errors
        }
    }

@router.get("/image/view/{file_path:path}", summary="预览 / 下载已上传图片")
async def view_image(file_path: str):
    print(f"file_path: {file_path}")
    file_path = unquote(file_path)
    normalized_path = os.path.normpath(file_path)
    print(f"file_path: {normalized_path}")
    if not normalized_path.exists() or not normalized_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")

    if not os.path.isabs(normalized_path):
        raise HTTPException(status_code=400, detail="必须提供绝对路径")

    return FileResponse(
        path=normalized_path,
        filename=os.path.basename(normalized_path)
    )

@router.delete("/image", summary="删除已上传图片")
async def delete_image(file_path: str = Query(..., description="上传接口返回的 file_path 字段值")):
    target = Path(file_path)

    try:
        target.resolve()
    except ValueError:
        raise HTTPException(status_code=403, detail="非法路径, 只能删除上传目录内的文件")

    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    target.unlink()
    return {
        "code": 0,
        "message": "删除成功",
        "data": {
            "file_path": file_path
        }
    }


