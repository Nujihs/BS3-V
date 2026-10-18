"""
Vercel Serverless 入口（api/index.py）

通过 DispatcherMiddleware 同时挂载：
  - 主应用（转换/认证/历史） → /
  - 后台管理（CRUD）        → /admin

vercel.json 中的 rewrite 会把原始路径通过 __path query 参数传入，
本文件在进入 WSGI 前将其恢复为 PATH_INFO，保证 Flask 路由正确。

适配器为自实现版本（不依赖第三方包）：将 Vercel Python Runtime 的
handler(event, context) 请求结构转换为标准 WSGI environ，并回写响应。
"""

import base64
import io
import json
import os
import sys
from urllib.parse import unquote, parse_qsl, urlencode

# 将项目根目录与 backend 目录加入 Python 路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'backend'))

from werkzeug.middleware.dispatcher import DispatcherMiddleware  # noqa: E402

import app as main_app_module  # noqa: E402
import admin_app as admin_app_module  # noqa: E402


def _restore_path(wsgi_app):
    """恢复 Vercel rewrite 丢失的原始 PATH_INFO（通过 __path query 参数传递）"""
    def wrapped(environ, start_response):
        query = environ.get('QUERY_STRING', '')
        params = parse_qsl(query, keep_blank_values=True)
        restored = None
        remaining = []
        for key, value in params:
            if key == '__path':
                restored = value
            else:
                remaining.append((key, value))
        if restored:
            environ['PATH_INFO'] = restored
            environ['QUERY_STRING'] = urlencode(remaining)
        return wsgi_app(environ, start_response)
    return wrapped


# 主应用挂载在 /，后台管理挂载在 /admin
application = _restore_path(DispatcherMiddleware(main_app_module.app, {
    '/admin': admin_app_module.app,
}))


def _build_environ(event: dict) -> dict:
    """将 Vercel event 转换为 WSGI environ"""
    method = (event.get('method') or 'GET').upper()
    path = event.get('path') or '/'
    query = event.get('query') or ''
    headers = event.get('headers') or {}

    environ = {
        'REQUEST_METHOD': method,
        'PATH_INFO': unquote(path) if path else '/',
        'QUERY_STRING': query,
        'SCRIPT_NAME': '',
        'SERVER_NAME': headers.get('host', 'vercel.app'),
        'SERVER_PORT': headers.get('x-forwarded-port', '443'),
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https') or 'https',
        'wsgi.input': None,
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }

    for k, v in headers.items():
        key = k.upper().replace('-', '_')
        if key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            environ[key] = v
        else:
            environ['HTTP_' + key] = v

    body = event.get('body') or ''
    raw = None
    # Vercel 对二进制请求体会 base64 编码并在 header 中标记
    if isinstance(body, str) and (headers.get('x-vercel-base64') == '1'
                                  or (body and '=' in body and _looks_like_base64(body))):
        try:
            raw = base64.b64decode(body)
        except Exception:
            raw = body.encode('utf-8')
    else:
        raw = body.encode('utf-8') if isinstance(body, str) else body
    environ['wsgi.input'] = io.BytesIO(raw)
    if 'CONTENT_LENGTH' not in environ:
        environ['CONTENT_LENGTH'] = str(len(raw))
    return environ


def _looks_like_base64(s: str) -> bool:
    """宽松判断字符串是否为 base64 编码"""
    if len(s) < 8:
        return False
    import re
    return bool(re.fullmatch(r'[A-Za-z0-9+/=\s]+', s[:256]))


def handler(event: dict, context):
    """Vercel Python Runtime 入口"""
    try:
        environ = _build_environ(event)

        status_holder = {}

        def start_response(status, response_headers, exc_info=None):
            status_holder['status'] = status
            status_holder['headers'] = response_headers

        body_iter = application(environ, start_response)
        body = b''.join(body_iter)

        status = status_holder.get('status', '200 OK')
        status_code = int(status.split(' ')[0])
        headers = {k: v for k, v in status_holder.get('headers', [])}

        content_type = headers.get('content-type', headers.get('Content-Type', '')).lower()
        if 'image/' in content_type or 'audio/' in content_type:
            return {
                'statusCode': status_code,
                'headers': {**headers, 'x-vercel-base64': '1'},
                'body': base64.b64encode(body).decode('utf-8'),
            }
        return {
            'statusCode': status_code,
            'headers': headers,
            'body': body.decode('utf-8', 'replace'),
        }
    except Exception as e:
        # 异常兜底：返回 JSON 错误详情，便于在前端/浏览器直接看到真实原因
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'content-type': 'application/json; charset=utf-8'},
            'body': json.dumps({
                'success': False,
                'error': f'FUNCTION ERROR: {type(e).__name__}: {str(e)}',
            }, ensure_ascii=False),
        }
