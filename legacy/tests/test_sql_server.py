"""
测试 SQL Server 配置
"""

import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=" * 60)
print("SQL Server Configuration Test")
print("=" * 60)
print()

# 检查数据库类型
db_type = os.getenv('DB_TYPE', 'sqlite')
print(f"Database Type: {db_type}")
print()

if db_type == 'sqlserver':
    print("SQL Server Configuration:")
    print(f"  Server: {os.getenv('SQL_SERVER_SERVER', 'localhost')}")
    print(f"  Database: {os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')}")
    print(f"  Driver: {os.getenv('SQL_SERVER_DRIVER', '{ODBC Driver 17 for SQL Server}')}")
    print(f"  Windows Auth: {os.getenv('SQL_SERVER_TRUSTED_CONNECTION', 'no')}")
    print()

    # 测试连接
    print("Testing connection...")
    try:
        import pyodbc

        if os.getenv('SQL_SERVER_TRUSTED_CONNECTION', 'no').lower() == 'yes':
            conn_str = (
                f"DRIVER={os.getenv('SQL_SERVER_DRIVER', '{ODBC Driver 17 for SQL Server}')};"
                f"SERVER={os.getenv('SQL_SERVER_SERVER', 'localhost')};"
                f"DATABASE={os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')};"
                f"Trusted_Connection=yes;"
            )
        else:
            conn_str = (
                f"DRIVER={os.getenv('SQL_SERVER_DRIVER', '{ODBC Driver 17 for SQL Server}')};"
                f"SERVER={os.getenv('SQL_SERVER_SERVER', 'localhost')};"
                f"DATABASE={os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')};"
                f"UID={os.getenv('SQL_SERVER_USERNAME', 'sa')};"
                f"PWD={os.getenv('SQL_SERVER_PASSWORD', '')}"
            )

        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()

        # 测试查询
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()

        cursor.execute("SELECT DB_NAME()")
        db_name = cursor.fetchone()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sys.tables WHERE name IN ('users', 'conversions', 'sessions')")
        tables = cursor.fetchall()

        conn.close()

        print("[OK] Connection successful!")
        print(f"  Version: {version[0][:60]}...")
        print(f"  Database: {db_name[0]}")
        print(f"  Tables found: {len(tables)} ({[t[0] for t in tables]})")
        print()

        if len(tables) == 3:
            print("[OK] All required tables exist!")
            print()
            print("Configuration is ready. You can now start the application:")
            print("  start.bat (Windows) or start.sh (Linux/Mac)")
        else:
            print("[WARNING] Some tables are missing. Please run:")
            print("  python create_sql_server_db.py")

    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print()
        print("Please check:")
        print("  1. SQL Server is running")
        print("  2. Database exists")
        print("  3. Windows authentication is working")

else:
    print("Using SQLite database")
    print()
    print("Configuration is ready. You can now start the application:")
    print("  start.bat (Windows) or start.sh (Linux/Mac)")

print()
print("=" * 60)
