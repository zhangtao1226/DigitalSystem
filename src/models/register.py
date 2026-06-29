# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : register.py
# @Desc      : 领卷登记
# @Time      : 2025/12/2 09:47
# @Software  : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from src.core.db import Base

class Register(Base):
    __tablename__ = "register"  # 数据库表名

    # 字段定义
    id = Column(Integer, primary_key=True, index=True, comment="ID")
    archive_type = Column(String(100), index=True, nullable=False, comment="档案类别")
    category = Column(String(25), index=True, nullable=False, comment="类型")
    batch_number = Column(String(50), index=True, nullable=False, comment="批次号")
    number_start = Column(String(50), index=True, nullable=False, comment="开始卷/件号")
    number_end = Column(String(50), index=True, nullable=False, comment="终止卷/件号")
    is_question = Column(Boolean, index=True, nullable=False, comment="是否登记问题")
    is_distribute = Column(Boolean, index=True, nullable=False, comment="是否分配")
    register = Column(String(100), index=True, nullable=False, comment="登记人")
    register_date = Column(DateTime, index=True, nullable=False, comment="登记日期")
    status = Column(Integer, index=True, nullable=False, comment="状态; 0: 保存; 1:提交; 2:完结")
    task_node = Column(Integer, index=True, nullable=False, comment="任务节点")
    is_import = Column(Boolean, index=True, nullable=False, comment="导入目录; 0: 未导入; 1: 已导入")

    # 添加问题表一对多关系
    questions = relationship("RegisterQuestion", back_populates="register", cascade="all, delete-orphan")

    # 添加任务表一对多关系
    tasks = relationship("Task", back_populates="register", cascade="all, delete-orphan")

    scans = relationship("Scan", back_populates="register")


    def __repr__(self):
        return (f"<Register(id={self.id}, archive_type={self.archive_type}, category={self.category}, "
                f"batch_number={self.batch_number}, number_start={self.number_start}, number_end={self.number_end},"
                f"is_question={self.is_question}, is_distribute={self.is_distribute}, register={self.register}, "
                f"register_date={self.register_date}, status={self.status}, task_node={self.task_node}, is_import={self.is_import})>")