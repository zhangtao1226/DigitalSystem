# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : register_question.py
# @Desc      :
# @Time      : 2025/12/2 13:23
# @Software  : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.db import Base


class RegisterQuestion(Base):
    __tablename__ = "register_question"  # 数据库表名

    # 字段定义
    id = Column(Integer, primary_key=True, comment="ID")
    register_id = Column(Integer, ForeignKey("register.id"), nullable=False, comment="登记记录ID")
    batch_number = Column(String(50), comment="批次号")
    number_start = Column(String(50), comment="开始卷/件号")
    number_end = Column(String(50), comment="终止卷/件号")
    volume_number = Column(String(25), comment="卷/件号")
    question_desc = Column(Text, comment="问题描述")
    recorder = Column(String(50), comment="记录人")
    recorder_time = Column(DateTime, comment="记录时间")
    status = Column(Integer, comment="状态; 0: 保存; 1: 提交")

    # 添加多对一关系
    register = relationship("Register", back_populates="questions")

    __table_args__ = (
        Index("idx_register_question_register", "register_id"),
        Index("idx_register_question_volume", "register_id", "volume_number", "recorder"),
        Index("idx_register_question_range", "batch_number", "number_start", "number_end"),
    )



    def __repr__(self):
        return (f"<RegisterQuestion(id={self.id}, register_id={self.register_id}, batch_number={self.batch_number}, volume_number={self.volume_number}, "
                f"question_desc={self.question_desc}, recorder={self.recorder}, recorder_time={self.recorder_time})>)")
