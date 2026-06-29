# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : workflow_service.py
# @Desc     : 
# @Time     : 2025/12/16 15:06
# @Software : PyCharm

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.db import SessionLocal
from src.models.workflow import Workflow

class WorkflowService:
    """工作流服务类"""
    def __init__(self, db: Optional[Session] = None):
        """
        初始化
        :param db: 数据库会话
        """
        # 支持外部传入会话（如事务场景），否则自动获取会话
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        """
        静态方法：获取数据库会话（内部使用）
        自动管理会话生命周期
        """
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def get_all_workflows(self, is_work=False) -> Workflow:
        if is_work:
            return self.db.query(Workflow).filter(Workflow.is_work == 1).order_by(Workflow.id.asc()).all()
        else:
            return self.db.query(Workflow).order_by(Workflow.id.asc()).all()

    def get_workflow_status_by_name(self, name: str) -> Workflow:
        return self.db.query(Workflow).filter(Workflow.work_name == name).first()

    def save_workflow(self, data: list[str]) -> Optional[Workflow]:
        workflow = self.get_all_workflows()

        for work in workflow:
            if work.work_name in data:
                work.status = True
            else:
                work.status = False

            self.db.commit()
            self.db.refresh(work)
        print(f'workflow = {workflow}')
        return workflow



workflow_service = WorkflowService()