# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : scan.py
# @Desc     : 
# @Time     : 2025/12/11 20:59
# @Software : PyCharm

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.db import Base

class Scan(Base):
    __tablename__ = "scan"

    # 定义字段
    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False, comment="任务ID")
    register_id = Column(Integer, ForeignKey("register.id"), nullable=False, comment="登记ID")
    dir_path = Column(String(200), nullable=False, comment="扫描保存路径")
    dir_name = Column(String(50), nullable=False, comment="扫描文件夹名称")
    scan_type = Column(String(50), nullable=False, comment="扫描格式")
    scan_dpi = Column(Integer, nullable=False, comment="扫描分辨率dpi")
    scan_model = Column(String(50), nullable=False, comment="扫描色彩模式")
    file_count = Column(Integer, nullable=False, comment="扫描文件数据")
    server_save_path = Column(String(50), comment="上传到服务器路径")
    operator = Column(String(50), comment="操作员")
    operator_date = Column(DateTime, comment="操作日期")

    task = relationship("Task", back_populates="scans")

    register = relationship("Register", back_populates="scans")

    __table_args__ = (
        Index("idx_scan_task", "task_id"),
        Index("idx_scan_register", "register_id"),
        Index("idx_scan_dir_name", "dir_name"),
    )

    def __repr__(self):
        return (f"<Scan(id={self.id}, task_id={self.task_id}, dir_path={self.dir_path}, dir_name={self.dir_name}, "
                f"server_save_path={self.server_save_path}, operator={self.operator}, operator_date={self.operator_date})>")
