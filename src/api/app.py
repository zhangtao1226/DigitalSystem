# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : app.py
# @Time     : 2026/4/20 9:21
# @Desc     : 服务APP

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        tittle="服务API",
        version="1.0.0",
        description= "智能OCR档案数字化加工管理系统"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    from src.api.routers import health, upload
    app.include_router(health.router, prefix="/api/v1", tags=["服务API检查"])
    app.include_router(upload.router, prefix="/api/v1/upload", tags=["上传文件"])
    # app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["OCR识别"])


    return app
