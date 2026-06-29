# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : registerQuestion_service.py
# @Desc      : 
# @Time      : 2025/12/3 01:26
# @Software  : PyCharm

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.db import SessionLocal
from src.models.register import Register
from src.models.register_question import RegisterQuestion


class RegisterQuestionService:
    """领卷登记问题服务类"""
    def __init__(self, db: Optional[Session] = None):
        """
        初始化
        :param db:
        """
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def batch_add(self, questions_list: List[Dict[str, Any]]) -> List[RegisterQuestion]:
        """
        批量插入
        :param questions_list:
        :return:
        """
        for question in questions_list:
            if "recorder_time" not in question:
                question["recorder_time"] = datetime.now()

        db_questions = [RegisterQuestion(**question) for question in questions_list]
        self.db.add_all(db_questions)
        self.db.commit()

        for question in db_questions:
            self.db.refresh(question)

        return db_questions

    def get_by_id(self, id: int) -> Optional[RegisterQuestion]:
        """
        根据 ID 查询单条登记记录
        :param id: 登记记录 ID
        :return: 找到的 RegisterQuestion 对象，未找到返回 None
        """
        return self.db.query(RegisterQuestion).filter(RegisterQuestion.id == id).first()

    def get_register_id(self, register_id: int) -> Optional[RegisterQuestion]:

        return self.db.query(RegisterQuestion).filter(RegisterQuestion.register_id == register_id).first()


    def get_list(self, register_id: Optional[int] = None, batch_number: Optional[str] = None, number_start:str = None, number_end:str = None) -> List[RegisterQuestion]:
        """
        :param register_id:
        :param batch_number:
        :param number_start:
        :param number_end:
        :return:
        """
        query = self.db.query(RegisterQuestion)

        if register_id:
            query = query.filter(RegisterQuestion.register_id == register_id)
        if batch_number:
            query = query.filter(RegisterQuestion.batch_number == batch_number)
        if number_start:
            query = query.filter(RegisterQuestion.number_start == number_start)
        if number_end:
            query = query.filter(RegisterQuestion.number_end == number_end)


        return query.all()

    def update(self, id, update_data: Dict[str, Any]) -> Optional[RegisterQuestion]:
        """
        更新
        :param id:
        :param update_data:
        :return:
        """
        db_question = self.get_by_id(id)
        if not db_question:
            return None

        for key, value in update_data.items():
            if hasattr(db_question, key):
                setattr(db_question, key, value)

        self.db.commit()
        self.db.refresh(db_question)
        return db_question

    def delete(self, id: int) -> bool:
        """
        根据 ID 删除
        :param id: 要删除的登记记录 ID
        :return: 删除成功返回 True，未找到返回 False
        """
        db_question = self.get_by_id(id)
        if not db_question:
            return False

        self.db.delete(db_question)
        self.db.commit()
        return True

    def get_data(self, where: Dict[str, Any] = None) -> List[RegisterQuestion]:
        return self.db.query(RegisterQuestion).filter_by(**where).all()

    def get_question(self, register_id: int, volume_number: str, recorder: str) -> RegisterQuestion:
        return (self.db.query(RegisterQuestion).
                filter(RegisterQuestion.register_id == register_id).
                filter(RegisterQuestion.volume_number == volume_number).
                filter(RegisterQuestion.recorder == recorder).first())

# 创建控制器实例（方便其他模块导入使用）
register_question_service = RegisterQuestionService()
