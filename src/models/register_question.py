# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : register_question.py
# @Desc      :
# @Time      : 2025/12/2 13:23
# @Software  : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.db import Base


class RegisterQuestion(Base):
    __tablename__ = "register_question"  # 数据库表名

    # 字段定义
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    register_id = Column(Integer, ForeignKey("register.id"), nullable=False, index=True, comment="登记记录ID")
    batch_number = Column(String(50), index=True, comment="批次号")
    number_start = Column(String(50), index=True, comment="开始卷/件号")
    number_end = Column(String(50), index=True, comment="终止卷/件号")
    volume_number = Column(String(25), index=True, comment="卷/件号")
    question_desc = Column(Text, index=True, comment="问题描述")
    recorder = Column(String(50), index=True, comment="记录人")
    recorder_time = Column(DateTime, index=True, comment="记录时间")
    status = Column(Integer, index=True, comment="状态; 0: 保存; 1: 提交")

    # 添加多对一关系
    register = relationship("Register", back_populates="questions")



    def __repr__(self):
        return (f"<RegisterQuestion(id={self.id}, register_id={self.register_id}, batch_number={self.batch_number}, volume_number={self.volume_number}, "
                f"question_desc={self.question_desc}, recorder={self.recorder}, recorder_time={self.recorder_time})>)")