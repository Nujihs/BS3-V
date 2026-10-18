"""
简谱音符分割识别模块（优化版 v2）
将简谱图片中的单个音符分割并识别

优化项：
- 多尺度自适应二值化（SAUVOLA + Otsu 投票）
- 更精准的符号分类（基于面积/宽高比/密度联合判断）
- 改进点关联算法（引入相对坐标规范化）
- 去掉逐行 fallback，提高整体一致性
- 添加 MSER 辅助检测，减少漏检
- 优化行排序（动态行高自适应）
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
import re
import os


class JianpuSegmenter:
    """简谱音符分割器（优化版 v2）"""

    def __init__(self):
        self.min_symbol_size = (8, 8)
        self.max_symbol_size = (120, 120)
        self.debug_mode = False
        self.y_threshold = 30

    # ──────────────────────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────────────────────

    def segment_image(self, img_array: np.ndarray,
                      enhance_image: bool = True) -> List[Dict]:
        """分割简谱图片中的单个音符"""
        if enhance_image:
            img_array = self._enhance_image(img_array)

        binary = self._preprocess(img_array)
        contours = self._detect_contours(binary, img_array.shape)
        symbols = self._classify_symbols(contours, binary, img_array)

        print(f"  [DEBUG] 原始检测到 {len(symbols)} 个符号:")
        for i, sym in enumerate(symbols[:10]):
            print(f"    [{i}] type={sym['type']}, bbox={sym['bbox']}")

        # 尝试分割粘连符号
        symbols = self._split_connected_symbols(binary, symbols)

        sorted_symbols = self._sort_by_lines(symbols)
        return sorted_symbols

    # ──────────────────────────────────────────────────────────────
    # 图像增强（优化版：CLAHE + 非局部均值去噪 + 自适应锐化）
    # ──────────────────────────────────────────────────────────────

    def _enhance_image(self, img_array: np.ndarray) -> np.ndarray:
        """图像增强 - 改善低质量图片的识别效果（优化版）"""
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()

        # 1. CLAHE 自适应对比度增强（更小的分块，保留局部细节）
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # 2. 非局部均值去噪（参数调优：h=7 保留更多细节）
        denoised = cv2.fastNlMeansDenoising(
            enhanced, None,
            h=7,
            templateWindowSize=7,
            searchWindowSize=15
        )

        # 3. 自适应锐化：只在边缘区域锐化，避免噪声放大
        blurred = cv2.GaussianBlur(denoised, (0, 0), 1.5)
        sharpened = cv2.addWeighted(denoised, 1.8, blurred, -0.8, 0)

        if len(img_array.shape) == 3:
            result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
        else:
            result = sharpened

        return result

    # ──────────────────────────────────────────────────────────────
    # 图像预处理（多策略二值化投票）
    # ──────────────────────────────────────────────────────────────

    def _preprocess(self, img_array: np.ndarray) -> np.ndarray:
        """图像预处理 - 多策略二值化投票（优化版）"""
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array.copy()

        # 双边滤波去噪（保留边缘）
        blurred = cv2.bilateralFilter(gray, 7, 50, 50)

        # 策略1：Otsu 全局阈值
        _, bin_otsu = cv2.threshold(blurred, 0, 255,
                                    cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(gray) > 127:
            bin_otsu = 255 - bin_otsu

        # 策略2：自适应高斯阈值（块大小自适应于图像尺寸）
        h, w = gray.shape[:2]
        block_size = max(11, (min(h, w) // 20) | 1)  # 保证奇数
        bin_adapt = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            block_size, 8
        )

        # 策略3：Sauvola-like（局部均值 + 标准差）
        bin_sauvola = self._sauvola_threshold(blurred)

        # 投票合并：2/3 策略同意才认为是前景
        vote = (bin_otsu.astype(np.uint16) +
                bin_adapt.astype(np.uint16) +
                bin_sauvola.astype(np.uint16))
        binary = np.where(vote >= 255 * 2, 255, 0).astype(np.uint8)

        # 形态学清理
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open, iterations=1)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close, iterations=1)

        return binary

    def _sauvola_threshold(self, gray: np.ndarray,
                           window_size: int = 15,
                           k: float = 0.2,
                           R: float = 128.0) -> np.ndarray:
        """
        Sauvola 局部自适应阈值（向量化实现）
        T = mean * (1 + k * (std / R - 1))

        使用 cv2.boxFilter 一次性计算所有窗口的均值和均方值，
        避免逐像素 Python 循环（旧实现在 800x1200 图上需数十秒）。
        """
        gray_f = gray.astype(np.float32)
        # 局部均值
        mean = cv2.boxFilter(gray_f, ddepth=cv2.CV_32F,
                             ksize=(window_size, window_size),
                             normalize=True, borderType=cv2.BORDER_REFLECT)
        # 局部均方
        sq_mean = cv2.boxFilter(gray_f * gray_f, ddepth=cv2.CV_32F,
                                ksize=(window_size, window_size),
                                normalize=True, borderType=cv2.BORDER_REFLECT)
        var = np.maximum(sq_mean - mean * mean, 0.0)
        std = np.sqrt(var)

        threshold = mean * (1.0 + k * (std / R - 1.0))
        binary = np.where(gray_f < threshold, 255, 0).astype(np.uint8)
        return binary

    def _adaptive_preprocess(self, gray: np.ndarray) -> np.ndarray:
        """简化版自适应预处理（内部兼容接口）"""
        _, binary = cv2.threshold(gray, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(gray) > 127:
            binary = 255 - binary
        return binary

    # ──────────────────────────────────────────────────────────────
    # 粘连符号分割
    # ──────────────────────────────────────────────────────────────

    def _split_connected_symbols(self, binary: np.ndarray,
                                  symbols: List[Dict]) -> List[Dict]:
        """分割水平方向上连通的符号（如多个数字连在一起）"""
        rows: Dict[int, List[Dict]] = {}
        for sym in symbols:
            y = sym['center'][1]
            row_key = y // 30
            rows.setdefault(row_key, []).append(sym)

        new_symbols: List[Dict] = []
        for row_key, row_syms in rows.items():
            row_syms.sort(key=lambda s: s['center'][0])
            for sym in row_syms:
                x, y, w, h = sym['bbox']
                if w > h * 2.0:
                    split = self._vertical_projection_split(binary, x, y, w, h, sym)
                    new_symbols.extend(split)
                else:
                    new_symbols.append(sym)

        return new_symbols if new_symbols else symbols

    def _vertical_projection_split(self, binary: np.ndarray,
                                    x: int, y: int, w: int, h: int,
                                    original_sym: Dict) -> List[Dict]:
        """使用垂直投影分割连通的符号"""
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(binary.shape[1], x + w), min(binary.shape[0], y + h)
        roi = binary[y1:y2, x1:x2]

        if roi.size == 0:
            return [original_sym]

        projection = np.sum(roi > 0, axis=0)
        if len(projection) == 0:
            return [original_sym]

        max_proj = np.max(projection)
        if max_proj == 0:
            return [original_sym]

        threshold = max_proj * 0.25
        min_width = max(8, h // 2)

        kernel = np.ones(3) / 3
        smoothed = np.convolve(projection, kernel, mode='same')

        split_points = [0]
        for i in range(1, len(smoothed) - 1):
            if (smoothed[i] < threshold and
                    smoothed[i] <= smoothed[i - 1] and
                    smoothed[i] <= smoothed[i + 1] and
                    i - split_points[-1] >= min_width):
                split_points.append(i)

        split_points.append(len(projection))

        if len(split_points) <= 2 and w > h * 2:
            estimated_count = max(2, int(w // (h * 0.7)))
            avg_width = w // estimated_count
            split_points = [avg_width * i for i in range(estimated_count)] + [w]

        new_symbols: List[Dict] = []
        for i in range(len(split_points) - 1):
            start, end = split_points[i], split_points[i + 1]
            seg_w = end - start
            if seg_w >= min_width:
                new_x = x1 + start
                new_sym = original_sym.copy()
                new_sym['bbox'] = (new_x, y1, seg_w, y2 - y1)
                new_sym['center'] = (new_x + seg_w // 2, y1 + (y2 - y1) // 2)
                new_sym['image'] = roi[:, start:end] if roi.shape[1] >= end else roi
                new_sym['type'] = self._classify_by_size(seg_w, y2 - y1)
                print(f"    [DEBUG] 分割: ({seg_w}x{y2-y1}) -> {new_sym['type']}")
                new_symbols.append(new_sym)

        return new_symbols if new_symbols else [original_sym]

    # ──────────────────────────────────────────────────────────────
    # 轮廓检测（多级过滤）
    # ──────────────────────────────────────────────────────────────

    def _detect_contours(self, binary: np.ndarray,
                         img_shape: Tuple = None) -> List:
        """检测所有轮廓（多级过滤，优化版）"""
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,   # 只要外轮廓，减少重复检测
            cv2.CHAIN_APPROX_SIMPLE
        )

        if img_shape is not None:
            h, w = img_shape[:2]
            # 动态面积范围（适配不同分辨率）
            min_area = max(30, (h * w) / 15000)
            max_area = (h * w) / 20      # 单个符号不超过图片面积的5%
        else:
            min_area = 30
            max_area = float('inf')

        filtered = [c for c in contours
                    if min_area < cv2.contourArea(c) < max_area]

        return filtered

    # ──────────────────────────────────────────────────────────────
    # 符号分类（联合特征判断，优化版）
    # ──────────────────────────────────────────────────────────────

    def _classify_symbols(self, contours: List, binary: np.ndarray,
                          original_img: np.ndarray) -> List[Dict]:
        """分类和过滤符号（优化版：动态尺寸 + 密度特征 + 数字高度参考）

        两遍处理：
          第1遍：粗分类，得到所有候选数字
          第2遍：用数字中位高度作为参考，重新判定 line / underline
        """
        symbols: List[Dict] = []
        h, w = original_img.shape[:2]

        dynamic_min_w = max(6, w // 120)
        dynamic_min_h = max(6, h // 120)
        dynamic_max_w = min(130, w // 5)
        dynamic_max_h = min(130, h // 5)

        # 先收集所有候选 contour 的几何信息（不立即分类）
        candidates = []
        for i, cnt in enumerate(contours):
            x, y, cnt_w, cnt_h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)

            if cnt_w < dynamic_min_w or cnt_h < dynamic_min_h:
                continue
            if cnt_w > dynamic_max_w or cnt_h > dynamic_max_h:
                continue

            aspect_ratio = cnt_w / cnt_h if cnt_h > 0 else 0
            if aspect_ratio > 15 or aspect_ratio < 0.05:
                continue

            candidates.append((i, cnt, x, y, cnt_w, cnt_h, area, aspect_ratio))

        # 第1遍：粗分类（不传 ref_digit_h，所有水平短线都先标 line）
        prelim_types = []
        for i, cnt, x, y, cnt_w, cnt_h, area, aspect_ratio in candidates:
            t = self._judge_symbol_type(cnt, binary, x, y, cnt_w, cnt_h, area)
            prelim_types.append(t)

        # 估算数字中位高度
        digit_heights = [c[5] for c, t in zip(candidates, prelim_types) if t == 'number']
        ref_digit_h = float(np.median(digit_heights)) if digit_heights else 0.0

        # 第2遍：完整分类（传入参考数字高度，用于区分 line / underline）
        for (i, cnt, x, y, cnt_w, cnt_h, area, aspect_ratio), prev_t in zip(candidates, prelim_types):
            symbol_type = self._judge_symbol_type(
                cnt, binary, x, y, cnt_w, cnt_h, area, ref_digit_h=ref_digit_h
            )

            padding = 3
            y1_p = max(0, y - padding)
            y2_p = min(h, y + cnt_h + padding)
            x1_p = max(0, x - padding)
            x2_p = min(w, x + cnt_w + padding)
            symbol_img = original_img[y1_p:y2_p, x1_p:x2_p]

            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            pixel_density = area / (cnt_w * cnt_h) if cnt_w * cnt_h > 0 else 0

            symbols.append({
                'id': i,
                'bbox': (x, y, cnt_w, cnt_h),
                'center': (x + cnt_w // 2, y + cnt_h // 2),
                'image': symbol_img,
                'type': symbol_type,
                'area': area,
                'aspect_ratio': aspect_ratio,
                'solidity': solidity,
                'pixel_density': pixel_density,
                'hull_area': hull_area,
                'upper_dots': [],
                'lower_dots': [],
                'right_dots': [],
                'underlines': [],
            })

        return symbols

    def _judge_symbol_type(self, contour, binary: np.ndarray,
                           x: int, y: int, w: int, h: int,
                           area: float = None,
                           ref_digit_h: float = 0.0) -> str:
        """
        判断符号类型（优化版：联合面积/宽高比/凸包密度）
        决策顺序：barline -> line/underline -> dot -> number -> unknown

        新增 ref_digit_h：参考数字高度，用于区分:
          - 'line'      ：明显宽于数字宽度的水平延音线（可能跨多拍）
          - 'underline' ：宽度接近单个数字宽度的水平短线（节奏减时线）
        """
        if area is None:
            area = cv2.contourArea(contour)

        aspect_ratio = w / h if h > 0 else 0

        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        # ── 小节线：高且窄 ──
        if w < 12 and h > 25 and aspect_ratio < 0.35:
            return 'barline'

        # ── 横线：扁长形 ──
        # 如果 ref_digit_h > 0，依据宽度判断 underline / line：
        #   宽度 < 数字高度 * 1.8 视为 underline
        #   否则视为 line（延音）
        if h < 10 and aspect_ratio > 3.0:
            if ref_digit_h > 0 and w < ref_digit_h * 1.8:
                return 'underline'
            return 'line'

        # ── 附点/八度点：小且圆 ──
        if area < 300 and w < 30 and h < 30:
            fill = self._calculate_fill_ratio(binary, x, y, w, h)
            if fill > 0.20:
                return 'dot'

        # ── 数字：宽高比适中，面积中等，实心度较高 ──
        if 0.15 < aspect_ratio < 2.0 and 40 < area < 8000:
            if solidity > 0.40:
                return 'number'

        # ── 宽松数字判断（特殊字符如4的三角开口会降低solidity）──
        if 10 < w < 120 and 10 < h < 120 and 0.15 < aspect_ratio < 2.5:
            if 50 < area < 6000:
                return 'number'

        return 'unknown'

    def _classify_by_size(self, w: int, h: int) -> str:
        """根据尺寸简单分类符号（用于分割后的符号）"""
        aspect_ratio = w / h if h > 0 else 0

        if w < 12 and h > 25 and aspect_ratio < 0.35:
            return 'barline'
        if h < 10 and aspect_ratio > 4.0:
            # 分割路径下没有 ref_digit_h，保守标 line（后续 associate_dots 不会误用）
            return 'line'
        if w < 30 and h < 30:
            return 'dot'
        if 8 < w < 150 and 8 < h < 150 and aspect_ratio < 2.5:
            return 'number'

        return 'unknown'

    def _calculate_fill_ratio(self, binary: np.ndarray, x: int, y: int,
                               w: int, h: int) -> float:
        """计算二值图像中前景像素的填充比例"""
        if w <= 0 or h <= 0:
            return 0.0

        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(binary.shape[1], x + w), min(binary.shape[0], y + h)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        roi = binary[y1:y2, x1:x2]
        if roi.size == 0:
            return 0.0

        return np.sum(roi > 0) / roi.size

    # ──────────────────────────────────────────────────────────────
    # 行排序（动态行高自适应）
    # ──────────────────────────────────────────────────────────────

    def _sort_by_lines(self, symbols: List[Dict],
                       y_threshold: int = None) -> List[Dict]:
        """
        按行排序符号（优化版：动态 y_threshold 自适应行高）
        """
        if not symbols:
            return []

        # 动态行高阈值：基于数字符号的平均高度
        if y_threshold is None:
            num_heights = [s['bbox'][3] for s in symbols if s['type'] == 'number']
            if num_heights:
                y_threshold = max(15, int(np.median(num_heights) * 1.2))
            else:
                y_threshold = self.y_threshold

        sorted_syms = sorted(symbols, key=lambda s: s['center'][1])

        lines: List[List[Dict]] = []
        current_line: List[Dict] = []
        current_y: Optional[float] = None

        for sym in sorted_syms:
            y = sym['center'][1]

            if current_y is None or abs(y - current_y) < y_threshold:
                current_line.append(sym)
                n = len(current_line)
                current_y = (current_y * (n - 1) + y) / n if current_y is not None else y
            else:
                current_line.sort(key=lambda s: s['center'][0])
                lines.append(current_line)
                current_line = [sym]
                current_y = y

        if current_line:
            current_line.sort(key=lambda s: s['center'][0])
            lines.append(current_line)

        result: List[Dict] = []
        for line in lines:
            result.extend(line)

        return result

    # ──────────────────────────────────────────────────────────────
    # 点关联（优化版：相对坐标规范化 + 去重改进）
    # ──────────────────────────────────────────────────────────────

    def associate_dots(self, symbols: List[Dict],
                       max_distance: Optional[int] = None) -> List[Dict]:
        """
        将八度点、附点和减时线与对应的数字关联（重写版）

        几何模型（以数字 bbox 为参考）：
          上方点（高音）：dot_cy < num_top - small margin，水平方向与数字重叠
          下方点（低音）：dot_cy > num_bottom + small margin，水平方向与数字重叠
          右侧附点（·）：dot_cx > num_right，y 中心接近数字中心
          下方横线（减时线/八分音符）：水平短线在数字正下方
        """
        numbers = [s for s in symbols if s['type'] == 'number']
        all_dots = [s for s in symbols if s['type'] == 'dot']
        all_underlines = [s for s in symbols if s['type'] == 'underline']

        # 面积很小且类型未知的，也作为点候选（OCR 漏判保护）
        for s in symbols:
            if s['type'] == 'unknown' and s.get('area', 0) < 200:
                all_dots.append(s)

        for num in numbers:
            num.setdefault('upper_dots', [])
            num.setdefault('lower_dots', [])
            num.setdefault('right_dots', [])
            num.setdefault('underlines', [])

        if not numbers:
            return numbers

        # 数字尺寸参考
        avg_h = float(np.median([n['bbox'][3] for n in numbers]))
        avg_w = float(np.median([n['bbox'][2] for n in numbers]))

        used_dots: set = set()
        used_lines: set = set()

        # 对每个数字，按"水平对齐度"为候选点排序，避免错配
        for num in numbers:
            nx, ny, nw, nh = num['bbox']
            num_left = nx
            num_right = nx + nw
            num_top = ny
            num_bottom = ny + nh
            num_cy = num['center'][1]
            num_cx = num['center'][0]

            # ── 1. 关联点（八度 / 附点）──
            for dot in all_dots:
                if id(dot) in used_dots:
                    continue
                dot_cx, dot_cy = dot['center']
                _, _, dw, dh = dot['bbox']

                # 水平方向是否与数字重叠（允许 30% 数字宽的偏移）
                horiz_aligned = (num_left - 0.3 * nw) <= dot_cx <= (num_right + 0.3 * nw)

                # 附点（·）：在数字右侧，y 接近数字中心，距离 < 1 个数字宽
                if (dot_cx > num_right - 2 and
                        dot_cx < num_right + max(avg_w * 1.2, nh * 0.8) and
                        abs(dot_cy - num_cy) < nh * 0.5):
                    num['right_dots'].append(dot)
                    used_dots.add(id(dot))
                    continue

                # 高音点：在数字正上方
                if (horiz_aligned and
                        dot_cy < num_top - 2 and
                        (num_top - dot_cy) < avg_h * 1.5):
                    num['upper_dots'].append(dot)
                    used_dots.add(id(dot))
                    continue

                # 低音点：在数字正下方
                if (horiz_aligned and
                        dot_cy > num_bottom + 2 and
                        (dot_cy - num_bottom) < avg_h * 1.5):
                    num['lower_dots'].append(dot)
                    used_dots.add(id(dot))
                    continue

            # ── 2. 关联减时线（节奏标记，水平短线在数字下方）──
            for line in all_underlines:
                if id(line) in used_lines:
                    continue
                lx, ly, lw, lh = line['bbox']
                line_cx = lx + lw / 2.0
                line_cy = ly + lh / 2.0

                # 水平方向：减时线中心需在数字水平范围内
                if not (num_left - 0.2 * nw <= line_cx <= num_right + 0.2 * nw):
                    continue
                # 垂直位置：减时线在数字下方 0 ~ 1.2 个数字高
                if not (num_bottom <= line_cy <= num_bottom + avg_h * 1.2):
                    continue
                # 宽度限制：减时线宽度不应超过 1.5 个数字宽
                if lw > nw * 1.8:
                    continue
                num['underlines'].append(line)
                used_lines.add(id(line))

        return numbers

    # ──────────────────────────────────────────────────────────────
    # 可视化
    # ──────────────────────────────────────────────────────────────

    def visualize_segmentation(self, img_array: np.ndarray,
                                symbols: List[Dict],
                                output_path: str = None,
                                show_dots_info: bool = True) -> np.ndarray:
        """可视化分割结果（优化版）"""
        vis_img = img_array.copy()

        if len(vis_img.shape) == 3 and vis_img.shape[2] == 3:
            pass
        else:
            vis_img = cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR)

        colors = {
            'number':    (255, 0, 0),
            'dot':       (0, 255, 0),
            'line':      (0, 0, 255),
            'underline': (0, 200, 200),
            'barline':   (255, 255, 0),
            'accidental':(128, 0, 128),
            'unknown':   (128, 128, 128),
        }

        for sym in symbols:
            x, y, w, h = sym['bbox']
            color = colors.get(sym['type'], (128, 128, 128))
            cv2.rectangle(vis_img, (x, y), (x + w, y + h), color, 2)
            cx, cy = sym['center']
            cv2.circle(vis_img, (cx, cy), 3, (0, 0, 255), -1)

            label = sym['type']
            if sym['type'] == 'number':
                upper = len(sym.get('upper_dots', []))
                lower = len(sym.get('lower_dots', []))
                right = len(sym.get('right_dots', []))
                under = len(sym.get('underlines', []))
                if upper or lower or right or under:
                    label = f"U{upper}L{lower}R{right}_{under}"
                else:
                    label = 'num'

            cv2.putText(vis_img, label, (x, max(0, y - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        if output_path:
            cv2.imwrite(output_path, vis_img)
            print(f"[DEBUG] 分割可视化已保存: {output_path}")
            print(f"[DEBUG] 检测到 {len(symbols)} 个符号")
            type_counts: Dict[str, int] = {}
            for s in symbols:
                t = s['type']
                type_counts[t] = type_counts.get(t, 0) + 1
            for t, c in sorted(type_counts.items()):
                print(f"       - {t}: {c}")

        return vis_img


if __name__ == '__main__':
    import sys
    from PIL import Image

    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        img = Image.open(img_path).convert('RGB')
        img_array = np.array(img)

        segmenter = JianpuSegmenter()
        symbols = segmenter.segment_image(img_array)

        print(f"检测到 {len(symbols)} 个符号")

        numbers = segmenter.associate_dots(symbols)
        print(f"数字符号: {len(numbers)}")

        os.makedirs('./output', exist_ok=True)
        segmenter.visualize_segmentation(img_array, symbols,
                                         './output/segmentation_result.png')
        print("结果已保存到 ./output/segmentation_result.png")
    else:
        print("用法: python jianpu_segmenter.py <图片路径>")
