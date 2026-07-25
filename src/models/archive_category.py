# -*-coding : utf-8 -*-
"""档案类别及目录字段定义。"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.core.db import Base


class ArchiveCategory(Base):
    __tablename__ = "archive_category"

    id = Column(Integer, primary_key=True, autoincrement=True)
    archive_type = Column(String(100), nullable=False, comment="档案门类")
    category_level = Column(String(50), nullable=False, comment="目录级别")
    category_code = Column(String(100), nullable=False, unique=True, comment="稳定内部编码")
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    fields = relationship(
        "ArchiveCategoryField",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="ArchiveCategoryField.sort_order",
    )
    __table_args__ = (
        UniqueConstraint(
            "archive_type",
            "category_level",
            name="uq_archive_category_type_level",
        ),
        Index("ix_archive_category_enabled", "enabled"),
    )

    @property
    def display_name(self):
        return f"{self.archive_type}-{self.category_level}"


class ArchiveCategoryField(Base):
    __tablename__ = "archive_category_field"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(
        Integer,
        ForeignKey("archive_category.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_name = Column(String(100), nullable=False, comment="稳定字段编码")
    alias = Column(String(100), nullable=False, comment="中文显示名称")
    field_type = Column(String(30), nullable=False, default="字符型")
    field_length = Column(Integer, nullable=False, default=50)
    required = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    category = relationship("ArchiveCategory", back_populates="fields")
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "field_name",
            name="uq_archive_category_field_name",
        ),
        UniqueConstraint(
            "category_id",
            "alias",
            name="uq_archive_category_field_alias",
        ),
        Index("ix_archive_category_field_order", "category_id", "sort_order"),
    )
