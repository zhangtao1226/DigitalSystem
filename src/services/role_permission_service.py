# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : role_permission_service.py
# @Time     : 2026/4/29 10:51
# @Desc     : 
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.db import SessionLocal

from src.models.role_permission_association import role_permission_association

class RolePermissionService:

    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_by_role_id(self, role_id: int) -> list[role_permission_association]:
        return self.db.query(role_permission_association).filter(role_permission_association.role_id == role_id).all()


role_permission_service = RolePermissionService()