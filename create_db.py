"""
PostgreSQL 数据库初始化脚本（原 create_sql_server_db.py 的 PG 版）

用法:
    python create_db.py
或显式指定连接:
    DATABASE_URL=postgresql://user:pass@host:5432/db python create_db.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
from db_pg import get_connection  # noqa: E402


def main():
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    schema = Path(schema_path).read_text(encoding='utf-8')

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(schema)
        conn.commit()
        print("[OK] 数据库表初始化完成（users / conversions / sessions）")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 初始化失败: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
