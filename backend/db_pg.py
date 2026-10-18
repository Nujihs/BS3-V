"""
PostgreSQL 连接封装
供认证模块与数据管理模块共用
"""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()


def get_dsn() -> str:
    """获取连接字符串：优先 DATABASE_URL（Vercel/Neon 等托管 PG），否则使用分项环境变量"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url
    return (
        f"host={os.getenv('PG_HOST', 'localhost')} "
        f"port={os.getenv('PG_PORT', '5432')} "
        f"dbname={os.getenv('PG_DATABASE', 'jianpu_db')} "
        f"user={os.getenv('PG_USER', 'jianpu')} "
        f"password={os.getenv('PG_PASSWORD', '')}"
    )


def get_connection():
    """获取数据库连接（非自动提交，调用方负责 commit/rollback）"""
    conn = psycopg2.connect(get_dsn())
    conn.autocommit = False
    return conn
