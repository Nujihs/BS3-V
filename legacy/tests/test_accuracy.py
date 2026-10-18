"""
简谱识别准确率测试脚本
测试所有测试图片的识别准确率
"""

import os
import sys
import re
from typing import Dict, List, Tuple

# Ground Truth 数据（正确的简谱）
# BD谱音符序列（不含休止符和小节线）
GROUND_TRUTH = {
    # 小星星 - C调 (35个音符)
    "微信图片_20260316143741_269_4": {
        "bd_notes": "6D 1B 6B 3B 3D 3D 3B 2D 2D 2B 1D 1B 3B 3B 2D 2D 2B 1D 3B 3B 2D 2D 2B 1D 1B 6B 3B 3D 3D 3B 2D 2D 2B 1D 1B",
        "key": "C",
        "name": "小星星",
        "note_count": 35
    },
    # 雪绒花 - C调 (52个音符)
    "微信图片_20260316145819_274_4": {
        "bd_notes": "2B 3B 4D 1B 3B 2D 2B 2B 2B 2D 3B 3D 3B 3D 3D 4B 4B 3D 3B 2B 3B 1B 1B 2D 4B 3D 3D 2D 2D 3D 1B 1B 3B 2D 5D 2D 6B 3D 3D 3D 5D 2D 2D 3B 2D 5D 2D 2D 3D 3D 5D 2D 2D",
        "key": "C",
        "name": "雪绒花",
        "note_count": 52
    },
    # 小星星变体 (25个音符)
    "微信图片_20260316143813_270_4": {
        "bd_notes": "2D 4B 3D 3D 2D 2D 3D 1B 1B 4D 5D 2D 6B 3D 3D 5D 2D 2D 3B 2D 5D 2D 2D 3D 3D",
        "key": "C",
        "name": "小星星变体",
        "note_count": 25
    },
    # 雪绒花变体 (约25个音符)
    "微信图片_20260316143949_271_4": {
        "bd_notes": "2D 4B 3D 3D 2D 2D 3D 1B 1B 3B 2D 5D 2D 6B 3D 3D 3D 5D 2D 2D 3B 2D 5D 2D 2D",
        "key": "C",
        "name": "雪绒花变体",
        "note_count": 25
    }
}


def normalize_for_comparison(symbols: List[str]) -> str:
    """标准化简谱符号用于比较"""
    result = []
    for s in symbols:
        # 移除所有空白
        if s in ['|', '-', '||', '-|', '-||', ':||', '||:']:
            continue
        # 保留数字和点
        digit = re.sub(r'[^0-7]', '', s)
        if digit:
            # 保留前置点（高音点）和后置点（附点）
            leading_dots = ''
            trailing_dots = ''
            for c in s:
                if c == '.':
                    if len(result) == 0 or (result and result[-1].isdigit() and not any(d in ''.join(result[-10:]) for d in '.')):
                        # 检查点是在数字前还是后
                        if not trailing_dots and leading_dots:
                            trailing_dots += '.'
                        else:
                            leading_dots += '.'
                    else:
                        leading_dots += '.'
                elif c.isdigit():
                    if leading_dots:
                        result.append(leading_dots + c)
                        leading_dots = ''
                    else:
                        result.append(c)
            if leading_dots and result:
                result[-1] = leading_dots + result[-1]
    
    return ' '.join(result)


def normalize_ground_truth(gt_text: str) -> str:
    """标准化Ground Truth用于比较"""
    result = []
    for s in gt_text.split():
        if s in ['|', '-']:
            continue
        digit = re.sub(r'[^0-7]', '', s)
        if digit:
            result.append(digit)
    return ' '.join(result)


def calculate_accuracy(recognized: str, ground_truth: str) -> Tuple[float, int, int, int]:
    """
    计算识别准确率
    
    Returns: (accuracy, correct, total, errors)
    """
    rec_symbols = recognized.split()
    gt_symbols = ground_truth.split()
    
    # 标准化
    rec_norm = []
    gt_norm = []
    
    for s in rec_symbols:
        digit = re.sub(r'[^0-7]', '', s)
        if digit:
            rec_norm.append(digit)
    
    for s in gt_symbols:
        digit = re.sub(r'[^0-7]', '', s)
        if digit:
            gt_norm.append(digit)
    
    # 动态规划计算最长公共子序列
    m, n = len(gt_norm), len(rec_norm)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if gt_norm[i-1] == rec_norm[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    lcs_length = dp[m][n]
    
    correct = lcs_length
    total = max(m, n)
    errors = abs(m - n) + min(m, n) - lcs_length
    
    # 计算准确率（考虑插入、删除、替换）
    if total == 0:
        return 0.0, 0, 0, 0
    
    # 简单的字符级准确率
    matches = 0
    min_len = min(len(gt_norm), len(rec_norm))
    for i in range(min_len):
        if gt_norm[i] == rec_norm[i]:
            matches += 1
    
    accuracy = matches / max(len(gt_norm), len(rec_norm)) if max(len(gt_norm), len(rec_norm)) > 0 else 0
    
    return accuracy, matches, len(gt_norm), len(rec_norm)


def analyze_errors(recognized: str, ground_truth: str) -> List[str]:
    """分析识别错误"""
    rec_symbols = recognized.split()
    gt_symbols = ground_truth.split()
    
    errors = []
    
    # 标准化
    rec_digits = [re.sub(r'[^0-7]', '', s) for s in rec_symbols if re.sub(r'[^0-7]', '', s)]
    gt_digits = [re.sub(r'[^0-7]', '', s) for s in gt_symbols if re.sub(r'[^0-7]', '', s)]
    
    min_len = min(len(rec_digits), len(gt_digits))
    
    for i in range(min_len):
        if rec_digits[i] != gt_digits[i]:
            errors.append(f"位置{i}: 识别为'{rec_digits[i]}'，应为'{gt_digits[i]}'")
    
    if len(rec_digits) > len(gt_digits):
        errors.append(f"识别多余{len(rec_digits) - len(gt_digits)}个符号: {rec_digits[len(gt_digits):]}")
    elif len(gt_digits) > len(rec_digits):
        errors.append(f"识别缺少{len(gt_digits) - len(rec_digits)}个符号: {gt_digits[len(rec_digits):]}")
    
    return errors


def extract_bd_notes_from_text(bd_text: str) -> List[str]:
    """从BD谱文本提取音符序列"""
    notes = []
    for line in bd_text.strip().split('\n'):
        for note in line.split():
            # 过滤休止符 [X] 和小节线 |
            if note and note not in ('[X]', '[x]', '|', '[R]') and not note.startswith('-'):
                if not note.endswith('-'):
                    notes.append(note)
            elif note and not note.startswith('-') and note not in ('[X]', '[x]', '|', '[R]'):
                # 移除附点休止符的 - 后缀
                clean_note = note.rstrip('-')
                if clean_note and clean_note not in ('[X]', '[x]', '|', '[R]'):
                    notes.append(clean_note)
    return notes


def extract_bd_notes_simple(bd_text: str) -> List[str]:
    """从BD谱文本简单提取所有非空白非小节线标记"""
    notes = []
    for line in bd_text.strip().split('\n'):
        for part in line.split():
            part = part.strip()
            if not part or part == '|':
                continue
            # 移除末尾的 -（延音线）
            part = part.rstrip('-')
            if part and part not in ('[X]', '[x]', '|', '[R]', ''):
                notes.append(part)
    return notes


def calculate_bd_accuracy(recognized_notes: List[str], ground_truth: str) -> Tuple[float, int, int, int]:
    """
    计算BD谱音符准确率
    
    Returns: (accuracy, correct, gt_len, rec_len)
    """
    gt_notes = ground_truth.split()
    rec_notes = recognized_notes
    
    if not rec_notes:
        return 0.0, 0, len(gt_notes), 0
    
    # 使用最长公共子序列计算
    m, n = len(gt_notes), len(rec_notes)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if gt_notes[i-1] == rec_notes[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    lcs_length = dp[m][n]
    
    # 准确率 = LCS长度 / GT长度
    accuracy = lcs_length / len(gt_notes) if gt_notes else 0
    
    return accuracy, lcs_length, len(gt_notes), len(rec_notes)


def test_image(image_path: str, ground_truth: Dict) -> Dict:
    """测试单张图片"""
    print(f"\n{'='*70}")
    print(f"测试: {ground_truth['name']} ({os.path.basename(image_path)})")
    print(f"{'='*70}")
    
    # 导入识别模块
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
    from final_jianpu_pipeline import process_jianpu_image
    
    try:
        result = process_jianpu_image(image_path, output_dir='./output_test')
        
        if not result['success']:
            return {
                'success': False,
                'error': '识别失败',
                'accuracy': 0.0
            }
        
        # 获取识别的BD谱文本
        bd_text = result.get('bd_text', '')
        recognized_notes = extract_bd_notes_simple(bd_text)
        recognized_text = ' '.join(recognized_notes)
        ground_truth_text = ground_truth['bd_notes']
        
        print(f"\n识别BD谱音符({len(recognized_notes)}个):")
        print(f"  {recognized_text}")
        
        print(f"\nGround Truth BD谱音符({ground_truth['note_count']}个):")
        print(f"  {ground_truth_text}")
        
        # 计算准确率
        accuracy, correct, gt_len, rec_len = calculate_bd_accuracy(
            recognized_notes, 
            ground_truth_text
        )
        
        # 分析错误
        errors = []
        gt_notes = ground_truth_text.split()
        for i in range(min(len(gt_notes), len(recognized_notes))):
            if gt_notes[i] != recognized_notes[i]:
                errors.append(f"位置{i}: 识别为'{recognized_notes[i]}'，应为'{gt_notes[i]}'")
        
        if len(recognized_notes) > len(gt_notes):
            errors.append(f"识别多余{len(recognized_notes) - len(gt_notes)}个音符")
        elif len(gt_notes) > len(recognized_notes):
            errors.append(f"识别缺少{len(gt_notes) - len(recognized_notes)}个音符")
        
        return {
            'success': True,
            'accuracy': accuracy,
            'correct': correct,
            'gt_length': gt_len,
            'rec_length': rec_len,
            'recognized': recognized_text,
            'errors': errors[:5]
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'accuracy': 0.0
        }


def run_accuracy_test():
    """运行准确率测试"""
    print("="*70)
    print("简谱识别准确率测试")
    print("="*70)
    
    test_data_dir = r"D:\Download\毕业设计数据"
    results = []
    
    total_accuracy = 0
    count = 0
    
    for filename, gt in GROUND_TRUTH.items():
        # 查找图片
        image_path = os.path.join(test_data_dir, f"{filename}.png")
        
        if not os.path.exists(image_path):
            # 尝试其他扩展名
            for ext in ['.jpg', '.jpeg', '.png']:
                alt_path = os.path.join(test_data_dir, f"{filename}{ext}")
                if os.path.exists(alt_path):
                    image_path = alt_path
                    break
        
        if not os.path.exists(image_path):
            print(f"\n警告: 找不到测试图片 {filename}")
            continue
        
        result = test_image(image_path, gt)
        results.append({
            'name': gt['name'],
            'file': filename,
            **result
        })
        
        if result['success']:
            total_accuracy += result['accuracy']
            count += 1
            
            print(f"\n准确率: {result['accuracy']*100:.1f}%")
            print(f"正确: {result['correct']}/{result['gt_length']} (GT), {result['correct']}/{result['rec_length']} (识别)")
            
            if result.get('errors'):
                print(f"\n主要错误:")
                for err in result['errors']:
                    print(f"  - {err}")
        else:
            print(f"\n测试失败: {result.get('error', '未知错误')}")
    
    # 总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    if count > 0:
        avg_accuracy = total_accuracy / count
        print(f"\n平均准确率: {avg_accuracy*100:.1f}%")
        
        print("\n各歌曲准确率:")
        for r in results:
            if r['success']:
                status = "[OK]" if r['accuracy'] >= 0.8 else "[FAIL]"
                print(f"  {status} {r['name']}: {r['accuracy']*100:.1f}%")
            else:
                print(f"  [FAIL] {r['name']}: 失败")
    else:
        print("\n没有成功完成任何测试")


if __name__ == '__main__':
    run_accuracy_test()
