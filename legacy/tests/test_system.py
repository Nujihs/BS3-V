"""
简谱转换系统测试脚本
"""

import requests
import json
import base64
import os

BASE_URL = 'http://127.0.0.1:5000'

def test_convert_text():
    """测试文字转换"""
    print("=" * 60)
    print("测试: 文字转换")
    print("=" * 60)
    
    test_cases = [
        {
            'name': '小星星',
            'text': '1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 - |',
            'key': 'C',
            'type': 'C'
        },
        {
            'name': '欢乐颂',
            'text': '3 3 4 5 | 5 4 3 2 | 1 1 2 3 | 3 2 2 - |',
            'key': 'C',
            'type': 'C'
        },
        {
            'name': '低音练习',
            'text': '5. 6. 7. 1 | 2 3 2 1 | 7. 1 7. 6. | 5. - - - |',
            'key': 'C',
            'type': 'LowC'
        }
    ]
    
    for case in test_cases:
        print(f"\n测试用例: {case['name']}")
        print(f"输入: {case['text']}")
        print(f"调号: {case['key']}, 口琴类型: {case['type']}")
        
        response = requests.post(f'{BASE_URL}/api/convert/text', json={
            'text': case['text'],
            'key_signature': case['key'],
            'harmonica_type': case['type']
        })
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print("✓ 转换成功")
                print(f"BD谱: {result['data']['bd_text'][:100]}...")
                print(f"分析: {result['data']['analysis']}")
            else:
                print(f"✗ 转换失败: {result['error']}")
        else:
            print(f"✗ 请求失败: HTTP {response.status_code}")

def test_get_history():
    """测试获取历史记录"""
    print("\n" + "=" * 60)
    print("测试: 获取历史记录")
    print("=" * 60)
    
    response = requests.get(f'{BASE_URL}/api/conversions')
    
    if response.status_code == 200:
        result = response.json()
        if result['success']:
            print(f"✓ 获取成功，共 {len(result['data'])} 条记录")
            for record in result['data'][:3]:
                print(f"  - ID: {record['id']}, 调号: {record['key_signature']}, 时间: {record['created_at']}")
        else:
            print(f"✗ 获取失败: {result['error']}")
    else:
        print(f"✗ 请求失败: HTTP {response.status_code}")

def test_delete_record(record_id):
    """测试删除记录"""
    print("\n" + "=" * 60)
    print("测试: 删除记录")
    print("=" * 60)
    
    response = requests.delete(f'{BASE_URL}/api/conversions/{record_id}')
    
    if response.status_code == 200:
        result = response.json()
        if result['success']:
            print(f"✓ 删除成功")
        else:
            print(f"✗ 删除失败: {result['error']}")
    else:
        print(f"✗ 请求失败: HTTP {response.status_code}")

def test_get_single_record(record_id):
    """测试获取单条记录"""
    print("\n" + "=" * 60)
    print("测试: 获取单条记录")
    print("=" * 60)
    
    response = requests.get(f'{BASE_URL}/api/conversions/{record_id}')
    
    if response.status_code == 200:
        result = response.json()
        if result['success']:
            print(f"✓ 获取成功")
            print(f"  ID: {result['data']['id']}")
            print(f"  调号: {result['data']['key_signature']}")
            print(f"  BD谱: {result['data']['bd_text'][:50]}...")
        else:
            print(f"✗ 获取失败: {result['error']}")
    else:
        print(f"✗ 请求失败: HTTP {response.status_code}")

def main():
    """运行所有测试"""
    print("\n========================================")
    print("  简谱转换系统 - 功能测试")
    print("========================================")
    
    # 检查服务器是否运行
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"\n✓ 服务器运行中: {BASE_URL}")
    except requests.exceptions.RequestException:
        print(f"\n✗ 服务器未运行，请先启动服务器: start.bat")
        return
    
    # 运行测试
    test_convert_text()
    test_get_history()
    
    # 获取第一条记录进行删除测试
    response = requests.get(f'{BASE_URL}/api/conversions')
    if response.status_code == 200:
        result = response.json()
        if result['success'] and len(result['data']) > 0:
            record_id = result['data'][0]['id']
            test_get_single_record(record_id)
            # 注意：这里不实际删除，避免影响历史记录
            # test_delete_record(record_id)
    
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    main()
