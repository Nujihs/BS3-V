#!/usr/bin/env python3
"""BS3-Vercel 主应用全流程测试脚本（本地 PostgreSQL 实测）"""
import json
import base64
import requests

BASE = "http://127.0.0.1:5000"
results = []
ok_count = 0
fail_count = 0


def check(name, cond, detail=""):
    global ok_count, fail_count
    status = "PASS" if cond else "FAIL"
    if cond:
        ok_count += 1
    else:
        fail_count += 1
    results.append((name, status, detail))
    print(f"[{status}] {name}" + (f"  -> {detail}" if detail and not cond else ""))


# 1. 首页
r = requests.get(f"{BASE}/")
check("GET / 首页", r.status_code == 200, r.status_code)

# 2. 注册
r = requests.post(f"{BASE}/api/auth/register", json={
    "username": "testuser1", "password": "pass123456", "email": "test1@example.com"})
d = r.json()
check("注册新用户", d.get("success") is True, str(d))

# 重复注册
r = requests.post(f"{BASE}/api/auth/register", json={
    "username": "testuser1", "password": "pass123456", "email": "test1@example.com"})
d = r.json()
check("重复用户名被拒绝", d.get("success") is False and "已存在" in d.get("error", ""), str(d))

# 3. 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "testuser1", "password": "pass123456"})
d = r.json()
check("登录成功", d.get("success") is True and d.get("token"), str(d.get("error")))
token = d.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

# 错误密码
r = requests.post(f"{BASE}/api/auth/login", json={"username": "testuser1", "password": "wrongpass"})
check("错误密码被拒绝", r.json().get("success") is False)

# 4. verify token
r = requests.get(f"{BASE}/api/auth/verify", headers=headers)
d = r.json()
check("Token 验证", d.get("success") is True and d.get("user", {}).get("username") == "testuser1", str(d))

# 5. 文本转换（核心功能）
jianpu = "| 1 2 3 4 | 5 6 7 1 |"
r = requests.post(f"{BASE}/api/convert/text",
                  json={"text": jianpu, "key_signature": "C", "harmonica_type": "C"},
                  headers=headers)
d = r.json()
check("文本转换成功", d.get("success") is True, str(d.get("error")))
data = d.get("data", {})
check("返回 BD 谱文本", bool(data.get("bd_text")), str(data.get("bd_text", ""))[:40])
check("返回 BD 谱图片 base64", bool(data.get("bd_image", "").startswith("data:image/png;base64,")))
check("返回口琴图示 base64", bool(data.get("harmonica_diagram", "").startswith("data:image/png;base64,")))
check("返回音频 base64", bool(data.get("audio_data", "").startswith("data:audio/wav;base64,")))
if data.get("audio_data"):
    audio_b64 = data["audio_data"].split(",", 1)[1]
    audio_bytes = base64.b64decode(audio_b64)
    check("音频为合法 WAV 文件", audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE", f"{len(audio_bytes)} bytes")
record_id = data.get("id")

# 6. 转换历史
r = requests.get(f"{BASE}/api/conversions", headers=headers)
d = r.json()
check("获取历史记录", d.get("success") is True and len(d.get("data", [])) >= 1, str(d.get("error")))

# 7. 单条记录
if record_id:
    r = requests.get(f"{BASE}/api/conversions/{record_id}", headers=headers)
    d = r.json()
    check("获取单条记录", d.get("success") is True and d.get("data", {}).get("id") == record_id, str(d.get("error")))

# 8. 未授权访问被拒绝
r = requests.get(f"{BASE}/api/conversions")
check("未登录访问历史被拒", r.status_code == 401)

# 9. 图片转换（未配置 OCR -> 应返回明确提示）
r = requests.post(f"{BASE}/api/convert/image",
                  files={"image": ("test.png", b"fake-image-bytes", "image/png")},
                  data={"key_signature": "C", "harmonica_type": "C"},
                  headers=headers)
d = r.json()
check("图片转换返回 OCR 配置提示", d.get("success") is False and "OCR" in d.get("error", ""), str(d))

# 10. 登出
r = requests.post(f"{BASE}/api/auth/logout", headers=headers)
check("登出成功", r.json().get("success") is True)

# 11. 登出后 token 失效
r = requests.get(f"{BASE}/api/auth/verify", headers=headers)
check("登出后 Token 失效", r.json().get("success") is False)

print(f"\n===== 结果: {ok_count} 通过, {fail_count} 失败 =====")
if fail_count:
    for name, status, detail in results:
        if status == "FAIL":
            print(f"  FAIL: {name}  {detail}")
