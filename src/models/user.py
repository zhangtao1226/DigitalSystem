# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : user.py
# @Desc      : 
# @Time      : 2025/12/1 16:38
# @Software  : PyCharm

from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean

from src.core.db import Base
from src.models.association import user_role_association

class User(Base):
    __tablename__ = "users"  # 数据库表名

    # 字段定义
    id = Column(Integer, primary_key=True, comment="用户ID")
    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    password = Column(String(255), nullable=False, comment="密码哈希（不存储明文）")
    is_active = Column(Boolean, default=True, comment="是否激活")
    create_time = Column(DateTime, comment="创建时间")
    update_time = Column(DateTime, comment="更新时间")
    last_login = Column(DateTime, comment="最近登录时间")

    # 多对多关系：用户关联多个角色（通过关联表）
    roles = relationship(
        "Role",  # 关联的模型类
        secondary=user_role_association,  # 关联表
        back_populates="users",  # 反向关联字段（角色模型中的users字段）
        lazy="select"  # 动态加载
    )

    def __repr__(self):
        return (f"<User(id={self.id}, username={self.username}, is_active={self.is_active}, roles={self.roles})>, "
                f"create_time={self.create_time}, update_time={self.update_time}, last_login={self.last_login})>")
