# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : role_service.py
# @Desc      : 角色服务层
# @Time      : 2025/12/1 17:00
# @Software  : PyCharm

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.db import SessionLocal
from src.models.role import Role
from src.models.user import User
from src.models.workflow import Workflow


class RoleService:
    """角色服务类"""
    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_role(self, name: str, permissions:Optional[str] = None, desc: Optional[str] = None) -> Role:
        role = Role(name=name, desc=desc)
        self.db.add(role)
        self.db.flush()

        if permissions:
            workflows = [
                self.db.query(Workflow).filter(Workflow.work_name == permission).first()
                for permission in permissions
            ]
            role.workflows = [w for w in workflows if w is not None]

        self.db.commit()
        self.db.refresh(role)
        return role

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        return self.db.query(Role).options(joinedload(Role.workflows)).filter(Role.id == role_id).first()

    def get_role_by_name(self, name: str) -> Optional[Role]:
        return self.db.query(Role).options(joinedload(Role.workflows)).filter(Role.name == name).first()

    def get_all_roles(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Role]:
        query: Query = self.db.query(Role).options(joinedload(Role.workflows))

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Role.name.ilike(search_term),
                    Role.desc.ilike(search_term)
                )
            )

        return query.order_by(Role.id.asc()).offset(skip).limit(limit).all()

    def update_role(self, role_id: int, data) -> Optional[Role]:
        role = self.get_role_by_id(role_id)
        if not role:
            return None

        # 更新字段
        for key, value in data.items():
            if not hasattr(role, key) or value is None:
                continue

            if key == "permissions":
                role.workflows = [
                    wf for name in value
                    if (wf := self.db.query(Workflow).order_by(Workflow.id.asc()).filter(Workflow.work_name == name).first()) is not None
                ]
            else:
                setattr(role, key, value)

        role.update_time = datetime.utcnow()
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete_role(self, role_id: int) -> bool:
        role = self.get_role_by_id(role_id)
        if not role:
            return False
        self.db.delete(role)
        self.db.commit()
        return True

    def get_role_users(self, role_id: int) -> Role:
        role = self.db.query(Role).options(joinedload(Role.users)).filter(Role.id == role_id).first()
        if not role:
            return []

        return role

    @staticmethod
    def add_user_to_role(db: Session, role_id: int, user_id: int) -> bool:
        role = RoleService.get_role_by_id(db, role_id)
        user = db.query(User).filter(User.id == user_id).first()

        if not role or not user:
            return False

        if user in role.users.all():
            return False

        role.users.append(user)
        db.commit()
        return True

    @staticmethod
    def remove_user_from_role(db: Session, role_id: int, user_id: int) -> bool:
        role = RoleService.get_role_by_id(db, role_id)
        user = db.query(User).filter(User.id == user_id).first()

        if not role or not user:
            return False

        if user not in role.users.all():
            return False

        role.users.remove(user)
        db.commit()
        return True


    def get_roles_count(self) -> int:
        return db.query(Role).count()


role_service = RoleService()
