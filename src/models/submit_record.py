# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : submit_record.py
# @Time     : 2026/4/9 15:45
# @Desc     : 

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index

from src.core.db import Base

class SubmitRecord(Base):
    __tablename__ = 'submit_record'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID")
    register_id = Column(Integer, index=True, comment="登记ID")
    task_id = Column(Integer, index=True, comment="任务ID")
    task_name = Column(String(30), index=True, nullable=False, comment="任务名称")
    number_start = Column(String(50), index=True, nullable=False, comment="提交起始卷/件号")
    number_end = Column(String(50), index=True, nullable=False, comment="提交截止卷/件号")
    operator = Column(String(50), index=True, comment="提交人")
    operator_date = Column(DateTime, index=True, comment="提交日期")


    def __repr__(self):
        return (f"<SubmitRecord(id={self.id}, register_id={self.register_id}, task_id={self.task_id}, "
                f"task_name={self.task_name}, number_start={self.number_start}, number_end={self.number_end}, "
                f"operator={self.operator}, operator_date={self.operator_date})>")



