# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : role_permission_association.py
# @Desc     : 角色与工作流权限关系表
# @Time     : 2025/12/18 10:05
# @Software : PyCharm

from sqlalchemy import Table, Column, Integer, ForeignKey

from src.core.db import Base


role_permission_association = Table(
    "role_permission_association",  # 数据库表名
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("workflow_id", Integer, ForeignKey("workflows.id"), primary_key=True)
)