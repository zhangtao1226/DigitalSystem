# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : task.py
# @Desc     : 
# @Time     : 2025/12/3 16:28
# @Software : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.core.db import Base

class Task(Base):
    __tablename__ = "task"

    # 定义字段
    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    task_id = Column(Integer, nullable=False, comment="任务id")
    register_id = Column(Integer, ForeignKey("register.id"), nullable=False, comment="登记记录ID")
    batch_number = Column(String(50), nullable=False, comment="批次号")
    number_start = Column(String(50), nullable=False, comment="起始卷/件号")
    number_end = Column(String(50), nullable=False, comment="截止卷/件号")
    task_name = Column(String(25), nullable=False, comment="任务名称")
    task_number_start = Column(String(50), comment="起始任务段号")
    task_number_end = Column(String(50), comment="截止任务段号")
    complete_number = Column(String(50), comment="已完成任务段")
    operator = Column(String(50), comment="操作员")
    dist_officer = Column(String(50), comment="分配人")
    dist_date = Column(DateTime, comment="分配日期")
    status = Column(Integer, nullable=False, comment="状态; 0: 保存; 1:提交;")
    is_ready = Column(Boolean, default=False, comment="前置任务是否已完成")
    is_do = Column(Boolean, default=False, comment="本任务是否完工")
    task_node = Column(Integer, nullable=False, comment="任务节点")
    operator_date = Column(DateTime, comment="操作日期")

    register = relationship("Register", back_populates="tasks")

    scans = relationship("Scan", back_populates="task")

    task_mark = relationship("TaskMark", back_populates="task")

    __table_args__ = (
        Index("idx_task_domain_id", "task_id"),
        Index("idx_task_operator_list", "task_name", "operator", id.desc(), "task_node"),
        Index("idx_task_register_segment", "register_id", "task_number_start", "id"),
        Index("idx_task_batch_flow", "batch_number", "register_id", "task_node", "status"),
        Index("idx_task_range", "batch_number", "task_node", "task_number_start", "task_number_end"),
    )

    def __repr__(self):
        return (f"<Task(id={self.id}, task_id={self.task_id}, register_id={self.register_id}, batch_number={self.batch_number}, "
                f"number_start={self.number_start}, number_end={self.number_end}, task_name={self.task_name}, "
                f"task_number_start={self.task_number_start}, task_number_end={self.task_number_end}>, complete_number={self.complete_number})>, "
                f"operator={self.operator}, dist_officer={self.dist_officer}, dist_date={self.dist_date}, status={self.status},"
                f"task_node={self.task_node}, operator_date={self.operator_date}, is_ready={self.is_ready}, is_do={self.is_do})>")
