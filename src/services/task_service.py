# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : task_service.py
# @Desc     : 
# @Time     : 2025/12/3 17:01
# @Software : PyCharm
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import asc, desc, func

from src.core.db import SessionLocal, fetch_page
from src.core.settings import settings
from src.models.task import Task
from src.services.workflow_service import workflow_service



class TaskService:
    # 主任务节点集合。settings.work_number 中部分节点名称带空格,
    # 这里统一通过 _work_number_by_name 做兼容匹配。
    MAIN_TASK_NODE_NAMES = (
        "拆卷/前处理",
        "扫描",
        "图像处理",
        "分件",
        "目录录入/校对",
        "成品转换/输出",
        "装订",
    )
    # 主流程流转图：
    # 图像处理后分为两支，分件和目录录入/校对都可以作为下一步。
    # 分件完成后仍可流向目录录入/校对；目录录入/校对完成后进入成品转换/输出。
    WORKFLOW_NEXT_NODE_NAMES = {
        "拆卷/前处理": ("扫描",),
        "扫描": ("图像处理",),
        "图像处理": ("分件", "目录录入/校对"),
        "分件": ("目录录入/校对",),
        "目录录入/校对": ("成品转换/输出",),
        "成品转换/输出": ("装订",),
        "装订": (),
    }

    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(self._get_db())


    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def batch_add(self, tasks_list: List[Dict[str, Any]]) -> List[Task]:
        """
        批量插入任务
        :param tasks_list:
        :return:
        """
        for task in tasks_list:
            if "dist_date" not in task:
                task["dist_date"] = datetime.now()

            if "operator_date" not in task:
                task["operator_date"] = datetime.now()

        db_task = [Task(**task) for task in tasks_list]
        self.db.add_all(db_task)
        self.db.commit()

        for task in db_task:
            self.db.refresh(task)

        return db_task

    def get_by_id(self, task_id: int) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_list(self,
                 skip: int = 0,
                 limit: int = 100,
                 operator: Optional[str] = None,
                 status: Optional[int] = None,
                 register_id: Optional[int] = None,
                 task_name: Optional[str] = None,
                 task_number_start: Optional[str] = None,
                 task_number_end: Optional[str] = None,
                 batch_number: Optional[str] = None,
                 order_by: bool = False,
    ) -> List[Task]:
        """
        分页查询
        :param skip: 跳过前 N 条（默认 0，用于分页）
        :param limit: 最多返回 N 条（默认 100）
        :param operator: 操作员
        :param status: 状态
        :param register_id: 登记记录ID
        :param task_name: 任务名称
        :param task_number_start: 任务段
        :param task_number_end: 任务段
        :param batch_number: 批次号
        :param order_by: 排序， True 时默认按照任务段开始号排序
        :return:
        """
        query = self.db.query(Task)

        if operator:
            query = query.filter(Task.operator == operator)
        if status is not None:
            query = query.filter(Task.status == status)
        if register_id:
            query = query.filter(Task.register_id == register_id)
        if task_name:
            query = query.filter(Task.task_name == task_name)
        if task_number_start:
            query = query.filter(Task.task_number_start == task_number_start)
        if task_number_end:
            query = query.filter(Task.task_number_end == task_number_end)
        if batch_number:
            query = query.filter(Task.batch_number == batch_number)
        if order_by:
            order_columns = (Task.task_number_start.asc(), Task.id.asc())
        else:
            order_columns = (Task.id.desc(), Task.task_node.asc())
        return fetch_page(query, Task, order_columns, skip, limit)

    def update(self, task_id: int, update_data: Dict[str, Any]) -> Optional[Task]:
        db_task = self.get_by_id(task_id)
        if not db_task:
            return None

        for key, value in update_data.items():
            if hasattr(db_task, key):
                setattr(db_task, key, value)

        self.db.commit()
        self.db.refresh(db_task)
        return db_task


    def get_total_count(self, **filters) -> int:
        query = self.db.query(Task)

        for key, value in filters.items():
            if hasattr(Task, key) and value is not None:
                query = query.filter(getattr(Task, key) == value)

        return query.count()

    def _completed_task_query(
            self,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ):
        query = self.db.query(Task).filter(
            Task.status == 1,
            Task.operator.isnot(None),
            Task.operator_date.isnot(None),
            Task.complete_number.isnot(None),
            func.trim(Task.complete_number) != "",
        )
        if operator:
            query = query.filter(Task.operator == operator)
        if start_date:
            query = query.filter(Task.operator_date >= start_date)
        if end_date:
            query = query.filter(Task.operator_date < end_date)
        return query

    @staticmethod
    def _append_unique(values: List[str], value: Optional[str]) -> None:
        value = (value or "").strip()
        if value and value not in values:
            values.append(value)

    @staticmethod
    def get_completed_volume_count(complete_number: Optional[str]) -> int:
        complete_number = (complete_number or "").strip()
        if not complete_number:
            return 0

        for separator in ("-", "~", "～", "—"):
            if separator in complete_number:
                number_start, number_end = complete_number.split(separator, 1)
                break
        else:
            return 1

        try:
            number_start = int(number_start.strip())
            number_end = int(number_end.strip())
        except ValueError:
            return 0

        if number_end < number_start:
            return 0
        return number_end - number_start + 1

    @staticmethod
    def _range_text(number_start: Optional[str], number_end: Optional[str]) -> str:
        number_start = (number_start or "").strip()
        number_end = (number_end or "").strip()
        if number_start and number_end:
            return f"{number_start}-{number_end}"
        return number_start or number_end

    @staticmethod
    def _range_end_value(range_text: Optional[str]) -> Optional[int]:
        range_text = (range_text or "").strip()
        if not range_text:
            return None

        for separator in ("-", "~", "～", "—"):
            if separator in range_text:
                _, number_end = range_text.split(separator, 1)
                break
        else:
            number_end = range_text

        try:
            return int(number_end.strip())
        except ValueError:
            return None

    @classmethod
    def _task_status_text(cls, task: Task) -> str:
        if task.is_do:
            return "完成"

        completed_end = cls._range_end_value(task.complete_number)
        assigned_end = cls._range_end_value(cls._range_text(task.task_number_start, task.task_number_end))
        if completed_end is not None and assigned_end is not None and completed_end >= assigned_end:
            return "完成"
        return "进行中"

    def get_completed_statistics(
            self,
            skip: int = 0,
            limit: int = 100,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            self._completed_task_query(operator=operator, start_date=start_date, end_date=end_date)
            .with_entities(
                Task.operator.label("operator"),
                func.count(func.distinct(Task.batch_number)).label("batch_count"),
                func.count(Task.id).label("task_count"),
                func.count(func.distinct(Task.task_name)).label("workflow_count"),
                func.min(Task.operator_date).label("first_done_at"),
                func.max(Task.operator_date).label("last_done_at"),
            )
            .group_by(Task.operator)
            .order_by(Task.operator.asc())
        )
        rows = query.offset(skip).limit(limit).all()
        result = [row._asdict() for row in rows]
        operators = [item["operator"] for item in result if item.get("operator")]
        if not operators:
            return result

        detail_rows = (
            self._completed_task_query(operator=operator, start_date=start_date, end_date=end_date)
            .filter(Task.operator.in_(operators))
            .order_by(Task.operator.asc(), Task.operator_date.asc(), Task.id.asc())
            .all()
        )
        detail_map = {
            operator_name: {
                "batch_numbers": [],
                "batch_ranges": [],
                "assigned_segments": [],
                "task_statuses": [],
                "completed_segments": [],
                "workflow_names": [],
                "volume_count": 0,
            }
            for operator_name in operators
        }
        for task in detail_rows:
            detail = detail_map.setdefault(task.operator, {
                "batch_numbers": [],
                "batch_ranges": [],
                "assigned_segments": [],
                "task_statuses": [],
                "completed_segments": [],
                "workflow_names": [],
                "volume_count": 0,
            })
            self._append_unique(detail["batch_numbers"], task.batch_number)
            self._append_unique(detail["batch_ranges"], self._range_text(task.number_start, task.number_end))
            self._append_unique(detail["assigned_segments"], self._range_text(task.task_number_start, task.task_number_end))
            self._append_unique(detail["task_statuses"], self._task_status_text(task))
            self._append_unique(detail["completed_segments"], task.complete_number)
            self._append_unique(detail["workflow_names"], task.task_name)
            detail["volume_count"] += self.get_completed_volume_count(task.complete_number)

        for item in result:
            detail = detail_map.get(item["operator"], {})
            item["batch_numbers"] = "、".join(detail.get("batch_numbers", []))
            item["batch_ranges"] = "、".join(detail.get("batch_ranges", []))
            item["assigned_segments"] = "、".join(detail.get("assigned_segments", []))
            item["task_statuses"] = "、".join(detail.get("task_statuses", []))
            item["completed_segments"] = "、".join(detail.get("completed_segments", []))
            item["workflow_names"] = "、".join(detail.get("workflow_names", []))
            item["volume_count"] = detail.get("volume_count", 0)

        return result

    def get_completed_statistics_count(
            self,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> int:
        grouped_query = (
            self._completed_task_query(operator=operator, start_date=start_date, end_date=end_date)
            .with_entities(Task.operator)
            .group_by(Task.operator)
            .subquery()
        )
        return self.db.query(func.count()).select_from(grouped_query).scalar() or 0

    def get_completed_statistics_summary(
            self,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        row = (
            self._completed_task_query(operator=operator, start_date=start_date, end_date=end_date)
            .with_entities(
                func.count(func.distinct(Task.operator)).label("operator_count"),
                func.count(func.distinct(Task.batch_number)).label("batch_count"),
                func.count(Task.id).label("task_count"),
                func.count(func.distinct(Task.task_name)).label("workflow_count"),
            )
            .one()
        )
        return {
            "operator_count": row.operator_count or 0,
            "batch_count": row.batch_count or 0,
            "task_count": row.task_count or 0,
            "workflow_count": row.workflow_count or 0,
            "volume_count": sum(
                self.get_completed_volume_count(task.complete_number)
                for task in self._completed_task_query(
                    operator=operator,
                    start_date=start_date,
                    end_date=end_date,
                ).all()
            ),
        }

    def get_completed_detail_list(
            self,
            skip: int = 0,
            limit: int = 100,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> List[Task]:
        return (
            self._completed_task_query(operator=operator, start_date=start_date, end_date=end_date)
            .order_by(Task.operator_date.desc(), Task.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_completed_detail_count(
            self,
            operator: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
    ) -> int:
        return self._completed_task_query(
            operator=operator,
            start_date=start_date,
            end_date=end_date,
        ).count()

    def get_last_one(self):
        """
        获取最后一条任务
        :return:
        """
        query = self.db.query(Task)

        return query.order_by(Task.id.desc()).first()

    def get_data(self, where: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据条件查询数据
        """
        return self.db.query(Task).filter_by(**where).all()

    def delete_task(self, id: int):
        db_question = self.get_by_id(id)
        if not db_question:
            return False

        self.db.delete(db_question)
        self.db.commit()
        return True

    def get_next_available_node(self, curr_task):
        next_nodes = self.get_next_available_nodes(curr_task)
        return next_nodes[0] if next_nodes else None

    def get_next_available_nodes(self, curr_task):
        main_node_vals = self._main_task_node_vals()
        if curr_task.task_node not in main_node_vals:
            next_node = self.db.query(func.min(Task.task_node)).filter(
                Task.batch_number == curr_task.batch_number,
                Task.task_node > curr_task.task_node,
                Task.register_id == curr_task.register_id,
            ).scalar()
            return [next_node] if next_node else []

        next_nodes = []
        visited = set()

        def task_node_exists(node_val):
            return self.db.query(Task.id).filter(
                Task.batch_number == curr_task.batch_number,
                Task.register_id == curr_task.register_id,
                Task.task_node == node_val,
            ).first() is not None

        def collect_available_from(node_val):
            if node_val is None or node_val in visited:
                return

            visited.add(node_val)
            node_name = self._node_name(node_val)
            next_node_vals = [
                self._work_number_by_name(next_name)
                for next_name in self._workflow_next_node_names(node_name)
            ]
            direct_next_nodes = [
                next_node_val
                for next_node_val in next_node_vals
                if next_node_val is not None and task_node_exists(next_node_val)
            ]
            if direct_next_nodes:
                next_nodes.extend(direct_next_nodes)
                return

            for next_node_val in next_node_vals:
                collect_available_from(next_node_val)

        curr_name = self._node_name(curr_task.task_node)
        direct_next_node_vals = [
            self._work_number_by_name(next_name)
            for next_name in self._workflow_next_node_names(curr_name)
        ]
        direct_next_nodes = [
            next_node_val
            for next_node_val in direct_next_node_vals
            if next_node_val is not None and task_node_exists(next_node_val)
        ]
        if direct_next_nodes:
            return direct_next_nodes

        for next_node_val in direct_next_node_vals:
            collect_available_from(next_node_val)

        return next_nodes

    def get_previous_node_all_info(self, id: int, register_id: int, batch_number: str) -> List[Dict[str, Any]]:
        """
        获取当前任务上一个实际存在节点的所有任务信息。

        不能使用 task_node - 1 判断前置节点, 因为任务节点是选配的,
        同一 register_id、batch_number 下的 task_node 可能不连续。
        同一节点也可能按任务段分配给多人, 因此返回 list。
        """
        curr_task = self.db.query(Task).filter(
            Task.id == id,
            Task.register_id == register_id,
            Task.batch_number == batch_number,
        ).first()
        if not curr_task:
            return []

        previous_task_node = self.db.query(func.max(Task.task_node)).filter(
            Task.register_id == curr_task.register_id,
            Task.batch_number == curr_task.batch_number,
            Task.task_node < curr_task.task_node,
        ).scalar()
        if previous_task_node is None:
            return []

        previous_tasks = self.db.query(Task).filter(
            Task.register_id == curr_task.register_id,
            Task.batch_number == curr_task.batch_number,
            Task.task_node == previous_task_node,
        ).order_by(Task.task_number_start.asc(), Task.id.asc()).all()

        return [
            {
                "id": task.id,
                "task_id": task.task_id,
                "register_id": task.register_id,
                "batch_number": task.batch_number,
                "number_start": task.number_start,
                "number_end": task.number_end,
                "task_name": task.task_name,
                "task_number_start": task.task_number_start,
                "task_number_end": task.task_number_end,
                "complete_number": task.complete_number,
                "operator": task.operator,
                "dist_officer": task.dist_officer,
                "dist_date": task.dist_date,
                "status": task.status,
                "is_ready": task.is_ready,
                "is_do": task.is_do,
                "task_node": task.task_node,
                "operator_date": task.operator_date,
            }
            for task in previous_tasks
        ]

    @staticmethod
    def _node_name(node_val):
        """根据 task_node 数值反查节点名称(task_name)"""
        for name, num in settings.work_number.items():
            if num == node_val:
                return name
        return None

    @staticmethod
    def _normalize_node_name(name):
        return "".join(str(name).split())

    @classmethod
    def _work_number_by_name(cls, node_name):
        node_name = cls._normalize_node_name(node_name)
        for name, num in settings.work_number.items():
            if cls._normalize_node_name(name) == node_name:
                return num
        return None

    @classmethod
    def _workflow_next_node_names(cls, node_name):
        node_name = cls._normalize_node_name(node_name)
        for name, next_names in cls.WORKFLOW_NEXT_NODE_NAMES.items():
            if cls._normalize_node_name(name) == node_name:
                return next_names
        return ()

    @classmethod
    def _main_task_node_vals(cls):
        return tuple(
            node_val
            for node_val in (cls._work_number_by_name(name) for name in cls.MAIN_TASK_NODE_NAMES)
            if node_val is not None
        )

    @staticmethod
    def _task_complete_range(task):
        if not task.complete_number or "-" not in task.complete_number:
            return None, None
        number_start, number_end = task.complete_number.split("-", 1)
        return number_start, number_end

    def _activate_node(self, curr_task, target_node_val):
        """
        激活目标节点上与当前任务区间重叠的下游任务。
        以当前提交的节点(curr_task.task_node)作为前置节点, 只要前置有任意一段已提交完成
        (complete_number 非空), 即把对应下游任务标记为就绪(is_ready)。
        注: 采用 complete_number 而非 is_do 判断, 以支持上游分批提交——上游提交了一批
        (如 0001-0010, 任务尚未整段完工), 下游即可开始处理该批, 无需等整段完工。
        :param curr_task: 刚提交的当前任务
        :param target_node_val: 待激活的目标节点号
        """
        curr_complete_start, curr_complete_end = self._task_complete_range(curr_task)
        if not curr_complete_start or not curr_complete_end:
            return

        affected_downstream = self.db.query(Task).filter(
            Task.batch_number == curr_task.batch_number,
            Task.register_id == curr_task.register_id,
            Task.task_number_start <= curr_complete_end,
            Task.task_number_end >= curr_complete_start,
            Task.task_node == target_node_val,
        ).all()

        for t_next in affected_downstream:
            # 前置 = 触发本次激活的当前节点
            pre_required = self.db.query(Task).filter(
                Task.batch_number == t_next.batch_number,
                Task.register_id == t_next.register_id,
                Task.task_node == curr_task.task_node,
                Task.task_number_start <= t_next.task_number_end,
                Task.task_number_end >= t_next.task_number_start,
            ).all()
            for p in pre_required:
                pre_complete_start, pre_complete_end = self._task_complete_range(p)
                if (
                    pre_complete_start
                    and pre_complete_end
                    and pre_complete_start <= t_next.task_number_end
                    and pre_complete_end >= t_next.task_number_start
                ):
                    t_next.is_ready = True
                    break

    def execute_task_submission(self, task_id: int, number_end: str):
        curr_task = self.db.query(Task).filter(Task.id == task_id).first()
        if not curr_task:
            return {"status": "error", "message": "任务不存在"}

        if curr_task.status != 1:
            return {"status": "error", "message": "任务尚未发布， 无法执行"}

        if not curr_task.is_ready:
            return {"status": "error", "message": "前置任务尚未完成, 请等待"}

        if curr_task.is_do:
            return {"status": "waring", "message": "该任务已经提交"}

        if number_end >= curr_task.task_number_end:
            curr_task.is_do = True

        curr_task.complete_number = f"{curr_task.task_number_start}-{number_end}"
        curr_task.operator_date = datetime.now()
        self.db.flush()

        # 按主任务流程激活下一个实际存在节点；图像处理后可同时激活两个分支。
        next_node_vals = self.get_next_available_nodes(curr_task)
        for next_node_val in next_node_vals:
            self._activate_node(curr_task, next_node_val)

        self.db.commit()

        if not next_node_vals:
            return {"status": "success", "message": "该批次流程已结束!"}
        return {"status": "success", "message": "提交成功"}

    def check_full_coverage(self, target_s, target_e, parts):
        sorted_parts = sorted(parts, key=lambda x: x.task_number_start)
        print(f"sorted_parts: {sorted_parts}")
        curr_max = target_s
        print(f"curr_max: {curr_max}")
        for p in sorted_parts:
            if p.task_number_start > curr_max:
                return False
            curr_max = max(curr_max, p.task_number_end)
        print(1111, curr_max, target_s, target_e, f"{curr_max > target_e}")
        return curr_max >= target_e

    def get_task_progress_desc(self, id: int):
        task = self.get_by_id(id)
        nodes = {
            1: "拆卷/前处理",
            2: "扫描",
            3: "图像处理",
            4: "分件",
            5: "成品转换/输出",
            6: "目录录入/校对",
            7: "装订"
        }

        if task.is_do:
            return f"{nodes.get(task.task_node)}已完成"

        if task.is_ready:
            return f"当前{nodes.get(task.task_node)}中"
        return "等待上游"

task_service = TaskService()
