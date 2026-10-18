"""
简谱转换系统启动脚本
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=" * 60)
print("简谱转BD谱系统 - 启动中")
print("=" * 60)
print()
print("Database: SQL Server")
print(f"  Server: {os.getenv('SQL_SERVER_SERVER', 'localhost')}")
print(f"  Database: {os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')}")
print()
print("Access the application at: http://127.0.0.1:5000")
print("Press Ctrl+C to stop the server")
print("=" * 60)
print()

# 添加 backend 目录到路径
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 启动 Flask 应用
try:
    from app import app
    app.run(host='127.0.0.1', port=5000, debug=True)
except KeyboardInterrupt:
    print("\nServer stopped.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
