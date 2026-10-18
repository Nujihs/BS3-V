"""
简谱识别流程 v3 — 通用版
=====================================
设计原则：
  - 零歌曲特定逻辑：所有后处理基于通用乐理规则
  - 多策略图像预处理：对同一图像跑多种增强方案，投票取最优
  - 线程安全 OCR 单例
  - 统一 logging，可通过环境变量 JIANPU_LOG_LEVEL 控制级别
  - RecognizerConfig 集中管理所有可调参数

识别管线：
  图像 → 多路预处理 → OCR行聚类 → 简谱符号提取
       ↘ 图像分割 → 逐符号OCR ↗
            ↓ 选更优结果
       通用后处理（乐理规则）→ 符号列表
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# ──────────────────────────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────────────────────────
_log_level = os.environ.get("JIANPU_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="[%(levelname)s] %(message)s",
    level=getattr(logging, _log_level, logging.INFO),
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 性能模式配置（可通过环境变量控制）
# ──────────────────────────────────────────────────────────────
# JIANPU_QUICK_MODE=1 启用快速模式，减少OCR调用次数（约2-3倍加速）
_JIANPU_QUICK_MODE = os.environ.get("JIANPU_QUICK_MODE", "0") == "1"

# ──────────────────────────────────────────────────────────────
# 路径
# ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import JianpuToBDConverter  # noqa: E402
from jianpu_segmenter import JianpuSegmenter  # noqa: E402


# ──────────────────────────────────────────────────────────────
# 配置类
# ──────────────────────────────────────────────────────────────
@dataclass
class RecognizerConfig:
    """所有可调参数集中在此处，方便调试和调优"""

    # OCR 阈值
    min_symbols_use_ocr: int = 30          # OCR 结果>=此值时直接采用
    min_symbols_acceptable: int = 8        # 低于此值视为识别失败
    ocr_conf_threshold: float = 0.15       # OCR 置信度过滤阈值

    # 行聚类
    y_cluster_coeff: float = 1 / 35        # y_threshold = img_h * coeff（最小15px）

    # 并发
    max_ocr_workers: int = min(6, (os.cpu_count() or 2))

    # OCR allowlist（简谱常见字符）
    # 收紧策略：仅保留数字 + 真正可能被误识别为数字的少数字母 + 简谱标记
    # 避免歌词中常见的 a/e/o 等字母被强行识别为数字
    ocr_allowlist: str = "01234567lLiIOoQSsZzTtEHh|.-"

    # 行过滤
    chinese_ratio_threshold: float = 0.55  # 中文占比>此值认为是歌词行（提高阈值，防止误过滤）
    english_word_threshold: int = 10       # 英文字母>此值认为是英文歌词行

    # 新增：高音/低音点检测参数
    high_dot_row_ratio: float = 0.35      # 高音点行位于数字上方的比例阈值
    low_dot_row_ratio: float = 0.65       # 低音点行位于数字下方的比例阈值

    # 新增：符号数量验证
    max_consecutive_ties: int = 3         # 最大连续延音线数量（4/4拍最多3个）
    min_note_ratio: float = 0.3           # 有效行中音符占符号的最低比例

    # 可视化
    save_visualization: bool = False

    # 输出目录（可被 process_jianpu_image 覆盖）
    output_dir: str = "./output"

    # 新增：图像预处理选项
    use_morphology: bool = True            # 是否使用形态学操作
    use_adaptive_threshold: bool = True    # 是否使用自适应阈值
    use_rotation_correction: bool = False  # 是否尝试旋转校正

    # 性能优化选项（可通过 JIANPU_QUICK_MODE=1 环境变量启用）
    quick_mode: bool = False
    skip_segmentation_fallback: bool = False


# ──────────────────────────────────────────────────────────────
# 线程安全 OCR 单例
# ──────────────────────────────────────────────────────────────
_OCR_LOCK = threading.Lock()
_OCR_READER_CACHE: Optional[object] = None


def _detect_gpu() -> bool:
    """检测 CUDA / ONNX GPU 是否可用"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        pass
    try:
        import onnxruntime
        return "CUDAExecutionProvider" in onnxruntime.get_available_providers()
    except ImportError:
        pass
    return False


# ──────────────────────────────────────────────────────────────
# OCR 引擎配置
# ──────────────────────────────────────────────────────────────
# 可选值: "easyocr" (默认), "fast" (轻量模式)
_OCR_MODE = os.environ.get("JIANPU_OCR_MODE", "easyocr").lower()


def get_ocr_reader(languages: Tuple[str, ...] = ("ch_sim", "en")):
    """获取全局 OCR Reader（懒加载，double-checked locking，线程安全）"""
    global _OCR_READER_CACHE, _OCR_MODE

    if _OCR_READER_CACHE is None:
        with _OCR_LOCK:
            if _OCR_READER_CACHE is None:
                import easyocr
                use_gpu = _detect_gpu()
                logger.info("初始化 EasyOCR 模型 (GPU=%s, 模式=%s)...", 
                           "是" if use_gpu else "否", _OCR_MODE)
                
                # 轻量模式：只加载必要语言，减少内存和初始化时间
                if _OCR_MODE == "fast":
                    # 轻量模式：降低 batch_size 和 workers
                    _OCR_READER_CACHE = easyocr.Reader(
                        list(languages),
                        gpu=use_gpu,
                        verbose=False,
                        quantize=True,
                        batch_size=4,  # 减小批次
                        workers=2,      # 减少线程
                    )
                else:
                    _OCR_READER_CACHE = easyocr.Reader(
                        list(languages),
                        gpu=use_gpu,
                        verbose=False,
                        quantize=True,
                    )
                logger.info("EasyOCR 模型初始化完成")
    return _OCR_READER_CACHE


def ocr_readtext(reader, img_array: np.ndarray):
    """OCR 读取文本"""
    return reader.readtext(img_array, detail=1, paragraph=False)


# ──────────────────────────────────────────────────────────────
# OCR 字符纠错表（无歌曲特定内容）
# ──────────────────────────────────────────────────────────────
# 格式：错误字符 → 正确数字
# 策略：仅收录"几乎肯定是数字"的字符；歌词中常见但与数字相似的字符
# （A, e, B 等）通过状态机的上下文判断处理，避免误识别。
_OCR_CHAR_MAP: Dict[str, str] = {}
_RAW_MAP: Dict[str, List[str]] = {
    "0": ["O", "o", "Q", "Ø", "©", "θ", "Θ"],
    "1": ["l", "I", "!", "i", "ı", "í", "¦", "ĺ", "ľ", "丨", "Ⅰ"],
    "2": ["Z", "z", "ƨ", "ž", "Ž"],
    "3": ["ε", "З", "Ǝ", "Є"],   # 注意：去掉单纯的 'E'，避免和键号 1=E 混淆
    "4": ["h", "ч", "H"],         # 保守：A/M/N 误判太多，只保留高置信
    "5": ["S", "s", "$", "§"],
    "6": ["б"],                   # 保守：'b'/'B' 在歌词常见，移到上下文判断
    "7": ["Γ", "¬", "ｲ"],
}
for _digit, _variants in _RAW_MAP.items():
    for _v in _variants:
        _OCR_CHAR_MAP.setdefault(_v, _digit)
# 数字本身也加入（避免重复逻辑）
for _d in "01234567":
    _OCR_CHAR_MAP[_d] = _d


def correct_ocr_char(ch: str, img_hw: Optional[Tuple[int, int]] = None) -> Optional[str]:
    """
    将单个 OCR 识别字符映射到简谱数字 '0'–'7'。
    img_hw: (height, width)，用于辅助判断数字 4。
    """
    ch = ch.strip()
    if not ch:
        return None
    # 直接查表
    if ch in _OCR_CHAR_MAP:
        return _OCR_CHAR_MAP[ch]
    # 数字 4 的宽高比辅助判断
    if ch.lower() in {"h", "a", "n", "rr", "ri", "r", "f", "t", "「", "ㄱ"}:
        if img_hw:
            h, w = img_hw
            if w > 0 and 0.3 < h / w < 1.8:
                return "4"
        return "4"
    return None


def correct_ocr_text(text: str, img_hw: Optional[Tuple[int, int]] = None) -> Optional[str]:
    """对整段 OCR 文本做纠错，返回第一个找到的有效数字"""
    text = text.strip()
    if not text:
        return None
    # 1. 直接整体纠错
    d = correct_ocr_char(text, img_hw)
    if d:
        return d
    # 2. 单字符尝试
    if len(text) == 1:
        return None
    # 3. 文本中找到唯一数字
    digits = re.findall(r"[0-7]", text)
    if len(digits) == 1:
        return digits[0]
    return None


# ──────────────────────────────────────────────────────────────
# 图像预处理工具
# ──────────────────────────────────────────────────────────────
def _preprocess_variants(img: Image.Image, config: Optional[RecognizerConfig] = None) -> List[np.ndarray]:
    """
    生成多种图像预处理变体，提高 OCR 召回率。
    返回 numpy 数组列表（RGB）。

    精简后的核心策略（覆盖 95%+ 简谱场景，不再生成低收益变体）：
      ① 放大 + CLAHE          —— 扫描件 / 拍照件首选
      ② Otsu 二值化            —— 高对比度印刷件
      ③ 自适应阈值             —— 局部光照变化
      ④ 对比度+锐化            —— 笔画偏淡的图（仅在非快速模式下启用）

    快速模式优化：
      - 仅使用 CLAHE + Otsu 两个变体
      - 适用于对速度要求高的场景

    被移除的变体：
      - 单独的"原图 CLAHE"     —— 与变体①重复
      - 形态学闭运算 + Otsu    —— 在简谱印刷件中收益低且会粘连相邻数字
    """
    import cv2

    if config is None:
        config = RecognizerConfig()

    variants: List[np.ndarray] = []
    gray_cv = np.array(img.convert("L"))
    img_h, img_w = gray_cv.shape

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    # ── 变体0：放大 1.5x + CLAHE（首选）──
    # 简谱数字通常 20px 左右，放大后 OCR 准确率显著提高
    scale = 1.5 if min(img_h, img_w) < 1200 else 1.0
    if scale != 1.0:
        resized = cv2.resize(gray_cv,
                             (int(img_w * scale), int(img_h * scale)),
                             interpolation=cv2.INTER_CUBIC)
    else:
        resized = gray_cv
    variants.append(cv2.cvtColor(clahe.apply(resized), cv2.COLOR_GRAY2RGB))

    # ── 变体1：Otsu 二值化（高对比度印刷件最准）──
    _, otsu = cv2.threshold(gray_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(cv2.cvtColor(otsu, cv2.COLOR_GRAY2RGB))

    # ── 快速模式：只使用两个变体，跳过后续处理 ──
    if config.quick_mode:
        return variants

    # ── 变体2：自适应阈值（局部光照变化）──
    if config.use_adaptive_threshold:
        # 块大小自适应于图像尺寸，保证奇数
        block = max(15, (min(img_h, img_w) // 30) | 1)
        adaptive = cv2.adaptiveThreshold(
            gray_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, block, 8
        )
        variants.append(cv2.cvtColor(adaptive, cv2.COLOR_GRAY2RGB))

    # ── 变体3：对比度+锐化（笔画偏淡）──
    pil_gray = Image.fromarray(gray_cv)
    enhanced = ImageEnhance.Contrast(pil_gray).enhance(2.2)
    enhanced_sharpened = enhanced.filter(ImageFilter.SHARPEN)
    variants.append(np.array(enhanced_sharpened.convert("RGB")))

    # ── 可选变体：放大 2x + Otsu（极小字体）──
    if config.use_rotation_correction:
        resized2 = cv2.resize(gray_cv, (int(img_w * 2), int(img_h * 2)),
                              interpolation=cv2.INTER_CUBIC)
        _, resized2_otsu = cv2.threshold(resized2, 0, 255,
                                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(cv2.cvtColor(resized2_otsu, cv2.COLOR_GRAY2RGB))

        rotated = _correct_skew(gray_cv)
        if rotated is not None:
            variants.append(rotated)

    return variants


def _correct_skew(gray_img: np.ndarray) -> Optional[np.ndarray]:
    """
    尝试校正图像倾斜（适用于扫描歪斜的简谱图片）。
    返回校正后的 RGB 图像数组，如果不需要校正则返回 None。
    """
    try:
        import cv2
        
        # 边缘检测
        edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
        
        # 霍夫直线检测
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            return None
        
        # 计算平均倾斜角度
        angles = []
        for rho, theta in lines[:, 0]:
            angle = (theta * 180 / np.pi) - 90
            if -45 < angle < 45:  # 只处理小角度倾斜
                angles.append(angle)
        
        if not angles:
            return None
        
        median_angle = np.median(angles)
        
        if abs(median_angle) < 0.5:  # 倾斜小于0.5度，不校正
            return None
        
        # 旋转图像
        (h, w) = gray_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            gray_img, M, (w, h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )
        
        return cv2.cvtColor(rotated, cv2.COLOR_GRAY2RGB)
        
    except Exception as e:
        logger.debug("倾斜校正失败: %s", e)
        return None


# ──────────────────────────────────────────────────────────────
# 主识别器
# ──────────────────────────────────────────────────────────────
class AdvancedJianpuRecognizer:
    """
    简谱识别器 v3（通用版）

    管线：
      多路图像预处理 → OCR → 行聚类 → 符号提取
                             ↘ 图像分割 → 逐符号OCR ↗
                                         ↓
                               通用乐理后处理
    """

    def __init__(
        self,
        use_segmentation: bool = True,
        config: Optional[RecognizerConfig] = None,
    ):
        self.cfg = config or RecognizerConfig()
        self.use_segmentation = use_segmentation
        self.segmenter = JianpuSegmenter() if use_segmentation else None

    # ────────────────────────────── 主入口 ──────────────────────────────

    def recognize(self, img_path: str) -> Dict:
        """识别简谱图片，返回统一结构的字典"""
        if not os.path.exists(img_path):
            return {"success": False, "error": f"文件不存在: {img_path}"}

        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)
        logger.info("图片尺寸: %s", img.size)

        # ── 方法零：标题区专项识别（最高优先级的调号 / 拍号来源）──
        # 标题区域格式高度规范化：1=X、X/Y、♩=N
        # 单独裁剪并 OCR 这一区域，准确率比全图扫描高得多
        # 快速模式下跳过（标题区识别也有额外OCR开销）
        title_key, title_time = None, None
        if not self.cfg.quick_mode:
            title_key, title_time = self._detect_from_title_region(img)
            if title_key:
                logger.info("标题区识别 调号=%s 拍号=%s", title_key, title_time)

        # ── 方法一：多策略 OCR ──
        ocr_symbols, key = self._multi_strategy_ocr(img)
        logger.info("多策略 OCR 识别到 %d 个符号", len(ocr_symbols))

        # ── 方法二：低识别率时的增强策略（快速模式跳过）──
        if len(ocr_symbols) < self.cfg.min_symbols_use_ocr and not self.cfg.quick_mode:
            logger.info("OCR 结果不足，尝试增强预处理...")
            enhanced_symbols, enhanced_key = self._enhanced_ocr(img)
            if len(enhanced_symbols) > len(ocr_symbols):
                logger.info("增强 OCR 识别到 %d 个符号（更优）", len(enhanced_symbols))
                ocr_symbols = enhanced_symbols
            # 调号合并规则：
            # - 若多策略已识别到非C调（如 F/G/D），增强OCR不得将其退回到 C
            #   （增强策略使用激进预处理，易破坏 1=X 文字结构，导致大量变体默认 C）
            # - 若多策略结果是 C（默认），允许增强OCR替换
            if enhanced_key != key:
                if key != "C" and enhanced_key == "C":
                    logger.info("调号保持: %s（增强OCR得 C，但多策略已明确识别到非C调）", key)
                else:
                    logger.info("调号修正: %s → %s（来自增强OCR）", key, enhanced_key)
                    key = enhanced_key

        # 标题区识别到的调号优先级最高（格式最规范）
        if title_key and title_key != key:
            logger.info("调号修正: %s → %s（来自标题区）", key, title_key)
            key = title_key

        # 标题区识别到的拍号也覆盖之前的投票（标题区准确率更高）
        if title_time:
            num = title_time[0]
            if num == 2:
                self.cfg.max_consecutive_ties = 1
            elif num == 3:
                self.cfg.max_consecutive_ties = 2
            else:
                self.cfg.max_consecutive_ties = 3
            logger.info("拍号修正: %s（来自标题区），最大连续延音线=%d",
                        title_time, self.cfg.max_consecutive_ties)

        if len(ocr_symbols) >= self.cfg.min_symbols_use_ocr:
            logger.info("OCR 结果充足，直接采用")
            return {
                "success": True,
                "symbols": ocr_symbols,
                "key_signature": key,
                "method": "ocr",
            }

        # ── 方法三：图像分割 OCR（可配置跳过）──
        seg_symbols: List[str] = []
        if self.use_segmentation and not self.cfg.skip_segmentation_fallback:
            logger.info("OCR 结果不足，尝试图像分割识别...")
            seg_symbols = self._recognize_with_segmentation(img_array)
            logger.info("分割识别到 %d 个符号", len(seg_symbols))

        # 选更优结果
        if seg_symbols and len(ocr_symbols) < len(seg_symbols):
            best_symbols = seg_symbols
            best_method = "segmentation"
        else:
            best_symbols = ocr_symbols
            best_method = "ocr" if ocr_symbols else "segmentation"

        if len(best_symbols) < self.cfg.min_symbols_acceptable:
            logger.warning("识别符号数量过少 (%d)，结果可信度低", len(best_symbols))
            return {
                "success": True,
                "symbols": best_symbols,
                "key_signature": key,
                "method": best_method,
                "low_confidence": True,
            }

        return {
            "success": True,
            "symbols": best_symbols,
            "key_signature": key,
            "method": best_method,
        }

    # ────────────────────────── 多策略 OCR ──────────────────────────────

    def _multi_strategy_ocr(self, img: Image.Image) -> Tuple[List[str], str]:
        """
        对多种图像预处理变体分别 OCR，选取识别到简谱符号最多的结果。

        关键设计：
        - 调号检测与符号计数解耦：调号通过所有变体投票确定，
          不依赖哪个变体音符最多，避免"最优变体恰好漏识别调号"的问题。
        - 拍号同样跨变体投票。
        """
        variants = _preprocess_variants(img, self.cfg)
        reader = get_ocr_reader()
        cfg = self.cfg

        best_symbols: List[str] = []
        best_count: int = -1

        # 独立收集所有变体的调号和拍号检测结果
        key_votes: Dict[str, int] = {}          # key → 出现次数
        time_votes: Dict[Tuple[int, int], int] = {}  # (num, den) → 出现次数

        for idx, variant in enumerate(variants):
            try:
                raw_lines = self._ocr_array_to_lines(variant, reader)
                jianpu_lines = self._extract_jianpu_lines(raw_lines)
                symbols = self._clean_and_normalize(jianpu_lines)

                # ── 调号投票（每个变体独立检测）──
                detected_key = self._detect_key(raw_lines)
                key_votes[detected_key] = key_votes.get(detected_key, 0) + 1

                # ── 拍号投票 ──
                time_sig = self._detect_time_signature(raw_lines)
                time_votes[time_sig] = time_votes.get(time_sig, 0) + 1

                note_count = sum(
                    1 for s in symbols
                    if s and (s[0] in "1234567" or
                              (s.startswith(".") and len(s) > 1 and s[1] in "1234567"))
                )
                logger.debug("预处理变体 %d: %d 个音符符号，检测调号=%s", idx, note_count, detected_key)

                if note_count > best_count:
                    best_count = note_count
                    best_symbols = symbols
            except Exception as exc:
                logger.debug("变体 %d OCR 异常: %s", idx, exc)

        # ── 最终调号：绝对多数投票 ──
        # 规则：非C调号必须票数 >= C的票数 * 0.6，且至少占总票数的20%，才能胜出。
        # 调整后更容易识别非C调（如G调），避免被C调压制。
        total_votes = sum(key_votes.values())
        c_votes = key_votes.get("C", 0)
        non_c_votes = {k: v for k, v in key_votes.items() if k != "C"}
        if non_c_votes:
            top_non_c = max(non_c_votes, key=lambda k: non_c_votes[k])
            top_non_c_count = non_c_votes[top_non_c]
            non_c_ratio = top_non_c_count / total_votes if total_votes > 0 else 0
            # 非C调号必须满足：票数 >= C票数的60% 且 占比 >= 20%
            # 这样即使C票略多，非C调也能通过（只要不是压倒性劣势）
            if top_non_c_count >= c_votes * 0.6 and non_c_ratio >= 0.20:
                best_key = top_non_c
            else:
                best_key = "C"
        else:
            best_key = "C"
        logger.info("调号投票结果: %s → 最终调号: %s", key_votes, best_key)

        # ── 最终拍号：排除默认 (4,4)，有明确检测结果时优先使用 ──
        non_default_time = {t: v for t, v in time_votes.items() if t != (4, 4)}
        if non_default_time:
            best_time = max(non_default_time, key=lambda t: non_default_time[t])
        else:
            best_time = (4, 4)

        # 根据拍号更新最大延音线数量
        numerator = best_time[0]
        if numerator == 2:
            cfg.max_consecutive_ties = 1
        elif numerator == 3:
            cfg.max_consecutive_ties = 2
        else:
            cfg.max_consecutive_ties = 3
        logger.debug("拍号投票结果: %s → 最终拍号: %s，最大延音线数: %d",
                     time_votes, best_time, cfg.max_consecutive_ties)

        return best_symbols, best_key

    def _enhanced_ocr(self, img: Image.Image) -> Tuple[List[str], str]:
        """
        增强 OCR：当标准预处理变体识别不足时，
        使用更激进的处理策略尝试提高识别率。
        """
        import cv2
        
        reader = get_ocr_reader()
        cfg = self.cfg
        best_symbols: List[str] = []
        best_count: int = -1
        key_votes: Dict[str, int] = {}   # 同样用投票确定调号

        gray_cv = np.array(img.convert("L"))
        img_h, img_w = gray_cv.shape

        def _try_variant(img_rgb: np.ndarray, label: str) -> None:
            nonlocal best_count, best_symbols
            try:
                raw_lines = self._ocr_array_to_lines(img_rgb, reader)
                jianpu_lines = self._extract_jianpu_lines(raw_lines)
                symbols = self._clean_and_normalize(jianpu_lines)
                detected_key = self._detect_key(raw_lines)
                key_votes[detected_key] = key_votes.get(detected_key, 0) + 1
                note_count = sum(1 for s in symbols if s and s[0] in "1234567")
                logger.debug("增强策略(%s): %d 个音符符号，调号=%s", label, note_count, detected_key)
                if note_count > best_count:
                    best_count = note_count
                    best_symbols = symbols
            except Exception as exc:
                logger.debug("增强策略(%s)异常: %s", label, exc)

        # 策略1: 更低阈值的二值化
        for thresh in [100, 80, 60]:
            _, bw = cv2.threshold(gray_cv, thresh, 255, cv2.THRESH_BINARY)
            _try_variant(cv2.cvtColor(bw, cv2.COLOR_GRAY2RGB), f"阈值={thresh}")

        # 策略2: Otsu 自动阈值
        _, otsu = cv2.threshold(gray_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _try_variant(cv2.cvtColor(otsu, cv2.COLOR_GRAY2RGB), "Otsu")

        # 策略3: 缩放后识别
        for scale in [1.5, 2.0]:
            resized = cv2.resize(gray_cv, (int(img_w * scale), int(img_h * scale)),
                                 interpolation=cv2.INTER_CUBIC)
            _try_variant(cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB), f"缩放{scale}")

        # 策略4: 形态学组合
        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 2))
        kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        opened = cv2.morphologyEx(gray_cv, cv2.MORPH_OPEN, kernel_small)
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_large)
        _try_variant(cv2.cvtColor(closed, cv2.COLOR_GRAY2RGB), "形态学组合")

        # 调号投票：绝对多数，非C必须票数 >= C且占比 >= 30%
        total_v = sum(key_votes.values())
        c_v = key_votes.get("C", 0)
        non_c = {k: v for k, v in key_votes.items() if k != "C"}
        if non_c:
            top_k = max(non_c, key=lambda k: non_c[k])
            # 非C调号必须满足：票数 >= C票数的60% 且 占比 >= 20%
            if non_c[top_k] >= c_v * 0.6 and non_c[top_k] / total_v >= 0.20:
                best_key = top_k
            else:
                best_key = "C"
        else:
            best_key = "C"
        logger.info("增强OCR调号投票: %s → %s", key_votes, best_key)

        return best_symbols, best_key

    def _ocr_array_to_lines(
        self, img_array: np.ndarray, reader
    ) -> List[str]:
        """
        对单张图像 OCR，按 Y 轴聚类后返回文本行列表。
        
        改进：
        - 动态 y_threshold 基于行高估算（而非固定系数）
        - 过滤极低置信度结果
        - 按 x 坐标严格排序，确保音符顺序正确
        """
        cfg = self.cfg
        results = ocr_readtext(reader, img_array)

        img_h = img_array.shape[0]

        # ── 高音点融合（在 y 聚类之前完成）──
        # 简谱中高音八度点（如 .1 .2）的小圆点位于数字正上方，
        # OCR 常把它识别为单独的 '.' 或 '1'，导致 .2 → 1 2。
        # 此步将这些小标记合并回对应数字，输出 .X 格式。
        results = self._fuse_octave_dots(results)

        # 动态计算行高：基于所有 bbox 高度的中位数
        bbox_heights = []
        for bbox, text, conf in results:
            if conf >= cfg.ocr_conf_threshold:
                h = max(p[1] for p in bbox) - min(p[1] for p in bbox)
                if h > 5:
                    bbox_heights.append(h)

        if bbox_heights:
            median_h = float(np.median(bbox_heights))
            # y_threshold 为行高的 75%（略宽松，防止延音线 '-' 落入独立簇）
            y_threshold = max(15, int(median_h * 0.75))
        else:
            y_threshold = max(15, int(img_h * cfg.y_cluster_coeff))

        logger.debug("行聚类 y_threshold = %d px", y_threshold)

        # Y 轴聚类：(加权均值 y) → [(x_left, text, conf), ...]
        clusters: Dict[float, List[Tuple[float, str, float]]] = {}

        for bbox, text, conf in results:
            if conf < cfg.ocr_conf_threshold:
                continue
            # 使用 bbox 中心 y（更稳定）
            y_center = (min(p[1] for p in bbox) + max(p[1] for p in bbox)) / 2.0
            x_left = bbox[0][0]

            matched_key: Optional[float] = None
            for ky in list(clusters):
                if abs(y_center - ky) < y_threshold:
                    matched_key = ky
                    break

            if matched_key is not None:
                clusters[matched_key].append((x_left, text, conf))
                items = clusters.pop(matched_key)
                # 加权平均 y（权重=置信度）
                total_conf = sum(c for _, _, c in items)
                new_y = sum(ky * c for _, _, c in items) / total_conf if total_conf > 0 else y_center
                # 修正：使用简单平均避免漂移
                new_y = (matched_key * (len(items) - 1) + y_center) / len(items)
                clusters[new_y] = items
            else:
                clusters[y_center] = [(x_left, text, conf)]

        sorted_lines: List[str] = []
        for ky in sorted(clusters):
            # 按 x 坐标严格排序（保证音符从左到右）
            row = sorted(clusters[ky], key=lambda t: t[0])
            sorted_lines.append(" ".join(item[1] for item in row))

        return sorted_lines

    # ──────────────────────── 高音点融合 ─────────────────────────────

    def _fuse_octave_dots(self, results: list) -> list:
        """
        在 y 聚类前，将高音八度点（位于数字正上方的小标记）与其数字融合。

        问题背景：
          简谱 .2 表示高音 2，印刷时小圆点在数字正上方（约 0.5~1.5 个字符高的距离）。
          EasyOCR 常把该小圆点单独识别为 '.'、'·'、'1' 或 ',' 等短文本，
          导致 .2 被拆成两个 token "1" + "2" 或只有 "2"（点被过滤）。

        算法：
          1. 计算所有 bbox 的参考字符高度（数字类结果的中位数高度 ref_h）
          2. 识别"点候选"：height < 0.55*ref_h，文本为短字符或点符号
          3. 对每个点候选，寻找正下方（y 间距 < 1.8*ref_h）且水平对齐
             （x 中心差 < 1.2*ref_h）的数字结果
          4. 若找到匹配，将点候选 + 数字合并为 '.digit'，使用数字的 bbox
        """
        if not results:
            return results

        # ── 第1步：提取每个 OCR 结果的几何信息 ──
        infos = []
        for bbox, text, conf in results:
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            y_top = min(ys)
            y_bot = max(ys)
            x_left = min(xs)
            x_right = max(xs)
            infos.append({
                'bbox': bbox,
                'text': text.strip(),
                'conf': conf,
                'y_top': y_top,
                'y_bot': y_bot,
                'x_left': x_left,
                'x_right': x_right,
                'h': y_bot - y_top,
                'w': x_right - x_left,
                'cx': (x_left + x_right) / 2.0,
                'cy': (y_top + y_bot) / 2.0,
            })

        # ── 第2步：估算参考字符高度（取纯数字 token 的中位高度）──
        digit_heights = [
            d['h'] for d in infos
            if d['text'] in '1234567' and d['h'] > 5
        ]
        if not digit_heights:
            return results  # 无法估算，跳过
        ref_h = float(np.median(digit_heights))
        ref_h = max(ref_h, 10.0)  # 保证最低参考值

        # ── 第3步：标注点候选 ──
        # 高音点标记：height 远小于普通数字，且文本非常短
        # 明确的点符号或可被误读为点的字符
        DOT_TEXTS = {'.', '·', ',', '`', '°', '。'}
        AMBIG_TEXTS = {'1', 'i', 'l', 'I', '!'}  # 点被读成这些字符

        def is_dot_candidate(info: dict) -> bool:
            t = info['text']
            if len(t) > 2:
                return False
            if info['h'] >= ref_h * 0.60:
                return False  # 太大，不像点
            # 明确的点字符，或高度确实很小的模糊字符
            if t in DOT_TEXTS:
                return True
            if t in AMBIG_TEXTS and info['h'] < ref_h * 0.45:
                return True
            return False

        # ── 第4步：两遍匹配 ──
        fusions: Dict[int, int] = {}     # dot_idx → digit_idx
        used_digits: set = set()

        for i, dot in enumerate(infos):
            if not is_dot_candidate(dot):
                continue

            best_j: Optional[int] = None
            best_score = float('inf')  # 综合评分（越小越好）
            best_gap = 0

            for j, digit in enumerate(infos):
                if j == i or j in used_digits:
                    continue
                if digit['text'] not in '1234567':
                    continue
                if digit['h'] < ref_h * 0.5:
                    continue  # 避免把另一个点当数字

                # 垂直方向：点必须在数字上方（允许轻微重叠，即 gap 可以略小于0）
                gap = digit['y_top'] - dot['y_bot']
                if gap < -ref_h * 0.3 or gap > ref_h * 1.8:
                    continue

                # 水平对齐：点的中心必须在数字水平范围内
                x_dist = abs(dot['cx'] - digit['cx'])
                if x_dist > max(digit['w'] * 0.8, ref_h * 1.2):
                    continue

                # 综合评分：垂直间距为主，水平偏移为辅（权重 0.5）
                # 这样即使两个数字垂直距离相同，也会选 x 更近的
                score = max(gap, 0) + x_dist * 0.5
                if score < best_score:
                    best_score = score
                    best_j = j
                    best_gap = gap

            if best_j is not None:
                fusions[i] = best_j
                used_digits.add(best_j)
                logger.debug(
                    "高音点融合: %r(%dpx) + %r → .%s (gap=%.0fpx)",
                    dot['text'], dot['h'], infos[best_j]['text'],
                    infos[best_j]['text'], best_gap
                )

        # ── 第5步：生成融合后的结果列表 ──
        fused_digit_idx = set(fusions.values())
        output = []
        for i, info in enumerate(infos):
            if i in fused_digit_idx:
                continue  # 这个数字已被点候选吸收
            if i in fusions:
                # 此点候选与下方数字融合，输出 '.digit'
                digit = infos[fusions[i]]
                output.append((digit['bbox'], '.' + digit['text'], min(info['conf'], digit['conf'])))
            else:
                output.append((info['bbox'], info['text'], info['conf']))

        fused_count = len(fusions)
        if fused_count:
            logger.info("高音点融合：共融合 %d 个高音点标记", fused_count)

        return output

    # ──────────────────────── 图像分割识别 ────────────────────────────

    def _batch_ocr_symbols(self, numbers: List[Dict]) -> List[Dict]:
        """并行 OCR 分割后的单个符号图像"""
        reader = get_ocr_reader()
        cfg = self.cfg

        def _ocr_one(num: Dict) -> Dict:
            t = num.get("type", "unknown")
            if t == "barline":
                num["recognized_digit"] = "|"
                return num
            if t == "line":
                num["recognized_digit"] = "-"
                return num
            if t not in ("number", "unknown"):
                num["recognized_digit"] = None
                return num

            num_img = num["image"]
            img_hw = (num_img.shape[0], num_img.shape[1]) if hasattr(num_img, "shape") else None

            try:
                results = ocr_readtext(reader, num_img)
            except Exception:
                results = []

            digit: Optional[str] = None
            if results:
                # 先逐个结果纠错
                for res in results:
                    raw_text = res[1].strip() if len(res) > 1 else ""
                    d = correct_ocr_text(raw_text, img_hw)
                    if d:
                        digit = d
                        break
                # 再在合并文本里找
                if digit is None:
                    combined = " ".join(r[1].strip() for r in results)
                    d = correct_ocr_text(combined, img_hw)
                    if d:
                        digit = d
                    else:
                        found = re.findall(r"[0-7]", combined)
                        if found:
                            digit = found[0]

            num["recognized_digit"] = digit
            return num

        max_workers = min(cfg.max_ocr_workers, len(numbers)) if numbers else 1
        if max_workers <= 1:
            for n in numbers:
                _ocr_one(n)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
                futures = {exe.submit(_ocr_one, n): n for n in numbers}
                for f in concurrent.futures.as_completed(futures):
                    try:
                        f.result()
                    except Exception as exc:
                        logger.warning("OCR 线程异常: %s", exc)

        return numbers

    def _recognize_with_segmentation(self, img_array: np.ndarray) -> List[str]:
        """图像分割 + 并行 OCR"""
        symbols = self.segmenter.segment_image(img_array, enhance_image=True)
        if not symbols:
            logger.warning("分割：未检测到任何符号")
            return []

        logger.debug("分割：检测到 %d 个符号", len(symbols))

        if self.cfg.save_visualization:
            out_dir = self.cfg.output_dir
            os.makedirs(out_dir, exist_ok=True)
            vis_path = os.path.join(out_dir, "segmentation_result.png")
            self.segmenter.visualize_segmentation(img_array, symbols, vis_path)
            logger.info("分割可视化保存至: %s", vis_path)

        numbers = self.segmenter.associate_dots(symbols)

        try:
            numbers = self._batch_ocr_symbols(numbers)
        except Exception as exc:
            logger.error("批量 OCR 失败: %s", exc)
            return []

        recognized: List[str] = []
        for num in numbers:
            digit = num.get("recognized_digit")
            if digit in ("|", "-"):
                recognized.append(digit)
                continue
            if digit and num.get("type", "unknown") in ("number", "unknown"):
                upper = len(num.get("upper_dots", []))
                lower = len(num.get("lower_dots", []))
                right = len(num.get("right_dots", []))
                under = len(num.get("underlines", []))
                token = digit
                if upper:
                    token = "." * upper + token
                if lower:
                    token = token + "." * lower
                if right:
                    # 附点（augmentation dot）使用 '*'，music_theory 识别为 1.5x 时值
                    token = token + "*"
                if under:
                    # 减时线（节奏标记）信息当前 BD 生成器不使用，但保留用于将来扩展
                    # 不影响音高/八度，故不加入 token
                    pass
                recognized.append(token)

        recognized = self._universal_post_process(recognized)
        return recognized

    # ──────────────────────── 符号提取与清理 ──────────────────────────

    def _extract_jianpu_lines(self, all_text: List[str]) -> List[str]:
        """
        从 OCR 行中过滤出简谱行。
        
        改进：
        - 更精确的行类型判断
        - 跳过小节号行（[5] [9] 等）
        - 基于音符密度而非简单数字计数
        """
        cfg = self.cfg
        jianpu_lines: List[str] = []

        for idx, line in enumerate(all_text):
            line = line.strip()
            if not line:
                continue

            # 跳过纯小节号行（[5]、(9)、{13} 或裸 5）
            if re.match(r"^\s*[\[\(\{]?\d{1,2}[\]\)\}]?\s*$", line):
                continue
            # 跳过调号/速度行
            if re.match(r"^\s*1\s*=\s*[CDEFGAB]", line, re.IGNORECASE):
                continue
            if re.match(r"^\s*[Jj♩]?\s*=\s*\d+", line):
                continue
            # 跳过页码行（"1/1"、"C-1" 等）
            if re.match(r"^\s*\d+\s*/\s*\d+\s*$", line) or re.match(r"^[Cc]-?\d+$", line.strip()):
                continue
            # 跳过制谱署名行
            if re.search(r"(制谱|作词|作曲|演唱|译配|歌谱|出处|英国儿歌|插曲)", line):
                continue

            # 移除行首/行内的 [N]/(N)/{N} 小节号（不影响后续音符）
            line = re.sub(r"[\[\(\{]\s*\d{1,2}\s*[\]\)\}]", " ", line)

            total = len(line.replace(" ", ""))
            if total == 0:
                continue

            zh_count = len(re.findall(r"[\u4e00-\u9fff]", line))
            en_letters = re.findall(r"[a-zA-Z]", line)
            en_count = len(en_letters)
            zh_ratio = zh_count / total

            # 检查行内是否包含简谱数字（包括高音点格式）
            has_jianpu_digits = bool(re.search(r"[1-7]", line))

            if not has_jianpu_digits:
                continue  # 无简谱数字的行直接跳过

            # 含简谱数字的行：判断是否为歌词夹杂数字
            if zh_ratio > cfg.chinese_ratio_threshold:
                # 中文占比高，但如果数字明显多于汉字，仍然保留
                digit_count_in_line = len(re.findall(r"[0-7]", line))
                if digit_count_in_line < zh_count:
                    logger.debug("行 %d 判定为歌词行（中文占比 %.2f）: %s...", idx + 1, zh_ratio, line[:30])
                    continue
                
            # 英文歌词行检测（多个英文字母，且数字少）
            # 降低阈值：双语谱（中英双语歌词）英文行字母通常 >= 8
            if en_count >= 6 and zh_ratio < 0.15:
                digit_count_in_line = len(re.findall(r"[0-7]", line))
                # 数字与字母比例太低 → 英文歌词行
                if digit_count_in_line < en_count * 0.25:
                    logger.debug("行 %d 判定为英文歌词行(letters=%d digits=%d): %s...",
                                 idx + 1, en_count, digit_count_in_line, line[:40])
                    continue
            # 仅含常见英文词（Happy / New / Year / to / you / all / are 等）且数字极少
            common_en_words = re.findall(
                r"\b(Happy|New|Year|Hello|Good|Morning|Night|to|you|all|are|We|We\'re|singing|dancing)\b",
                line, re.IGNORECASE
            )
            if len(common_en_words) >= 2 and len(re.findall(r"[0-7]", line)) <= 1:
                logger.debug("行 %d 判定为英文歌词行(关键词匹配): %s...", idx + 1, line[:40])
                continue

            jianpu_line = self._extract_symbols_from_line(line)
            if not jianpu_line:
                continue

            sym_list = jianpu_line.split()
            digit_count = sum(1 for s in sym_list if re.search(r"[1-7]", s))
            total_sym = len(sym_list)
            
            # 至少有2个音符符号，且音符占比 >= min_note_ratio
            note_ratio = digit_count / total_sym if total_sym > 0 else 0
            if digit_count >= 2 and note_ratio >= cfg.min_note_ratio:
                logger.debug("行 %d → 简谱行(音符占比%.2f): %s", idx + 1, note_ratio, jianpu_line[:60])
                jianpu_lines.append(jianpu_line)

        return jianpu_lines

    def _extract_symbols_from_line(self, line: str) -> str:
        """
        从单行文本中提取简谱符号。
        
        改进：
        - 更准确的高音点(i→.X)识别，包括带数字的 i1、i2 等
        - 修复数字4的识别（OCR 常将 4 识别为 h/A/H）
        - 修复下划线（低音）的保留逻辑
        - 更稳健的状态机处理粘连字符
        """
        # 跳过纯速度/调号标记行
        if re.search(r"=\s*\d+", line) and not re.search(r"[0-7]", line.replace("=", "").replace("1=", "")):
            return ""
        if re.match(r"^\s*1\s*=\s*[CDEFGAB]", line, re.IGNORECASE):
            return ""
        # 跳过小节号行（如 [5] [9] [13] 等）
        if re.match(r"^\s*[\[\(]?\d{1,2}[\]\)]?\s*$", line.strip()):
            return ""

        # ── 行级预处理 ──
        line = line.replace("—", "-").replace("–", "-").replace("_", "-")
        # 附点符号（中点）：'·' 在数字间是附点（1.5 倍时值）
        # 句号/小数点 → 视为低音点（trailing dot）
        # 注意：仅当 '·' 紧跟数字、且后面也是数字或分隔符时才视为附点
        line = re.sub(r"([0-7])·(?=\s*[\d|\-]|$)", r"\1*", line)
        line = line.replace("·", ".").replace("。", ".").replace("，", " ")
        line = line.replace("¡", ".").replace("ı", "1")  # ı→1（不是点）

        # OCR 字符替换（小节线 | 不动）
        # 注意顺序：先替换多字符序列，再替换单字符
        line = re.sub(r"(?<!\|)I(?!\|)", "1", line)   # I→1，但不影响 |
        line = line.replace("l", "1")
        line = line.replace("O", "0").replace("o", "0").replace("Q", "0")
        line = line.replace("S", "5").replace("s", "5")
        line = line.replace("Z", "2").replace("z", "2")
        line = line.replace("T", "7")
        line = line.replace("E", "3")
        # 注意：不在行级全局替换 b→6、A→4、e→3，避免破坏文字
        # 这些在字符级状态机中按上下文处理

        # 高音 i 标记归一化：
        # OCR 常将高音数字识别为 "i1", "i2", "i3" 等（i 紧跟数字）
        # 将其转换为 ".1", ".2", ".3" 等
        line = re.sub(r"\bi([1-7])", r".\1", line)
        # 独立 i（后面没有数字）→ 高音1的前缀标记
        line = re.sub(r"\bi\b(?!\d)", ".1_placeholder", line)
        
        # 数字粘连修复：如 "11" → "1 1"（简谱中相同数字紧挨着几乎总是两个独立音符）
        line = re.sub(r"([0-7])([0-7])", r"\1 \2", line)
        # 再跑一遍（处理3个连续的情况）
        line = re.sub(r"([0-7])([0-7])", r"\1 \2", line)

        line = re.sub(r"\s+", " ", line).strip()

        # ── 字符级状态机 ──
        symbols: List[str] = []
        i = 0
        n = len(line)

        while i < n:
            ch = line[i]

            # 跳过速度/节拍标记（=120, J=120 等）
            if ch == "=":
                i += 1
                while i < n and (line[i].isdigit() or line[i] in "JMC♩"):
                    i += 1
                continue

            # 高音占位符（独立 i 转换）
            if line[i:i+14] == ".1_placeholder":
                # 检查后面是否跟着数字
                j = i + 14
                while j < n and line[j] == " ":
                    j += 1
                if j < n and line[j] in "01234567":
                    symbol = "." + line[j]
                    i = j + 1
                    # 收集后置点
                    while i < n and line[i] == ".":
                        symbol += "."
                        i += 1
                    symbols.append(symbol)
                else:
                    # 独立 i 视为高音 1
                    symbols.append(".1")
                    i += 14
                continue

            # 数字 0–7
            if ch in "01234567":
                # 跳过紧跟在 = 后的调号数字
                if i > 0 and line[i - 1] == "=":
                    i += 1
                    continue

                symbol = ch
                i += 1
                # 收集后置附点（如 3.）和增时附点（'*'）
                while i < n and line[i] in ".*":
                    symbol += line[i]
                    i += 1
                symbols.append(symbol)
                continue

            # 前置点（高音：.1, .2, ..7 等）
            if ch == ".":
                dots = "."
                i += 1
                while i < n and line[i] == ".":
                    dots += "."
                    i += 1
                if i < n and line[i] in "01234567":
                    symbol = dots + line[i]
                    i += 1
                    # 收集后置附点
                    while i < n and line[i] == ".":
                        symbol += "."
                        i += 1
                    symbols.append(symbol)
                # 孤立点：忽略
                continue

            # 小节线
            if ch == "|":
                if i + 1 < n and line[i + 1] == "|":
                    symbols.append("||")
                    i += 2
                elif i + 1 < n and line[i + 1] == ":":
                    symbols.append("||")
                    i += 2
                else:
                    symbols.append("|")
                    i += 1
                continue

            # 重复记号结束 :||
            if ch == ":":
                if i + 1 < n and line[i + 1] == "|":
                    symbols.append(":||")
                    i += 2
                else:
                    i += 1
                continue

            # 延音线 / 空拍
            if ch in "-一":
                symbols.append("-")
                i += 1
                continue

            # 按上下文处理可能是数字的字母
            if ch in "bBAhHA":
                # 检查上下文：前后有数字则视为相应数字
                prev_is_note = bool(symbols) and (symbols[-1] in "1234567" or 
                                                   (len(symbols[-1]) > 0 and symbols[-1][-1] in "1234567."))
                next_ch = line[i+1] if i+1 < n else ""
                next_is_note = next_ch in "01234567.|-" or next_ch == " "
                
                if prev_is_note or next_is_note:
                    mapping = {"b": "6", "B": "6", "A": "4", "h": "4", "H": "4"}
                    d = mapping.get(ch)
                    if d:
                        symbol = d
                        i += 1
                        while i < n and line[i] == ".":
                            symbol += "."
                            i += 1
                        symbols.append(symbol)
                        continue
            
            i += 1

        return " ".join(symbols)

    def _clean_and_normalize(self, lines: List[str]) -> List[str]:
        """规范化 + 通用后处理"""
        all_symbols: List[str] = []
        for line in lines:
            for sym in line.split():
                all_symbols.append(self._normalize_dots(sym))

        all_symbols = self._fix_char_confusions(all_symbols)
        all_symbols = self._remove_spurious_zeros(all_symbols)
        all_symbols = self._deduplicate_barlines(all_symbols)
        all_symbols = self._remove_excess_consecutive(all_symbols)
        all_symbols = self._universal_post_process(all_symbols)

        return all_symbols

    # ──────────────────────── 通用后处理（乐理规则）──────────────────────

    def _fix_char_confusions(self, symbols: List[str]) -> List[str]:
        """
        修复残留的 OCR 字符混淆（逐符号映射）。
        只处理整体为单个字符的符号，不破坏带点的符号（如 .2, 3.）。

        改进：添加上下文修复，处理高音点被误拆分的情况：
        - '1 2' → '.2'（当 1 是小字符、位于 2 上方时）
        - 'l 2' → '.2'
        - 其他可能的混淆模式
        """
        result: List[str] = []
        i = 0
        while i < len(symbols):
            sym = symbols[i]

            # ── 上下文修复：检测被拆分的高音点 ──
            # 模式：1 2, l 2, i 2 → .2
            # 条件：前一个符号是小字符（可能是点），后一个是 2
            if i + 1 < len(symbols):
                curr = sym
                next_sym = symbols[i + 1]

                # 检查当前是否是可能是高音点的字符
                is_dot_like = (curr in ('1', 'l', 'i', 'I', '!', '.') and
                              len(curr) == 1)

                # 检查下一个是否是 2-7 的数字
                if is_dot_like and next_sym in '234567':
                    # 转换为 .X 格式
                    result.append('.' + next_sym)
                    logger.debug("修复高音点: %s %s → .%s", curr, next_sym, next_sym)
                    i += 2
                    continue

            # 标准处理
            if len(sym) == 1 and sym not in "01234567|-. ":
                d = correct_ocr_char(sym)
                result.append(d if d else sym)
            else:
                result.append(sym)
            i += 1

        return result

    def _remove_spurious_zeros(self, symbols: List[str]) -> List[str]:
        """
        移除上下文不合理的休止符 '0'。
        
        改进：更保守的策略，只删除明确错误的情况：
        - 删除：两侧都是同一音符，且 0 孤立出现（如 1 0 1）
        - 保留：小节内合理位置的休止符
        - 保留：0 后面跟 | 或 - 的情况（可能是真休止符）
        
        注意：简谱中休止符(0)是合法的，只在明确是O误识别时才删除
        """
        result: List[str] = []
        notes = set("1234567")
        for i, sym in enumerate(symbols):
            if sym == "0":
                prev_sym = result[-1] if result else ""
                nxt_sym = symbols[i + 1] if i + 1 < len(symbols) else ""
                prev_core = prev_sym[0] if prev_sym else ""
                nxt_core = nxt_sym[0] if nxt_sym else ""
                
                # 只在非常确定是误识别时才删除：
                # 两侧是相同音符（如 3 0 3），且不在小节线附近
                if (prev_core in notes and nxt_core in notes and 
                        prev_core == nxt_core and
                        prev_sym not in ("|", "") and nxt_sym not in ("|", "-")):
                    logger.debug("移除疑似误识别休止符 '0' 位置 %d (前=%s 后=%s)", i, prev_sym, nxt_sym)
                    continue
                # 行首孤立 0（小节线 | 后的 0 且后面跟数字）
                if prev_core == "|" and nxt_core in notes:
                    logger.debug("移除小节首疑似误识别休止符 '0' 位置 %d", i)
                    continue
            result.append(sym)
        return result

    def _deduplicate_barlines(self, symbols: List[str]) -> List[str]:
        """合并连续小节线"""
        result: List[str] = []
        for sym in symbols:
            if sym == "|" and result and result[-1] == "|":
                continue
            result.append(sym)
        return result

    def _remove_excess_consecutive(self, symbols: List[str]) -> List[str]:
        """
        移除同一音符连续出现超过 2 次的多余副本。
        简谱中同一音符连续 3 次以上极为罕见，通常是 OCR 重复识别。
        """
        result: List[str] = []
        run = 0
        prev = None
        for sym in symbols:
            if sym == prev and re.match(r"^[1-7]\.?$", sym):
                run += 1
                if run > 2:
                    logger.debug("去除连续重复音符: %s", sym)
                    continue
            else:
                run = 1
                prev = sym
            result.append(sym)
        return result

    def _universal_post_process(self, symbols: List[str]) -> List[str]:
        """
        通用乐理后处理（无歌曲特定逻辑）。

        规则均基于乐理通用性：
        1. 孤立附点合并：数字 + 孤立 '.' + 数字 → 数字. + 数字
        2. 附点前置归位：数字 + '.数字' → 数字. + 数字
        3. 基于音程合理性的 7/4 上下文纠错
        4. 去除调号前缀
        5. 清理过长的连续延音线
        """
        if not symbols:
            return symbols

        result = list(symbols)

        # ── 规则0：清理过长的连续延音线 ──
        # 连续3个以上的 '-' 通常不是真正的延音线，可能是OCR误识别
        result = self._clean_excessive_ties(result)

        # ── 规则1：孤立附点合并 ──
        # 模式：A '.' B → A. B（当 A 和 B 都是音符时）
        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(result) - 2:
                a, dot, b = result[i], result[i + 1], result[i + 2]
                a_is_note = re.match(r"^\.?[0-7]", a)
                b_is_note = re.match(r"^\.?[0-7]", b)
                if dot == "." and a_is_note and b_is_note and not a.endswith("."):
                    result[i] = a + "."
                    del result[i + 1]
                    changed = True
                    break
                i += 1

        # ── 规则2：'.数字' 与前置音符归并 ──
        # 模式：A '.' 'B' → A. B（OCR 有时将附点当作下一个符号前缀）
        # 注意：不能处理 .2、.3 等已合并的前置点格式！
        # 需要确保是独立的 '.' + '数字' 模式
        i = 0
        while i < len(result) - 1:
            a, dotb = result[i], result[i + 1]
            # 检查是否是 A '.' 'B' 模式（独立的点 + 数字）
            # 不能匹配 .2、.3 等已经合并的前置点格式
            if (re.match(r"^[1-7]$", a) and
                    dotb == '.' and
                    i + 2 < len(result) and
                    re.match(r"^[1-7]$", result[i + 2])):
                # 找到 A '.' B 模式
                result[i] = a + "."
                # 保留 B，移除中间的 '.'
                del result[i + 1]
                i += 2
                continue
            i += 1

        # ── 规则3：基于音程的 7 → 4 纠错 ──
        # 理论依据：7 与 4 字形相似；在中国简谱中，7 通常只在导音
        # 位置出现（紧邻 1 或 .1）；若 7 周围音符音程跨度过大（>4度），
        # 且 4 在该位置音程更合理，则替换。
        result = self._context_correct_7_to_4(result)

        # ── 规则4：修复附点音符 OCR 误识别 ──
        # 常见模式：
        # - 1 2 后跟休止或小节线 → .2（雪绒花等）
        # - 2 1 后跟休止或小节线 → .2
        result = self._fix_dotted_note_ocr_errors(result)

        return result

    def _clean_excessive_ties(self, symbols: List[str]) -> List[str]:
        """
        清理过长的连续延音线。
        
        改进：
        - 根据拍号动态决定最大允许延音线数量
        - 对 4/4 拍：最多允许 3 个连续 '-'（四分音符 + 三拍延音 = 全音符）
        - 对 3/4 拍：最多允许 2 个连续 '-'
        - 对 2/4 拍：最多允许 1 个连续 '-'
        """
        cfg = self.cfg
        max_ties = cfg.max_consecutive_ties
        
        result = list(symbols)
        i = 0
        while i < len(result):
            if result[i] == "-":
                j = i + 1
                while j < len(result) and result[j] == "-":
                    j += 1
                
                run_length = j - i
                
                if run_length > max_ties:
                    logger.debug(
                        "清理过长延音线: %d个连续'-'在位置 %d-%d, 截断为%d个",
                        run_length, i, j - 1, max_ties
                    )
                    result = result[:i + max_ties] + result[j:]
                    i = i + max_ties
                else:
                    i = j
            else:
                i += 1
        
        return result

    def _context_correct_7_to_4(self, symbols: List[str]) -> List[str]:
        """
        通用的 7 → 4 纠错。
        
        改进：更保守的策略，只在以下情况替换：
        - 7 的前后音符都在 [3,5] 范围内（四度以内跳进合理）
        - 7 不在小节末尾（末尾的 7 更可能是真正的导音）
        - 7 的前后不是 1（1 附近的 7 通常是合法导音）
        
        注意：7 → 4 是有损操作，过于激进会破坏正确的乐曲。
        """
        note_indices = [
            i for i, s in enumerate(symbols)
            if s and re.match(r"^\.?[1-7]", s)
        ]

        def core_digit(s: str) -> int:
            m = re.search(r"[1-7]", s)
            return int(m.group()) if m else 0

        result = list(symbols)
        for pos in note_indices:
            if not (result[pos] and core_digit(result[pos]) == 7):
                continue
            
            # 7 在小节末尾（后面跟 | 或 -）不替换
            next_sym = symbols[pos + 1] if pos + 1 < len(symbols) else ""
            if next_sym in ("|", "-", "||", ":||", ""):
                continue

            # 找前后最近的音符
            prev_pos = next((p for p in reversed(note_indices) if p < pos), None)
            next_pos = next((p for p in note_indices if p > pos), None)

            prev_d = core_digit(result[prev_pos]) if prev_pos is not None else 0
            next_d = core_digit(result[next_pos]) if next_pos is not None else 0

            # 如果前后有 1，则 7 很可能是合法导音，不替换
            if prev_d == 1 or next_d == 1:
                continue

            # 7 被 [3,5] 范围音符夹住（两侧都是中间音域），且音程跨度合理
            if (prev_d in (3, 4, 5) and next_d in (3, 4, 5)):
                logger.debug(
                    "通用纠错: 7 → 4 位置 %d (前=%d 后=%d)", pos, prev_d, next_d
                )
                sym = result[pos]
                result[pos] = re.sub(r"7", "4", sym, count=1)

        return result

    def _fix_dotted_note_ocr_errors(self, symbols: List[str]) -> List[str]:
        """
        修复附点音符的 OCR 误识别（通用规则）。

        改进：
        - 检测 X - - 模式（二分音符）中末尾多余的延音线
        - 修复前置附点被分离的情况
        - 修复雪绒花式的 X -- 误识别（2-- 应该是附点二分音符）
        - 修复 X Y 模式 → X - Y（相邻音符中间的短横线被误识别为音符）
        - 修复后置点被错误添加到音符上的情况（如 5. → 5）
        """
        if not symbols or len(symbols) < 3:
            return symbols

        result = list(symbols)

        # ── 规则0: 修复错误的后置点 ──
        # 在简谱中，X. 通常出现在乐句末尾，后面跟 | 或 -
        # 如果 X. 后面紧跟另一个音符 Y（不是 | 或 -），可能是误识别
        # 例如：5. 2 → 5 - 2（5 后面的点是延音线误识别）
        # 注意：不能修改 .2 等前置点格式！
        i = 0
        while i < len(result) - 1:
            sym = result[i]
            if re.match(r"^[1-7]\.$", sym):  # X. 格式（后置点）
                next_sym = result[i + 1]
                # 只在下一个是音符且不是 | 或 - 时才修改
                if (re.match(r"^[1-7]$", next_sym) and
                    next_sym not in ('|', '-')):
                    # 修复：X. → X，next_sym 保持不变（可能是下一个音符）
                    result[i] = sym[0]
                    logger.debug("修复后置点误识别: %s → %s", sym, sym[0])
            i += 1

        # ── 规则1: 修复被分离的前置附点 ──
        # 模式: X '.' '.Y' → X '.Y'（多余的孤立点被合并）
        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(result) - 2:
                a, dot, dot_b = result[i], result[i + 1], result[i + 2]
                if (dot == "." and
                    re.match(r"^\.[1-7]", dot_b) and
                    re.match(r"^[1-7]", a)):
                    result[i + 1] = dot_b
                    del result[i + 2]
                    changed = True
                    logger.debug("附点合并: %s %s %s → %s %s at pos %d",
                               a, dot, dot_b, a, dot_b, i)
                i += 1

        # ── 规则2: 修复相邻音符中间的延音线被误识别为音符 ──
        # 模式: X Y Z → X - Y Z（当 X 和 Z 是相邻音符，Y 是延音线误识别）
        # 常见模式：3 5 → 3 - 5, 1 2 → .1 - 2 等
        i = 0
        while i < len(result) - 2:
            a, b, c = result[i], result[i + 1], result[i + 2]

            # 检查是否是有效的音符模式
            a_is_note = bool(re.match(r"^\.?[1-7]$", a))
            c_is_note = bool(re.match(r"^\.?[1-7]$", c))

            if a_is_note and c_is_note:
                # 获取音符的核心数字
                a_core = re.search(r"[1-7]", a).group() if re.search(r"[1-7]", a) else ""
                c_core = re.search(r"[1-7]", c).group() if re.search(r"[1-7]", c) else ""

                # 如果 b 是小字符（如 1, 2, 3 等），可能是误识别的延音线或分隔
                if b in ('1', '2', '3', 'l', 'i', 'I', '!') and len(b) == 1:
                    # 检查是否可能是前置点的一部分
                    # 如果 a 是高音（.X），则 b 可能是下一个音符
                    # 否则，b 可能是延音线误识别
                    if not a.startswith('.'):
                        # 将 b 替换为延音线
                        result[i + 1] = '-'
                        logger.debug("修复延音线误识别: %s %s %s → %s - %s",
                                   a, b, c, a, c)
                        i += 1
                        continue

            i += 1

        # ── 规则3: 修复 1 2 模式（可能应该是 .2）──
        # 在简谱中，1 和 2 很少紧挨着，除非有特殊含义
        # 更可能是 .2 被拆分
        i = 0
        while i < len(result) - 1:
            if result[i] in ('1', 'l', 'i', 'I') and result[i + 1] == '2':
                # 检查上下文：如果前一个是小节开头或者有延音线，更可能是 .2
                if i == 0 or result[i - 1] in ('|', '-', ' '):
                    result[i] = '.2'
                    del result[i + 1]
                    logger.debug("修复高音点 .2: 1 2 → .2 at pos %d", i)
                    continue
            i += 1

        # ── 规则4: 修复 3/4 拍中的 .2 - - 模式 ──
        # 雪绒花等 3/4 拍歌曲常见 .2 - -（附点二分音符）
        # OCR 可能误识别为各种模式
        i = 0
        while i < len(result):
            sym = result[i]

            # 模式: .2 后跟多个延音线（正确）
            # 模式: . 后跟 2 和延音线（可能被误识别）
            if sym == '.' and i + 1 < len(result):
                next_sym = result[i + 1]
                if next_sym == '2':
                    # 检查后面是否跟着延音线
                    if i + 2 < len(result) and result[i + 2] == '-':
                        # 确认是 .2 - - 模式
                        result[i] = '.2'
                        logger.debug("修复附点音符: . 2 - → .2 -")
                        i += 1
                        continue

            i += 1

        # ── 规则5: 修复 .3 - 5 模式（应该是 .2 - -）──
        # OCR 可能将 .2 - - 误识别为 .3 - 5
        # 检测模式：.X - Y，当 Y 与 X 相邻时可能误识别
        # 注意：不能修改 .2 - - 模式，这是合法的高音附点二分音符！
        i = 0
        while i < len(result) - 2:
            a, b, c = result[i], result[i + 1], result[i + 2]
            if re.match(r"^\.[1-7]$", a) and b == '-' and re.match(r"^[1-7]$", c):
                # 获取 .X 中的 X
                a_core = re.search(r"[1-7]", a).group()
                c_core = c
                # 检查音程：如果 c 与 a_core 相差 1 或 2，且不是 .2 - - 模式
                # .2 - - 是合法的高音附点二分音符，不能修改！
                try:
                    a_num = int(a_core)
                    c_num = int(c_core)
                    diff = abs(a_num - c_num)
                    # 如果音程在 1-2 度之间，且不是 .2 - - 模式，可能是误识别
                    # .2 - - 模式：a = .2, c = 2, diff = 0
                    if diff >= 1 and diff <= 2 and i + 3 < len(result) and result[i + 3] == '-':
                        # .X - Y - → .X - -（Y 是延音线误识别）
                        result[i + 2] = '-'
                        logger.debug("修复音符误识别: %s - %s → %s - -", a, c, a)
                except ValueError:
                    pass
            i += 1

        return result

    # ──────────────────────── 辅助工具 ───────────────────────────────

    def _normalize_dots(self, symbol: str) -> str:
        """规范化前置/后置点，确保格式一致"""
        leading = 0
        trailing = 0
        core = symbol
        while core.startswith("."):
            leading += 1
            core = core[1:]
        while core.endswith("."):
            trailing += 1
            core = core[:-1]
        if leading:
            return "." * leading + core
        if trailing:
            return core + "." * trailing
        return symbol

    def _detect_time_signature(self, all_text: List[str]) -> Tuple[int, int]:
        """
        从 OCR 文本中检测拍号（如 4/4, 3/4, 2/4）。
        返回 (分子, 分母) 元组，默认 (4, 4)。

        改进：增加对 OCR 误识别模式的处理：
        - 3 拍号后可能跟着换行或空格
        - 识别 "3" + 换行/空格 + "4" 模式
        - 识别 3/4 常见变体
        """
        full = " ".join(all_text)
        # 匹配常见拍号格式：4/4, 3/4, 2/4, 6/8
        m = re.search(r"(\d)\s*/\s*(\d)", full)
        if m:
            try:
                num, den = int(m.group(1)), int(m.group(2))
                if num in (2, 3, 4, 6) and den in (4, 8):
                    logger.info("检测到拍号: %d/%d", num, den)
                    return num, den
            except ValueError:
                pass
        # OCR 有时将 4/4 识别为 "44" 或 "4 4"
        if re.search(r"4\s*4", full):
            return 4, 4
        if re.search(r"3\s*4", full):
            return 3, 4
        if re.search(r"2\s*4", full):
            return 2, 4
        if re.search(r"2\s*8", full):
            return 2, 8
        if re.search(r"6\s*8", full):
            return 6, 8

        # ── 增强：OCR 可能将 3/4 误识别为单独 "3" ──
        # 检查标题区附近是否有单独的 "3" 后面紧跟换行
        # 这通常表示 3/4 拍号被 OCR 误识别为单独的数字
        if re.search(r"1\s*=\s*[CDEFGAB].*?\b3\b", full, re.DOTALL):
            # 3 出现在调号附近，很可能是 3/4 拍号
            logger.info("检测到拍号: 3/4（从标题区附近推断）")
            return 3, 4

        # 检查 3 是否紧跟在调号后面（常见于简谱格式）
        if re.search(r"(?:1\s*=\s*[CDEFGAB])\s*3\s*(?:\n|$|[^\d])", full):
            logger.info("检测到拍号: 3/4（从调号后推断）")
            return 3, 4

        return 4, 4  # 默认 4/4

    def _detect_from_title_region(self, img: Image.Image) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
        """
        裁剪图像顶部 ~22% 区域专门 OCR 标题信息（调号/拍号/速度）。

        标题区域内容格式高度规范化（1=X、X/Y、♩=N），
        在缩小的纯白背景上 OCR 准确率远高于全图扫描，
        且不受谱面歌词中数字（如小节号 [5][9]）干扰。

        返回 (调号, 拍号) 或 (None, None)。
        """
        import cv2

        try:
            w, h = img.size
            # 标题区高度：图像高度的 8%~22%
            top_h = max(120, int(h * 0.22))
            top_h = min(top_h, h // 2)
            crop = img.crop((0, 0, w, top_h))

            # 放大到至少 1200px 宽，提高 OCR 准确率
            target_w = max(1200, w)
            ratio = target_w / w
            crop_resized = crop.resize(
                (target_w, int(top_h * ratio)),
                Image.LANCZOS
            )
            # 高对比度处理（标题区域通常已经清晰，简单二值化即可）
            arr = np.array(crop_resized.convert("L"))
            _, binarized = cv2.threshold(arr, 0, 255,
                                         cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            arr_rgb = cv2.cvtColor(binarized, cv2.COLOR_GRAY2RGB)

            reader = get_ocr_reader()
            results = ocr_readtext(reader, arr_rgb)
            texts = [r[1] for r in results if len(r) > 1]
            logger.debug("标题区 OCR 文本: %s", texts)

            full = " ".join(texts)
            logger.debug("标题区原始文本: %r", full)

            # 预处理：统一常见的 OCR 误识别
            # "1" 可能被识别为 l / I / i（加粗样式下尤其常见）
            # "=" 可能被识别为 二/三/≡/—/＝
            normalized = re.sub(r"[lIi](?=\s*[=二≡—三＝＝])", "1", full)
            normalized = re.sub(r"[二三≡—＝＝]", "=", normalized)
            # 调号字母大小写
            normalized = normalized.replace("f", "F").replace("g", "G").replace(
                "d", "D").replace("a", "A").replace("e", "E").replace("c", "C")

            # 调号：匹配 1=X 格式（含升降号）
            key = None
            # 第1优先：降号在前（bB / ♭B）
            m = re.search(r"1\s*=\s*[b♭]\s*([CDEFGAB])", normalized)
            if m:
                key = m.group(1).upper() + "b"
            # 第2优先：升号在后（F# / G♯）
            if not key:
                m = re.search(r"1\s*=\s*([CDEFGAB])\s*([#♯])", normalized)
                if m:
                    key = m.group(1).upper() + "#"
            # 第3优先：无升降号
            if not key:
                m = re.search(r"1\s*=\s*([CDEFGAB])(?![#♯b♭\w])", normalized)
                if m:
                    key = m.group(1).upper()

            # 拍号：尽量匹配 X/Y 形式
            time_sig = None
            m = re.search(r"\b([2346])\s*/\s*([48])\b", full)
            if m:
                time_sig = (int(m.group(1)), int(m.group(2)))
            else:
                # OCR 把分数线识别成空格时（3 4 / 4 4）
                # 避免把音符序列中的数字对误认为拍号
                m = re.search(r"(?<!=)\b([234])\s+([48])\b(?!\s*[=])", normalized)
                if m:
                    time_sig = (int(m.group(1)), int(m.group(2)))

            return key, time_sig
        except Exception as exc:
            logger.debug("标题区识别失败: %s", exc)
            return None, None

    def _detect_key(self, all_text: List[str]) -> str:
        """
        从 OCR 文本行列表中检测调号。

        OCR 对 "1=X" 这行的常见误识别模式（按调号分类）：

          C调：1=C → "1=C", "l=C", "1≡C", "1-C", "I=C"
          D调：1=D → "1=D", "1=0"（D被识别为0）
          E调：1=E → "1=E", "1=3"（E被识别为3）
          F调：1=F → "1=F", "1二F", "1卫F", "1=卫", "1二", "l=F"
               OCR 常把 = 识别为 二/卫/三/≡/—
          G调：1=G → "1=G", "1=6"（G被识别为6）
          A调：1=A → "1=A", "1=4"（A被识别为4）
          B调：1=B → "1=B", "1=6"（B/G混淆）
          bB调：1=bB → "1=bB", "1=♭B"
          F#调：1=F# → "1=F#", "1=升F"

        策略：
          1. 预处理：统一 OCR 误识别的 = 号和调号字母
          2. 按优先级匹配：显式 1=X > X调 > Key:X
          3. 兜底：返回 C
        """
        full = " ".join(all_text)

        # ── 步骤1：统一 = 号的 OCR 误识别 ──
        # 把各种 = 的误识别统一成 "="
        full = re.sub(r"1\s*[二三≡—=＝]\s*", "1=", full)
        full = full.replace("1卫", "1=F").replace("l卫", "1=F")
        full = full.replace("l=", "1=").replace("I=", "1=")

        # ── 步骤2：统一调号字母的 OCR 误识别 ──
        # 在 "1=" 之后，修正常见的字母误识别
        def fix_key_letter(m: re.Match) -> str:
            raw = m.group(1).strip()
            # 数字误识别为字母
            letter_map = {
                "0": "D",   # D → 0
                "3": "E",   # E → 3（但要排除是音符的情况）
                "4": "A",   # A → 4
                "6": "G",   # G → 6（但要排除是音符的情况）
                "8": "B",   # B → 8（少见）
                # 字母大小写统一
                "c": "C", "d": "D", "e": "E", "f": "F",
                "g": "G", "a": "A", "b": "B",
                # 常见误识别
                "卫": "F", "于": "F", "于": "F",
                "升": "#",
                "♭": "b", "b": "b",
            }
            # 升降号处理
            accidental = ""
            if len(raw) > 1:
                if raw[1] in ("#", "♯", "升"):
                    accidental = "#"
                elif raw[1] in ("b", "♭", "降"):
                    accidental = "b"
            base = raw[0]
            base = letter_map.get(base, base).upper()
            # 验证是合法调号字母
            if base in "CDEFGAB":
                return "1=" + base + accidental
            return m.group(0)  # 无法识别，保持原样

        full = re.sub(r"1=(.{1,3})", fix_key_letter, full)

        # ── 步骤3：按优先级匹配调号 ──
        # 优先级1：显式 1=X 格式（最可靠）
        m = re.search(r"1\s*=\s*([CDEFGAB][#b]?)", full, re.IGNORECASE)
        if m:
            key = m.group(1).upper()
            logger.info("检测到调号(1=X格式): %s", key)
            return key

        # 优先级2：X调 格式
        m = re.search(r"([CDEFGAB][#b]?)\s*调", full, re.IGNORECASE)
        if m:
            key = m.group(1).upper()
            logger.info("检测到调号(X调格式): %s", key)
            return key

        # 优先级3：Key:X 格式（英文谱常见）
        m = re.search(r"[Kk]ey\s*[:：]\s*([CDEFGAB][#b]?)", full)
        if m:
            key = m.group(1).upper()
            logger.info("检测到调号(Key:X格式): %s", key)
            return key

        # 优先级4：从标题行附近查找孤立的调号字母
        # 简谱标题行通常在前几行，格式如 "1=C 4/4" 或 "C大调"
        for line in all_text[:5]:  # 只看前5行
            # 匹配行内孤立的 "=X" 模式
            m = re.search(r"=\s*([CDEFGAB][#b]?)\b", line, re.IGNORECASE)
            if m:
                key = m.group(1).upper()
                logger.info("检测到调号(行内=X): %s", key)
                return key

        logger.debug("未检测到调号，使用默认 C")
        return "C"

    def _detect_key_from_symbols(self, symbols: List[str]) -> str:
        """从符号列表推断调号（用于分割识别路径）"""
        full = " ".join(symbols)
        m = re.search(r"1\s*=\s*([CDEFGAB][#b]?)", full, re.IGNORECASE)
        return m.group(1).upper() if m else "C"


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────
def process_jianpu_image(
    image_path: str,
    output_dir: str = "./output",
    use_segmentation: bool = True,
    config: Optional[RecognizerConfig] = None,
) -> Dict:
    """
    简谱图片 → BD 谱完整管线。

    Args:
        image_path:       输入图片路径
        output_dir:       结果输出目录
        use_segmentation: 是否启用图像分割辅助识别
        config:           自定义识别参数，None 则使用默认值

    Returns:
        {
          'success': bool,
          'bd_text': str,
          'audio': ...,
          'output_dir': str,
          'recognition': dict,
        }
    """
    sep = "=" * 70
    logger.info("\n%s\n处理: %s\n%s", sep, image_path, sep)

    if not os.path.exists(image_path):
        logger.error("文件不存在: %s", image_path)
        return {"success": False, "error": "File not found"}

    cfg = config or RecognizerConfig(output_dir=output_dir)
    cfg.output_dir = output_dir

    # 检查环境变量以启用快速模式
    if os.environ.get("JIANPU_QUICK_MODE", "0") == "1":
        cfg.quick_mode = True
        cfg.skip_segmentation_fallback = True
        logger.info("快速模式已启用（JIANPU_QUICK_MODE=1）")

    # ── 步骤1：识别 ──
    recognizer = AdvancedJianpuRecognizer(
        use_segmentation=use_segmentation, config=cfg
    )
    recognition_result = recognizer.recognize(image_path)

    if not recognition_result.get("success"):
        logger.error("识别失败")
        return {"success": False, "error": "Recognition failed"}

    symbols = recognition_result["symbols"]
    logger.info(
        "识别方法: %s | 符号数: %d | 调号: %s",
        recognition_result.get("method"),
        len(symbols),
        recognition_result.get("key_signature"),
    )
    if recognition_result.get("low_confidence"):
        logger.warning("本次识别置信度较低，结果仅供参考")

    logger.debug("符号（前50）: %s", " ".join(symbols[:50]))

    # ── 步骤2：转换 BD 谱 ──
    logger.info("\n%s\n转换为 BD 谱\n%s", sep, sep)
    converter = JianpuToBDConverter()
    jianpu_text = " ".join(symbols)

    result = converter.process_text(
        jianpu_text,
        key_signature=recognition_result["key_signature"],
    )

    logger.info("BD 谱:\n%s", result["bd_text"])
    analysis = result["analysis"]
    logger.info(
        "演奏分析 — 总音符: %d  吹: %d  吸: %d  孔位: %s",
        analysis["total_notes"],
        analysis["blow_count"],
        analysis["draw_count"],
        analysis["hole_usage"],
    )

    # ── 步骤3：保存 ──
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    save_dir = os.path.join(output_dir, base_name)
    os.makedirs(save_dir, exist_ok=True)
    converter.save_results(
        result, save_dir, jianpu_text,
        recognition_result.get("key_signature", "C"), "C",
    )
    logger.info("结果已保存至: %s", save_dir)

    return {
        "success": True,
        "bd_text": result["bd_text"],
        "audio": result["audio"],
        "output_dir": save_dir,
        "recognition": recognition_result,
    }


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="简谱识别 → BD 谱转换")
    parser.add_argument("image_path", help="简谱图片路径")
    parser.add_argument("--no-segment", action="store_true", help="禁用图像分割，仅用 OCR")
    parser.add_argument("--output", "-o", default="./output", help="输出目录")
    parser.add_argument("--save-vis", action="store_true", help="保存分割可视化图")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速模式：减少预处理变体，跳过增强OCR和备用方案（约2-3倍加速）",
    )

    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    cfg = RecognizerConfig(
        output_dir=args.output,
        save_visualization=args.save_vis,
        quick_mode=args.quick,
        skip_segmentation_fallback=args.quick,  # 快速模式也跳过分割备用
    )

    res = process_jianpu_image(
        args.image_path,
        output_dir=args.output,
        use_segmentation=not args.no_segment,
        config=cfg,
    )

    print("\n处理成功!" if res["success"] else "\n处理失败")
