# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : db.py
# @Desc      : 本地 SQLite 内置数据库
# @Time      : 2025/12/1 10:57
# @Software  : PyCharm

import os
import re
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session as OrmSession, sessionmaker
from sqlalchemy.sql.sqltypes import Boolean, DateTime


# 加载项目根目录 .env 文件中的数据库配置
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=False)

DATABASE_INIT_SQL_ENV = "DATABASE_INIT_SQL_PATH"
DATABASE_INIT_SQL_PATH = PROJECT_ROOT / "public.sql"
DEFAULT_LOCAL_DB_PATH = PROJECT_ROOT / "database" / "digitalSystem.db"
SQLITE_SCHEMA_VERSION = 2
SQLITE_BUSY_TIMEOUT_MS = 15_000
SQLITE_CACHE_SIZE_KIB = 32 * 1024
DEEP_PAGE_THRESHOLD = 1_000

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

MANAGED_INDEXES = {
    "archive_stamp": {
        "idx_archive_stamp_name": ("template_name",),
    },
    "define_template": {
        "idx_define_template_name": ("template_name",),
    },
    "director": {
        "idx_director_register": ("register_id", "id"),
        "idx_director_filter": ("archive_type", "category", "id DESC"),
        "idx_director_identity": ("doc_number", "archive_type", "category", "title"),
    },
    "operation": {
        "idx_operation_operator_list": ("operator", "id"),
        "idx_operation_task_date": ("task_id", "operator_date"),
        "idx_operation_work_list": ("task_name", "operator", "status", "id"),
    },
    "register": {
        "idx_register_batch": ("batch_number",),
        "idx_register_distribute_list": ("is_distribute", "id DESC"),
        "idx_register_owner_list": ("register", "id DESC"),
        "idx_register_filter": (
            "archive_type",
            "category",
            "is_distribute",
            "status",
            "task_node",
            "id DESC",
        ),
    },
    "register_question": {
        "idx_register_question_register": ("register_id",),
        "idx_register_question_volume": ("register_id", "volume_number", "recorder"),
        "idx_register_question_range": ("batch_number", "number_start", "number_end"),
    },
    "roles": {},
    "scan": {
        "idx_scan_task": ("task_id",),
        "idx_scan_register": ("register_id",),
        "idx_scan_dir_name": ("dir_name",),
    },
    "scan_images": {
        "idx_scan_images_order": ("scan_id", "page_index", "file_name"),
    },
    "submit_record": {
        "idx_submit_record_register": ("register_id",),
        "idx_submit_record_task": ("task_id",),
        "idx_submit_record_operator_date": ("operator", "operator_date"),
    },
    "task": {
        "idx_task_domain_id": ("task_id",),
        "idx_task_operator_list": ("task_name", "operator", "id DESC", "task_node"),
        "idx_task_register_segment": ("register_id", "task_number_start", "id"),
        "idx_task_batch_flow": ("batch_number", "register_id", "task_node", "status"),
        "idx_task_range": (
            "batch_number",
            "task_node",
            "task_number_start",
            "task_number_end",
        ),
    },
    "task_mark": {
        "idx_task_mark_history": ("task_id", "is_deleted", "mark_date DESC", "id"),
        "idx_task_mark_status": ("task_id", "is_deleted", "is_fixed", "mark_stage"),
        "idx_task_mark_batch": (
            "batch_number",
            "task_node",
            "mark_stage",
            "is_deleted",
            "mark_date DESC",
        ),
    },
    "task_progress": {
        "idx_task_progress_task": ("task_id", "status", "operate_date"),
    },
    "users": {},
    "user_role_association": {
        "idx_user_role_by_role": ("role_id", "user_id"),
    },
    "workflows": {},
}

FTS_DEFINITIONS = {
    "director_fts": {
        "content_table": "director",
        "columns": ("title", "doc_number"),
    },
    "task_mark_fts": {
        "content_table": "task_mark",
        "columns": (
            "mark_type",
            "description",
            "scan_file",
            "inspector",
            "field_name",
        ),
    },
}

_initialization_lock = threading.Lock()
_database_initialized = False
_fts5_available = False


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
        connect_args={
            "check_same_thread": False,
            "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
        },
    )


engine = _create_database_engine()


@event.listens_for(engine, "connect")
def _set_sqlite_connection_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute(f"PRAGMA cache_size=-{SQLITE_CACHE_SIZE_KIB}")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _coerce_datetime_value(value):
    if value is None or isinstance(value, (datetime, date)):
        return value

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    return value


@event.listens_for(OrmSession, "before_flush")
def _coerce_model_datetime_columns(session, flush_context, instances):
    for obj in tuple(session.new) + tuple(session.dirty):
        mapper = getattr(obj, "__mapper__", None)
        if mapper is None:
            continue

        for column in mapper.columns:
            if not isinstance(column.type, DateTime):
                continue

            value = getattr(obj, column.key, None)
            coerced_value = _coerce_datetime_value(value)
            if coerced_value is not value:
                setattr(obj, column.key, coerced_value)


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


def backup_database(backup_dir: Optional[Path] = None) -> Path:
    """使用 SQLite Backup API 创建一致性备份。"""
    _ensure_sqlite_parent_dir()
    target_dir = backup_dir or LOCAL_DB_PATH.parent / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target_path = target_dir / f"{LOCAL_DB_PATH.stem}_{timestamp}.db"

    source = sqlite3.connect(str(LOCAL_DB_PATH))
    destination = sqlite3.connect(str(target_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target_path


def _configure_database_file() -> None:
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.exec_driver_sql("PRAGMA wal_autocheckpoint=1000")


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _create_index_sql(index_name: str, table_name: str, columns: Sequence[str]) -> str:
    column_sql = ", ".join(
        " ".join(
            [_quote_identifier(parts[0]), *parts[1:]]
        )
        for column in columns
        for parts in [column.split()]
    )
    return (
        f"CREATE INDEX IF NOT EXISTS {_quote_identifier(index_name)} "
        f"ON {_quote_identifier(table_name)} ({column_sql})"
    )


def _reconcile_managed_indexes() -> None:
    managed_tables = tuple(MANAGED_INDEXES)
    table_placeholders = ", ".join(f":table_{index}" for index in range(len(managed_tables)))
    parameters = {
        f"table_{index}": table_name
        for index, table_name in enumerate(managed_tables)
    }

    with engine.begin() as connection:
        existing_indexes = connection.execute(
            text(
                f"""
                SELECT name
                FROM sqlite_schema
                WHERE type = 'index'
                  AND sql IS NOT NULL
                  AND tbl_name IN ({table_placeholders})
                """
            ),
            parameters,
        ).scalars().all()

        for index_name in existing_indexes:
            connection.exec_driver_sql(
                f"DROP INDEX IF EXISTS {_quote_identifier(index_name)}"
            )

        for table_name, indexes in MANAGED_INDEXES.items():
            for index_name, columns in indexes.items():
                connection.exec_driver_sql(
                    _create_index_sql(index_name, table_name, columns)
                )


def _fts_trigger_sql(
        fts_table: str,
        content_table: str,
        columns: Sequence[str],
) -> tuple[str, ...]:
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    new_values = ", ".join(f"new.{_quote_identifier(column)}" for column in columns)
    old_values = ", ".join(f"old.{_quote_identifier(column)}" for column in columns)
    insert_columns = f"rowid, {quoted_columns}"
    delete_columns = f"{_quote_identifier(fts_table)}, rowid, {quoted_columns}"
    quoted_fts = _quote_identifier(fts_table)
    quoted_content = _quote_identifier(content_table)

    return (
        f"""
        CREATE TRIGGER IF NOT EXISTS {_quote_identifier(f'{content_table}_fts_ai')}
        AFTER INSERT ON {quoted_content} BEGIN
            INSERT INTO {quoted_fts} ({insert_columns})
            VALUES (new.id, {new_values});
        END
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS {_quote_identifier(f'{content_table}_fts_ad')}
        AFTER DELETE ON {quoted_content} BEGIN
            INSERT INTO {quoted_fts} ({delete_columns})
            VALUES ('delete', old.id, {old_values});
        END
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS {_quote_identifier(f'{content_table}_fts_au')}
        AFTER UPDATE ON {quoted_content} BEGIN
            INSERT INTO {quoted_fts} ({delete_columns})
            VALUES ('delete', old.id, {old_values});
            INSERT INTO {quoted_fts} ({insert_columns})
            VALUES (new.id, {new_values});
        END
        """,
    )


def _ensure_fts5_tables() -> bool:
    global _fts5_available

    try:
        with engine.begin() as connection:
            for fts_table, definition in FTS_DEFINITIONS.items():
                content_table = definition["content_table"]
                columns = definition["columns"]
                existed = connection.execute(
                    text(
                        """
                        SELECT 1
                        FROM sqlite_schema
                        WHERE type = 'table' AND name = :table_name
                        """
                    ),
                    {"table_name": fts_table},
                ).first() is not None

                column_sql = ", ".join(_quote_identifier(column) for column in columns)
                connection.exec_driver_sql(
                    f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {_quote_identifier(fts_table)}
                    USING fts5(
                        {column_sql},
                        content={_quote_identifier(content_table)},
                        content_rowid='id',
                        tokenize='trigram'
                    )
                    """
                )

                for trigger_sql in _fts_trigger_sql(
                    fts_table,
                    content_table,
                    columns,
                ):
                    connection.exec_driver_sql(trigger_sql)

                if not existed:
                    connection.exec_driver_sql(
                        f"INSERT INTO {_quote_identifier(fts_table)} "
                        f"({_quote_identifier(fts_table)}) VALUES ('rebuild')"
                    )
        _fts5_available = True
    except (SQLAlchemyError, sqlite3.DatabaseError):
        _fts5_available = False

    return _fts5_available


def can_use_fts5(fts_table: str, keyword: Optional[str]) -> bool:
    """Trigram 至少需要 3 个字符；短关键词继续使用 LIKE。"""
    return (
        _fts5_available
        and fts_table in FTS_DEFINITIONS
        and keyword is not None
        and len(keyword.strip()) >= 3
    )


def build_fts5_query(keyword: str) -> str:
    return f'"{keyword.strip().replace(chr(34), chr(34) * 2)}"'


def fetch_page(
    query,
    model,
    order_columns: Sequence,
    skip: int,
    limit: int,
):
    """
    小页直接分页；深页先从索引中获取主键，再关联业务表。

    保留原有 skip/limit 接口，避免页面层大范围改动。
    """
    skip = max(int(skip or 0), 0)
    limit = max(int(limit or 0), 0)
    ordered_query = query.order_by(None).order_by(*order_columns)
    if limit == 0:
        return []
    if skip < DEEP_PAGE_THRESHOLD:
        return ordered_query.offset(skip).limit(limit).all()

    page_ids = (
        query.order_by(None)
        .with_entities(model.id.label("_page_id"))
        .order_by(*order_columns)
        .offset(skip)
        .limit(limit)
        .subquery()
    )
    return (
        query.session.query(model)
        .join(page_ids, model.id == page_ids.c._page_id)
        .order_by(*order_columns)
        .all()
    )


def optimize_database() -> None:
    """执行适合启动阶段的轻量统计与 WAL 维护。"""
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA optimize")
        connection.exec_driver_sql("PRAGMA wal_checkpoint(PASSIVE)")


def _migrate_database_schema(had_tables: bool) -> bool:
    with engine.connect() as connection:
        current_version = int(
            connection.exec_driver_sql("PRAGMA user_version").scalar() or 0
        )

    if current_version >= SQLITE_SCHEMA_VERSION:
        return False

    if had_tables and LOCAL_DB_PATH.exists():
        backup_database()

    _reconcile_managed_indexes()
    with engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version={SQLITE_SCHEMA_VERSION}")
        connection.exec_driver_sql("ANALYZE")
    return True


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
    global _database_initialized

    with _initialization_lock:
        if _database_initialized:
            return False

        _ensure_sqlite_parent_dir()
        _configure_database_file()

        # 导入模型模块后，Base.metadata 才包含完整表结构。
        import src.models  # noqa: F401

        had_tables = _core_tables_exist()
        Base.metadata.create_all(bind=engine)
        seeded = _seed_database_from_public_sql(sql_path)
        migrated = _migrate_database_schema(had_tables)
        _ensure_fts5_tables()
        optimize_database()
        _database_initialized = True
        return (not had_tables) or seeded or migrated


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
