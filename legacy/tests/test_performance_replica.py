#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
复刻性能测试 - 使用实际曲谱数据
统计处理时间和音符可演奏性
"""

import sys
import os
import time

# 添加 backend 目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(script_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from music_theory import MusicTheoryConverter


class PerformanceTest:
    """性能测试类"""
    
    def __init__(self):
        self.results = []
        self.total_notes = 0
        self.playable_notes = 0
        self.out_of_range_notes = 0
    
    def add(self, processing_time, playable, out_of_range):
        """添加测试结果"""
        self.results.append(processing_time)
        self.total_notes += playable + out_of_range
        self.playable_notes += playable
        self.out_of_range_notes += out_of_range
    
    def get_stats(self):
        """获取统计数据"""
        if not self.results:
            return {}
        
        sorted_times = sorted(self.results)
        n = len(sorted_times)
        
        return {
            'count': n,
            'min': min(self.results),
            'max': max(self.results),
            'avg': sum(self.results) / n,
            'total_notes': self.total_notes,
            'playable_notes': self.playable_notes,
            'out_of_range_notes': self.out_of_range_notes,
        }


# 测试数据集 - 使用用户提供的实际曲谱
TEST_CASES = [
    # ========== 基础测试 (13个) ==========
    # 基础C调-欢乐颂
    ('3 3 4 5 | 5 4 3 2 | 1 1 2 3 | 3 - 2 - ||', 'C', 'C', '基础C调-欢乐颂'),
    # 低音练习
    ('5 6 7 1. | 2. 3. 4. 5. ||', 'C', 'C', '低音练习'),
    # 高音测试
    ('5 6 7 1. 2. 3. 4. 5. |', 'C', 'C', '高音测试'),
    # 复杂混合音域
    ('1 2 3 4 5 6 7 1. 2. 3. 4. 5. 6. ||', 'C', 'C', '复杂混合音域'),
    # 全音域跨越测试
    ('1 3 5 7 | 1. 2. 3. 4. 5. 6. 7. | 1. ||', 'C', 'C', '全音域跨越测试'),
    # 小星星
    ('1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 - ||', 'C', 'C', '小星星'),
    # 新年歌
    ('5 5 6 5 | 1 1 1 - | 5 5 6 5 | 2 2 2 - | 3 3 2 3 | 4 4 3 - ||', 'C', 'C', '新年歌'),
    # 两只老虎
    ('1 2 3 1 | 1 2 3 1 | 3 4 5 - | 3 4 5 - | 5 6 5 4 3 2 | 1 5 1 - ||', 'C', 'C', '两只老虎'),
    # 世上只有妈妈好
    ('3 2 1 6 | 5 6 1 - | 1 2 3 2 | 1 2 5 - ||', 'C', 'C', '世上只有妈妈好'),
    # 生日歌
    ('5 5 6 5 1 7 | 5 5 6 5 2 1 ||', 'G', 'C', '生日歌'),
    # 茉莉花
    ('3 3 5 5 | 6 5 6 5 | 5 3 2 2 | 3 5 5 - ||', 'C', 'C', '茉莉花'),
    # 送别
    ('1 5 3 2 | 1 3 5 - | 5 6 4 3 | 2 3 1 - ||', 'C', 'C', '送别'),
    # 喀秋莎
    ('5 3 5 6 | 5 3 5 6 | 7 6 5 6 | 5 3 1 - ||', 'C', 'C', '喀秋莎'),
    
    # ========== 特殊符号测试 (6个) ==========
    # 长音测试
    ('1 - - - | 2 - - - | 3 - - - ||', 'C', 'C', '长音测试'),
    # 附点音符
    ('1. 2. 3. 4. | 5. 6. 7. 1. ||', 'C', 'C', '附点音符'),
    # 休止符测试
    ('1 0 2 0 | 3 0 4 0 | 5 0 6 0 ||', 'C', 'C', '休止符测试'),
    # 复杂延音线
    ('1 2 3 - | 4 5 6 - | 7 1. - - ||', 'C', 'C', '复杂延音线'),
    # 连续附点音符
    ('1. 2. 3. 4. 5. 6. | 7. 1. 2. 3. ||', 'C', 'C', '连续附点音符'),
    # 混合特殊符号
    ('1. 0 2. 0 | 3 - 4 - | 5. 6. 7. 1. ||', 'C', 'C', '混合特殊符号'),
    
    # ========== 节奏音程测试 (4个) ==========
    # 音程跳转测试
    ('1 5 | 5 1 | 2 5 | 5 2 | 3 5 | 5 3 ||', 'C', 'C', '音程跳转测试'),
    # 三和弦分解
    ('1 3 5 3 | 2 4 6 4 | 3 5 7 5 | 1. 3. 5. ||', 'C', 'C', '三和弦分解'),
    # 快速音阶
    ('1 2 3 4 5 6 7 1. 2. 3. 4. 5. 6. 7. 1.. ||', 'C', 'C', '快速音阶'),
    # 跨小节连音
    ('1 2 3 4 | 5 6 7 1 | 2 3 4 5 | 6 7 1. - ||', 'C', 'C', '跨小节连音'),
    
    # ========== 复杂节奏测试 (1个) ==========
    # 复杂节奏组合
    ('1. 2. 3 4 5. 6 7 1. 2. 3. 4. 5. 6. 7. 1.. ||', 'C', 'C', '复杂节奏组合'),
    
    # ========== Low C调测试 (3个) ==========
    # Low C调-低音区
    ('5 6 7 1 | 2 3 4 5 | 1 2 3 4 | 5 6 7 1. ||', 'C', 'LowC', 'Low C调-低音区'),
    # Low C调-混合音域
    ('1 3 5 7 | 1. 2. 3. 4. 5. 6. 7. | 1. ||', 'C', 'LowC', 'Low C调-混合音域'),
    # Low C调-完整音域
    ('5 5 3 3 | 1 1 - - | 5 5 3 3 | 1 1 - - ||', 'C', 'LowC', 'Low C调-完整音域'),
    
    # ========== 大规模曲目测试 (3个) ==========
    # 大规模曲目-卡农
    ('1 3 5 5 | 4 2 3 - | 5 5 4 2 | 3 1 - - | 1 3 5 5 | 4 2 3 - | 5 4 3 2 | 1 5 1 - ||', 'C', 'C', '卡农'),
    # 大规模曲目-天空之城
    ('6 7 1 3 | 5 3 2 1 | 7 1 2 3 | 4 3 2 1 | 6 7 1 3 | 5 3 2 1 | 7 1 2 3 | 4 3 2 1 ||', 'G', 'C', '天空之城'),
    # 大规模曲目-致爱丽丝
    ('5 3 5 6 | 5 3 5 6 | 7 6 5 4 | 3 2 1 2 | 4 3 2 3 | 4 3 2 3 | 5 6 5 4 | 3 2 1 - ||', 'C', 'C', '致爱丽丝'),
]


def is_note_playable(bd_notation):
    """
    判断音符是否可直接演奏
    标准C调口琴音域: 
    - 低音: 1B, 2B, 3B, 4B, 5B, 6B, 7B
    - 中音: 1D, 2D, 3D, 4D, 5D, 6D, 7D
    - 高音: 1T, 2T, 3T, 4T, 5T, 6T, 7T
    
    超出标准音域需要压音或其他口琴
    """
    if not bd_notation:
        return True
    
    # 标准音域定义
    playable_ranges = {
        # 低音区
        '1B', '2B', '3B', '4B', '5B', '6B', '7B',
        # 中音区
        '1D', '2D', '3D', '4D', '5D', '6D', '7D',
        # 高音区
        '1T', '2T', '3T', '4T', '5T', '6T', '7T',
        # 低音区半音变化
        '1B.', '2B.', '3B.', '4B.', '5B.', '6B.', '7B.',
        '1B#', '2B#', '3B#', '4B#', '5B#', '6B#', '7B#',
        '2Bb', '3Bb', '4Bb', '5Bb', '6Bb', '7Bb',
        # 中音区半音变化
        '1D.', '2D.', '3D.', '4D.', '5D.', '6D.', '7D.',
        '1D#', '2D#', '3D#', '4D#', '5D#', '6D#', '7D#',
        '1Db', '2Db', '3Db', '4Db', '5Db', '6Db', '7Db',
        # 高音区半音变化
        '1T.', '2T.', '3T.', '4T.', '5T.', '6T.', '7T.',
        '1T#', '2T#', '3T#', '4T#', '5T#', '6T#', '7T#',
        '1Tb', '2Tb', '3Tb', '4Tb', '5Tb', '6Tb', '7Tb',
    }
    
    clean = bd_notation.strip()
    return clean in playable_ranges


def run_test():
    """运行性能测试"""
    print("=" * 75)
    print("           复刻性能测试 - 使用实际曲谱数据")
    print("=" * 75)
    print()
    
    test = PerformanceTest()
    
    # 按类别分组统计
    categories = {
        '基础测试': [],
        '特殊符号测试': [],
        '节奏音程测试': [],
        '复杂节奏测试': [],
        'Low C调测试': [],
        '大规模曲目测试': [],
    }
    
    print("测试进行中...")
    print("-" * 75)
    
    for i, (jianpu, key, harmonica_type, name) in enumerate(TEST_CASES):
        start_time = time.time()
        
        # 执行转换
        theory = MusicTheoryConverter(key, harmonica_type)
        notes = theory.parse_jianpu(jianpu)
        converted = theory.convert_to_c_major(notes)
        
        # 统计音符
        playable = 0
        out_of_range = 0
        
        for note in converted:
            bd_notation = note.get('bd_notation', '')
            if bd_notation:
                if is_note_playable(bd_notation):
                    playable += 1
                else:
                    out_of_range += 1
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 记录结果
        test.add(processing_time, playable, out_of_range)
        
        # 分配到类别
        if 'Low C' in name:
            categories['Low C调测试'].append((name, processing_time, playable, out_of_range))
        elif '卡农' in name or '天空之城' in name or '致爱丽丝' in name:
            categories['大规模曲目测试'].append((name, processing_time, playable, out_of_range))
        elif '节奏组合' in name or '复杂节奏' in name:
            categories['复杂节奏测试'].append((name, processing_time, playable, out_of_range))
        elif any(x in name for x in ['音程', '和弦', '音阶', '连音']):
            categories['节奏音程测试'].append((name, processing_time, playable, out_of_range))
        elif any(x in name for x in ['长音', '附点', '休止', '延音', '特殊']):
            categories['特殊符号测试'].append((name, processing_time, playable, out_of_range))
        else:
            categories['基础测试'].append((name, processing_time, playable, out_of_range))
        
        # 打印进度
        status = "[PASS]" if out_of_range == 0 else "[PART]"
        print(f"  {status} [{i+1:02d}/30] {name:12s} {key:3s}调 ({harmonica_type:4s}): "
              f"{processing_time:.3f}s | Playable:{playable:3d} OutRange:{out_of_range:3d}")
    
    print("-" * 75)
    
    # 获取统计结果
    stats = test.get_stats()
    
    # 打印结果
    print("\n" + "=" * 75)
    print("                        【测试结果汇总】")
    print("=" * 75)
    
    print("\n【处理时间统计】")
    print(f"  - 测试案例数:   {stats['count']} 个")
    print(f"  - 平均处理时间: {stats['avg']:.3f} 秒")
    print(f"  - 最快案例:    {stats['min']:.3f} 秒")
    print(f"  - 最慢案例:    {stats['max']:.3f} 秒")
    
    print("\n【音符可演奏性统计】")
    print(f"  - 总音符数:          {stats['total_notes']} 个")
    print(f"  - 可直接演奏:        {stats['playable_notes']} 个 ({stats['playable_notes']/stats['total_notes']*100:.1f}%)")
    print(f"  - 超出音域:          {stats['out_of_range_notes']} 个 ({stats['out_of_range_notes']/stats['total_notes']*100:.1f}%)")
    
    # 分类统计
    print("\n【分类测试结果】")
    print("-" * 75)
    print(f"{'类别':<15} {'数量':>5} {'可演奏':>8} {'超出音域':>8} {'可演奏率':>10}")
    print("-" * 75)
    
    for cat, items in categories.items():
        if items:
            total = sum(p+o for _,_,p,o in items)
            playable = sum(p for _,_,p,o in items)
            out = sum(o for _,_,p,o in items)
            rate = playable/total*100 if total > 0 else 0
            print(f"{cat:<15} {len(items):>5} {playable:>8} {out:>8} {rate:>9.1f}%")
    
    print("-" * 75)
    total_all = sum(len(v) for v in categories.values())
    print(f"{'总计':<15} {total_all:>5}")
    
    playable_pct = stats['playable_notes'] / stats['total_notes'] * 100
    
    print("\n" + "=" * 75)
    print("【对比用户提供的统计数据】")
    print("-" * 75)
    print(f"  用户提供的平均处理时间: 0.366秒")
    print(f"  用户提供的最快案例:    0.233秒")
    print(f"  用户提供的最慢案例:    0.730秒")
    print(f"  用户提供的总音符数:     819个")
    print(f"  用户提供的可演奏率:    72.2% (591/819)")
    print("-" * 75)
    
    print("\n【结论】")
    if stats['avg'] <= 0.01:
        print("  [OK] 纯转换处理速度极快 (<1ms)，满足实时应用需求")
    if playable_pct >= 70:
        print(f"  [OK] {playable_pct:.1f}% 音符可直接演奏，兼容性好")
    
    print("\n" + "=" * 75)
    print("                        测试完成!")
    print("=" * 75)
    
    return stats


if __name__ == '__main__':
    run_test()
