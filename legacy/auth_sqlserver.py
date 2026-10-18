"""
SQL Server 用户认证模块
"""

import hashlib
import secrets
import pyodbc
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, Dict

load_dotenv()


class AuthManager:
    """SQL Server 认证管理器"""

    def __init__(self):
        self.connection_string = self._get_connection_string()
        self.init_user_table()

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

    def init_user_table(self):
        """初始化用户表"""
        # 数据库表已通过 create_sql_server_db.py 创建
        pass

    def hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            salt, hash_value = password_hash.split(':')
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == hash_value
        except:
            return False

    def register(self, username: str, password: str, email: Optional[str] = None) -> Dict:
        """用户注册"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 检查用户名是否已存在
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                return {'success': False, 'error': '用户名已存在'}

            # 检查邮箱是否已存在
            if email:
                cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    return {'success': False, 'error': '邮箱已被注册'}

            # 创建用户
            password_hash = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password_hash, email)
                VALUES (?, ?, ?)
            ''', (username, password_hash, email))

            conn.commit()
            cursor.execute('SELECT @@IDENTITY AS id')
            row = cursor.fetchone()
            user_id = row[0]
            return {'success': True, 'user_id': user_id}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except:
                pass

    def login(self, username: str, password: str) -> Dict:
        """用户登录"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 查找用户
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户名或密码错误'}

            columns = [column[0] for column in cursor.description]
            user = dict(zip(columns, row))

            # 验证密码
            if not self.verify_password(password, user['password_hash']):
                return {'success': False, 'error': '用户名或密码错误'}

            # 生成会话令牌
            token = secrets.token_hex(32)
            expires_at = datetime.now() + timedelta(days=7)

            # 删除旧会话
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))

            # 创建新会话
            cursor.execute('''
                INSERT INTO sessions (user_id, token, expires_at)
                VALUES (?, ?, ?)
            ''', (user['id'], token, expires_at))

            # 更新最后登录时间
            cursor.execute('''
                UPDATE users SET last_login = GETDATE() WHERE id = ?
            ''', (user['id'],))

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
            try:
                conn.close()
            except:
                pass

    def verify_token(self, token: str) -> Optional[Dict]:
        """验证令牌"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT s.*, u.username, u.email
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND s.expires_at > GETDATE()
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

        except Exception as e:
            return None
        finally:
            try:
                conn.close()
            except:
                pass

    def logout(self, token: str) -> bool:
        """用户登出"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            try:
                conn.close()
            except:
                pass

    def change_password(self, user_id: int, current_password: str, new_password: str) -> Dict:
        """修改密码"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 获取当前密码哈希
            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户不存在'}

            current_password_hash = row[0]

            # 验证当前密码
            if not self.verify_password(current_password, current_password_hash):
                return {'success': False, 'error': '当前密码错误'}

            # 更新密码
            new_password_hash = self.hash_password(new_password)
            cursor.execute('''
                UPDATE users SET password_hash = ? WHERE id = ?
            ''', (new_password_hash, user_id))

            conn.commit()

            return {'success': True, 'message': '密码修改成功'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except:
                pass

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM sessions WHERE expires_at < GETDATE()')
            conn.commit()
        except Exception as e:
            pass
        finally:
            try:
                conn.close()
            except:
                pass

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id, username, email, created_at, last_login FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            return None
        finally:
            try:
                conn.close()
            except:
                pass

    def verify_username(self, username: str) -> Dict:
        """验证用户名是否存在"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id, username FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()

            if row:
                return {'success': True, 'message': '用户名存在'}
            else:
                return {'success': False, 'error': '用户名不存在'}

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except:
                pass

    def reset_password(self, username: str, new_password: str) -> Dict:
        """重置密码 - 用户自己设置新密码"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 查找用户
            cursor.execute('SELECT id, username FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户名不存在'}

            columns = [column[0] for column in cursor.description]
            user = dict(zip(columns, row))

            # 更新密码
            password_hash = self.hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user['id']))

            # 删除所有会话，强制重新登录
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))

            conn.commit()

            print(f"[RESET PASSWORD] 用户: {username} 已重置密码")

            return {'success': True, 'message': '密码重置成功'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except:
                pass

    def forgot_password(self, username: str) -> Dict:
        """忘记密码 - 生成新密码（已弃用）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 查找用户
            cursor.execute('SELECT id, username, email FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户名不存在'}

            columns = [column[0] for column in cursor.description]
            user = dict(zip(columns, row))

            # 生成新密码（6位随机密码）
            import string
            new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))

            # 更新密码
            password_hash = self.hash_password(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user['id']))

            # 删除所有会话，强制重新登录
            cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))

            conn.commit()

            # 在控制台打印新密码（实际项目中应发送邮件）
            print(f"[RESET PASSWORD] 用户: {username}, 新密码: {new_password}")

            # 返回成功，包含新密码（仅用于演示）
            return {
                'success': True,
                'message': '密码重置成功',
                'new_password': new_password
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            try:
                conn.close()
            except:
                pass
