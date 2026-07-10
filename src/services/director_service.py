# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : director_service.py
# @Desc      : 
# @Time      : 2026/2/26 14:02
# @Software  : PyCharm
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import text

from src.core.db import (
    SessionLocal,
    build_fts5_query,
    can_use_fts5,
    fetch_page,
)
from src.models.director_model import DirectorModel as Director

class DirectorService:
    def __init__(self, db:Optional[Session] = None):
        self.db = db or next(self._get_db())

    @staticmethod
    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def batch_add(self, data_list: List[Dict[str, Any]]) -> dict[str, Any]:
        """
        批量保存目录数据
        """
        db_director = [Director(**data) for data in data_list]

        add_result = {
            "status": "success",
            "exit_list": []
        }
        try:
            exit_list = []
            for director in db_director.copy():
                condition = {
                    "doc_number": director.doc_number,
                    "archive_type": director.archive_type,
                    "category": director.category,
                    "title": director.title,
                }
                is_exit = self.get_dir_info(condition)
                if is_exit:
                    exit_list.append(director.doc_number)
                    db_director.remove(director)
                    continue
            add_result["exit_list"] = exit_list
        except Exception as e:
            print(e)

        if db_director:
            self.db.add_all(db_director)
            self.db.commit()
        return add_result

    def get_director_by_registerId(self, register_id: int) -> List[Director]:
        """
        根据登记ID获取目录数据
        """
        return self.db.query(Director).order_by(Director.id.asc()).filter(Director.register_id == register_id).all()


    def get_director_by_id(self, id: int) -> Optional[Director]:
        """"""
        return self.db.query(Director).filter(Director.id == id).first()


    def update_director(self, id, data: Dict[str, Any]) -> Optional[Director]:
        """
        根据id更新目录信息
        """
        director = self.get_director_by_id(id)
        if not director:
            return None

        for key, value in data.items():
            if hasattr(director, key) and value is not None:
                setattr(director, key, value)

        director.update_date = datetime.now()
        self.db.commit()
        self.db.refresh(director)
        return director

    def delete_director_by_id(self, id: int) -> bool:
        """"""
        director = self.get_director_by_id(id)
        if not director:
            return False

        self.db.delete(director)
        self.db.commit()
        return True

    def delete_director_by_registerId(self, register_id: int) -> bool:
        director = self.get_dir_info({"register_id": register_id})
        if director:
            for item in director:
                self.delete_director_by_id(item.id)

            return True
        else:
            return False

    def get_dir_info(self, where: Dict[str, Any]) -> List[Director]:
        return self.db.query(Director).filter_by(**where).all()

    @staticmethod
    def _apply_search_filters(query, title: str = None, doc_number: str = None):
        if title:
            if can_use_fts5("director_fts", title):
                query = query.filter(
                    text(
                        "director.id IN ("
                        "SELECT rowid FROM director_fts "
                        "WHERE director_fts MATCH :director_title_fts"
                        ")"
                    )
                ).params(
                    director_title_fts=f"title : {build_fts5_query(title)}"
                )
            else:
                query = query.filter(Director.title.like(f"%{title}%"))

        if doc_number:
            if can_use_fts5("director_fts", doc_number):
                query = query.filter(
                    text(
                        "director.id IN ("
                        "SELECT rowid FROM director_fts "
                        "WHERE director_fts MATCH :director_doc_number_fts"
                        ")"
                    )
                ).params(
                    director_doc_number_fts=(
                        f"doc_number : {build_fts5_query(doc_number)}"
                    )
                )
            else:
                query = query.filter(Director.doc_number.like(f"%{doc_number}%"))
        return query

    def get_total(self, archive_type:str = None, category: str = None, title:str = None, doc_number:str = None) -> Optional[int]:
        query = self.db.query(Director)

        if archive_type:
            query = query.filter(Director.archive_type == archive_type)

        if category:
            query = query.filter(Director.category == category)

        query = self._apply_search_filters(query, title, doc_number)
        return query.count()

    def get_list(self,
                 skip: int = 0,
                 limit: int = 100,
                 archive_type: str = None,
                 category: str = None,
                 title: str = None,
                 doc_number: str = None,
    ) -> List[Director]:
        """
        分页查询
        :param skip: 跳过前 N 条（默认 0，用于分页）
        :param limit: 最多返回 N 条（默认 100）
        :archive_type: 档案门类
        :category: 档案类别
        :title： 题名
        :doc_number 档号
        :return:
        """
        query = self.db.query(Director)

        if archive_type:
            query = query.filter(Director.archive_type == archive_type)
        if category:
            query = query.filter(Director.category == category)
        query = self._apply_search_filters(query, title, doc_number)
        return fetch_page(
            query,
            Director,
            (Director.id.desc(),),
            skip,
            limit,
        )

director_service = DirectorService()
