# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : Result.py
# @Time     : 2026/6/1 9:25
# @Desc     : 


class Result:

    @staticmethod
    def success(code: int = 1, message:str = "操作成功", data: any = None):
        return {"code":code, "message":message, "data":data}

    @staticmethod
    def fail(code: int = -1, message:str = "操作失败"):
        return {"code":code, "message":message}
