# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : operation_service.py
# @Desc     : 
# @Time     : 2026/3/7 11:17
# @Software : PyCharm

from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy.sql import and_, or_
from typing import List, Optional, Dict, Any, Union
from sqlalchemy import func
from sqlalchemy.orm import Query

from src.core.db import SessionLocal
from src.models.operation import Operation

class OperationService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())


    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def save_data(self, data_list: List[Dict[str, Any]]) -> List[Operation]:
        """
        保存数据
        """
        for data in data_list:
            if 'operator_date' not in data:
                data['operator_date'] = datetime.now()

        db_operation = [Operation(**data) for data in data_list]
        self.db.add_all(db_operation)
        self.db.commit()

        for operation in db_operation:
            self.db.refresh(operation)

        return db_operation

    def get_by_id(self, id: int) -> Optional[Operation]:
        return self.db.query(Operation).filter(Operation.id == id).first()

    def get_list(
            self,
            skip: int = 0,
            limit: int = 100,
            operator: Optional[str] = None,
            task_id: Optional[int] = None,
            task_name: Optional[str] = None,
            task_number_start: Optional[str] = None,
            task_number_end: Optional[str] = None,
            operator_date: Optional[datetime] = None,
        ) -> List[Operation]:
        query = self.db.query(Operation)

        if task_id is not None:
            query = query.filter(Operation.task_id == task_id)

        if task_name is not None:
            query = query.filter(Operation.task_name == task_name)

        if task_number_start is not None:
            query = query.filter(Operation.task_number_start == task_number_start)

        if task_number_end is not None:
            query = query.filter(Operation.task_number_end == task_number_end)

        if operator is not None:
            query = query.filter(Operation.operator == operator)

        # if operator_date is not None:
        #     query = query.filter(Operation.operator_date == operator_date)

        query = query.filter(Operation.task_id > 0)
        return query.order_by(Operation.operator).offset(skip).limit(limit).all()

    def get_total_count(self, **filters) -> int:
        query = self.db.query(Operation)
        # 动态添加过滤条件
        for key, value in filters.items():
            if hasattr(Operation, key):
                query = query.filter(getattr(Operation, key) == value)

        query = query.filter(Operation.task_id > 0)
        return query.count()

    def count_task_by_operator(
            self,
            distinct: bool = False,
            filters: Optional[Union[List, tuple]] = None  # 新增：过滤条件参数
    ) -> List[Dict[str, Optional[str | int]]]:
        """
        按操作员统计任务数量（支持过滤条件）

        Args:
            distinct: 是否统计去重后的任务名称（True=去重，False=不去重）
            filters: 过滤条件列表/元组，支持SQLAlchemy的filter条件，例如：
                     [Operation.status == 'completed', Operation.create_time >= '2026-01-01']

        Returns:
            包含操作员和对应任务数量的字典列表，格式：[{"operator": "操作员", "task_count": 数量}]
        """
        # 1. 定义统计逻辑
        count_column = Operation.task_name
        count_expr = func.count(func.distinct(count_column)).label("task_count") if distinct else func.count(
            count_column).label("task_count")

        # 2. 构建基础查询
        query: Query = (
            self.db.query(
                Operation.operator.label("operator"),
                count_expr
            )
            .group_by(Operation.operator)
            .order_by(Operation.operator)
        )

        # 3. 新增：添加过滤条件（核心逻辑）
        if filters:
            # 处理单个条件或多个条件组合
            if isinstance(filters, (list, tuple)):
                # 多条件默认用AND连接，也可根据需求改为or_
                query = query.filter(and_(*filters))
            else:
                # 单个条件直接传入
                query = query.filter(filters)

        try:
            # 4. 执行查询并转换结果
            result = query.all()
            result_dict = [row._asdict() for row in result]
        except Exception as e:
            result_dict = []

        return result_dict

operation_service = OperationService()