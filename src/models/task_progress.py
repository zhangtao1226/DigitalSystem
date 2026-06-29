# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : task_progress.py
# @Time     : 2026/4/22 16:08
# @Desc     : 
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.core.db import Base

class TaskProgress(Base):
    __tablename__ = 'task_progress'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('task.id'), nullable=False)
    sub_start = Column(String(50), nullable=False, comment="本次提交起始号")
    sub_end = Column(String(50), nullable=False, comment="本次提交截止号")
    status = Column(Integer, default=0, comment="0：保存；1：提交")
    operator = Column(String(50), index=True)
    operate_date = Column(DateTime, index=True)


    task = relationship("Task",)

    def __repr__(self):
        return (f"<TaskProgress(id={self.id}, task_id={self.task_id}, sub_start={self.sub_start}, "
                f"sub_end={self.sub_end}, status={self.status}, operator={self.operator}, operate_date={self.operate_date})>")
