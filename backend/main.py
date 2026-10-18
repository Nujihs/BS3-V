"""
简谱转BD谱主程序
"""

import os
import sys
import argparse
import tempfile
from typing import Dict

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from music_theory import MusicTheoryConverter
from bd_generator import BDGenerator, BDPatternAnalyzer
from audio_synthesizer import HarmonicaAudioSynthesizer


class JianpuToBDConverter:
    """简谱转BD谱转换器"""

    def __init__(self):
        self.theory_converter = MusicTheoryConverter()
        self.bd_generator = BDGenerator()
        self.pattern_analyzer = BDPatternAnalyzer()
        self.audio_synthesizer = HarmonicaAudioSynthesizer()
        self.audio_synth = self.audio_synthesizer  # 别名兼容web_app

    def process_text(self, jianpu_text: str, key_signature: str = 'C', harmonica_type: str = 'C') -> Dict:
        """处理简谱文本"""
        self.theory_converter = MusicTheoryConverter(key_signature, harmonica_type)

        notes = self.theory_converter.parse_jianpu(jianpu_text)
        converted_notes = self.theory_converter.convert_to_c_major(notes)

        # 调试输出
        print(f"[DEBUG] 输入简谱: {jianpu_text}")
        print(f"[DEBUG] 音符数量: {len(converted_notes)}")
        print(f"[DEBUG] 前5个音符: {converted_notes[:5]}")

        bd_text = self.bd_generator.generate_text_notation(converted_notes)

        # 检查是否有 None 值
        bd_sequence = []
        for n in converted_notes:
            if not n.get('is_measure_line'):
                bd = n.get('bd_notation')
                if bd is None:
                    bd = '-'
                bd_sequence.append(bd)

        analysis = self.pattern_analyzer.analyze_sequence(bd_sequence)

        audio = self.audio_synthesizer.generate_sequence(converted_notes)
        audio = self.audio_synthesizer.add_reverb(audio, room_size=0.3)

        # 生成BD谱图片 - 使用时间戳确保路径唯一
        import time
        output_dir = tempfile.gettempdir()
        timestamp = int(time.time() * 1000)

        # 生成完整BD谱图片（包含口琴布局）
        bd_img_path = os.path.join(output_dir, f'bd_notation_{timestamp}.png')
        harmonica_diagram = self.bd_generator.generate_harmonica_diagram(
            [n['note_name'] for n in converted_notes if n.get('note_name') and not n.get('is_rest')],
            self.bd_generator.harmonica_background_image,
            key_signature
        )
        harmonica_diagram.save(bd_img_path)

        # 生成单独的口琴孔位图示（用于收据显示）
        played_notes = [n['note_name'] for n in converted_notes if n.get('note_name') and not n.get('is_rest')]
        harmonica_diagram_path = os.path.join(output_dir, f'harmonica_diagram_{timestamp}.png')

        # 检查口琴背景图片是否存在
        if self.bd_generator.harmonica_background_image and not os.path.exists(self.bd_generator.harmonica_background_image):
            print(f"[WARNING] 口琴背景图片不存在: {self.bd_generator.harmonica_background_image}")

        try:
            harmonica_diagram = self.bd_generator.generate_harmonica_diagram(played_notes, self.bd_generator.harmonica_background_image, key_signature)
            harmonica_diagram.save(harmonica_diagram_path)
        except Exception as e:
            print(f"[ERROR] 生成口琴图示失败: {str(e)}")
            # 使用默认的口琴图示
            harmonica_diagram = self.bd_generator.generate_harmonica_diagram(played_notes, None, key_signature)
            harmonica_diagram.save(harmonica_diagram_path)

        return {
            'bd_text': bd_text,
            'notes': converted_notes,
            'analysis': analysis,
            'audio': audio,
            'bd_image': bd_img_path,
            'harmonica_diagram': harmonica_diagram_path,
        }

    def process_image(self, image_path: str, key_signature: str = 'C', harmonica_type: str = 'C') -> Dict:
        """处理简谱图片（可插拔外部 OCR，原 EasyOCR 管线已移至 legacy/）"""
        from ocr_client import ocr_image_to_text, OCRNotConfigured
        try:
            jianpu_text = ocr_image_to_text(image_path)
        except OCRNotConfigured as e:
            raise Exception(str(e))
        return self.process_text(jianpu_text, key_signature, harmonica_type)

    def save_results(self, result: Dict, output_dir: str, jianpu_str: str = None, key_signature: str = 'C', harmonica_type: str = 'C'):
        """保存处理结果"""
        os.makedirs(output_dir, exist_ok=True)

        # 保存BD谱文本
        bd_text_path = os.path.join(output_dir, 'bd_notation.txt')
        with open(bd_text_path, 'w', encoding='utf-8') as f:
            f.write(result['bd_text'])
        print(f"BD谱文字已保存: {bd_text_path}")

        # 保存BD谱图片（包含口琴布局）
        bd_img_path = os.path.join(output_dir, 'bd_notation.png')
        harmonica_diagram = self.bd_generator.generate_harmonica_diagram(
            [n['note_name'] for n in result['notes'] if n.get('note_name') and not n.get('is_rest')],
            self.bd_generator.harmonica_background_image,
            key_signature
        )
        harmonica_diagram.save(bd_img_path)
        print(f"BD谱图片已保存: {bd_img_path}")

        # 保存音频
        if result['audio'] is not None and len(result['audio']) > 0:
            audio_path = os.path.join(output_dir, 'harmonica_preview.wav')
            self.audio_synthesizer.save_audio(result['audio'], audio_path)
            print(f"音频已保存: {audio_path}")


def main():
    parser = argparse.ArgumentParser(description='简谱转C调十孔口琴BD谱')
    parser.add_argument('--mode', choices=['text', 'image', 'demo'], default='demo')
    parser.add_argument('--input', '-i', help='输入文件路径')
    parser.add_argument('--key', '-k', default='C', help='调号')
    parser.add_argument('--output', '-o', default='./output', help='输出目录')
    
    args = parser.parse_args()
    
    converter = JianpuToBDConverter()
    
    if args.mode == 'demo':
        print("=" * 60)
        print("简谱转BD谱 - 演示模式")
        print("=" * 60)
        
        jianpu_demo = "| 3 3 4 5 | 5 4 3 2 | 1 1 2 3 | 3 2 2 - |"
        print(f"\n输入简谱: {jianpu_demo}")
        
        result = converter.process_text(jianpu_demo, 'C')
        
        print("\nBD谱输出:")
        print(result['bd_text'])
        print(f"\n总音符数: {result['analysis']['total_notes']}")
        
        converter.save_results(result, args.output)


if __name__ == '__main__':
    main()
