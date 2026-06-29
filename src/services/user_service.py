# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : user_service.py
# @Desc      : 用户服务层
# @Time      : 2025/12/1 17:00
# @Software  : PyCharm

from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import asc, desc
from datetime import datetime
from typing import List, Optional, Dict, Any
from werkzeug.security import generate_password_hash

from src.models.role import Role
from src.models.user import User
from src.core.db import SessionLocal
from src.services.role_service import role_service


class UserService:
    """用户服务类"""
    def __init__(self, db: Optional[Session] = None):
        """
        初始化
        :param db: 数据库会话
        """
        # 支持外部传入会话（如事务场景），否则自动获取会话
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        """
        静态方法：获取数据库会话（内部使用）
        自动管理会话生命周期
        """
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_user(self, data) -> User:
        user = User(
            username=data['username'],
            password=generate_password_hash(data['password']),
            is_active=data['is_active'],
            create_time=data['create_time'] if 'create_time' in data else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            update_time=data['update_time'] if 'update_time' in data else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        if data['roles']:
            roles = [
                self.db.query(Role).filter(Role.name == role).first() for role in data['roles']
            ]
            user.roles = [r for r in roles if r is not None]
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户
        :param username: 用户名
        :return:  Optional[User]: 用户对象或None
        """
        return self.db.query(User).filter(User.username == username).first()

    def get_all_users(self, skip: int = 0, limit: int = 100,
                      search: Optional[str] = None,
                      is_active: Optional[bool] = None,
                      role_name: Optional[str] = None,
                      ) -> List[User]:

        query: Query = self.db.query(User).options(selectinload(User.roles))

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )

        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if role_name is not None:
            query = query.join(User.roles).filter(Role.name == role_name)

        return query.order_by(User.id.asc()).offset(skip).limit(limit).all()

    def update_user(self, user_id: int, data) -> Optional[User]:
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        for key, value in data.items():
            if key == 'roles':
                user.roles = [
                    r for name in value
                    if (r := self.db.query(Role).filter(Role.name == name).first()) is not None
                ]

        if len(data['password']) > 0:
            user.password = generate_password_hash(data['password'])
        user.username = data['username']
        user.is_active = data['is_active']
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_login_time(self, user_id):
        user = self.get_user_by_id(user_id)
        user.last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.commit()
        self.db.refresh(user)


    def delete_user(self, user_id: int) -> bool:
        """
        删除用户（会自动解除与角色的关联）
        :param user_id: 用户ID
        :return:  bool: 是否删除成功
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # 由于设置了 ondelete='CASCADE'，关联表中的记录会自动删除
        self.db.delete(user)
        self.db.commit()
        return True

    @staticmethod
    def authenticate_user(db: Session, username: str, password_hash: str) -> Optional[User]:
        """
        用户认证

        Args:
            db: 数据库会话
            username: 用户名或邮箱
            password_hash: 密码哈希

        Returns:
            Optional[User]: 认证成功的用户对象或None
        """
        user = db.query(User).filter(
            or_(User.username == username, User.email == username),
            User.password_hash == password_hash,
            User.is_active == True
        ).first()

        if user:
            # 更新最后登录时间
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)

        return user

    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[Role]:
        """
        获取用户的所有角色

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            List[Role]: 角色列表
        """
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            return []

        return user.roles.all()

    @staticmethod
    def has_role(db: Session, user_id: int, role_name: str) -> bool:
        """
        检查用户是否拥有指定角色

        Args:
            db: 数据库会话
            user_id: 用户ID
            role_name: 角色名称

        Returns:
            bool: 是否拥有该角色
        """
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            return False

        return user.roles.filter(Role.name == role_name).first() is not None

    @staticmethod
    def update_user_roles(db: Session, user_id: int, role_ids: List[int]) -> bool:
        """
        更新用户的角色（替换原有角色）

        Args:
            db: 数据库会话
            user_id: 用户ID
            role_ids: 角色ID列表

        Returns:
            bool: 是否更新成功
        """
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            return False

        # 获取所有角色对象
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()

        # 清空原有角色并添加新角色
        user.roles = roles
        db.commit()
        return True

    @staticmethod
    def get_users_count(db: Session, is_active: Optional[bool] = None) -> int:
        """
        获取用户总数

        Args:
            db: 数据库会话
            is_active: 是否激活

        Returns:
            int: 用户总数
        """
        query = db.query(User)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        return query.count()

    @staticmethod
    def get_users_by_role(db: Session, role_id: int) -> List[User]:
        """
        获取拥有指定角色的所有用户

        Args:
            db: 数据库会话
            role_id: 角色ID

        Returns:
            List[User]: 用户列表
        """
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return []

        return role.users.all()

user_service = UserService()