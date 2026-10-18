"""
数据库配置文件
用于切换 SQLite 和 SQL Server 数据库
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ========================================
# 数据库类型配置：'sqlite' 或 'sqlserver'
# ========================================
DB_TYPE = os.getenv('DB_TYPE', 'sqlite')  # 默认使用 SQLite


# ========================================
# SQLite 配置
# ========================================
def get_sqlite_config():
    """获取 SQLite 数据库配置"""
    import sys
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_FILE = os.path.join(PROJECT_ROOT, 'database', 'jianpu_conversions.db')
    return DB_FILE


# ========================================
# SQL Server 配置
# ========================================
def get_sql_server_config():
    """获取 SQL Server 配置"""
    config = {
        'driver': os.getenv('SQL_SERVER_DRIVER', '{ODBC Driver 17 for SQL Server}'),
        'server': os.getenv('SQL_SERVER_SERVER', 'localhost'),
        'database': os.getenv('SQL_SERVER_DATABASE', 'JianpuDB'),
        'username': os.getenv('SQL_SERVER_USERNAME', 'sa'),
        'password': os.getenv('SQL_SERVER_PASSWORD', ''),
        'trusted_connection': os.getenv('SQL_SERVER_TRUSTED_CONNECTION', 'no')
    }
    return config


def get_sql_server_connection_string():
    """获取 SQL Server 连接字符串"""
    config = get_sql_server_config()
    
    if config['trusted_connection'].lower() == 'yes':
        # 使用 Windows 认证
        conn_str = (
            f"DRIVER={config['driver']};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"Trusted_Connection=yes;"
        )
    else:
        # 使用 SQL Server 认证
        conn_str = (
            f"DRIVER={config['driver']};"
            f"SERVER={config['server']};"
            f"DATABASE={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']}"
        )
    
    return conn_str


# ========================================
# 数据库工厂函数
# ========================================
def get_database_config():
    """根据配置获取相应的数据库配置"""
    if DB_TYPE == 'sqlserver':
        return {
            'type': 'sqlserver',
            'connection_string': get_sql_server_connection_string()
        }
    else:
        return {
            'type': 'sqlite',
            'db_file': get_sqlite_config()
        }


def test_sql_server_connection():
    """测试 SQL Server 连接"""
    try:
        import pyodbc
        conn_str = get_sql_server_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        conn.close()
        return True, version[0] if version else "Unknown"
    except Exception as e:
        return False, str(e)


if __name__ == '__main__':
    print("=" * 60)
    print("数据库配置测试")
    print("=" * 60)
    
    print(f"\n当前数据库类型: {DB_TYPE}")
    
    if DB_TYPE == 'sqlite':
        print(f"SQLite 数据库路径: {get_sqlite_config()}")
    elif DB_TYPE == 'sqlserver':
        print(f"SQL Server 配置:")
        config = get_sql_server_config()
        print(f"  服务器: {config['server']}")
        print(f"  数据库: {config['database']}")
        print(f"  用户名: {config['username']}")
        print(f"  驱动: {config['driver']}")
        
        print("\n测试连接...")
        success, message = test_sql_server_connection()
        if success:
            print(f"✓ 连接成功！")
            print(f"  版本: {message[:100]}...")
        else:
            print(f"✗ 连接失败: {message}")
    
    print("\n" + "=" * 60)
