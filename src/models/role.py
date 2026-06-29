# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : role.py
# @Desc      : 
# @Time      : 2025/12/1 16:38
# @Software  : PyCharm

from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean

from src.core.db import Base
from src.models.association import user_role_association
from src.models.role_permission_association import role_permission_association

class Role(Base):
    __tablename__ = "roles"  # 数据库表名

    # 字段定义
    id = Column(Integer, primary_key=True, index=True, comment="角色ID")
    name = Column(String(50), unique=True, index=True, nullable=False, comment="角色名称（如：管理员、质检员、操作员）")
    desc = Column(String(200), nullable=True, comment="角色描述")
    is_active = Column(Boolean, default=True, comment="是否激活")
    create_time = Column(DateTime, comment="创建时间")
    update_time = Column(DateTime, comment="更新时间")

    # 多对多关系：角色关联多个用户（通过关联表）
    users = relationship(
        "User",  # 关联的模型类（字符串形式避免循环导入）
        secondary=user_role_association,  # 关联表
        back_populates="roles",  # 反向关联字段（用户模型中的roles字段）
        lazy="select"  # 动态加载（避免一次性加载所有关联数据）
    )

    # 多对多关系: 角色与权限
    workflows = relationship(
        "Workflow",
        secondary=role_permission_association,
        back_populates="roles",
        lazy="select"
    )

    @property
    def permissions(self):
        return self.workflows

    @permissions.setter
    def permissions(self, value):
        self.workflows = value

    def __repr__(self):
        return (f"<Role(id={self.id}, name={self.name}, desc={self.desc}, permissions={self.workflows},  "
                f"users={self.users}, "
                f"create_time={self.create_time}, "
                f"update_time={self.update_time})>")
