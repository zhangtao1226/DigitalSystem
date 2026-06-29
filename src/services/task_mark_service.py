# -*-coding : utf-8 -*-
# @Author   : zhangTao
# @File     : task_mark_service.py
# @Time     : 2026/6/12 16:58
# @Desc     : 质检标记 Service —— 增删改查 / 分页 / 统计 / 闭环管理

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import asc, desc, func, or_
from src.core.db import SessionLocal
from src.models.task_mark_model import TaskMark


MARK_STAGE = {
    "扫描质检": 1,
    "图像处理质检": 2,
    "目录质检": 3,
    "分件质检": 4
}

MARK_TYPES = {
    1: ["缺页", "超扫页", "重复扫描", "图像模糊", "图像歪斜", "页面污损", "其他"],
    2: ["黑边未处理", "图片倾斜", "色彩异常", "裁切不当", "其他"],
    3: ["档号错误", "题名错误", "日期错误", "页数错误", "保管期限错误", "责任者错误", "其他"],
    4: ["分件缺页", "分件多页", "分件错误", "图像异常", "分件命名错误","其他"]
}

MARK_STAGE_REVERSE = {v: k for k, v in MARK_STAGE.items()}

class TaskMarkService:
    def __init__(self, db: Optional[SessionLocal] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def add_mark(self, data: Dict[str, Any]) -> Optional[TaskMark]:
        try:
            mark = TaskMark(
                task_id=data["task_id"],
                batch_number=data["batch_number"],
                task_node=data["task_node"],
                mark_stage=data["mark_stage"],
                mark_type=data["mark_type"],
                level=data.get("level", "一般"),
                description=data.get("description", ""),
                inspector=data["inspector"],
                mark_date=data.get(
                    "mark_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ),
                # 可选
                scan_file=data.get("scan_file"),
                field_name=data.get("field_name"),
                field_value_before=data.get("field_value_before"),
                field_value_after=data.get("field_value_after"),
                is_fixed=data.get("is_fixed", False),
                fix_date=data.get("fix_date"),
                fix_people=data.get("fix_people"),
                fix_remark=data.get("fix_remark"),
                is_deleted=False,
            )
            self.db.add(mark)
            self.db.commit()
            self.db.refresh(mark)
            return mark
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"add_mark 失败: {e}") from e

    def batch_add_marks(self, data_list: List[Dict[str, Any]]) -> List[TaskMark]:
        try:
            marks = []
            for data in data_list:
                mark = TaskMark(
                    task_id=data["task_id"],
                    batch_number=data["batch_number"],
                    task_node=data["task_node"],
                    mark_stage=data["mark_stage"],
                    mark_type=data["mark_type"],
                    level=data.get("level", "一般"),
                    description=data.get("description", ""),
                    inspector=data["inspector"],
                    mark_date=data.get(
                        "mark_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ),
                    scan_file=data.get("scan_file"),
                    page_no=data.get("page_no"),
                    field_name=data.get("field_name"),
                    field_value_before=data.get("field_value_before"),
                    field_value_after=data.get("field_value_after"),
                    is_fixed=data.get("is_fixed", False),
                    fix_date=data.get("fix_date"),
                    fix_people=data.get("fix_people"),
                    fix_remark=data.get("fix_remark"),
                    is_deleted=False,
                )
                marks.append(mark)
            self.db.add_all(marks)
            self.db.commit()
            for m in marks:
                self.db.refresh(m)
            return marks
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"batch_add_marks 失败: {e}") from e

    def get_by_id(self, mark_id: int) -> Optional[TaskMark]:
        return (
            self.db.query(TaskMark)
            .filter(TaskMark.id == mark_id, TaskMark.is_deleted == False)
            .first()
        )

    def get_mark_info(self, condition: Dict[str, Any]) -> List[TaskMark]:
        q = self.db.query(TaskMark).filter(TaskMark.is_deleted == False)

        if "task_id" in condition:
            q = q.filter(TaskMark.task_id == condition["task_id"])
        if "batch_number" in condition:
            q = q.filter(TaskMark.batch_number == condition["batch_number"])
        if "task_node" in condition:
            q = q.filter(TaskMark.task_node == condition["task_node"])
        if "mark_stage" in condition:
            q = q.filter(TaskMark.mark_stage == condition["mark_stage"])
        if "mark_type" in condition:
            q = q.filter(TaskMark.mark_type == condition["mark_type"])
        if "level" in condition:
            q = q.filter(TaskMark.level == condition["level"])
        if "inspector" in condition:
            q = q.filter(TaskMark.inspector == condition["inspector"])
        if "is_fixed" in condition:
            q = q.filter(TaskMark.is_fixed == condition["is_fixed"])
        if "scan_file" in condition:
            q = q.filter(TaskMark.scan_file == condition["scan_file"])

        return q.order_by(desc(TaskMark.mark_date)).all()

    def get_unfixed_marks_by_task_nodes(self, task_nodes: List[Dict[str, Any]]) -> List[TaskMark]:
        """
        根据 [{"id": task_id, "task_node": task_node}, ...] 查询未完成标记。

        参数中的 id 对应 task 表主键, 也就是 task_mark.task_id。
        task_id 与 task_node 必须成对匹配, 避免多个任务节点交叉查询出错误标记。
        """
        task_node_pairs = set()
        for item in task_nodes or []:
            task_id = item.get("id")
            task_node = item.get("task_node")
            if task_id is None or task_node is None:
                continue
            task_node_pairs.add((task_id, task_node))

        if not task_node_pairs:
            return []

        task_ids = [task_id for task_id, _ in task_node_pairs]
        marks = (
            self.db.query(TaskMark)
            .filter(
                TaskMark.task_id.in_(task_ids),
                TaskMark.is_fixed == False,
                TaskMark.is_deleted == False,
            )
            .order_by(asc(TaskMark.mark_date), asc(TaskMark.id))
            .all()
        )

        return [
            mark
            for mark in marks
            if (mark.task_id, mark.task_node) in task_node_pairs
        ]

    def has_unfixed_marks_by_task_nodes(self, task_nodes: List[Dict[str, Any]]) -> bool:
        """根据任务 id 和 task_node 列表判断是否存在未完成标记。"""
        return bool(self.get_unfixed_marks_by_task_nodes(task_nodes))

    def get_pending_marks_by_file(self, task_id: int, scan_file: str) -> List[TaskMark]:
        return (
            self.db.query(TaskMark)
            .filter(
                TaskMark.task_id == task_id,
                TaskMark.scan_file == scan_file,
                TaskMark.is_fixed == False,
                TaskMark.is_deleted == False,
            )
            .order_by(asc(TaskMark.mark_date))
            .all()
        )

    def get_pending_marks_by_folder(
        self, task_id: int, folder_path: str
    ) -> List[TaskMark]:

        return (
            self.db.query(TaskMark)
            .filter(
                TaskMark.task_id == task_id,
                TaskMark.is_fixed == False,
                TaskMark.is_deleted == False,
                TaskMark.scan_file != None,  # 目录质检无 scan_file，排除
            )
            .order_by(asc(TaskMark.mark_date))
            .all()
        )

    def get_marks_by_task(self, task_id: int) -> List[TaskMark]:
        return (
            self.db.query(TaskMark)
            .filter(TaskMark.task_id == task_id, TaskMark.is_deleted == False)
            .order_by(desc(TaskMark.mark_date))
            .all()
        )

    def get_page(
        self,
        page: int = 1,
        page_size: int = 20,
        task_id: Optional[int] = None,
        mark_stage: Optional[int] = None,
        level: Optional[str] = None,
        is_fixed: Optional[bool] = None,
        keyword: Optional[str] = None,
        order_by: str = "mark_date",
        order_dir: str = "desc",
    ) -> Tuple[List[TaskMark], int]:

        q = self.db.query(TaskMark).filter(TaskMark.is_deleted == False)

        if task_id is not None:
            q = q.filter(TaskMark.task_id == task_id)
        if mark_stage is not None:
            q = q.filter(TaskMark.mark_stage == mark_stage)
        if level is not None:
            q = q.filter(TaskMark.level == level)
        if is_fixed is not None:
            q = q.filter(TaskMark.is_fixed == is_fixed)

        if keyword:
            kw = f"%{keyword}%"
            q = q.filter(
                or_(
                    TaskMark.mark_type.like(kw),
                    TaskMark.description.like(kw),
                    TaskMark.scan_file.like(kw),
                    TaskMark.inspector.like(kw),
                    TaskMark.field_name.like(kw),
                )
            )

        col_map = {
            "mark_date": TaskMark.mark_date,
            "level": TaskMark.level,
            "mark_type": TaskMark.mark_type,
            "id": TaskMark.id,
        }
        col = col_map.get(order_by, TaskMark.mark_date)
        q = q.order_by(asc(col) if order_dir == "asc" else desc(col))

        total = q.count()
        offset = (page - 1) * page_size
        items = q.offset(offset).limit(page_size).all()
        return items, total

    def update_mark(self, mark_id: int, data: Dict[str, Any]) -> Optional[TaskMark]:

        IMMUTABLE = {
            "id",
            "task_id",
            "batch_number",
            "task_node",
            "inspector",
            "mark_date",
        }
        mark = self.get_by_id(mark_id)
        if not mark:
            return None
        try:
            for key, val in data.items():
                if key not in IMMUTABLE and hasattr(mark, key):
                    setattr(mark, key, val)
            self.db.commit()
            self.db.refresh(mark)
            return mark
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"update_mark 失败 (id={mark_id}): {e}") from e

    def mark_fixed(
        self, mark_id: int, fix_data: Optional[Dict[str, Any]] = None
    ) -> Optional[TaskMark]:

        mark = self.get_by_id(mark_id)
        if not mark:
            return None
        try:
            mark.is_fixed = True
            mark.fix_date = (fix_data or {}).get(
                "fix_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            mark.fix_remark = (fix_data or {}).get("fix_remark", "")
            if fix_data and "field_value_after" in fix_data:
                mark.field_value_after = fix_data["field_value_after"]
            self.db.commit()
            self.db.refresh(mark)
            return mark
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"mark_fixed 失败 (id={mark_id}): {e}") from e

    def batch_mark_fixed(
        self,
        mark_ids: List[int],
        fix_remark: str = "",
        operator: str = "",
    ) -> int:

        if not mark_ids:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        remark = fix_remark or (
            f"批量确认修改完成（操作人：{operator}）"
            if operator
            else "批量确认修改完成"
        )
        try:
            updated = (
                self.db.query(TaskMark)
                .filter(
                    TaskMark.id.in_(mark_ids),
                    TaskMark.is_fixed == False,
                    TaskMark.is_deleted == False,
                )
                .all()
            )
            for m in updated:
                m.is_fixed = True
                m.fix_date = now
                m.fix_remark = remark
            self.db.commit()
            return len(updated)
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"batch_mark_fixed 失败: {e}") from e

    def reopen_mark(self, mark_id: int, reason: str = "") -> Optional[TaskMark]:

        mark = self.get_by_id(mark_id)
        if not mark:
            return None
        try:
            mark.is_fixed = False
            mark.fix_date = None
            mark.fix_remark = f"[撤销] {reason}" if reason else "[撤销已修改]"
            self.db.commit()
            self.db.refresh(mark)
            return mark
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"reopen_mark 失败 (id={mark_id}): {e}") from e

    def delete_mark(self, mark_id: int) -> bool:

        mark = self.get_by_id(mark_id)
        if not mark:
            return False
        try:
            mark.is_deleted = True
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"delete_mark 失败 (id={mark_id}): {e}") from e

    def batch_delete_marks(self, mark_ids: List[int]) -> int:
        if not mark_ids:
            return 0
        try:
            rows = (
                self.db.query(TaskMark)
                .filter(TaskMark.id.in_(mark_ids), TaskMark.is_deleted == False)
                .all()
            )
            for m in rows:
                m.is_deleted = True
            self.db.commit()
            return len(rows)
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"batch_delete_marks 失败: {e}") from e

    def hard_delete_mark(self, mark_id: int) -> bool:

        mark = self.db.query(TaskMark).filter(TaskMark.id == mark_id).first()
        if not mark:
            return False
        try:
            self.db.delete(mark)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"hard_delete_mark 失败 (id={mark_id}): {e}") from e

    def count_by_task(self, task_id: int) -> Dict[str, int]:

        base = self.db.query(TaskMark).filter(
            TaskMark.task_id == task_id, TaskMark.is_deleted == False
        )
        total = base.count()
        fixed = base.filter(TaskMark.is_fixed == True).count()
        pending = total - fixed

        level_rows = (
            self.db.query(TaskMark.level, func.count(TaskMark.id))
            .filter(TaskMark.task_id == task_id, TaskMark.is_deleted == False)
            .group_by(TaskMark.level)
            .all()
        )
        result = {"total": total, "pending": pending, "fixed": fixed}
        result.update({lv: cnt for lv, cnt in level_rows})
        return result

    def count_by_stage(self, task_id: int) -> Dict[str, Dict[str, int]]:

        rows = (
            self.db.query(
                TaskMark.mark_stage, TaskMark.is_fixed, func.count(TaskMark.id)
            )
            .filter(TaskMark.task_id == task_id, TaskMark.is_deleted == False)
            .group_by(TaskMark.mark_stage, TaskMark.is_fixed)
            .all()
        )
        result: Dict[str, Dict[str, int]] = {
            name: {"total": 0, "pending": 0, "fixed": 0}
            for name in MARK_STAGE_REVERSE.values()
        }
        for stage_id, is_fixed, cnt in rows:
            name = MARK_STAGE_REVERSE.get(stage_id, f"阶段{stage_id}")
            if name not in result:
                result[name] = {"total": 0, "pending": 0, "fixed": 0}
            result[name]["total"] += cnt
            if is_fixed:
                result[name]["fixed"] += cnt
            else:
                result[name]["pending"] += cnt
        return result

    def check_task_mark_pass(self, task_id: int) -> Tuple[bool, Dict[str, int]]:

        rows = (
            self.db.query(TaskMark.mark_stage, func.count(TaskMark.id))
            .filter(
                TaskMark.task_id == task_id,
                TaskMark.is_fixed == False,
                TaskMark.is_deleted == False,
            )
            .group_by(TaskMark.mark_stage)
            .all()
        )
        pending = {MARK_STAGE_REVERSE.get(s, f"阶段{s}"): c for s, c in rows}
        return (len(pending) == 0, pending)

    def get_total_count(self, **filters):
        query = self.db.query(TaskMark).filter(TaskMark.is_deleted == False)

        for key, value in filters.items():
            if hasattr(TaskMark, key) and value is not None:
                query = query.filter(getattr(TaskMark, key) == value)

        return query.count()

task_mark_service = TaskMarkService()
