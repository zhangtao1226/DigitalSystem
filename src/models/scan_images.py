# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : scan_images.py
# @Time     : 2026/4/27 11:22
# @Desc     : 
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.db import Base

class ScanImages(Base):
    __tablename__ = "scan_images"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    scan_id = Column(Integer, ForeignKey("scan.id"), nullable=False, comment="扫描表ID")
    file_name = Column(String(20), nullable=False, comment="扫描文件名")
    page_index = Column(Integer, nullable=True, comment="当前页码")
    is_ocr = Column(Boolean,  default=False, comment="是否OCR")
    create_time = Column(DateTime, comment="创建时间")
    operator = Column(String(20), comment="操作人")

    scan = relationship("Scan", backref="scan_images")

    __table_args__ = (
        Index("idx_scan_images_order", "scan_id", "page_index", "file_name"),
    )

    def __repr__(self):
        return (f"<ScanImages(scan_id={self.scan_id}, scan_id={self.scan_id}, file_name={self.file_name}, "
                f"page_index={self.page_index}, is_ocr={self.is_ocr}, create_time={self.create_time}, "
                f"operator={self.operator})>")
