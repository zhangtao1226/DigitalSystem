# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : register_service.py
# @Desc      : 领卷登记服务层
# @Time      : 2025/12/2 14:00
# @Software  : PyCharm

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.db import SessionLocal
from src.models.register import Register


class RegisterService:
    """领卷登记服务类"""
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

    # ------------------------------ 新增操作 ------------------------------
    def create(
            self,
            archive_type: str,
            category: str,
            batch_number: str,
            number_start: str,
            number_end: str,
            register: str,
            is_question: bool = False,
            is_distribute: bool = False,
            status: int = 0,
            task_node: int = 0,
            is_import: bool = False,
    ) -> Register:
        """
        新增领卷登记记录
        :param archive_type: 档案类别（必填）
        :param category: 类型（必填）
        :param batch_number: 批次号（必填，唯一）
        :param number_start: 开始卷/件号（必填）
        :param number_end: 终止卷/件号（必填）
        :param register: 登记人（必填）
        :param is_question: 是否登记问题（默认 False）
        :param is_distribute: 是否分配（默认 False）
        :param status: 状态（默认 0: 保存; 1: 提交）
        :param task_node: 任务节点(默认0; 领卷登记)
        :return: 新增的 Register 对象（含数据库自增 ID）
        """
        db_register = Register(
            archive_type=archive_type,
            category=category,
            batch_number=batch_number,
            number_start=number_start,
            number_end=number_end,
            register=register,
            is_question=is_question,
            is_distribute=is_distribute,
            register_date=datetime.now(),  # 自动填充当前时间
            status=status,
            task_node=task_node,
            is_import=is_import
        )

        self.db.add(db_register)
        self.db.commit()
        self.db.refresh(db_register)
        return db_register

    # ------------------------------ 查询操作 ------------------------------
    def get_by_id(self, register_id: int) -> Optional[Register]:
        """
        根据 ID 查询单条登记记录
        :param register_id: 登记记录 ID
        :return: 找到的 Register 对象，未找到返回 None
        """
        return self.db.query(Register).filter(Register.id == register_id).first()

    def get_by_batch_number(self, batch_number: str) -> Optional[Register]:
        """
        根据批次号查询登记记录（批次号唯一）
        :param batch_number: 批次号
        :return: 找到的 Register 对象，未找到返回 None
        """
        return self.db.query(Register).filter(Register.batch_number == batch_number).first()

    def get_list(
            self,
            skip: int = 0,
            limit: int = 100,
            archive_type: Optional[str] = None,
            category: Optional[str] = None,
            is_distribute: Optional[bool] = None,
            status: Optional[int] = None,
            task_node: Optional[int] = None,
            register: Optional[str] = None,
    ) -> List[Register]:
        """
        分页查询登记记录（支持多条件过滤）
        :param skip: 跳过前 N 条（默认 0，用于分页）
        :param limit: 最多返回 N 条（默认 100）
        :param archive_type: 档案类别（可选过滤条件）
        :param category: 类型（可选过滤条件）
        :param is_distribute: 是否分配（可选过滤条件）
        :param status: 状态（可选过滤条件）
        :param task_node: 任务节点 (可选过滤条件)
        :param register: 登记人
        :return: 登记记录列表
        """
        query = self.db.query(Register)
        # 条件过滤（仅当参数不为 None 时添加）
        if archive_type is not None:
            query = query.filter(Register.archive_type == archive_type)
        if category is not None:
            query = query.filter(Register.category == category)
        if is_distribute is not None:
            query = query.filter(Register.is_distribute == is_distribute)
        if status is not None:
            query = query.filter(Register.status == status)
        if task_node is not None:
            query = query.filter(Register.task_node <= task_node)

        if register is not None:
            query = query.filter(Register.register == register)

        return query.order_by(Register.id.desc()).offset(skip).limit(limit).all()

    def get_total_count(self, **filters) -> int:
        """
        获取符合条件的记录总数（用于分页计算）
        :param filters: 过滤条件字典（如 {"archive_type": "人事档案", "is_distribute": True}）
        :return: 记录总数
        """
        query = self.db.query(Register)
        # 动态添加过滤条件
        for key, value in filters.items():
            if hasattr(Register, key) and value is not None:
                query = query.filter(getattr(Register, key) == value)
        return query.count()

    # ------------------------------ 更新操作 ------------------------------
    def update(self, register_id: int, update_data: Dict[str, Any]) -> Optional[Register]:
        """
        根据 ID 更新登记记录（支持部分字段更新）
        :param register_id: 要更新的登记记录 ID
        :param update_data: 要更新的字段字典（如 {"status": "已分配", "is_distribute": True}）
        :return: 更新后的 Register 对象，未找到返回 None
        """
        db_register = self.get_by_id(register_id)
        if not db_register:
            return None

        for key, value in update_data.items():
            if hasattr(Register, key):
                setattr(db_register, key, value)

        self.db.commit()
        self.db.refresh(db_register)
        return db_register

    # ------------------------------ 删除操作 ------------------------------
    def delete(self, register_id: int) -> bool:
        """
        根据 ID 删除登记记录
        :param register_id: 要删除的登记记录 ID
        :return: 删除成功返回 True，未找到返回 False
        """
        db_register = self.get_by_id(register_id)
        if not db_register:
            return False

        self.db.delete(db_register)
        self.db.commit()
        return True

    # ------------------------------ 批量操作（新增扩展功能） ------------------------------
    def batch_create(self, register_list: List[Dict[str, Any]]) -> List[Register]:
        """
        批量新增登记记录（提高批量插入效率）
        :param register_list: 登记记录列表（每个元素是字段字典）
        :return: 新增的 Register 对象列表
        """
        # 补充默认字段（如登记时间）
        for item in register_list:
            if "register_date" not in item:
                item["register_date"] = datetime.now()
            if "is_question" not in item:
                item["is_question"] = False
            if "is_distribute" not in item:
                item["is_distribute"] = False
            if "status" not in item:
                item["status"] = 0
            if "task_node" not in item:
                item["task_node"] = 0

        # 批量创建对象并添加到会话
        db_registers = [Register(**item) for item in register_list]
        self.db.add_all(db_registers)
        self.db.commit()

        # 刷新所有对象以获取自增 ID
        for register in db_registers:
            self.db.refresh(register)

        return db_registers

    def get_data(self, where: Dict[str, Any]) -> List[Register]:

        return self.db.query(Register).filter_by(**where).all()


#创建控制器实例（方便其他模块导入使用）
register_service = RegisterService()
