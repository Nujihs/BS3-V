"""
简谱转换系统 - Flask后端应用
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from functools import wraps
import os
import sys
import tempfile
from datetime import datetime
import json
from typing import Dict, List
import numpy as np
from PIL import Image
import base64

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入转换器和认证模块
from main import JianpuToBDConverter

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入PostgreSQL模块（Vercel适配：原SQL Server版已移至legacy/）
from auth_pg import AuthManager
from database_manager_pg import DatabaseManager
print("[INFO] Using PostgreSQL database")

# 创建Flask应用（前端统一使用 public/，与 Vercel 静态托管同源）
app = Flask(__name__, template_folder='../public', static_folder='../public/static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'jianpu-converter-secret-key-2024')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出目录路径
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 初始化转换器和认证管理器
converter = JianpuToBDConverter()
auth_manager = AuthManager()
db_manager = DatabaseManager()
print(f"[INFO] PostgreSQL: {os.getenv('PG_HOST', 'localhost')}/{os.getenv('PG_DATABASE', 'jianpu_db')}")


def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'error': '未提供认证令牌'}), 401

        if token.startswith('Bearer '):
            token = token[7:]

        user = auth_manager.verify_token(token)
        if not user:
            return jsonify({'success': False, 'error': '无效或过期的令牌'}), 401

        # 将用户信息添加到请求上下文
        request.user = user
        return f(*args, **kwargs)
    return decorated_function


def optional_auth(f):
    """可选认证装饰器（允许未登录访问）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        user = None

        if token:
            if token.startswith('Bearer '):
                token = token[7:]
            user = auth_manager.verify_token(token)

        # 将用户信息（可能为None）添加到请求上下文
        request.user = user
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ==================== 认证相关API ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '')
        email = email.strip() if email else None
        
        if not username:
            return jsonify({'success': False, 'error': '用户名不能为空'})
        
        if len(username) < 3:
            return jsonify({'success': False, 'error': '用户名至少3个字符'})
        
        if not password:
            return jsonify({'success': False, 'error': '密码不能为空'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少6个字符'})
        
        result = auth_manager.register(username, password, email)
        return jsonify(result)
    
    except Exception as e:
        import traceback
        print(f"注册错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码不能为空'})
        
        result = auth_manager.login(username, password)
        return jsonify(result)
    
    except Exception as e:
        import traceback
        print(f"登录错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    try:
        token = request.headers.get('Authorization', '')
        if token.startswith('Bearer '):
            token = token[7:]

        if token:
            auth_manager.logout(token)

        return jsonify({'success': True, 'message': '登出成功'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """修改密码"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'success': False, 'error': '请提供当前密码和新密码'})

        result = auth_manager.change_password(request.user['user_id'], current_password, new_password)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/verify', methods=['GET'])
def verify_auth():
    """验证令牌"""
    try:
        token = request.headers.get('Authorization', '')
        if token.startswith('Bearer '):
            token = token[7:]
        
        if not token:
            return jsonify({'success': False, 'error': '未提供令牌'})
        
        user = auth_manager.verify_token(token)
        if user:
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'error': '无效或过期的令牌'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/user', methods=['GET'])
@require_auth
def get_user_info():
    """获取当前用户信息"""
    try:
        user_info = auth_manager.get_user_by_id(request.user['user_id'])
        if user_info:
            return jsonify({'success': True, 'data': user_info})
        else:
            return jsonify({'success': False, 'error': '用户不存在'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/verify-username', methods=['POST'])
def verify_username():
    """验证用户名是否存在"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()

        if not username:
            return jsonify({'success': False, 'error': '用户名不能为空'})

        result = auth_manager.verify_username(username)
        return jsonify(result)

    except Exception as e:
        import traceback
        print(f"验证用户名错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """重置密码 - 用户自己设置新密码"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username:
            return jsonify({'success': False, 'error': '用户名不能为空'})

        if not password:
            return jsonify({'success': False, 'error': '密码不能为空'})

        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少需要6个字符'})

        result = auth_manager.reset_password(username, password)
        return jsonify(result)

    except Exception as e:
        import traceback
        print(f"重置密码错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


# ==================== 转换相关API ====================


@app.route('/api/convert/text', methods=['POST'])
@optional_auth
def convert_text():
    """转换简谱文本"""
    try:
        data = request.get_json()
        jianpu_text = data.get('text', '').strip()
        key_signature = data.get('key_signature', 'C')
        harmonica_type = data.get('harmonica_type', 'C')
        
        if not jianpu_text:
            return jsonify({'success': False, 'error': '请输入简谱'})
        
        # 转换简谱
        result = converter.process_text(jianpu_text, key_signature, harmonica_type)

        # 音频转为 base64 内联返回（Serverless 无持久磁盘，不落盘）
        audio_base64 = base64.b64encode(
            converter.audio_synth.to_wav_bytes(result['audio'])
        ).decode('utf-8')

        # 读取BD谱图片并转换为base64
        with open(result['bd_image'], 'rb') as f:
            bd_image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 读取口琴孔位图示并转换为base64
        with open(result['harmonica_diagram'], 'rb') as f:
            harmonica_diagram_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 保存转换记录，关联用户（如果已登录）
        user_id = request.user['user_id'] if request.user else None
        record_data = {
            'input_text': jianpu_text,
            'input_image': None,
            'key_signature': key_signature,
            'harmonica_type': harmonica_type,
            'bd_text': result['bd_text'],
            'bd_image': bd_image_base64,
            'analysis': result['analysis'],
            'user_id': user_id
        }

        record_id = db_manager.save_conversion(record_data)

        return jsonify({
            'success': True,
            'data': {
                'id': record_id,
                'bd_text': result['bd_text'],
                'bd_image': f'data:image/png;base64,{bd_image_base64}',
                'harmonica_diagram': f'data:image/png;base64,{harmonica_diagram_base64}',
                'audio_data': f'data:audio/wav;base64,{audio_base64}',
                'analysis': result['analysis']
            }
        })
    
    except Exception as e:
        import traceback
        print(f"转换错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/convert/image', methods=['POST'])
@optional_auth
def convert_image():
    """转换简谱图片"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '请上传图片'})
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'})
        
        key_signature = request.form.get('key_signature', 'C')
        harmonica_type = request.form.get('harmonica_type', 'C')
        
        # 保存临时图片
        temp_path = os.path.join(tempfile.gettempdir(), 'temp_jianpu.png')
        file.save(temp_path)
        
        # 转换图片
        result = converter.process_image(temp_path, key_signature, harmonica_type)

        # 音频转为 base64 内联返回（Serverless 无持久磁盘，不落盘）
        audio_base64 = base64.b64encode(
            converter.audio_synth.to_wav_bytes(result['audio'])
        ).decode('utf-8')

        # 读取BD谱图片并转换为base64
        with open(result['bd_image'], 'rb') as f:
            bd_image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 读取口琴孔位图示并转换为base64
        with open(result['harmonica_diagram'], 'rb') as f:
            harmonica_diagram_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 读取原始图片并转换为base64
        with open(temp_path, 'rb') as f:
            input_image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 保存转换记录，关联用户（如果已登录）
        user_id = request.user['user_id'] if request.user else None
        record_data = {
            'input_text': None,
            'input_image': input_image_base64,
            'key_signature': key_signature,
            'harmonica_type': harmonica_type,
            'bd_text': result['bd_text'],
            'bd_image': bd_image_base64,
            'analysis': result['analysis'],
            'user_id': user_id
        }

        record_id = db_manager.save_conversion(record_data)

        return jsonify({
            'success': True,
            'data': {
                'id': record_id,
                'bd_text': result['bd_text'],
                'bd_image': f'data:image/png;base64,{bd_image_base64}',
                'harmonica_diagram': f'data:image/png;base64,{harmonica_diagram_base64}',
                'input_image': f'data:image/png;base64,{input_image_base64}',
                'audio_data': f'data:audio/wav;base64,{audio_base64}',
                'analysis': result['analysis']
            }
        })
    
    except Exception as e:
        import traceback
        print(f"转换错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/conversions', methods=['GET'])
@require_auth
def get_conversions():
    """获取转换历史记录"""
    try:
        user_id = request.user['user_id']
        # 只返回当前用户的记录，不限制数量
        records = db_manager.get_conversions_by_user(user_id, limit=None)
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/conversions/<int:record_id>', methods=['GET'])
@require_auth
def get_conversion(record_id: int):
    """获取单个转换记录"""
    try:
        user_id = request.user['user_id']
        record = db_manager.get_conversion_by_id(record_id)
        
        if record:
            # 检查是否属于当前用户
            if record.get('user_id') != user_id:
                return jsonify({'success': False, 'error': '无权访问此记录'}), 403
            
            # 添加data URI前缀
            if record['bd_image']:
                record['bd_image'] = f'data:image/png;base64,{record["bd_image"]}'
            if record['input_image']:
                record['input_image'] = f'data:image/png;base64,{record["input_image"]}'
            return jsonify({'success': True, 'data': record})
        else:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/conversions/<int:record_id>', methods=['DELETE'])
@require_auth
def delete_conversion(record_id: int):
    """删除转换记录"""
    try:
        user_id = request.user['user_id']
        print(f"[INFO] 删除记录请求: ID={record_id}, UserID={user_id}")
        
        # 先检查记录是否属于当前用户
        record = db_manager.get_conversion_by_id(record_id)
        if not record:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
        
        if record.get('user_id') != user_id:
            return jsonify({'success': False, 'error': '无权删除此记录'}), 403
        
        deleted = db_manager.delete_conversion(record_id)
        print(f"[INFO] 删除结果: {deleted}")

        if deleted:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        import traceback
        print(f"[ERROR] 删除记录失败: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/static/<path:filename>')
def serve_static(filename):
    """提供静态文件（前端统一在 public/）"""
    return send_from_directory(os.path.join(PROJECT_ROOT, 'public', 'static'), filename)


@app.route('/static/audio/<path:filename>')
def serve_audio(filename):
    """提供音频文件"""
    return send_from_directory(OUTPUT_DIR, filename)


def main():
    """启动应用"""
    # 确保必要的目录存在
    os.makedirs(os.path.join(PROJECT_ROOT, 'public'), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_ROOT, 'public', 'static'), exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("========================================")
    print("  简谱转BD谱系统 - Web服务")
    print("========================================")
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"数据库: PostgreSQL - {os.getenv('PG_HOST', 'localhost')}/{os.getenv('PG_DATABASE', 'jianpu_db')}")
    print("========================================\n")

    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True
    )


if __name__ == '__main__':
    main()
