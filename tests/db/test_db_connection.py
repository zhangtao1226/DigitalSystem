# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : test_db_connection.py
# @Desc      : 本地 SQLite 内置数据库连接与初始化检查
# @Time      : 2025/12/1 16:39
# @Software  : PyCharm

from src.core.db import (
    LOCAL_DB_PATH,
    MANAGED_INDEXES,
    SQLITE_SCHEMA_VERSION,
    check_database_connection,
    engine,
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


def test_sqlite_optimizations_enabled():
    initialize_database_tables()
    expected_indexes = {
        index_name
        for indexes in MANAGED_INDEXES.values()
        for index_name in indexes
    }

    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert (
            connection.exec_driver_sql("PRAGMA user_version").scalar()
            == SQLITE_SCHEMA_VERSION
        )

        actual_indexes = set(
            connection.execute(
                text(
                    """
                    SELECT name
                    FROM sqlite_schema
                    WHERE type = 'index' AND sql IS NOT NULL
                    """
                )
            ).scalars()
        )
        assert expected_indexes.issubset(actual_indexes)

        fts_table_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sqlite_schema
                WHERE type = 'table'
                  AND name IN ('director_fts', 'task_mark_fts')
                """
            )
        ).scalar()
        assert fts_table_count == 2
