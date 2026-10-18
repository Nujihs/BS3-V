"""
音乐理论模块：处理调号转换、音高计算等
"""

from typing import List, Optional
from config import KEY_SIGNATURES, C_HARMONICA_BD, LOW_C_HARMONICA_BD


# 简谱度数（1..7）相对于该调主音的半音数
JIANPU_DEGREE_SEMITONES = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}


class MusicTheoryConverter:
    """音乐理论转换器"""
    
    CHROMATIC_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def __init__(self, source_key: str = 'C', harmonica_type: str = 'C'):
        self.source_key = source_key
        self.key_offset = KEY_SIGNATURES.get(source_key, 0)
        self.harmonica_type = harmonica_type
        # 根据口琴类型选择BD映射
        if harmonica_type == 'LowC':
            self.bd_map = LOW_C_HARMONICA_BD
        else:
            self.bd_map = C_HARMONICA_BD
    
    def parse_jianpu(self, jianpu_str: str) -> List[dict]:
        """解析简谱字符串"""
        notes = []
        import re
        # 使用正则表达式匹配简谱符号：
        # 高音: ..5 .6 (点前数字)，低音: 5. 6.. (数字后点)，中音: 1-7
        # 附点: 3* (1.5 倍时值)
        # | 小节线，- 延音线
        pattern = re.compile(r'\.+[0-7][\.*]*|[0-7][\.*]+|[0-7]|\||-')
        tokens = pattern.findall(jianpu_str)
        
        for token in tokens:
            if not token:
                continue
            
            if token == '|':
                notes.append({
                    'is_measure_line': True,
                    'original': token,
                    'octave': 4,
                    'duration_multiplier': 1.0,
                    'note_name': 'BAR',
                    'degree': 0,
                    'is_rest': False,
                    'is_tie': False,
                    'is_dotted': False,
                    'jianpu': '|'
                })
                continue
            
            if token == '-':
                notes.append({
                    'jianpu': '-',
                    'is_tie': True,
                    'is_rest': False,
                    'original': token,
                    'octave': 4,
                    'duration_multiplier': 1.0,
                    'note_name': 'TIE',
                    'degree': 0,
                    'is_dotted': False
                })
                continue
            
            note_info = self._parse_single_note(token)
            if note_info:
                notes.append(note_info)
        
        return notes
    
    def _parse_single_note(self, token: str) -> Optional[dict]:
        """解析单个简谱音符"""
        token = token.strip()
        if not token:
            return None
        
        if token == '0':
            return {'jianpu': '0', 'degree': 0, 'octave': 0, 'is_rest': True, 
                   'original': token, 'is_dotted': False, 'duration_multiplier': 1.0}
        
        is_dotted = '*' in token
        if is_dotted:
            token = token.replace('*', '')
        
        octave_shift = 0
        leading_dots = 0
        trailing_dots = 0
        temp = token
        
        while temp.startswith('.'):
            leading_dots += 1
            temp = temp[1:]
        
        while temp.endswith('.'):
            trailing_dots += 1
            temp = temp[:-1]
        
        degree_str = temp
        
        if leading_dots > 0:
            octave_shift = leading_dots
        elif trailing_dots > 0:
            octave_shift = -trailing_dots
        
        if degree_str and degree_str[0] in '1234567':
            degree = int(degree_str[0])
        else:
            return None
        
        duration_multiplier = 1.5 if is_dotted else 1.0
        
        return {
            'jianpu': token,
            'degree': degree,
            'octave': octave_shift,
            'is_rest': False,
            'original': token,
            'is_dotted': is_dotted,
            'duration_multiplier': duration_multiplier
        }
    
    def convert_to_c_major(self, notes: List[dict]) -> List[dict]:
        """将源调简谱音符转换为C调实际音高（concert pitch）"""
        converted = []

        # 源调主音相对于C的半音数（如G调=7, F调=5, Bb调=10）
        root_semitone = self.key_offset
        base_octave = 4

        for note in notes:
            if note.get('is_measure_line'):
                converted.append({
                    **note,
                    'octave': 4,
                    'duration_multiplier': note.get('duration_multiplier', 1.0),
                    'note_name': 'BAR'
                })
                continue

            if note.get('is_tie'):
                converted.append({
                    **note,
                    'note_name': 'TIE',
                    'midi_note': None,
                    'octave': 4,
                    'duration_multiplier': note.get('duration_multiplier', 1.0)
                })
                continue

            if note['is_rest']:
                converted.append({
                    **note,
                    'note_name': 'REST',
                    'midi_note': None,
                    'octave': 4,
                    'duration_multiplier': note.get('duration_multiplier', 1.0)
                })
                continue

            degree = note['degree']
            user_octave_shift = note.get('octave', 0) or 0

            # 简谱度数 → 相对主音半音
            rel_semitone = JIANPU_DEGREE_SEMITONES.get(degree, 0)

            # 加上主音半音得到相对C的绝对半音；超过12时进位八度
            absolute_semitone = root_semitone + rel_semitone
            note_chroma = absolute_semitone % 12
            octave_carry = absolute_semitone // 12

            octave = base_octave + octave_carry + user_octave_shift
            note_name = self.CHROMATIC_SCALE[note_chroma]
            full_note = f"{note_name}{octave}"
            bd_notation = self.bd_map.get(full_note, None)

            converted.append({
                **note,
                'note_name': full_note,
                'actual_semitone': note_chroma,
                'octave': user_octave_shift,
                'octave_actual': octave,
                'bd_notation': bd_notation,
                'playable': bd_notation is not None,
                'duration_multiplier': note.get('duration_multiplier', 1.0)
            })

        return converted
    
    def _get_root_note(self) -> str:
        """获取调号的主音音名"""
        key = self.source_key.rstrip('m')
        return key if key in self.CHROMATIC_SCALE else 'C'
