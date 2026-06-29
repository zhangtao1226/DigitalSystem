# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : ocr.py
# @Time     : 2026/4/20 10:56
# @Desc     : 
import os
import re
import time

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from src.core.settings import settings


router = APIRouter()

ocr_detector = None

def get_detector():
    global ocr_detector
    if ocr_detector is None:
        from src.utils.OCRDetector import OCRDetector
        ocr_detector = OCRDetector()
    return ocr_detector

@router.post("/", summary="OCR_API")
async def ocr(file:UploadFile = File(...), is_save:bool = False):
    result_payload = {
        "code": 200,
        "message": "success",
        "rec_texts": "",
        "file_json": None
    }

    content = await file.read()
    print("接收到内容：", len(content))

    if len(content) > settings.max_file_size:
        raise HTTPException(status_code=413, detail=f"文件过大({len(content) / 1024 /1024:.1f}MB), 最大允许 20MB")

    if len(content) == 0:
        raise HTTPException(status_code=413, detail=f"文件为空")


    # 根据OCR上传的文件， 找到服务器中对应的文件
    save_path = Path(settings.temp_path) / file.filename
    save_path.write_bytes(content)

    ocr_detector = get_detector()
    print(f"save_path: {save_path}")

    rec_texts = ocr_detector.detect(image=save_path, res_save=is_save)
    print(f"rec_texts", rec_texts)

    if rec_texts is not None:
        result_payload["rec_texts"] = rec_texts
        print(result_payload)

    if is_save:
        save_json_file = save_path.with_suffix(".json")
        print(f"save_json_file={save_json_file}")
        result_payload["file_json"] = save_json_file


    return result_payload














