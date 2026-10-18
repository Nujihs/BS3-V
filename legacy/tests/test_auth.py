"""
认证功能测试脚本
"""

import requests
import json

BASE_URL = 'http://127.0.0.1:5000'


def test_register():
    """测试注册功能"""
    print("\n=== 测试注册 ===")
    
    username = 'testuser'
    password = 'test123'
    email = 'test@example.com'
    
    response = requests.post(f'{BASE_URL}/api/auth/register', json={
        'username': username,
        'password': password,
        'email': email
    })
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        print("✓ 注册成功")
        return username, password
    else:
        print(f"✗ 注册失败: {result.get('error')}")
        return None, None


def test_login(username, password):
    """测试登录功能"""
    print("\n=== 测试登录 ===")
    
    response = requests.post(f'{BASE_URL}/api/auth/login', json={
        'username': username,
        'password': password
    })
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        token = result.get('token')
        print(f"✓ 登录成功")
        print(f"令牌: {token[:20]}...")
        return token
    else:
        print(f"✗ 登录失败: {result.get('error')}")
        return None


def test_verify_token(token):
    """测试令牌验证"""
    print("\n=== 测试令牌验证 ===")
    
    response = requests.get(f'{BASE_URL}/api/auth/verify', headers={
        'Authorization': f'Bearer {token}'
    })
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        print("✓ 令牌验证成功")
        return True
    else:
        print(f"✗ 令牌验证失败: {result.get('error')}")
        return False


def test_convert_text(token):
    """测试文字转换（需要认证）"""
    print("\n=== 测试文字转换 ===")
    
    response = requests.post(f'{BASE_URL}/api/convert/text',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'text': '1 1 5 5 | 6 6 5 - |',
            'key_signature': 'C',
            'harmonica_type': 'C'
        }
    )
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        print("✓ 转换成功")
        return result.get('data', {}).get('id')
    else:
        print(f"✗ 转换失败: {result.get('error')}")
        return None


def test_get_conversions(token):
    """测试获取历史记录（需要认证）"""
    print("\n=== 测试获取历史记录 ===")
    
    response = requests.get(f'{BASE_URL}/api/conversions',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    if result.get('success'):
        records = result.get('data', [])
        print(f"✓ 获取成功，共 {len(records)} 条记录")
        return records
    else:
        print(f"✗ 获取失败: {result.get('error')}")
        return []


def test_logout(token):
    """测试登出功能"""
    print("\n=== 测试登出 ===")
    
    response = requests.post(f'{BASE_URL}/api/auth/logout',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    result = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success'):
        print("✓ 登出成功")
        return True
    else:
        print(f"✗ 登出失败: {result.get('error')}")
        return False


def main():
    """运行所有测试"""
    print("=" * 50)
    print("  认证功能测试")
    print("=" * 50)
    print(f"服务器地址: {BASE_URL}")
    
    try:
        # 测试注册
        username, password = test_register()
        
        if not username or not password:
            print("\n⚠️  注册失败，使用测试账号...")
            username = 'testuser'
            password = 'test123'
        
        # 测试登录
        token = test_login(username, password)
        
        if not token:
            print("\n✗ 登录失败，无法继续测试")
            return
        
        # 测试令牌验证
        test_verify_token(token)
        
        # 测试文字转换
        record_id = test_convert_text(token)
        
        # 测试获取历史记录
        records = test_get_conversions(token)
        
        # 测试登出
        test_logout(token)
        
        # 测试登出后令牌是否失效
        print("\n=== 测试登出后令牌失效 ===")
        is_valid = test_verify_token(token)
        if not is_valid:
            print("✓ 令牌已正确失效")
        else:
            print("✗ 令牌未失效，存在安全问题")
        
        print("\n" + "=" * 50)
        print("  测试完成")
        print("=" * 50)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ 无法连接到服务器")
        print("请确保服务器正在运行:")
        print("  start.bat")
    except Exception as e:
        print(f"\n✗ 测试出错: {str(e)}")
        import traceback
        print(traceback.format_exc())


if __name__ == '__main__':
    main()
