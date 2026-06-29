# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : task_mark_model.py
# @Time     : 2026/6/15 11:09
# @Desc     : 质检标记表
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text, Boolean
from sqlalchemy.orm import relationship

from src.core.db import Base

class TaskMark(Base):
    __tablename__ = "task_mark"
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False, index=True, comment="关联任务ID")
    batch_number = Column(String(50), nullable=False, index=True, comment="批次号")
    task_node = Column(Integer, nullable=False, index=True, comment="任务节点号")

    mark_stage = Column(Integer, nullable=False, index=True, comment="质检阶段：1=扫描 2=图像处理 3=目录")

    scan_file = Column(String(255), nullable=True, comment="文件件名")
    field_name = Column(String(100), nullable=True, comment="目录字段名, 如： 档号、题名等")
    field_value_before = Column(String(255), nullable=True, comment="目录字段原始值")

    mark_type = Column(String(50), nullable=False, comment="标记类型, 与 mark_stage 对应")
    level = Column(String(10), nullable=False, default="一般", comment="严重程度：严重/一般/轻微")
    description = Column(Text, nullable=True, comment="问题详细描述")

    inspector = Column(String(0), nullable=False, index=True, comment="质检员姓名")
    mark_date = Column(DateTime, nullable=False, index=True, comment="标记时间")

    is_fixed = Column(Boolean, default=False, comment="是否修改完成")
    fix_date = Column(DateTime, nullable=True, comment="修改时间")
    fix_people = Column(String(25), nullable=True, comment="修改人")
    fix_remark= Column(Text, nullable=True, comment="修改说明：如：已重扫 第 7 页/ 更正档号")
    field_value_after = Column(String(255), nullable=True, comment="目录子段修改后的值")
    is_deleted = Column(Boolean, default=False, comment="软删除")

    task = relationship("Task", back_populates="task_mark")

    def __repr__(self):
        return (f"<TaskMark(id={self.id}, task_id={self.task_id}, mark_stage={self.mark_stage}, "
                f"mark_date={self.mark_date}, scan_file={self.scan_file}, "
                f"field_name={self.field_name}, field_value_before={self.field_value_before}, "
                f"mark_type={self.mark_type}, level={self.level}, description={self.description}, "
                f"inspector={self.inspector}, mark_date={self.mark_date}"
                f"is_fixe={self.is_fixed}, fix_date={self.fix_date}"
                f"fix_remark={self.fix_remark}, field_value_after={self.field_value_after}, is_deleted={self.is_deleted})>")
