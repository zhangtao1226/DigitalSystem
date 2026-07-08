# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : db.py
# @Desc      : 本地 SQLite 内置数据库
# @Time      : 2025/12/1 10:57
# @Software  : PyCharm

import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import Boolean


# 加载项目根目录 .env 文件中的数据库配置
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=True)

DATABASE_INIT_SQL_ENV = "DATABASE_INIT_SQL_PATH"
DATABASE_INIT_SQL_PATH = PROJECT_ROOT / "public.sql"
DEFAULT_LOCAL_DB_PATH = PROJECT_ROOT / "database" / "digitalSystem.db"

REQUIRED_DATABASE_TABLES = (
    "users",
    "roles",
    "workflows",
    "user_role_association",
)

SEED_TABLE_ORDER = (
    "roles",
    "users",
    "workflows",
    "user_role_association",
    "role_permission_association",
)


def _resolve_local_db_path() -> Path:
    configured_path = os.getenv("LOCAL_DB_PATH", "").strip()
    if not configured_path:
        return DEFAULT_LOCAL_DB_PATH

    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


LOCAL_DB_PATH = _resolve_local_db_path()
DB_NAME = LOCAL_DB_PATH.name
SQLALCHEMY_DATABASE_URL = f"sqlite:///{LOCAL_DB_PATH.as_posix()}"


def _ensure_sqlite_parent_dir() -> None:
    LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _create_database_engine():
    return create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )


engine = _create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def check_database_connection() -> bool:
    """检查本地 SQLite 数据库是否可以正常连接。"""
    try:
        _ensure_sqlite_parent_dir()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    except OSError:
        return False


def check_postgres_server_connection() -> bool:
    """兼容旧调用：内置数据库模式下检查本地 SQLite 即可。"""
    return check_database_connection()


def ensure_database_exists() -> bool:
    """确保本地数据库文件所在目录存在，并建立一次连接。"""
    existed = LOCAL_DB_PATH.exists()
    _ensure_sqlite_parent_dir()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return not existed


def _core_tables_exist() -> bool:
    with engine.connect() as connection:
        table_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN ('users', 'roles', 'workflows', 'user_role_association')
                """
            )
        ).scalar()
    return int(table_count or 0) == len(REQUIRED_DATABASE_TABLES)


def _seed_data_exists() -> bool:
    if not _core_tables_exist():
        return False

    with engine.connect() as connection:
        users_count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar()
        roles_count = connection.execute(text("SELECT COUNT(*) FROM roles")).scalar()
        workflows_count = connection.execute(text("SELECT COUNT(*) FROM workflows")).scalar()
    return all(int(value or 0) > 0 for value in (users_count, roles_count, workflows_count))


def is_database_initialized() -> bool:
    """检查核心业务表是否已经创建，并且 public.sql 中的基础数据是否已导入。"""
    return _core_tables_exist() and _seed_data_exists()


def _resolve_database_init_sql_path(sql_path: Optional[str] = None) -> Path:
    env_sql_path = os.getenv(DATABASE_INIT_SQL_ENV)
    candidates = []

    for candidate in (sql_path, env_sql_path):
        if candidate:
            candidates.append(Path(candidate).expanduser())

    candidates.extend([
        DATABASE_INIT_SQL_PATH,
        PROJECT_ROOT / "src" / "core" / "public.sql",
    ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _read_sql_script(script_path: Path) -> str:
    script_bytes = script_path.read_bytes()
    decode_error = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return script_bytes.decode(encoding)
        except UnicodeDecodeError as e:
            decode_error = e

    if decode_error:
        raise UnicodeDecodeError(
            decode_error.encoding,
            decode_error.object,
            decode_error.start,
            decode_error.end,
            f"无法识别 SQL 文件编码: {script_path}",
        )
    return ""


def _split_sql_values(values_sql: str) -> list[str]:
    values = []
    current = []
    in_quote = False
    index = 0

    while index < len(values_sql):
        char = values_sql[index]
        current.append(char)

        if char == "'":
            if in_quote and index + 1 < len(values_sql) and values_sql[index + 1] == "'":
                index += 1
                current.append(values_sql[index])
            else:
                in_quote = not in_quote
        elif char == "," and not in_quote:
            current.pop()
            values.append("".join(current).strip())
            current = []

        index += 1

    if current:
        values.append("".join(current).strip())
    return values


def _bool_column_indexes() -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for table in Base.metadata.sorted_tables:
        indexes = {
            index
            for index, column in enumerate(table.columns)
            if isinstance(column.type, Boolean)
        }
        if indexes:
            result[table.name] = indexes
    return result


def _normalize_seed_value(raw_value: str, is_boolean: bool) -> str:
    if is_boolean:
        normalized = raw_value.strip().lower()
        if normalized == "'t'":
            return "1"
        if normalized == "'f'":
            return "0"
    return raw_value


def _extract_public_sql_inserts(sql_script: str) -> dict[str, list[str]]:
    insert_re = re.compile(
        r'^INSERT INTO\s+"public"\."(?P<table>[^"]+)"\s+VALUES\s+\((?P<values>.*)\);$',
        re.IGNORECASE,
    )
    bool_indexes = _bool_column_indexes()
    inserts: dict[str, list[str]] = {}

    for line in sql_script.splitlines():
        line = line.strip()
        match = insert_re.match(line)
        if not match:
            continue

        table_name = match.group("table")
        values = _split_sql_values(match.group("values"))
        table_bool_indexes = bool_indexes.get(table_name, set())
        values = [
            _normalize_seed_value(value, index in table_bool_indexes)
            for index, value in enumerate(values)
        ]
        inserts.setdefault(table_name, []).append(
            f'INSERT OR IGNORE INTO "{table_name}" VALUES ({", ".join(values)})'
        )

    return inserts


def _seed_database_from_public_sql(sql_path: Optional[str] = None) -> bool:
    if _seed_data_exists():
        return False

    script_path = _resolve_database_init_sql_path(sql_path)
    if not script_path.exists():
        raise FileNotFoundError(f"未找到数据库初始化脚本: {script_path}")

    inserts_by_table = _extract_public_sql_inserts(_read_sql_script(script_path))
    raw_connection = engine.raw_connection()
    try:
        cursor = raw_connection.cursor()
        try:
            for table_name in SEED_TABLE_ORDER:
                for statement in inserts_by_table.get(table_name, []):
                    cursor.execute(statement)
        finally:
            cursor.close()
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        raw_connection.close()

    return True


def initialize_database_tables(sql_path: Optional[str] = None) -> bool:
    """
    初始化本地 SQLite 数据库。

    表结构由 SQLAlchemy 模型创建；基础用户、角色、工作流等数据从 public.sql 导入。
    返回 True 表示本次创建了表或导入了种子数据。
    """
    _ensure_sqlite_parent_dir()

    # 导入模型模块后，Base.metadata 才包含完整表结构。
    import src.models  # noqa: F401

    had_tables = _core_tables_exist()
    Base.metadata.create_all(bind=engine)
    seeded = _seed_database_from_public_sql(sql_path)
    return (not had_tables) or seeded


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
