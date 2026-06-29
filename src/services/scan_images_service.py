# -*-coding : utf-8 -*-
# @Author   : zhangTao
# @File     : scan_images_service.py
# @Time     : 2026/4/27 13:09
# @Desc     : 扫描图片信息服务
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.db import SessionLocal
from src.models.scan import Scan
from src.models.scan_images import ScanImages

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".pdf"}


class ScanImagesService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def insert_data(self, data: Dict[str, Any]) -> ScanImages:
        db_scan_image = ScanImages(
            scan_id=data["scan_id"],
            file_name=data["file_name"],
            page_index=data.get("page_index"),
            is_ocr=data.get("is_ocr", False),
            create_time=data.get("create_time") or datetime.now(),
            operator=data.get("operator"),
        )

        self.db.add(db_scan_image)
        self.db.commit()
        self.db.refresh(db_scan_image)
        return db_scan_image

    def get_by_id(self, id: int) -> Optional[ScanImages]:
        return self.db.query(ScanImages).filter(ScanImages.id == id).first()

    def get_list_by_scan_id(self, scan_id: int) -> List[ScanImages]:
        return (
            self.db.query(ScanImages)
            .filter(ScanImages.scan_id == scan_id)
            .order_by(ScanImages.page_index.asc().nullslast(), ScanImages.file_name.asc())
            .all()
        )

    def update(self, id: int, data: Dict[str, Any]) -> Optional[ScanImages]:
        db_scan_image = self.get_by_id(id)
        if db_scan_image is None:
            return None

        for key, value in data.items():
            if hasattr(ScanImages, key):
                setattr(db_scan_image, key, value)

        self.db.commit()
        self.db.refresh(db_scan_image)
        return db_scan_image

    def delete(self, id: int) -> bool:
        db_scan_image = self.get_by_id(id)
        if not db_scan_image:
            return False

        self.db.delete(db_scan_image)
        self.db.commit()
        return True

    def get_image_info(self, where: Dict[str, Any]) -> List[ScanImages]:
        return self.db.query(ScanImages).filter_by(**where).all()

    def upsert_image_info(self, data: Dict[str, Any]) -> ScanImages:
        where = {
            "scan_id": data["scan_id"],
            "file_name": data["file_name"],
        }
        existing = self.db.query(ScanImages).filter_by(**where).first()
        if existing:
            return self.update(existing.id, data)
        return self.insert_data(data)

    def sync_scan_images_from_folder(
        self,
        scan_id: int,
        image_dir_path: str,
        operator: str = "",
        extensions=None,
    ) -> List[ScanImages]:
        """将扫描文件夹中的图片文件名同步到 scan_images 表。"""
        extensions = extensions or IMG_EXTENSIONS
        if not image_dir_path or not os.path.isdir(image_dir_path):
            return []

        saved_images = []
        page_num = 1
        for file_name in sorted(os.listdir(image_dir_path)):
            image_path = os.path.join(image_dir_path, file_name)
            if not os.path.isfile(image_path):
                continue
            if os.path.splitext(file_name)[1].lower() not in extensions:
                continue

            image_info_data = {
                "scan_id": scan_id,
                "file_name": file_name,
                "page_index": page_num,
                "is_ocr": False,
                "operator": operator,
                "create_time": datetime.now(),
            }
            saved_images.append(self.upsert_image_info(image_info_data))
            page_num += 1
        return saved_images

    def get_image_paths_by_scan(self, scan: Scan, base_dir: str = None) -> List[str]:
        """根据 scan 和 scan_images 记录还原本地图片完整路径。"""
        if not scan:
            return []

        image_dir = os.path.join(base_dir or scan.dir_path, scan.dir_name)
        image_infos = self.get_list_by_scan_id(scan.id)
        image_paths = []
        for image_info in image_infos:
            image_path = os.path.join(image_dir, image_info.file_name)
            if os.path.isfile(image_path):
                image_paths.append(image_path)
        return image_paths


scan_images_service = ScanImagesService()
