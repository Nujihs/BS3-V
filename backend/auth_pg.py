"""
PostgreSQL 用户认证模块（原 auth_sqlserver.py 的 PG 移植版）
"""

import hashlib
import secrets
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, Dict

from db_pg import get_connection

load_dotenv()


class AuthManager:
    """PostgreSQL 认证管理器"""

    def __init__(self):
        # 惰性初始化：不在 import 阶段连接数据库（Serverless 冷启动容错，
        # 数据库暂不可用时函数仍可启动，连接延迟到首次调用）
        pass

    def init_user_table(self):
        """确保表存在（幂等，schema 由 create_db.py / schema.sql 创建）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_login TIMESTAMPTZ
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    def hash_password(self, password: str) -> str:
        """密码哈希（保持与原项目一致的 SHA256+盐 格式，兼容旧数据）"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, hash_value = password_hash.split(':')
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == hash_value
        except Exception:
            return False

    def register(self, username: str, password: str, email: Optional[str] = None) -> Dict:
        """用户注册"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cursor.fetchone():
                return {'success': False, 'error': '用户名已存在'}

            if email:
                cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
                if cursor.fetchone():
                    return {'success': False, 'error': '邮箱已被注册'}

            password_hash = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password_hash, email)
                VALUES (%s, %s, %s)
                RETURNING id
            ''', (username, password_hash, email))
            user_id = cursor.fetchone()[0]
            conn.commit()
            return {'success': True, 'user_id': user_id}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def login(self, username: str, password: str) -> Dict:
        """用户登录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户名或密码错误'}

            columns = [column[0] for column in cursor.description]
            user = dict(zip(columns, row))

            if not self.verify_password(password, user['password_hash']):
                return {'success': False, 'error': '用户名或密码错误'}

            token = secrets.token_hex(32)
            expires_at = datetime.now() + timedelta(days=7)

            cursor.execute('DELETE FROM sessions WHERE user_id = %s', (user['id'],))
            cursor.execute('''
                INSERT INTO sessions (user_id, token, expires_at)
                VALUES (%s, %s, %s)
            ''', (user['id'], token, expires_at))
            cursor.execute('UPDATE users SET last_login = NOW() WHERE id = %s', (user['id'],))
            conn.commit()

            return {
                'success': True,
                'token': token,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def verify_token(self, token: str) -> Optional[Dict]:
        """验证令牌"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT s.*, u.username, u.email
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = %s AND s.expires_at > NOW()
            ''', (token,))
            row = cursor.fetchone()

            if row:
                columns = [column[0] for column in cursor.description]
                session = dict(zip(columns, row))
                return {
                    'user_id': session['user_id'],
                    'username': session['username'],
                    'email': session['email']
                }
            return None
        except Exception:
            return None
        finally:
            conn.close()

    def logout(self, token: str) -> bool:
        """用户登出"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM sessions WHERE token = %s', (token,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def change_password(self, user_id: int, current_password: str, new_password: str) -> Dict:
        """修改密码"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': '用户不存在'}

            if not self.verify_password(current_password, row[0]):
                return {'success': False, 'error': '当前密码错误'}

            new_password_hash = self.hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', (new_password_hash, user_id))
            conn.commit()
            return {'success': True, 'message': '密码修改成功'}
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM sessions WHERE expires_at < NOW()')
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id, username, email, created_at, last_login FROM users WHERE id = %s', (user_id,))
            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception:
            return None
        finally:
            conn.close()

    def verify_username(self, username: str) -> Dict:
        """验证用户名是否存在"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id, username FROM users WHERE username = %s', (username,))
            row = cursor.fetchone()
            if row:
                return {'success': True, 'message': '用户名存在'}
            return {'success': False, 'error': '用户名不存在'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def reset_password(self, username: str, new_password: str) -> Dict:
        """重置密码 - 用户自己设置新密码"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id, username FROM users WHERE username = %s', (username,))
            row = cursor.fetchone()
            if not row:
                return {'success': False, 'error': '用户名不存在'}

            columns = [column[0] for column in cursor.description]
            user = dict(zip(columns, row))

            password_hash = self.hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', (password_hash, user['id']))
            cursor.execute('DELETE FROM sessions WHERE user_id = %s', (user['id'],))
            conn.commit()
            return {'success': True, 'message': '密码重置成功'}
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
