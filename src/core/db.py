# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : db.py
# @Desc      : 
# @Time      : 2025/12/1 10:57
# @Software  : PyCharm

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# 加载环境变量（从.env文件读取数据库配置）
load_dotenv()

# 数据库连接配置（优先从环境变量读取，默认值用于测试）
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "test1")

# 构建PostgreSQL连接URL
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 创建数据库引擎（echo=True：打印SQL语句，开发环境可用）
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,  # 生产环境关闭SQL打印
    pool_pre_ping=True,  # 连接前检查可用性，避免无效连接
)

# 创建会话工厂（每次请求创建一个会话，线程安全）
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基础模型类（所有ORM模型都继承此类）
Base = declarative_base()

# 获取数据库会话（依赖注入模式，方便使用）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # 确保会话最终关闭
