"""
PostgreSQL 数据库管理器（原 database_manager_sqlserver.py 的 PG 移植版）
"""

import os
import json
from typing import Dict, List

from db_pg import get_connection


class DatabaseManager:
    """PostgreSQL 数据库管理器"""

    def __init__(self):
        # 惰性初始化：不在 import 阶段连接数据库（Serverless 冷启动容错）
        pass

    def init_db(self):
        """确保转换记录与会话表存在（幂等）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    input_text TEXT,
                    input_image TEXT,
                    key_signature VARCHAR(10) NOT NULL,
                    harmonica_type VARCHAR(10) NOT NULL,
                    bd_text TEXT NOT NULL,
                    bd_image TEXT,
                    analysis TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_user ON conversions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_created ON conversions(created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')
            conn.commit()
        finally:
            conn.close()

    def save_conversion(self, data: Dict) -> int:
        """保存转换记录，返回记录 ID"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO conversions
                (input_text, input_image, key_signature, harmonica_type, bd_text, bd_image, analysis, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
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
            record_id = cursor.fetchone()[0]
            conn.commit()
            return record_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def _rows_to_records(cursor, rows) -> List[Dict]:
        """行转字典并解析 JSON 字段"""
        columns = [column[0] for column in cursor.description]
        records = [dict(zip(columns, row)) for row in rows]
        for record in records:
            if record.get('analysis'):
                try:
                    record['analysis'] = json.loads(record['analysis'])
                except Exception:
                    record['analysis'] = {}
        return records

    def get_conversions(self, limit: int = None) -> List[Dict]:
        """获取全部转换记录（后台管理用）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if limit is None:
                cursor.execute('''
                    SELECT * FROM conversions
                    ORDER BY created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT * FROM conversions
                    ORDER BY created_at DESC
                    LIMIT %s
                ''', (limit,))
            return self._rows_to_records(cursor, cursor.fetchall())
        finally:
            conn.close()

    def get_conversions_by_user(self, user_id: int, limit: int = None) -> List[Dict]:
        """获取指定用户的转换记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if limit is None:
                cursor.execute('''
                    SELECT * FROM conversions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM conversions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ''', (user_id, limit))
            return self._rows_to_records(cursor, cursor.fetchall())
        finally:
            conn.close()

    def delete_conversion(self, record_id: int) -> bool:
        """删除转换记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id FROM conversions WHERE id = %s', (record_id,))
            exists = cursor.fetchone() is not None
            if not exists:
                return False
            cursor.execute('DELETE FROM conversions WHERE id = %s', (record_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_conversion_by_id(self, record_id: int) -> Dict:
        """根据 ID 获取转换记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM conversions WHERE id = %s', (record_id,))
            row = cursor.fetchone()
            if row:
                return self._rows_to_records(cursor, [row])[0]
            return None
        finally:
            conn.close()
