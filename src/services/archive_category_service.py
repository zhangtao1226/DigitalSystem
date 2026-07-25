# -*-coding : utf-8 -*-
"""档案类别及目录字段定义的统一数据库服务。"""
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from src.core.db import SessionLocal, engine
from src.models.archive_category import ArchiveCategory, ArchiveCategoryField


class ArchiveCategoryService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()

    def _commit(self):
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def ensure_tables():
        ArchiveCategory.__table__.create(bind=engine, checkfirst=True)
        ArchiveCategoryField.__table__.create(bind=engine, checkfirst=True)

    def get_categories(self, enabled_only=True):
        self.db.expire_all()
        query = self.db.query(ArchiveCategory).options(
            joinedload(ArchiveCategory.fields)
        )
        if enabled_only:
            query = query.filter(ArchiveCategory.enabled.is_(True))
        return query.order_by(
            ArchiveCategory.archive_type,
            ArchiveCategory.category_level,
        ).all()

    def get_category(self, archive_type, category_level):
        self.db.expire_all()
        return (
            self.db.query(ArchiveCategory)
            .options(joinedload(ArchiveCategory.fields))
            .filter(
                ArchiveCategory.archive_type == archive_type,
                ArchiveCategory.category_level == category_level,
            )
            .first()
        )

    def get_by_display_name(self, display_name):
        if "-" not in display_name:
            return None
        return self.get_category(*display_name.rsplit("-", 1))

    def get_fields(self, archive_type, category_level, enabled_only=True):
        category = self.get_category(archive_type, category_level)
        if not category:
            return []
        fields = sorted(category.fields, key=lambda item: (item.sort_order, item.id))
        return [item for item in fields if item.enabled] if enabled_only else fields

    def get_headers(self, archive_type, category_level):
        return [item.alias for item in self.get_fields(archive_type, category_level)]

    def get_field_names(self, archive_type, category_level):
        return [
            item.field_name for item in self.get_fields(archive_type, category_level)
        ]

    def create_category(self, archive_type, category_level, category_code=""):
        archive_type = archive_type.strip()
        category_level = category_level.strip()
        if not archive_type or not category_level:
            raise ValueError("档案门类和目录级别不能为空")

        display_name = f"{archive_type}-{category_level}"
        if len(display_name) > 31 or re.search(r"[\\/*?:\[\]]", display_name):
            raise ValueError(
                "档案类别名称不符合 Excel 工作表命名规则"
                "（最多31个字符，不能含 \\ / * ? : [ ]）"
            )
        if self.get_category(archive_type, category_level):
            raise ValueError("档案类别已存在")

        code = category_code.strip() or display_name
        if (
            self.db.query(ArchiveCategory)
            .filter(ArchiveCategory.category_code == code)
            .first()
        ):
            raise ValueError("档案类别编码已存在")

        category = ArchiveCategory(
            archive_type=archive_type,
            category_level=category_level,
            category_code=code,
        )
        self.db.add(category)
        self._commit()
        self.db.refresh(category)
        return category

    @staticmethod
    def _validate_business_aliases(aliases):
        aliases = {str(alias).strip() for alias in aliases}
        if not aliases.intersection({"档号", "合同编号"}):
            raise ValueError("缺少业务必需字段：档号或合同编号")
        if not aliases.intersection({"题名", "合同名称"}):
            raise ValueError("缺少业务必需字段：题名或合同名称")

    def replace_fields(
        self,
        category_id: int,
        fields: List[Dict],
        expected_version: Optional[int] = None,
    ):
        category = (
            self.db.query(ArchiveCategory)
            .filter(ArchiveCategory.id == category_id)
            .first()
        )
        if not category:
            raise ValueError("档案类别不存在")
        if expected_version is not None and category.version != expected_version:
            raise ValueError("档案类别已被其他客户端修改，请刷新后重试")

        normalized = []
        field_names = set()
        aliases = set()
        for index, item in enumerate(fields, start=1):
            field_name = str(item.get("field_name", "")).strip()
            alias = str(item.get("alias", "")).strip()
            if not field_name or not alias:
                raise ValueError("字段名和别名不能为空")
            if field_name in field_names or alias in aliases:
                raise ValueError(f"字段名或别名重复：{field_name}/{alias}")
            field_names.add(field_name)
            aliases.add(alias)
            normalized.append(
                {
                    "field_name": field_name,
                    "alias": alias,
                    "field_type": str(item.get("field_type") or "字符型"),
                    "field_length": int(
                        item.get("length") or item.get("field_length") or 50
                    ),
                    "required": str(item.get("required", "否")).strip().upper()
                    in ("是", "Y", "YES", "TRUE", "1"),
                    "sort_order": index,
                }
            )

        self._validate_business_aliases(aliases)

        existing_fields = (
            self.db.query(ArchiveCategoryField)
            .filter(ArchiveCategoryField.category_id == category.id)
            .all()
        )
        existing_by_name = {item.field_name: item for item in existing_fields}
        existing_by_alias = {item.alias: item for item in existing_fields}
        used_fields = set()

        for item in normalized:
            field = existing_by_name.get(item["field_name"]) or existing_by_alias.get(
                item["alias"]
            )
            if field is None:
                field = ArchiveCategoryField(category_id=category.id)
                self.db.add(field)
            for key, value in item.items():
                setattr(field, key, value)
            field.enabled = True
            field.updated_at = datetime.now()
            used_fields.add(field)

        for field in existing_fields:
            if field not in used_fields:
                field.enabled = False
                field.updated_at = datetime.now()

        category.version += 1
        category.updated_at = datetime.now()
        self._commit()
        return self.get_category(category.archive_type, category.category_level)

    def import_excel(self, file_path, overwrite=False):
        import pandas as pd

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"未找到档案模板：{path}")

        excel = pd.ExcelFile(str(path))
        result = {"created": 0, "updated": 0, "skipped": 0}
        for sheet_name in excel.sheet_names:
            if "-" not in sheet_name:
                result["skipped"] += 1
                continue

            archive_type, category_level = sheet_name.rsplit("-", 1)
            df = pd.read_excel(str(path), sheet_name=sheet_name)
            category = self.get_category(archive_type, category_level)
            existed = category is not None
            if existed and not overwrite:
                result["skipped"] += 1
                continue

            # 普通模板使用“字段名=内部编码、别名=中文显示名”，现有合同
            # 模板两列相反。根据业务核心字段所在列自动识别并规范化。
            first_values = {
                str(value).strip()
                for value in df.iloc[:, 1].dropna().tolist()
            }
            second_values = {
                str(value).strip()
                for value in df.iloc[:, 2].dropna().tolist()
            }
            business_aliases = {"档号", "合同编号", "题名", "合同名称"}
            swap_name_alias = len(first_values & business_aliases) > len(
                second_values & business_aliases
            )

            fields = []
            for _, row in df.iterrows():
                values = row.tolist()
                if len(values) < 6:
                    raise ValueError(f"工作表 {sheet_name} 字段列不足")

                def clean(value, default=""):
                    return default if pd.isna(value) else value

                fields.append(
                    {
                        "field_name": clean(
                            values[2] if swap_name_alias else values[1]
                        ),
                        "alias": clean(
                            values[1] if swap_name_alias else values[2]
                        ),
                        "field_type": clean(values[3], "字符型"),
                        "length": clean(values[4], 50),
                        "required": (
                            "是"
                            if str(clean(values[5])).strip().upper()
                            in ("Y", "是", "TRUE", "1")
                            else "否"
                        ),
                    }
                )

            self._validate_business_aliases(item["alias"] for item in fields)
            if category is None:
                category = self.create_category(archive_type, category_level)
            self.replace_fields(category.id, fields)
            result["updated" if existed else "created"] += 1

        return result

    def bootstrap_from_excel(self, file_path):
        if self.db.query(ArchiveCategory).count() > 0:
            return {"created": 0, "updated": 0, "skipped": 0}
        return self.import_excel(file_path)

    def export_excel(self, file_path):
        import pandas as pd

        columns = ["序号", "字段名", "别名", "类型", "长度", "是否必填"]
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            for category in self.get_categories(enabled_only=False):
                rows = []
                fields = sorted(
                    category.fields,
                    key=lambda item: (item.sort_order, item.id),
                )
                for index, field in enumerate(
                    (item for item in fields if item.enabled),
                    start=1,
                ):
                    rows.append(
                        [
                            index,
                            field.field_name,
                            field.alias,
                            field.field_type,
                            field.field_length,
                            "Y" if field.required else "N",
                        ]
                    )
                pd.DataFrame(rows, columns=columns).to_excel(
                    writer,
                    sheet_name=category.display_name,
                    index=False,
                )


archive_category_service = ArchiveCategoryService()
