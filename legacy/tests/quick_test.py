"""
快速测试 SQL Server 配置和应用启动
"""

import sys
import os
from dotenv import load_dotenv

# 添加 backend 目录到路径
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 加载环境变量
load_dotenv()

print("=" * 60)
print("Quick Test - SQL Server Configuration")
print("=" * 60)
print()

# 测试 1: 导入模块
print("[Test 1] Importing modules...")
try:
    from main import JianpuToBDConverter
    print("  [OK] JianpuToBDConverter imported")
except Exception as e:
    print(f"  [ERROR] Failed to import JianpuToBDConverter: {e}")

db_type = os.getenv('DB_TYPE', 'sqlite')

if db_type == 'sqlserver':
    try:
        from auth_sqlserver import AuthManager
        print("  [OK] AuthManager (SQL Server) imported")
    except Exception as e:
        print(f"  [ERROR] Failed to import AuthManager: {e}")

    try:
        from database_manager_sqlserver import DatabaseManager
        print("  [OK] DatabaseManager (SQL Server) imported")
    except Exception as e:
        print(f"  [ERROR] Failed to import DatabaseManager: {e}")
else:
    try:
        from auth import AuthManager
        print("  [OK] AuthManager (SQLite) imported")
    except Exception as e:
        print(f"  [ERROR] Failed to import AuthManager: {e}")

print()

# 测试 2: 初始化管理器
print("[Test 2] Initializing managers...")
try:
    converter = JianpuToBDConverter()
    print("  [OK] JianpuToBDConverter initialized")
except Exception as e:
    print(f"  [ERROR] Failed to initialize JianpuToBDConverter: {e}")

if db_type == 'sqlserver':
    try:
        auth_manager = AuthManager()
        print("  [OK] AuthManager (SQL Server) initialized")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize AuthManager: {e}")

    try:
        db_manager = DatabaseManager()
        print("  [OK] DatabaseManager (SQL Server) initialized")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize DatabaseManager: {e}")
else:
    try:
        DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'jianpu_conversions.db')
        auth_manager = AuthManager(DB_FILE)
        print("  [OK] AuthManager (SQLite) initialized")
    except Exception as e:
        print(f"  [ERROR] Failed to initialize AuthManager: {e}")

print()

# 测试 3: 导入 Flask 应用
print("[Test 3] Importing Flask app...")
try:
    from app import app
    print("  [OK] Flask app imported")
    print(f"  [INFO] Secret Key: {app.config['SECRET_KEY'][:20]}...")
except Exception as e:
    print(f"  [ERROR] Failed to import Flask app: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("All tests completed!")
print("=" * 60)
print()

if db_type == 'sqlserver':
    print("To start the application:")
    print("  python run_server.py")
else:
    print("To start the application:")
    print("  python run_server.py")
