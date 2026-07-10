# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : archive_stamp.py
# @Time     : 2026/5/12 14:47
# @Desc     : 

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from src.core.db import Base

class ArchiveStamp(Base):
    __tablename__ = 'archive_stamp'

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    template_name = Column(String(50), nullable=False, comment="模版名称")
    template_format = Column(Integer, nullable=False, comment="章格式; 0: 6格章; 1: 8格章")
    show_field_labels = Column(Integer, default=1, comment="是否显示字段; 默认:显示; 0: 不显示")
    fields_json = Column(Text, nullable=False, comment="归档章字段")
    create_time = Column(DateTime, comment="创建时间")
    update_time = Column(DateTime, comment="更新时间")

    __table_args__ = (
        Index("idx_archive_stamp_name", "template_name"),
    )
    operator = Column(String(30), nullable=False, comment="创建者")

    def __repr__(self):
        return (f"<ArchiveStamp(id={self.id}, template_name={self.template_name}, template_format={self.template_format}, "
                f"show_field_labels={self.show_field_labels}, fields_json={self.fields_json}, "
                f"create_time={self.create_time}, update_time={self.update_time}, operator={self.operator})>")
