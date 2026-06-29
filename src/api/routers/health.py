# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : health.py
# @Time     : 2026/4/20 9:26
# @Desc     : 
from fastapi import APIRouter

router = APIRouter()

@router.get("/health", summary="Health check")
async def health_check():
    return {"status": "ok", "service": "智能OCR档案数字化加工管理系统"}

if __name__ == "__main__":
    pass
