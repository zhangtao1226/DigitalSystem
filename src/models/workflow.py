# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : workflow.py
# @Desc     : 
# @Time     : 2025/12/16 14:40
# @Software : PyCharm

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean

from src.core.db import Base
from src.models.role_permission_association import role_permission_association


class Workflow(Base):
    __tablename__ = "workflows"  # 数据库表名

    # 字段定义

    id = Column(Integer, primary_key=True, nullable=False, comment="工作流索引")
    work_name = Column(String(25), unique=True, nullable=False, comment="工作流名称")
    status = Column(Boolean, default=False, comment="是否启用")
    is_work = Column(Integer, nullable=False, comment="0: 非工作流; 1:可配的工作流;")

    # 多对多关系
    roles = relationship(
        "Role",
        secondary=role_permission_association,
        back_populates="workflows",
        lazy="dynamic"
    )

    def __repr__(self):
        return (f"<Workflow(id={self.id}, work_name={self.work_name}, status={self.status}, is_work={self.is_work}"
                f")>")
