# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : task_progress_service.py
# @Time     : 2026/4/22 16:18
# @Desc     : 
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import asc, desc, func

from src.core.db import SessionLocal
from src.models.task_progress import TaskProgress


class TaskProgressService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def add_record(self, data: Dict[str, Any]) -> Optional[TaskProgress]:
        record = TaskProgress(
            task_id = data["task_id"],
            sub_start = data["sub_start"],
            sub_end = data["sub_end"],
            status = data["status"],
            operator = data["operator"],
            operate_date = datetime.now()
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_data(self, where: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.db.query(TaskProgress).filter_by(**where).all()

    def get_by_id(self, id: int) -> Optional[TaskProgress]:
        return self.db.query(TaskProgress).filter(TaskProgress.id == id).first()

    def update_record(self, id: int, update_data: Dict[str, Any]) -> TaskProgress:
        record = self.get_by_id(id)

        if not record:
            return None

        for key, value in update_data.items():
            if hasattr(record, key):
                setattr(record, key, value)

        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_record(self, id: int) -> Optional[TaskProgress]:
        db_record = self.get_by_id(id)
        if not db_record:
            return False

        self.db.delete(db_record)
        self.db.commit()
        return True

task_progress_service = TaskProgressService()