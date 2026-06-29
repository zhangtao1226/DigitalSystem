# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : ResponseDetector.py
# @Time     : 2026/5/6 9:36
# @Desc     : 
from typing import Any, Optional, Dict, List, Generic, TypeVar
from schemas.ResponseModel import BaseResponse, ErrorResponse

class ResponseDetector:

    @staticmethod
    def success(data: Any = None, message: str = None) -> BaseResponse:
        return BaseResponse(code=200, message=message, data=data)

    @staticmethod
    def error(code: int = 400, message: str = 'error', details: Any = None) -> ErrorResponse:
        return ErrorResponse(code=code, message=message, details=details)