"""
简谱转BD谱完整测试数据集
基于用户构建的30个测试案例
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


class TestResult:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.results = []
    
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


def run_test(result, name, jianpu, key, expected, harmonica_type='C'):
    """运行单个测试"""
    try:
        theory = MusicTheoryConverter(key, harmonica_type)
        notes = theory.parse_jianpu(jianpu)
        converted = theory.convert_to_c_major(notes)
        pure_notes = [n['bd_notation'] for n in converted if n.get('bd_notation')]
        
        if pure_notes == expected:
            result.add(name, True)
            return True
        else:
            diff = []
            for i, (e, a) in enumerate(zip(expected, pure_notes)):
                if e != a:
                    diff.append(f"pos{i}: expect {e}, got {a}")
            if len(expected) != len(pure_notes):
                diff.append(f"length: expect {len(expected)}, got {len(pure_notes)}")
            result.add(name, False, "; ".join(diff[:5]))
            return False
    except Exception as ex:
        result.add(name, False, str(ex)[:100])
        return False


def main():
    result = TestResult()
    
    print("=" * 70)
    print("Jianpu to BD Conversion Test - 30 Test Cases")
    print("=" * 70)
    
    # ========== 基础测试 (13个) ==========
    print("\n[Basic Tests]")
    
    run_test(result, "Twinkle Star", "1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 - ||",
             "C", ['1B', '1B', '3B', '3B', '3D', '3D', '3B', '2D', '2D', '2B', '2B', '1D', '1D', '1B'])
    
    run_test(result, "Happy Birthday", "5 5 6 5 1 7 | 5 5 6 5 2 1 ||",
             "G", ['4D', '4D', '5B', '4D', '3B', '4D', '4D', '5B', '4D', '3D', '3B'])
    
    run_test(result, "Two Tigers", "1 2 3 1 | 1 2 3 1 | 3 4 5 - | 3 4 5 - | 5 6 5 4 3 2 | 1 5 1 - ||",
             "C", ['1B', '1D', '2B', '1B', '1B', '1D', '2B', '1B', '2B', '2D', '3B', '2B', '2D', '3B', '3B', '3D', '3B', '2D', '2B', '1D', '1B', '3B', '1B'])
    
    run_test(result, "Mother Love", "3 2 1 6 | 5 6 1 - | 1 2 3 2 | 1 2 5 - ||",
             "C", ['2B', '1D', '1B', '3D', '3B', '3D', '1B', '1B', '1D', '2B', '1D', '1B', '1D', '3B'])
    
    run_test(result, "Jasmine", "3 3 5 5 | 6 5 6 5 | 5 3 2 2 | 3 5 5 - ||",
             "C", ['2B', '2B', '3B', '3B', '3D', '3B', '3D', '3B', '3B', '2B', '1D', '1D', '2B', '3B', '3B'])
    
    run_test(result, "Farewell", "1 5 3 2 | 1 3 5 - | 5 6 4 3 | 2 3 1 - ||",
             "C", ['1B', '3B', '2B', '1D', '1B', '2B', '3B', '3B', '3D', '2D', '2B', '1D', '2B', '1B'])
    
    run_test(result, "Katyusha", "5 3 5 6 | 5 3 5 6 | 7 6 5 6 | 5 3 1 - ||",
             "C", ['3B', '2B', '3B', '3D', '3B', '2B', '3B', '3D', '3D', '3D', '3B', '3D', '3B', '2B', '1B'])
    
    run_test(result, "Ode to Joy", "3 3 4 5 | 5 4 3 2 | 1 1 2 3 | 3 - 2 - ||",
             "C", ['2B', '2B', '2D', '3B', '3B', '2D', '2B', '1D', '1B', '1B', '1D', '2B', '2B', '1D'])
    
    run_test(result, "Bass Practice", "5 6 7 1. | 2. 3. 4. 5. ||",
             "C", ['3B', '3D', '3D', '1D', '1B', '2B', '2D', '3B'])
    
    run_test(result, "High Pitch Test", "5 6 7 1. 2. 3. 4. 5. |",
             "C", ['3B', '3D', '3D', '1D', '1B', '2B', '2D', '3B'])
    
    run_test(result, "Full Range Test", "1 3 5 7 | 1. 2. 3. 4. 5. 6. 7. | 1. ||",
             "C", ['1B', '2B', '3B', '3D', '1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    run_test(result, "Complex Mixed Range", "1 2 3 4 5 6 7 1. 2. 3. 4. 5. 6. ||",
             "C", ['1B', '1D', '2B', '2D', '3B', '3D', '3D', '1D', '1B', '2B', '2D', '3B', '3D'])
    
    run_test(result, "New Year Song", "5 5 6 5 | 1 1 1 - | 5 5 6 5 | 2 2 2 - | 3 3 2 3 | 4 4 3 - ||",
             "C", ['3B', '3B', '3D', '3B', '1B', '1B', '1B', '3B', '3B', '3D', '3B', '1D', '1D', '1D', '2B', '2B', '1D', '2B', '2D', '2D', '2B'])
    
    # ========== 特殊符号测试 (6个) ==========
    print("\n[Special Symbols Tests]")
    
    run_test(result, "Long Note Test", "1 - - - | 2 - - - | 3 - - - ||",
             "C", ['1B', '1D', '2B'])
    
    run_test(result, "Dotted Notes Test", "1. 2. 3. 4. | 5. 6. 7. 1. ||",
             "C", ['1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    run_test(result, "Rest Test", "1 0 2 0 | 3 0 4 0 | 5 0 6 0 ||",
             "C", ['1B', '1D', '2B', '2D', '3B', '3D'])
    
    run_test(result, "Complex Tie Test", "1 2 3 - | 4 5 6 - | 7 1. - - ||",
             "C", ['1B', '1D', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    run_test(result, "Continuous Dots Test", "1. 2. 3. 4. 5. 6. | 7. 1. 2. 3. ||",
             "C", ['1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D', '1B', '2B'])
    
    run_test(result, "Mixed Symbols Test", "1. 0 2. 0 | 3 - 4 - | 5. 6. 7. 1. ||",
             "C", ['1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    # ========== 节奏音程测试 (4个) ==========
    print("\n[Rhythm Interval Tests]")
    
    run_test(result, "Interval Jump Test", "1 5 | 5 1 | 2 5 | 5 2 | 3 5 | 5 3 ||",
             "C", ['1B', '3B', '3B', '1B', '1D', '3B', '3B', '1D', '2B', '3B', '3B', '2B'])
    
    run_test(result, "Triad Test", "1 3 5 3 | 2 4 6 4 | 3 5 7 5 | 1. 3. 5. ||",
             "C", ['1B', '2B', '3B', '2B', '1D', '2D', '3D', '2D', '2B', '3B', '3D', '3B', '1D', '2B', '3B'])
    
    run_test(result, "Fast Scale Test", "1 2 3 4 5 6 7 1. 2. 3. 4. 5. 6. 7. 1.. ||",
             "C", ['1B', '1D', '2B', '2D', '3B', '3D', '3D', '1D', '1B', '2B', '2D', '3B', '3D', '3D'])
    
    run_test(result, "Cross Measure Test", "1 2 3 4 | 5 6 7 1 | 2 3 4 5 | 6 7 1. - ||",
             "C", ['1B', '1D', '2B', '2D', '3B', '3D', '3D', '1B', '1D', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    # ========== 复杂节奏测试 (1个) ==========
    print("\n[Complex Rhythm Test]")
    
    run_test(result, "Complex Rhythm", "1. 2. 3 4 5. 6 7 1. 2. 3. 4. 5. 6. 7. 1.. ||",
             "C", ['1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D', '1B', '2B', '2D', '3B', '3D', '3D'])
    
    # ========== Low C调测试 (3个) ==========
    print("\n[Low C Harmonica Tests]")
    
    run_test(result, "Low C-Bass Range", "5 6 7 1 | 2 3 4 5 | 1 2 3 4 | 5 6 7 1. ||",
             "C", ['3B', '3D', '3D', '1B', '1D', '2B', '2D', '3B', '1B', '1D', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    run_test(result, "Low C-Mixed Range", "1 3 5 7 | 1. 2. 3. 4. 5. 6. 7. | 1. ||",
             "C", ['1B', '2B', '3B', '3D', '1D', '1B', '2B', '2D', '3B', '3D', '3D', '1D'])
    
    run_test(result, "Low C-Full Range", "5 5 3 3 | 1 1 - - | 5 5 3 3 | 1 1 - - ||",
             "C", ['3B', '3B', '2B', '2B', '1B', '1B', '3B', '3B', '2B', '2B', '1B', '1B'])
    
    # ========== 大规模曲目测试 (3个) ==========
    print("\n[Large Scale Pieces Tests]")
    
    run_test(result, "Canon", "1 3 5 5 | 4 2 3 - | 5 5 4 2 | 3 1 - - | 1 3 5 5 | 4 2 3 - | 5 4 3 2 | 1 5 1 - ||",
             "C", ['1B', '2B', '3B', '3B', '2D', '1D', '2B', '3B', '3B', '2D', '1D', '2B', '1B', '1B', '2B', '3B', '3B', '2D', '1D', '2B', '3B', '2D', '2B', '1D', '1B', '3B', '1B'])
    
    run_test(result, "Castle in Sky", "6 7 1 3 | 5 3 2 1 | 7 1 2 3 | 4 3 2 1 | 6 7 1 3 | 5 3 2 1 | 7 1 2 3 | 4 3 2 1 ||",
             "G", ['5B', '3B', '3D', '4D', '3D', '3D', '3B', '3B', '3D', '3D', '4B', '3D', '3D', '3B', '5B', '3B', '3D', '4D', '3D', '3D', '3B', '3B', '3D', '3D', '4B', '3D', '3D', '3B'])
    
    run_test(result, "Fur Elise", "5 3 5 6 | 5 3 5 6 | 7 6 5 4 | 3 2 1 2 | 4 3 2 3 | 4 3 2 3 | 5 6 5 4 | 3 2 1 - ||",
             "C", ['3B', '2B', '3B', '3D', '3B', '2B', '3B', '3D', '3D', '3D', '3B', '2D', '2B', '1D', '1B', '1D', '2D', '2B', '1D', '2B', '2D', '2B', '1D', '2B', '3B', '3D', '3B', '2D', '2B', '1D', '1B'])
    
    # ========== 输出结果 ==========
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    print(f"\nTotal tests: {result.total}")
    print(f"Passed: {result.passed}")
    print(f"Failed: {result.failed}")
    print(f"Accuracy: {result.passed/result.total*100:.1f}%")
    
    if result.failed > 0:
        print("\nFailed tests:")
        for name, status, details in result.results:
            if status == "FAIL":
                print(f"  - {name}: {details}")
    
    print("\n" + "=" * 70)
    if result.passed / result.total >= 0.95:
        print("[PASS] Test accuracy reached 95% target!")
    else:
        print("[FAIL] Test accuracy below 95% target")
    print("=" * 70)


if __name__ == '__main__':
    main()
