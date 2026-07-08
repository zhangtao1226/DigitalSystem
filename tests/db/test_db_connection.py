# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : test_db_connection.py
# @Desc      : 本地 SQLite 内置数据库连接与初始化检查
# @Time      : 2025/12/1 16:39
# @Software  : PyCharm

from src.core.db import (
    LOCAL_DB_PATH,
    check_database_connection,
    get_db,
    initialize_database_tables,
    is_database_initialized,
)
from sqlalchemy import text


def test_local_db_connection():
    assert check_database_connection()


def test_local_db_initialization():
    initialize_database_tables()
    assert is_database_initialized()
    assert LOCAL_DB_PATH.exists()


def test_seed_data_loaded():
    db = next(get_db())
    try:
        assert db.execute(text("SELECT COUNT(*) FROM users WHERE username = 'admin'")).scalar() == 1
        assert db.execute(text("SELECT COUNT(*) FROM roles WHERE name = '管理员'")).scalar() == 1
        assert db.execute(text("SELECT COUNT(*) FROM workflows WHERE work_name = '领卷登记'")).scalar() == 1
    finally:
        db.close()
