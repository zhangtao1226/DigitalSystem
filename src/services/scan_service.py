# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : scan_service.py
# @Desc      : 
# @Time      : 2026/2/4 16:06
# @Software  : PyCharm


from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any


from src.core.db import SessionLocal

from src.models.scan import Scan


class ScanService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())


    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def save_data(self, data_list: List[Dict[str, Any]]) -> List[Scan]:
        """
        批量保存扫描数据
        """
        for data in data_list:
            if 'operator_date' not in data:
                data['operator_date'] = datetime.now()


        db_scan = [Scan(**data) for data in data_list]

        self.db.add_all(db_scan)
        self.db.commit()

        for scan in db_scan:
            self.db.refresh(scan)

        return db_scan

    def get_by_id(self, id: int) -> Optional[Scan]:
        return self.db.query(Scan).filter(Scan.id == id).first()

    def get_scan_info(self, where: Dict[str, Any]) -> List[Scan]:
        return self.db.query(Scan).filter_by(**where).all()

    def get_one_scan_info(self, where: Dict[str, Any]) -> Optional[Scan]:
        return self.db.query(Scan).filter_by(**where).first()

    def get_scan_by_folder(
        self,
        task_id: int,
        register_id: int,
        dir_path: str,
        dir_name: str,
    ) -> Optional[Scan]:
        return self.get_one_scan_info({
            "task_id": task_id,
            "register_id": register_id,
            "dir_path": dir_path,
            "dir_name": dir_name,
        })

    def get_scan_info_taskId(self, task_ids: list) -> List[Scan]:
        if not task_ids:
            return []
        return self.db.query(Scan).filter(Scan.task_id.in_(task_ids)).all()

    def update(self, id: int, update: Dict[str, Any]) -> bool:
        scan = self.get_by_id(id)
        if scan is None:
            return False
        try:
            for key, value in update.items():
                if hasattr(scan, key):
                    setattr(scan, key, value)

            self.db.commit()
            self.db.refresh(scan)
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_dir_name(self, dir_name: str) -> bool:
        scan = self.db.query(Scan).filter(Scan.dir_name.like(dir_name)).all()
        if scan:
            return True
        return False



scan_service = ScanService()