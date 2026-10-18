"""
音频合成模块 - 生成口琴演奏音频
"""

import numpy as np
import soundfile as sf
from typing import List, Dict, Optional
from config import NOTE_TO_MIDI, BD_TO_TECHNIQUE, AUDIO_SAMPLE_RATE, AUDIO_DURATION_DEFAULT, AUDIO_TEMPO_DEFAULT
import io
import base64


class HarmonicaAudioSynthesizer:
    """口琴音频合成器"""
    
    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        self.sample_rate = sample_rate
        
        self.harmonica_params = {
            'blow': {
                'harmonics': [1.0, 0.3, 0.15, 0.08, 0.05],
                'attack': 0.05, 'decay': 0.1, 'sustain': 0.7, 'release': 0.2,
                'breath_noise': 0.02,
            },
            'draw': {
                'harmonics': [1.0, 0.25, 0.12, 0.06, 0.04],
                'attack': 0.06, 'decay': 0.12, 'sustain': 0.65, 'release': 0.25,
                'breath_noise': 0.03,
            }
        }
        
        self.hole_brightness = {i: 0.8 + (i-1) * 0.05 for i in range(1, 11)}
    
    def midi_to_freq(self, midi_note: int) -> float:
        """MIDI音符编号转频率"""
        return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    
    def generate_note(self, note_name: str, bd_notation: str,
                     duration: float = AUDIO_DURATION_DEFAULT) -> np.ndarray:
        """生成单个音符的音频"""
        if note_name == 'REST' or not bd_notation:
            return np.zeros(int(self.sample_rate * duration))
        
        technique = BD_TO_TECHNIQUE.get(bd_notation, {})
        action = technique.get('action', 'blow')
        hole = technique.get('hole', 4)
        
        midi_note = NOTE_TO_MIDI.get(note_name, 60)
        frequency = self.midi_to_freq(midi_note)
        
        params = self.harmonica_params[action]
        brightness = self.hole_brightness.get(hole, 1.0)
        
        audio = self._synthesize_wave(frequency, duration, params, brightness)
        return audio
    
    def _synthesize_wave(self, frequency: float, duration: float,
                        params: dict, brightness: float) -> np.ndarray:
        """合成单音波形"""
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        wave = np.zeros(num_samples)
        harmonics = params['harmonics']
        
        for i, amp in enumerate(harmonics):
            harmonic_freq = frequency * (i + 1)
            adjusted_amp = amp * (brightness ** i)
            wave += adjusted_amp * np.sin(2 * np.pi * harmonic_freq * t)
        
        wave = np.tanh(wave * 1.2) * 0.8
        
        envelope = self._generate_adsr_envelope(duration, params)
        wave = wave * envelope
        
        if params['breath_noise'] > 0:
            noise = np.random.normal(0, params['breath_noise'], num_samples)
            noise = self._lowpass_filter(noise, 2000)
            wave = wave + noise
        
        max_amp = np.max(np.abs(wave))
        if max_amp > 0:
            wave = wave / max_amp * 0.8
        
        return wave
    
    def _generate_adsr_envelope(self, duration: float, params: dict) -> np.ndarray:
        """生成ADSR包络"""
        num_samples = int(self.sample_rate * duration)
        envelope = np.zeros(num_samples)
        
        attack_samples = int(self.sample_rate * params['attack'])
        decay_samples = int(self.sample_rate * params['decay'])
        release_samples = int(self.sample_rate * params['release'])
        sustain_level = params['sustain']
        
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        
        if decay_samples > 0:
            start = attack_samples
            end = min(attack_samples + decay_samples, num_samples)
            envelope[start:end] = np.linspace(1, sustain_level, end - start)
        
        sustain_start = attack_samples + decay_samples
        if sustain_start < num_samples - release_samples:
            envelope[sustain_start:num_samples - release_samples] = sustain_level
        
        if release_samples > 0:
            release_start = max(0, num_samples - release_samples)
            envelope[release_start:] = np.linspace(
                envelope[release_start] if release_start < num_samples else sustain_level,
                0, num_samples - release_start
            )
        
        return envelope
    
    def _lowpass_filter(self, signal: np.ndarray, cutoff: float) -> np.ndarray:
        """简单低通滤波器"""
        rc = 1.0 / (2 * np.pi * cutoff)
        dt = 1.0 / self.sample_rate
        alpha = dt / (rc + dt)
        
        filtered = np.zeros_like(signal)
        filtered[0] = signal[0]
        
        for i in range(1, len(signal)):
            filtered[i] = filtered[i-1] + alpha * (signal[i] - filtered[i-1])
        
        return filtered
    
    def generate_sequence(self, notes: List[dict],
                         tempo: int = AUDIO_TEMPO_DEFAULT) -> np.ndarray:
        """生成完整乐曲的音频"""
        beat_duration = 60.0 / tempo
        
        audio_segments = []
        pending_note = None
        pending_duration = 0.0
        base_duration = 0.0
        
        for note in notes:
            if note.get('is_tie') and pending_note is not None:
                pending_duration += base_duration * 0.5
                continue
            
            if pending_note is not None:
                note_audio = self.generate_note(
                    pending_note.get('note_name', 'REST'),
                    pending_note.get('bd_notation', None),
                    pending_duration
                )
                audio_segments.append(note_audio)
                pending_note = None
                pending_duration = 0.0
                base_duration = 0.0
            
            if note.get('is_measure_line'):
                continue
            
            duration_multiplier = note.get('duration_multiplier', 1.0)
            base_duration = beat_duration * duration_multiplier
            
            pending_note = note
            pending_duration = base_duration
        
        if pending_note is not None:
            note_audio = self.generate_note(
                pending_note.get('note_name', 'REST'),
                pending_note.get('bd_notation', None),
                pending_duration
            )
            audio_segments.append(note_audio)
        
        if audio_segments:
            full_audio = np.concatenate(audio_segments)
        else:
            full_audio = np.array([])
        
        return full_audio
    
    def add_reverb(self, audio: np.ndarray, room_size: float = 0.5,
                   damping: float = 0.5) -> np.ndarray:
        """添加混响效果"""
        if audio is None or len(audio) == 0:
            return np.array([])
        
        delay_times = [0.03, 0.037, 0.043, 0.05]
        gains = [0.4, 0.37, 0.33, 0.3]
        
        output = audio.copy()
        
        for delay, gain in zip(delay_times, gains):
            delay_samples = int(self.sample_rate * delay * room_size)
            if delay_samples < len(audio):
                delayed = np.zeros_like(audio)
                delayed[delay_samples:] = audio[:-delay_samples] * gain * (1 - damping)
                output = output + delayed
        
        max_amp = np.max(np.abs(output))
        if max_amp > 0:
            output = output / max_amp * 0.9
        
        return output
    
    def save_audio(self, audio: np.ndarray, filepath: str, format: str = 'wav'):
        """保存音频到文件"""
        sf.write(filepath, audio, self.sample_rate, format=format)

    def to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """将音频转为 WAV 字节（用于 base64 内联返回，适配 Serverless 无持久磁盘）"""
        if audio is None or len(audio) == 0:
            audio = np.zeros(int(self.sample_rate * 0.5))
        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format='wav')
        return buf.getvalue()
