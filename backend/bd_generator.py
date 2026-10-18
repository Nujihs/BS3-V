"""
BD谱生成模块
将转换后的音符生成BD谱文字和图片
"""

from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Optional
from config import C_HARMONICA_BD, BD_TO_TECHNIQUE
import os


class BDGenerator:
    """BD谱生成器"""
    
    def __init__(self):
        # 口琴布局可视化
        self.harmonica_layout = {
            1: {'blow': 'C3', 'draw': 'D3'},
            2: {'blow': 'E3', 'draw': 'G3'},
            3: {'blow': 'G3', 'draw': 'B3'},
            4: {'blow': 'C4', 'draw': 'D4'},
            5: {'blow': 'E4', 'draw': 'F4'},
            6: {'blow': 'G4', 'draw': 'A4'},
            7: {'blow': 'C5', 'draw': 'B4'},
            8: {'blow': 'E5', 'draw': 'D5'},
            9: {'blow': 'G5', 'draw': 'F5'},
            10: {'blow': 'C6', 'draw': 'A5'},
        }
        # 口琴背景图片路径（使用绝对路径，前端统一在 public/）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        bg_image_path = os.path.join(project_root, 'public', 'static', 'images', 'image.png')
        if os.path.exists(bg_image_path):
            self.harmonica_background_image = bg_image_path
        else:
            self.harmonica_background_image = None
            print(f"[WARNING] 口琴背景图片未找到: {bg_image_path}")
    
    def generate_text_notation(self, notes: List[dict]) -> str:
        """
        生成BD谱文字表示
        :param notes: 转换后的音符列表
        :return: BD谱字符串
        """
        bd_sequence = []
        
        for note in notes:
            if note.get('is_measure_line'):
                # 保留小节线
                bd_sequence.append('|')
            elif note.get('is_rest'):
                bd_sequence.append('-')
            elif note.get('is_tie'):
                bd_sequence.append('-')
            elif note.get('bd_notation'):
                bd_sequence.append(note['bd_notation'])
            else:
                # 不可演奏的音符
                bd_sequence.append('[X]')
        
        # 按小节分组显示
        return self._format_with_measures(bd_sequence)
    
    def _format_with_measures(self, bd_sequence: List[str]) -> str:
        """按小节格式化BD谱 - 保留原始小节结构"""
        lines = []
        current_line = []
        
        for bd in bd_sequence:
            if bd == '|':
                # 小节线，结束当前小节
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                else:
                    # 连续的小节线，添加空小节
                    lines.append('')
            else:
                current_line.append(bd)
                
                # 每行最多4个小节（约16个音符）
                if len(current_line) >= 16:
                    lines.append(' '.join(current_line))
                    current_line = []
        
        # 添加剩余音符
        if current_line:
            lines.append(' '.join(current_line))
        
        # 用 | 连接各行
        return ' |\n'.join(lines) + ' |'
    
    def _detect_hole_positions(self, bg_image: Image.Image) -> dict:
        """
        自动检测背景图片中孔位的位置
        :param bg_image: 背景图片
        :return: 包含 start_x, start_y, hole_width, hole_height 的字典
        """
        import numpy as np
        arr = np.array(bg_image.convert('RGB'))
        height, width = arr.shape[:2]
        
        # 设定检测区域（通常口琴孔在这一行）
        scan_y = int(height * 0.60)  # 调整到图片的60%高度位置（往上移）
        scan_height = 60  # 扫描高度范围
        
        # 在扫描区域内查找深色像素（孔的边缘）
        scan_area = arr[scan_y:scan_y+scan_height, :, :]
        dark = (scan_area[:,:,0] < 80) & (scan_area[:,:,1] < 80) & (scan_area[:,:,2] < 80)
        dark_y, dark_x = np.where(dark)
        
        if len(dark_x) < 10:
            # 没有检测到孔，使用默认位置
            print("[WARNING] 无法自动检测孔位，使用默认位置")
            return {
                'start_x': 0,
                'start_y': int(height * 0.60),  # 与扫描起点保持一致
                'hole_width': 46,
                'hole_height': 45,
                'detected': False
            }
        
        # 找出深色像素最集中的列（孔的左边缘）
        x_counts = np.bincount(dark_x, minlength=width)
        
        # 找到所有可能的孔边缘（深色像素突然增加的位置）
        hole_edges = []
        threshold = 10  # 至少有10个深色像素才算孔边缘
        prev_count = 0
        for x in range(width):
            if x_counts[x] > threshold and prev_count <= threshold:
                hole_edges.append(x)
            prev_count = x_counts[x]
        
        # 计算孔之间的平均距离
        if len(hole_edges) >= 2:
            distances = [hole_edges[i+1] - hole_edges[i] for i in range(len(hole_edges)-1)]
            avg_distance = np.median(distances) if distances else 86
            hole_width = int(avg_distance * 0.54)  # 孔宽约为间距的54%
        else:
            hole_width = 46
            avg_distance = 86
        
        # 第一个孔的位置
        first_hole_x = hole_edges[0] if hole_edges else 0
        
        # 估算 start_y（孔的垂直位置）
        # 使用深色像素的最小y值作为孔的上边缘（更准确）
        if len(dark_y) > 0:
            start_y = int(scan_y + np.min(dark_y))  # 使用最小值使高亮更靠上
        else:
            start_y = int(height * 0.60)
        
        print(f"[INFO] 自动检测到孔位: start_x={first_hole_x}, start_y={start_y}, hole_width={hole_width}")
        
        return {
            'start_x': first_hole_x,
            'start_y': start_y,
            'hole_width': hole_width,
            'hole_height': int(hole_width * 0.98),  # 高度与宽度接近
            'detected': True
        }

    def generate_harmonica_diagram(self, highlight_notes: List[str] = None,
                                   background_image_path: Optional[str] = None,
                                   key_signature: str = 'C') -> Image.Image:
        """
        生成口琴指法示意图
        :param highlight_notes: 需要高亮的音符列表
        :param background_image_path: 口琴背景图片路径（可选）
        :param key_signature: 简谱调号（如'C', 'G', 'D'等）
        :return: 口琴布局图
        """
        has_background = background_image_path and os.path.exists(background_image_path)

        # 加载背景图片或创建白色背景
        if has_background:
            base_img = Image.open(background_image_path).convert('RGB')
            img_width, img_height = base_img.size
        else:
            img_width = 900
            img_height = 300
            base_img = Image.new('RGB', (img_width, img_height), color='white')

        # 创建透明层用于绘制高亮
        overlay = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        try:
            font = ImageFont.truetype("simhei.ttf", 16)
            big_font = ImageFont.truetype("simhei.ttf", 20)
        except:
            font = ImageFont.load_default()
            big_font = ImageFont.load_default()

        # 如果没有背景图片，绘制完整的口琴布局
        if not has_background:
            # 标题
            title_text = f"C调十孔口琴音孔布局（演奏{key_signature}调乐曲）"
            draw.text((200, 20), title_text, fill='black', font=big_font)

            # 绘制10个孔
            hole_width = 75
            hole_height = 150
            start_x = 30
            start_y = 80
        else:
            # 使用真实口琴图片的孔位坐标
            # 自动检测孔位位置
            detected = self._detect_hole_positions(base_img)
            if detected['detected']:
                hole_width = detected['hole_width']
                hole_height = detected['hole_height']
                start_x = detected['start_x']
                start_y = detected['start_y']
            else:
                # 使用默认位置
                hole_width = 46
                hole_height = 45
                start_x = 0
                start_y = 225

        # 构建音符到孔位的反向映射（基于 BD_TO_TECHNIQUE）
        note_to_hole = {}
        for bd, info in BD_TO_TECHNIQUE.items():
            if info.get('hole') and info.get('note'):
                hole = info['hole']
                action = info['action']
                note = info['note']
                if hole not in note_to_hole:
                    note_to_hole[hole] = {}
                note_to_hole[hole][action] = note

        for hole_num in range(1, 11):
            x = start_x + (hole_num - 1) * (hole_width + 40)

            # 获取该孔的音符（使用正确的映射）
            hole_notes = note_to_hole.get(hole_num, {})
            blow_note = hole_notes.get('blow', '')
            draw_note = hole_notes.get('draw', '')

            # 吹音区域高亮（上半部分）- 检查音符是否在高亮列表中
            if highlight_notes and blow_note in highlight_notes:
                draw.rectangle([x, start_y, x + hole_width, start_y + hole_height//2],
                              fill=(100, 149, 237, 128), outline='blue', width=2)  # 半透明蓝色

            # 吸音区域高亮（下半部分）
            if highlight_notes and draw_note in highlight_notes:
                draw.rectangle([x, start_y + hole_height//2, x + hole_width, start_y + hole_height],
                              fill=(144, 238, 144, 128), outline='green', width=2)  # 半透明绿色

            # 如果没有背景图片，绘制完整的信息
            if not has_background:
                # 孔号
                draw.text((x + hole_width//2 - 8, start_y - 25),
                         f"{hole_num}孔", fill='black', font=font)

                # 吹音（上半部分）
                blow_bd = C_HARMONICA_BD.get(blow_note, '')
                blow_color = 'lightblue' if highlight_notes and blow_note in highlight_notes else 'white'
                draw.rectangle([x, start_y, x + hole_width, start_y + hole_height//2],
                              fill=blow_color, outline='black', width=1)
                draw.text((x + 10, start_y + 20), f"吹 {blow_bd}", fill='blue', font=font)
                draw.text((x + 15, start_y + 45), blow_note, fill='gray', font=font)

                # 吸音（下半部分）
                draw_bd = C_HARMONICA_BD.get(draw_note, '')
                draw_color = 'lightgreen' if highlight_notes and draw_note in highlight_notes else 'white'
                draw.rectangle([x, start_y + hole_height//2, x + hole_width, start_y + hole_height],
                              fill=draw_color, outline='black', width=1)
                draw.text((x + 10, start_y + hole_height//2 + 20), f"吸 {draw_bd}", fill='green', font=font)
                draw.text((x + 15, start_y + hole_height//2 + 45), draw_note, fill='gray', font=font)

        # 在右上角添加图例说明
        legend_x = img_width - 180
        legend_y = 20

        # 绘制图例背景框（增加高度以容纳调号信息）
        legend_box_height = 105  # 增加框的高度
        draw.rectangle([legend_x - 10, legend_y - 10, legend_x + 170, legend_y + legend_box_height],
                      fill=(255, 255, 255, 220), outline='black', width=2)

        # 调号说明
        key_text = f"{key_signature}调 (演奏调号)"
        draw.text((legend_x, legend_y), key_text, fill='red', font=big_font)

        # 口琴类型说明
        harmonica_text = "C调十孔口琴"
        draw.text((legend_x, legend_y + 25), harmonica_text, fill='black', font=font)

        # 吹音图例
        draw.rectangle([legend_x, legend_y + 50, legend_x + 30, legend_y + 70],
                      fill=(100, 149, 237, 200), outline='blue', width=2)
        draw.text((legend_x + 40, legend_y + 52), "吹 (Blow)", fill='black', font=font)

        # 吸音图例
        draw.rectangle([legend_x, legend_y + 75, legend_x + 30, legend_y + 95],
                      fill=(144, 238, 144, 200), outline='green', width=2)
        draw.text((legend_x + 40, legend_y + 77), "吸 (Draw)", fill='black', font=font)

        # 合并图片
        if has_background:
            result = Image.alpha_composite(base_img.convert('RGBA'), overlay)
        else:
            result = Image.alpha_composite(base_img.convert('RGBA'), overlay)

        return result.convert('RGB')
    
class BDPatternAnalyzer:
    """BD谱模式分析器"""
    
    def __init__(self):
        self.common_patterns = {
            '吹音上行': ['4B', '5B', '6B', '7B'],
            '吹音下行': ['7B', '6B', '5B', '4B'],
            '吸音上行': ['4D', '5D', '6D', '7D', '8D'],
            '吸音下行': ['8D', '7D', '6D', '5D', '4D'],
            '单孔颤音': ['4B', '4D'],
            '双孔吹': ['4B', '5B'],
            '双孔吸': ['4D', '5D'],
        }
    
    def analyze_sequence(self, bd_sequence: List[str]) -> Dict:
        """分析BD谱序列"""
        if not bd_sequence:
            return {
                'total_notes': 0,
                'blow_count': 0,
                'draw_count': 0,
                'hole_usage': {},
                'patterns_found': [],
            }
        
        # 过滤掉 None 值和休止符
        valid_notes = [b for b in bd_sequence if b and b != '-']
        
        analysis = {
            'total_notes': len(valid_notes),
            'blow_count': sum(1 for b in valid_notes if b and 'B' in b),
            'draw_count': sum(1 for b in valid_notes if b and 'D' in b),
            'hole_usage': {},
            'patterns_found': [],
        }
        
        # 统计孔位使用
        for bd in valid_notes:
            if bd and bd in BD_TO_TECHNIQUE:
                technique = BD_TO_TECHNIQUE[bd]
                if technique and 'hole' in technique:
                    hole = technique['hole']
                    analysis['hole_usage'][hole] = analysis['hole_usage'].get(hole, 0) + 1
        
        # 识别常见模式
        for pattern_name, pattern_seq in self.common_patterns.items():
            if self._find_pattern(valid_notes, pattern_seq):
                analysis['patterns_found'].append(pattern_name)
        
        return analysis
    
    def _find_pattern(self, sequence: List[str], pattern: List[str]) -> bool:
        """在序列中查找模式"""
        if not sequence or not pattern:
            return False
        pattern_len = len(pattern)
        if pattern_len == 0:
            return False
        if len(sequence) < pattern_len:
            return False
        for i in range(len(sequence) - pattern_len + 1):
            if sequence[i:i+pattern_len] == pattern:
                return True
        return False
