# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : association.py
# @Desc      : 用户与角色关系表
# @Time      : 2025/12/1 16:37
# @Software  : PyCharm

from sqlalchemy import Table, Column, Integer, ForeignKey

from src.core.db import Base

# 关联表：user_id关联用户表，role_id关联角色表
user_role_association = Table(
    "user_role_association",  # 数据库表名
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)