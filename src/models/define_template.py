# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : define_template.py
# @Time     : 2026/4/16 17:00
# @Desc     : 自定义模板

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.core.db import Base

class DefineTemplate(Base):
    __tablename__ = "define_template"

    # 定义字段
    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    template_name = Column(String(50), nullable=False, comment="模板名称")
    field_info = Column(String(100), nullable=False, comment="字段信息（包含坐标）JSON 格式")
    creator = Column(String(20), nullable=False, comment="创建者")
    create_date = Column(DateTime, comment="创建日期")

    __table_args__ = (
        Index("idx_define_template_name", "template_name"),
    )


    def __repr__(self):
        return (f"<DefineTemplate(id={self.id}, template_name={self.template_name}, field_info={self.field_info}, "
                f"creator={self.creator}, create_date={self.create_date})>")
