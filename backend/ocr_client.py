"""
可插拔 OCR 客户端
原项目使用 EasyOCR（PyTorch/OpenCV，数百 MB，无法部署到 Vercel Serverless）。
本模块改为调用外部 OCR API：配置 OCR_API_URL 与 OCR_API_KEY 后启用；
未配置时返回明确错误提示，文本转换功能不受影响。
"""

import os
import json
from typing import Dict

import requests


class OCRNotConfigured(Exception):
    """未配置外部 OCR 服务"""


def ocr_image_to_text(image_path: str) -> str:
    """
    调用外部 OCR API 识别简谱图片，返回识别文本（以空格连接的符号序列）。

    兼容约定（可配置）：
      - 请求：POST 图片文件（字段名 image）到 OCR_API_URL
      - 鉴权：Authorization: Bearer <OCR_API_KEY>（可通过 OCR_API_KEY_HEADER 自定义头）
      - 响应：JSON，识别文本字段名由 OCR_TEXT_FIELD 指定（默认 text），
              若无该字段则尝试拼接 data.items[].text 等常见结构
    """
    api_url = os.getenv('OCR_API_URL', '').strip()
    api_key = os.getenv('OCR_API_KEY', '').strip()
    if not api_url or not api_key:
        raise OCRNotConfigured(
            '图片 OCR 功能需要外部服务：请在环境变量中配置 OCR_API_URL 与 OCR_API_KEY'
        )

    auth_header = os.getenv('OCR_API_KEY_HEADER', 'Authorization').strip()
    text_field = os.getenv('OCR_TEXT_FIELD', 'text').strip()
    field_name = os.getenv('OCR_FILE_FIELD', 'image').strip()

    headers = {}
    if auth_header.lower() == 'authorization':
        headers['Authorization'] = f'Bearer {api_key}'
    else:
        headers[auth_header] = api_key

    with open(image_path, 'rb') as f:
        files = {field_name: (os.path.basename(image_path), f)}
        resp = requests.post(api_url, headers=headers, files=files, timeout=60)

    if resp.status_code != 200:
        raise OCRNotConfigured(f'OCR 服务返回异常状态码: {resp.status_code}')

    try:
        data = resp.json()
    except Exception:
        raise OCRNotConfigured('OCR 服务返回的不是合法 JSON')

    text = _extract_text(data, text_field)
    if not text:
        raise OCRNotConfigured('OCR 服务未返回识别文本')
    return text


def _extract_text(data: Dict, text_field: str) -> str:
    """从常见 OCR 响应结构中提取文本"""
    if isinstance(data, str):
        return data

    def _dig(obj):
        """深度优先查找字符串/文本字段"""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            for key in ('text', 'words', 'content', 'result'):
                if key in obj and obj[key]:
                    val = obj[key]
                    if isinstance(val, str):
                        return val
                    if isinstance(val, list):
                        parts = [_dig(i) for i in val if isinstance(i, dict)]
                        return ' '.join([p for p in parts if p])
            for v in obj.values():
                r = _dig(v)
                if r:
                    return r
        if isinstance(obj, list):
            for v in obj:
                r = _dig(v)
                if r:
                    return r
        return None

    if text_field and isinstance(data, dict) and data.get(text_field):
        return str(data[text_field])

    result = _dig(data)
    return (result or '').strip()
