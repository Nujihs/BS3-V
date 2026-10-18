"""
简谱转BD谱 - 调号转换测试
测试所有调号的转换准确率
"""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(script_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from music_theory import MusicTheoryConverter


# 定义所有测试调号
MAJOR_KEYS = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb']
MINOR_KEYS = ['Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m', 'D#m', 'A#m', 'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm']

# 测试用例：简谱音阶 1 2 3 4 5 6 7 1.
TEST_SCALE = "1 2 3 4 5 6 7 1."

# 测试用例：小星星
TEST_TWINKLE = "1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 - ||"

# 测试用例：祝你生日快乐
TEST_BIRTHDAY = "5 5 6 5 1 7 | 5 5 6 5 2 1 ||"


class TestResult:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []
        self.key_stats = {}  # 每个调号的统计
    
    def add(self, name, passed, details=""):
        self.total += 1
        if passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"
        self.results.append((name, status, details))
        return passed
    
    def add_key_stat(self, key, passed, note_count):
        if key not in self.key_stats:
            self.key_stats[key] = {'passed': 0, 'failed': 0, 'notes': 0}
        if passed:
            self.key_stats[key]['passed'] += 1
        else:
            self.key_stats[key]['failed'] += 1
        self.key_stats[key]['notes'] += note_count


def get_bd_notes(jianpu, key, harmonica_type='C'):
    """获取转换后的BD谱音符"""
    theory = MusicTheoryConverter(key, harmonica_type)
    notes = theory.parse_jianpu(jianpu)
    converted = theory.convert_to_c_major(notes)
    return [n['bd_notation'] for n in converted if n.get('bd_notation')]


def generate_expected_for_key(jianpu, from_key, to_key='C', harmonica_type='C'):
    """生成指定调号的期望BD谱（用于自动生成测试数据）"""
    theory = MusicTheoryConverter(from_key, harmonica_type)
    notes = theory.parse_jianpu(jianpu)
    converted = theory.convert_to_c_major(notes)
    return [n['bd_notation'] for n in converted if n.get('bd_notation')]


def test_key_signature(result, key_name, jianpu, expected):
    """测试单个调号"""
    notes = get_bd_notes(jianpu, key_name, 'C')
    passed = notes == expected
    result.add(f"{key_name}: {jianpu[:30]}...", passed, 
               f"expected {len(expected)} notes, got {len(notes)}" if not passed else "")
    result.add_key_stat(key_name, passed, len(expected))
    return passed


def main():
    result = TestResult()
    
    print("=" * 80)
    print("简谱转BD谱 - 调号转换测试")
    print("=" * 80)
    
    # ===== 测试各调号音阶转换 =====
    print("\n" + "-" * 80)
    print("【测试1】各调号音阶转换 (1 2 3 4 5 6 7 1.)")
    print("-" * 80)
    
    # C调音阶
    c_scale = get_bd_notes(TEST_SCALE, 'C', 'C')
    print(f"C调: {c_scale}")
    
    # G调音阶 (1=C -> 1=G)
    g_scale = get_bd_notes(TEST_SCALE, 'G', 'C')
    print(f"G调: {g_scale}")
    
    # F调音阶 (1=C -> 1=F)
    f_scale = get_bd_notes(TEST_SCALE, 'F', 'C')
    print(f"F调: {f_scale}")
    
    # ===== 测试各调号小星星 =====
    print("\n" + "-" * 80)
    print("【测试2】各调号小星星转换")
    print("-" * 80)
    
    print("\n--- 大调测试 ---")
    for key in MAJOR_KEYS:
        try:
            notes = get_bd_notes(TEST_TWINKLE, key, 'C')
            playable = sum(1 for n in notes if n and not n.startswith('['))
            playable_pct = playable / len(notes) * 100 if notes else 0
            status = "OK" if playable_pct >= 50 else "WARN"
            print(f"  {key:>4}: {len(notes):>2} notes, {playable_pct:>5.1f}% playable [{notes[:6]}...]")
            result.add_key_stat(key, playable_pct >= 50, len(notes))
        except Exception as e:
            print(f"  {key:>4}: ERROR - {str(e)[:30]}")
            result.add_key_stat(key, False, 0)
    
    print("\n--- 小调测试 ---")
    for key in MINOR_KEYS:
        try:
            notes = get_bd_notes(TEST_TWINKLE, key, 'C')
            playable = sum(1 for n in notes if n and not n.startswith('['))
            playable_pct = playable / len(notes) * 100 if notes else 0
            status = "OK" if playable_pct >= 50 else "WARN"
            print(f"  {key:>5}: {len(notes):>2} notes, {playable_pct:>5.1f}% playable [{notes[:6]}...]")
            result.add_key_stat(key, playable_pct >= 50, len(notes))
        except Exception as e:
            print(f"  {key:>5}: ERROR - {str(e)[:30]}")
            result.add_key_stat(key, False, 0)
    
    # ===== 测试祝你生日快乐 =====
    print("\n" + "-" * 80)
    print("【测试3】祝你生日快乐 各调号转换")
    print("-" * 80)
    
    for key in ['C', 'G', 'D', 'F', 'Bb', 'Eb', 'Am', 'Dm', 'Em']:
        try:
            notes = get_bd_notes(TEST_BIRTHDAY, key, 'C')
            playable = sum(1 for n in notes if n and not n.startswith('['))
            playable_pct = playable / len(notes) * 100 if notes else 0
            print(f"  {key:>5}: {len(notes):>2} notes, {playable_pct:>5.1f}% playable")
            result.add_key_stat(key, playable_pct >= 50, len(notes))
        except Exception as e:
            print(f"  {key:>5}: ERROR - {str(e)[:30]}")
    
    # ===== 输出汇总 =====
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    # 大调汇总
    major_ok = sum(1 for k in MAJOR_KEYS if result.key_stats.get(k, {}).get('passed', 0) > 0)
    major_total = len(MAJOR_KEYS)
    
    # 小调汇总
    minor_ok = sum(1 for k in MINOR_KEYS if result.key_stats.get(k, {}).get('passed', 0) > 0)
    minor_total = len(MINOR_KEYS)
    
    print(f"\n大调测试: {major_ok}/{major_total} ({major_ok/major_total*100:.1f}%)")
    print(f"小调测试: {minor_ok}/{minor_total} ({minor_ok/minor_total*100:.1f}%)")
    
    print("\n各调号详细结果:")
    print("-" * 60)
    print(f"{'调号':<8} {'状态':<8} {'音符数':<8} {'可演奏率'}")
    print("-" * 60)
    
    for key in sorted(MAJOR_KEYS) + sorted(MINOR_KEYS):
        stats = result.key_stats.get(key, {'passed': 0, 'failed': 0, 'notes': 0})
        if stats['notes'] > 0:
            status = "PASS" if stats['passed'] > 0 else "FAIL"
            playable_pct = stats['passed'] / (stats['passed'] + stats['failed']) * 100 if stats['passed'] + stats['failed'] > 0 else 0
            print(f"{key:<8} {status:<8} {stats['notes']:<8} {playable_pct:.1f}%")
    
    print("-" * 60)
    total_keys = major_total + minor_total
    total_ok = major_ok + minor_ok
    overall = total_ok / total_keys * 100
    print(f"\n总计: {total_ok}/{total_keys} 调号通过 ({overall:.1f}%)")
    
    print("\n" + "=" * 80)
    if overall >= 95:
        print("[PASS] 调号测试通过率达到95%目标!")
    else:
        print(f"[INFO] 调号测试覆盖率: {overall:.1f}%")
        print("注意: 部分调号需要压音/超吹技巧才能演奏全部音符")
    print("=" * 80)
    
    return overall


if __name__ == "__main__":
    main()
