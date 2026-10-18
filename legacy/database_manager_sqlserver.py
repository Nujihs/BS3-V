"""
SQL Server 数据库管理器
"""

import pyodbc
import os
from dotenv import load_dotenv
from typing import Dict, List
import json

load_dotenv()


class DatabaseManager:
    """SQL Server 数据库管理器"""

    def __init__(self):
        self.connection_string = self._get_connection_string()

    def _get_connection_string(self):
        """获取连接字符串"""
        server = os.getenv('SQL_SERVER_SERVER', 'localhost')
        database = os.getenv('SQL_SERVER_DATABASE', 'JianpuDB')

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;"
        )
        return conn_str

    def get_connection(self):
        """获取数据库连接"""
        conn = pyodbc.connect(self.connection_string)
        conn.autocommit = False
        return conn

    def init_db(self):
        """初始化数据库表"""
        # 数据库表已通过 create_sql_server_db.py 创建
        pass

    def save_conversion(self, data: Dict) -> int:
        """保存转换记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO conversions
                (input_text, input_image, key_signature, harmonica_type, bd_text, bd_image, analysis, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('input_text'),
                data.get('input_image'),
                data.get('key_signature'),
                data.get('harmonica_type'),
                data.get('bd_text'),
                data.get('bd_image'),
                json.dumps(data.get('analysis', {}), ensure_ascii=False),
                data.get('user_id')
            ))

            conn.commit()
            cursor.execute('SELECT @@IDENTITY AS id')
            row = cursor.fetchone()
            record_id = row[0]
            return record_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_conversions(self, limit: int = None) -> List[Dict]:
        """获取转换记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if limit is None:
                cursor.execute('''
                    SELECT * FROM conversions
                    ORDER BY created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT TOP (?) * FROM conversions
                    ORDER BY created_at DESC
                ''', (limit,))

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            records = [dict(zip(columns, row)) for row in rows]

            # 解析JSON字段
            for record in records:
                if record['analysis']:
                    try:
                        record['analysis'] = json.loads(record['analysis'])
                    except:
                        record['analysis'] = {}

            return records
        finally:
            conn.close()

    def get_conversions_by_user(self, user_id: int, limit: int = None) -> List[Dict]:
        """获取指定用户的转换记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if limit is None:
                cursor.execute('''
                    SELECT * FROM conversions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT TOP (?) * FROM conversions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (limit, user_id))

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            records = [dict(zip(columns, row)) for row in rows]

            # 解析JSON字段
            for record in records:
                if record['analysis']:
                    try:
                        record['analysis'] = json.loads(record['analysis'])
                    except:
                        record['analysis'] = {}

            return records
        finally:
            conn.close()

    def delete_conversion(self, record_id: int) -> bool:
        """删除转换记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 先检查记录是否存在
            cursor.execute('SELECT id FROM conversions WHERE id = ?', (record_id,))
            exists = cursor.fetchone() is not None
            print(f"[DB] Checking record ID={record_id}, exists={exists}")

            if not exists:
                print(f"[DB] Record does not exist: {record_id}")
                return False

            # 执行删除
            cursor.execute('DELETE FROM conversions WHERE id = ?', (record_id,))
            conn.commit()
            deleted_count = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
            print(f"[DB] Deleted record ID={record_id}, count={deleted_count}")
            return True
        except Exception as e:
            print(f"[DB] Delete failed: {str(e)}")
            import traceback
            print(traceback.format_exc())
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_conversion_by_id(self, record_id: int) -> Dict:
        """根据ID获取转换记录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM conversions WHERE id = ?', (record_id,))
            row = cursor.fetchone()

            if row:
                columns = [column[0] for column in cursor.description]
                record = dict(zip(columns, row))
                if record['analysis']:
                    try:
                        record['analysis'] = json.loads(record['analysis'])
                    except:
                        record['analysis'] = {}
                return record

            return None
        finally:
            conn.close()
