"""
简谱转换系统 - 后台管理系统
提供对数据库的增删改查（CRUD）功能
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from datetime import datetime
import os
import sys
import json
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 创建Flask应用
app = Flask(__name__, 
           template_folder='../admin/templates',
           static_folder='../admin/static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'admin-secret-key-2024')

# 添加 datetime 到模板上下文
@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)

def get_db_connection():
    """获取数据库连接（NamedTupleCursor：行既可按下标也可按属性访问）"""
    from db_pg import get_dsn
    conn = psycopg2.connect(get_dsn())
    conn.autocommit = False
    return conn

def get_db_cursor(conn):
    """创建 NamedTupleCursor 游标"""
    return conn.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 路由 ====================

@app.route('/', strict_slashes=False)
def index():
    """首页（strict_slashes=False：让 /admin 不带尾斜杠也能直达，避免 308 中间跳转）"""
    if 'admin_logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # 调试输出
        print(f"[DEBUG] 登录尝试: username='{username}', password='{password}'")
        print(f"[DEBUG] 预期: username='admin', password='admin123'")
        print(f"[DEBUG] 用户名匹配: {username == 'admin'}")
        print(f"[DEBUG] 密码匹配: {password == 'admin123'}")

        # 简单硬编码管理员（生产环境应使用数据库存储）
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['login_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[DEBUG] 登录成功，重定向到 dashboard")
            return redirect(url_for('dashboard'))
        else:
            print(f"[DEBUG] 登录失败")
            return render_template('login.html', error='用户名或密码错误')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """管理员登出"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """仪表板"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # 统计数据
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversions")
        conversion_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        # 最近活动
        cursor.execute("SELECT id, username, created_at FROM users ORDER BY id DESC LIMIT 5")
        recent_users = cursor.fetchall()
        
        cursor.execute("SELECT id, key_signature, harmonica_type, created_at FROM conversions ORDER BY id DESC LIMIT 5")
        recent_conversions = cursor.fetchall()
        
        conn.close()
        
        return render_template('dashboard.html',
                          user_count=user_count,
                          conversion_count=conversion_count,
                          session_count=session_count,
                          recent_users=recent_users,
                          recent_conversions=recent_conversions)
    except Exception as e:
        return f"错误: {str(e)}"

# ==================== 用户管理 ====================

@app.route('/users')
@login_required
def users():
    """用户列表"""
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    search_query = request.args.get('search', '').strip()

    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)

        if search_query:
            # 模糊搜索（搜索用户名或邮箱）
            cursor.execute("""
                SELECT COUNT(*)
                FROM users
                WHERE username LIKE %s OR email LIKE %s
            """, (f'%{search_query}%', f'%{search_query}%'))
            total = cursor.fetchone()[0]

            # 获取搜索结果
            cursor.execute("""
                SELECT id, username, email, created_at, last_login
                FROM users
                WHERE username LIKE %s OR email LIKE %s
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """, (f'%{search_query}%', f'%{search_query}%', per_page, offset))
        else:
            # 获取所有用户
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]

            # 获取用户列表
            cursor.execute("""
                SELECT id, username, email, created_at, last_login
                FROM users
                ORDER BY id DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))

        users_list = cursor.fetchall()
        conn.close()

        total_pages = (total + per_page - 1) // per_page
        return render_template('users.html',
                          users=users_list,
                          page=page,
                          total_pages=total_pages,
                          total=total,
                          search_query=search_query)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    """新建用户"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        try:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)

            # 密码哈希（使用与前端登录相同的加盐哈希方法）
            import hashlib
            import secrets
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            password_hash = f"{salt}:{password_hash}"

            cursor.execute("""
                INSERT INTO users (username, password_hash, email, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (username, password_hash, email or None))

            conn.commit()
            conn.close()

            return redirect(url_for('users'))
        except Exception as e:
            return render_template('user_form.html', error=str(e))
    
    return render_template('user_form.html', action='create')

@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """编辑用户"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        try:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            
            cursor.execute("""
                UPDATE users
                SET username = %s, email = %s
                WHERE id = %s
            """, (username, email or None, user_id))
            
            conn.commit()
            conn.close()
            
            return redirect(url_for('users'))
        except Exception as e:
            return render_template('user_form.html', error=str(e), action='edit')
    
    # GET请求 - 显示表单
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return render_template('user_form.html', user=user, action='edit')
        else:
            return redirect(url_for('users'))
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """删除用户"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)

        # 先获取用户名，用于清除前端头像
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        username_row = cursor.fetchone()

        if not username_row:
            conn.close()
            return "用户不存在"

        username = username_row[0]

        # 删除用户的会话
        cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))

        # 删除用户的转换记录
        cursor.execute("DELETE FROM conversions WHERE user_id = %s", (user_id,))

        # 删除用户
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()
        conn.close()

        return redirect(url_for('users'))
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/users/<int:user_id>/change-password', methods=['GET', 'POST'])
@login_required
def change_password(user_id):
    """修改用户密码"""
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 验证密码
        if not password or len(password) < 6:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            conn.close()
            return render_template('change_password.html',
                              user=user,
                              error='密码长度至少为6个字符')
        
        if password != confirm_password:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            conn.close()
            return render_template('change_password.html',
                              user=user,
                              error='两次输入的密码不一致')
        
        try:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)

            # 密码哈希（使用与前端登录相同的加盐哈希方法）
            import hashlib
            import secrets
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            password_hash = f"{salt}:{password_hash}"

            cursor.execute("""
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
            """, (password_hash, user_id))

            conn.commit()
            conn.close()

            # 获取用户信息
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            conn.close()

            return render_template('change_password.html',
                              user=user,
                              success='密码修改成功！')
        except Exception as e:
            conn = get_db_connection()
            cursor = get_db_cursor(conn)
            cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            conn.close()
            return render_template('change_password.html',
                              user=user,
                              error=f'修改失败: {str(e)}')
    
    # GET请求 - 显示表单
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return render_template('change_password.html', user=user)
        else:
            return redirect(url_for('users'))
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/users/<int:user_id>')
@login_required
def view_user(user_id):
    """查看用户详情"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        # 获取用户的转换记录
        cursor.execute("""
            SELECT id, key_signature, harmonica_type, created_at
            FROM conversions
            WHERE user_id = %s
            ORDER BY id DESC
        """, (user_id,))
        conversions = cursor.fetchall()
        
        conn.close()
        
        if user:
            return render_template('user_detail.html', user=user, conversions=conversions)
        else:
            return redirect(url_for('users'))
    except Exception as e:
        return f"错误: {str(e)}"

# ==================== 转换记录管理 ====================

@app.route('/conversions')
@login_required
def conversions():
    """转换记录列表"""
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    user_id = request.args.get('user_id')
    
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        # 构建查询
        if user_id:
            cursor.execute(f"""
                SELECT COUNT(*) FROM conversions WHERE user_id = {user_id}
            """)
            total = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT c.id, c.key_signature, c.harmonica_type, c.created_at, u.username
                FROM conversions c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.user_id = {user_id}
                ORDER BY c.id DESC
                LIMIT {per_page} OFFSET {offset}
            """)
        else:
            cursor.execute("SELECT COUNT(*) FROM conversions")
            total = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT c.id, c.key_signature, c.harmonica_type, c.created_at, u.username
                FROM conversions c
                LEFT JOIN users u ON c.user_id = u.id
                ORDER BY c.id DESC
                LIMIT {per_page} OFFSET {offset}
            """)
        
        conversions_list = cursor.fetchall()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page
        return render_template('conversions.html',
                          conversions=conversions_list,
                          page=page,
                          total_pages=total_pages,
                          total=total,
                          user_id=user_id)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/conversions/<int:conversion_id>')
@login_required
def view_conversion(conversion_id):
    """查看转换记录详情"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT * FROM conversions WHERE id = %s", (conversion_id,))
        conversion = cursor.fetchone()
        
        conn.close()
        
        if conversion:
            # 解析JSON字段
            analysis = conversion[8] if conversion[8] else '{}'
            try:
                analysis_data = json.loads(analysis)
            except:
                analysis_data = {}
            
            return render_template('conversion_detail.html', 
                              conversion=conversion,
                              analysis=analysis_data)
        else:
            return redirect(url_for('conversions'))
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/conversions/<int:conversion_id>/delete', methods=['POST'])
@login_required
def delete_conversion(conversion_id):
    """删除转换记录"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("DELETE FROM conversions WHERE id = %s", (conversion_id,))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('conversions'))
    except Exception as e:
        return f"错误: {str(e)}"

# ==================== 会话管理 ====================

@app.route('/sessions')
@login_required
def sessions():
    """会话列表"""
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total = cursor.fetchone()[0]
        
        cursor.execute(f"""
            SELECT s.id, u.username, s.token, s.created_at, s.expires_at
            FROM sessions s
            LEFT JOIN users u ON s.user_id = u.id
            ORDER BY s.id DESC
            LIMIT {per_page} OFFSET {offset}
        """)
        
        sessions_list = cursor.fetchall()
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page
        return render_template('sessions.html',
                          sessions=sessions_list,
                          page=page,
                          total_pages=total_pages,
                          total=total)
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_session(session_id):
    """删除会话"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('sessions'))
    except Exception as e:
        return f"错误: {str(e)}"

@app.route('/sessions/clear-expired', methods=['POST'])
@login_required
def clear_expired_sessions():
    """清理过期会话"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("DELETE FROM sessions WHERE expires_at < NOW()")
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return redirect(url_for('sessions'))
    except Exception as e:
        return f"错误: {str(e)}"

# ==================== API接口 ====================

@app.route('/api/stats')
@login_required
def api_stats():
    """获取统计数据"""
    try:
        conn = get_db_connection()
        cursor = get_db_cursor(conn)
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversions")
        conversion_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        # 按调号统计
        cursor.execute("""
            SELECT key_signature, COUNT(*) as count
            FROM conversions
            WHERE key_signature IS NOT NULL
            GROUP BY key_signature
            ORDER BY count DESC
        """)
        key_stats = cursor.fetchall()
        
        # 按口琴类型统计
        cursor.execute("""
            SELECT harmonica_type, COUNT(*) as count
            FROM conversions
            WHERE harmonica_type IS NOT NULL
            GROUP BY harmonica_type
            ORDER BY count DESC
        """)
        harmonica_stats = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'user_count': user_count,
                'conversion_count': conversion_count,
                'session_count': session_count,
                'key_signature_stats': [{'name': k, 'value': c} for k, c in key_stats],
                'harmonica_type_stats': [{'name': h, 'value': c} for h, c in harmonica_stats]
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def main():
    """启动应用"""
    print("="*60)
    print("  简谱转换系统 - 后台管理系统")
    print("="*60)
    print(f"访问地址: http://127.0.0.1:5001")
    print(f"默认账号: admin / admin123")
    print("="*60)
    
    app.run(host='127.0.0.1', port=5001, debug=True)

if __name__ == '__main__':
    main()
