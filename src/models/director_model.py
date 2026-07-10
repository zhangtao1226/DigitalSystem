# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : director_model.py
# @Desc      : 目录表
# @Time      : 2026/2/26 11:18
# @Software  : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.db import Base

class DirectorModel(Base):
    __tablename__ = "director"

    id = Column(Integer, primary_key=True, comment="ID")
    register_id = Column(Integer, comment="登记ID")
    archive_type = Column(String(25), nullable=False, comment="档案门类")
    category = Column(String(25), nullable=False, comment="档案类别")
    doc_number = Column(String(100), nullable=False, comment="档号")
    title = Column(String(100), nullable=False, comment="题名")
    director_info = Column(Text, nullable=False, comment="目录信息")
    source = Column(String(100), nullable=False, comment="目录来源")
    create_date = Column(DateTime, nullable=False, comment="创建时间")
    update_date = Column(DateTime, nullable=False, comment="更新时间")
    operator = Column(String(100), nullable=False, comment="操作人")

    __table_args__ = (
        Index("idx_director_register", "register_id", "id"),
        Index("idx_director_filter", "archive_type", "category", id.desc()),
        Index("idx_director_identity", "doc_number", "archive_type", "category", "title"),
    )

    def __repr__(self):
        return (f"<Director(id={self.id}, register_id={self.register_id}, archive_type={self.archive_type}, "
                f"category={self.category}, doc_number={self.doc_number}, title={self.title},source={self.source}, director_info={self.director_info}), "
                f"create_date={self.create_date}, update_date={self.update_date}, "
                f"operator={self.operator})>")
