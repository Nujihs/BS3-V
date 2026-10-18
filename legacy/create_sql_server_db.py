"""
创建 SQL Server 数据库和表
"""

import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

# SQL Server 连接配置
SERVER = os.getenv('SQL_SERVER_SERVER', 'localhost')
DATABASE_NAME = os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')

def create_database():
    """创建数据库"""
    print(f"Creating database: {DATABASE_NAME}")
    
    # 连接到 master 数据库
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;"
    )
    
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    
    try:
        # 检查数据库是否存在
        cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{DATABASE_NAME}'")
        result = cursor.fetchone()
        
        if not result:
            cursor.execute(f"CREATE DATABASE [{DATABASE_NAME}]")
            print(f"[OK] Database '{DATABASE_NAME}' created successfully")
        else:
            print(f"[INFO] Database '{DATABASE_NAME}' already exists")
    finally:
        conn.close()

def create_tables():
    """创建表"""
    print(f"Creating tables in database: {DATABASE_NAME}")
    
    # 连接到目标数据库
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    
    try:
        # 创建用户表
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
            CREATE TABLE users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                username NVARCHAR(50) NOT NULL UNIQUE,
                password_hash NVARCHAR(255) NOT NULL,
                email NVARCHAR(100) UNIQUE,
                created_at DATETIME2 DEFAULT GETDATE(),
                last_login DATETIME2
            )
        ''')
        conn.commit()
        print("[OK] Table 'users' created/verified")
        
        # 创建转换记录表
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'conversions')
            CREATE TABLE conversions (
                id INT IDENTITY(1,1) PRIMARY KEY,
                input_text NVARCHAR(MAX) NULL,
                input_image NVARCHAR(MAX) NULL,
                key_signature NVARCHAR(10) NULL,
                harmonica_type NVARCHAR(10) NULL,
                bd_text NVARCHAR(MAX) NULL,
                bd_image NVARCHAR(MAX) NULL,
                analysis NVARCHAR(MAX) NULL,
                created_at DATETIME2 DEFAULT GETDATE(),
                user_id INT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        conn.commit()
        print("[OK] Table 'conversions' created/verified")
        
        # 创建会话表
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'sessions')
            CREATE TABLE sessions (
                id INT IDENTITY(1,1) PRIMARY KEY,
                user_id INT NOT NULL,
                token NVARCHAR(255) NOT NULL UNIQUE,
                expires_at DATETIME2 NOT NULL,
                created_at DATETIME2 DEFAULT GETDATE(),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        print("[OK] Table 'sessions' created/verified")
        
        # 创建索引
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_conversions_user_id' AND object_id = OBJECT_ID('conversions'))
            CREATE INDEX idx_conversions_user_id ON conversions(user_id)
        ''')
        conn.commit()
        print("[OK] Index 'idx_conversions_user_id' created/verified")
        
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_conversions_created_at' AND object_id = OBJECT_ID('conversions'))
            CREATE INDEX idx_conversions_created_at ON conversions(created_at DESC)
        ''')
        conn.commit()
        print("[OK] Index 'idx_conversions_created_at' created/verified")
        
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_sessions_token' AND object_id = OBJECT_ID('sessions'))
            CREATE INDEX idx_sessions_token ON sessions(token)
        ''')
        conn.commit()
        print("[OK] Index 'idx_sessions_token' created/verified")
        
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_sessions_expires_at' AND object_id = OBJECT_ID('sessions'))
            CREATE INDEX idx_sessions_expires_at ON sessions(expires_at)
        ''')
        conn.commit()
        print("[OK] Index 'idx_sessions_expires_at' created/verified")
        
    finally:
        conn.close()

def test_connection():
    """测试连接"""
    print("Testing SQL Server connection...")
    
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    
    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()
        
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        print(f"[OK] Connected successfully")
        print(f"[INFO] SQL Server Version: {version[0][:60]}...")
        
        cursor.execute("SELECT DB_NAME()")
        db_name = cursor.fetchone()
        print(f"[INFO] Current Database: {db_name[0]}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("SQL Server Database Setup")
    print("=" * 60)
    print()
    
    # 创建数据库
    create_database()
    print()
    
    # 创建表
    create_tables()
    print()
    
    # 测试连接
    test_connection()
    
    print()
    print("=" * 60)
    print("Setup completed successfully!")
    print("=" * 60)
