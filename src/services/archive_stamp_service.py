# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : archive_stamp_service.py
# @Time     : 2026/5/12 15:23
# @Desc     : 

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import asc, desc
from datetime import datetime
from typing import List, Optional, Dict, Any


from src.core.db import SessionLocal
from src.models.archive_stamp import ArchiveStamp



class ArchiveStampService:

    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())


    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_all(self) -> list[ArchiveStamp]:
         return self.db.query(ArchiveStamp).order_by(ArchiveStamp.id.desc()).all()

    def create(self, data: dict) -> ArchiveStamp:

        insert_data = dict()
        for key, value in data.items():
            if hasattr(ArchiveStamp, key):
                insert_data[key] = value

        db_data = ArchiveStamp(**insert_data)
        self.db.add(db_data)
        self.db.commit()
        self.db.refresh(db_data)
        return db_data

    def get_by_id(self, id: int) -> ArchiveStamp:
        return self.db.query(ArchiveStamp).filter(ArchiveStamp.id == id).first()

    def get_by_name(self, name: str) -> ArchiveStamp:
        return self.db.query(ArchiveStamp).filter(ArchiveStamp.template_name == name).first()

    def update(self, id:int , data: dict) -> ArchiveStamp:
        db_data = self.get_by_id(id)

        if not db_data:
            return None

        for key, value in data.items():
            if hasattr(db_data, key):
                setattr(db_data, key, value)

        self.db.commit()
        self.db.refresh(db_data)
        return db_data

    def delete(self, id: int) -> bool:
        db_data = self.get_by_id(id)
        if not db_data:
            return False

        self.db.delete(db_data)
        self.db.commit()
        return True

    def check_name_exists(self, name: str) -> bool:
        db_data = self.db.query(ArchiveStamp).filter(ArchiveStamp.template_name == name).first()
        if not db_data:
            return False
        return True


archive_stamp_service = ArchiveStampService()
