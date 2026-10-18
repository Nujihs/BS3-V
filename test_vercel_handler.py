"""Vercel handler 适配层模拟测试：验证 DispatcherMiddleware 挂载 + __path 路径恢复"""
import sys
import json
import os

sys.path.insert(0, "/home/user/Doubao/chats/38447782371484162/BS3-vercel")
sys.path.insert(0, "/home/user/Doubao/chats/38447782371484162/BS3-vercel/api")

from api.index import handler  # noqa: E402

ok_count = 0
fail_count = 0


def check(name, cond, detail=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"[PASS] {name}")
    else:
        fail_count += 1
        print(f"[FAIL] {name} -> {detail}")


def call(method, path, query="", body=None, content_type="application/json"):
    """构造 Vercel event（模拟 rewrite 后：path=/api/index, query 带 __path）"""
    event = {
        "method": method,
        "path": "/api/index",          # rewrite 目标路径
        "query": f"__path={path}" + (f"&{query}" if query else ""),
        "headers": {
            "content-type": content_type,
            "host": "bs3-vercel.vercel.app",
            "x-forwarded-proto": "https",
        },
        "body": json.dumps(body) if body is not None and not isinstance(body, str) else (body or ""),
    }
    return handler(event, None)


# 1. 登录（经过 __path 恢复 → /api/auth/login）
resp = call("POST", "/api/auth/login", body={"username": "testuser1", "password": "pass123456"})
d = json.loads(resp["body"])
check("handler: 登录成功", resp["statusCode"] == 200 and d.get("success") is True, str(d))
token = d.get("token", "")

# 2. verify token
resp = call("GET", "/api/auth/verify", body=None)
resp = handler({
    "method": "GET",
    "path": "/api/index",
    "query": "__path=/api/auth/verify",
    "headers": {"content-type": "application/json", "authorization": f"Bearer {token}",
                "host": "bs3-vercel.vercel.app", "x-forwarded-proto": "https"},
    "body": "",
}, None)
d = json.loads(resp["body"])
check("handler: Token 验证", resp["statusCode"] == 200 and d.get("success") is True, str(d))

# 3. 文本转换
resp = call("POST", "/api/convert/text",
            body={"text": "| 5 6 5 3 | 5 6 5 2 |", "key_signature": "C", "harmonica_type": "C"})
resp = handler({
    "method": "POST",
    "path": "/api/index",
    "query": "__path=/api/convert/text",
    "headers": {"content-type": "application/json", "authorization": f"Bearer {token}",
                "host": "bs3-vercel.vercel.app", "x-forwarded-proto": "https"},
    "body": json.dumps({"text": "| 5 6 5 3 | 5 6 5 2 |", "key_signature": "C", "harmonica_type": "C"}),
}, None)
d = json.loads(resp["body"])
check("handler: 文本转换", resp["statusCode"] == 200 and d.get("success") is True and "audio_data" in d.get("data", {}), str(d.get("error")))

# 4. 后台管理登录页（DispatcherMiddleware /admin）
resp = handler({
    "method": "GET",
    "path": "/api/index",
    "query": "__path=/admin/login",
    "headers": {"content-type": "text/html", "host": "bs3-vercel.vercel.app", "x-forwarded-proto": "https"},
    "body": "",
}, None)
check("handler: /admin/login 页面", resp["statusCode"] == 200 and "登录" in resp["body"], f"{resp['statusCode']}")

# 5. 后台管理登录 POST（表单）
form_body = "username=admin&password=admin123"
resp = handler({
    "method": "POST",
    "path": "/api/index",
    "query": "__path=/admin/login",
    "headers": {"content-type": "application/x-www-form-urlencoded",
                "host": "bs3-vercel.vercel.app", "x-forwarded-proto": "https",
                "cookie": ""},
    "body": form_body,
}, None)
check("handler: /admin/login POST", resp["statusCode"] in (200, 302), f"{resp['statusCode']} {str(resp.get('headers'))[:120]}")

# 6. 未匹配路径（兜底 rewrite）→ Flask 404
resp = handler({
    "method": "GET",
    "path": "/api/index",
    "query": "__path=/no-such-page",
    "headers": {"content-type": "text/html", "host": "bs3-vercel.vercel.app", "x-forwarded-proto": "https"},
    "body": "",
}, None)
check("handler: 未知路径 404", resp["statusCode"] == 404, f"{resp['statusCode']}")

print(f"\n===== Vercel handler 模拟: {ok_count} 通过, {fail_count} 失败 =====")
