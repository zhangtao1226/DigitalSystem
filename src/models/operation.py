# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : operation.py
# @Desc     : 操作表
# @Time     : 2026/3/7 10:18
# @Software : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Index, Text

from src.core.db import Base

class Operation(Base):
    __tablename__ = "operation"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")
    task_id = Column(Integer, index=True, nullable=False, comment="任务ID")
    task_name = Column(String(50), index=True, nullable=False, comment="任务名称")
    task_number_start = Column(String(50), index=True, comment="提交的任务段开始号")
    task_number_end = Column(String(50), index=True, comment="提交的任务段开始号")
    status = Column(Integer, index=True, comment="操作状态; 0: 保存; 1: 提交")
    operator = Column(String(50), index=True, nullable=False, comment="操作人")
    operator_date = Column(DateTime, index=True, nullable=False, comment="操作日期")
    operator_remark = Column(Text, index=True, comment="备注")

    __table_args__ = (
        Index('task_id_idx', 'task_id'),
        Index('operator_date_range', 'operator_date'),
    )

    def __repr__(self):
        return (f"<Operation(id={self.id}, name_id={self.task_id}, task_name={self.task_name}, operator={self.operator},"
                f" task_number_start={self.task_number_start}, task_number_end={self.task_number_end}, status={self.status},"
                f"operator_date={self.operator_date})>")