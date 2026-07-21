# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : DocumentBorderCleaner.py
# @Time     : 2026/3/25 8:40
# @Desc     : 去黑边

import os
import cv2
import numpy as np
from PIL import Image
from pathlib import Path

from src.utils.LoggerDetector import logger

class DocumentBorderCleaner:

    def __init__(
        self,
        shadow_threshold=170,
        padding=6,
        scan_limit=0.06,
        min_density=0.02,
        neutral_tolerance=40,
        min_border_span=0.08,
        shadow_expand=8,
        shadow_neutral_tolerance=65,
        shadow_contrast=8,
        color_saturation_protect=40,
        color_protect_expand=2,
        color_object_group_expand=12,
        residual_edge_contrast=16,
        residual_neutral_ratio=0.55,
    ):
        self.shadow_threshold = shadow_threshold
        self.padding = padding
        self.scan_limit = scan_limit
        self.min_density = min_density
        # 黑色/灰色的三个颜色通道彼此接近，红章则具有很高的通道色差。
        self.neutral_tolerance = neutral_tolerance
        # 仅将形成一定长度的边缘连通块判定为黑边，避免清除页边文字。
        self.min_border_span = min_border_span
        # 黑线周围通常还有抗锯齿、压缩或扫描产生的中性灰过渡层。
        # 只允许从已确认的黑边核心向外扩展有限像素，避免扩大到正文区域。
        self.shadow_expand = shadow_expand
        self.shadow_neutral_tolerance = shadow_neutral_tolerance
        self.shadow_contrast = shadow_contrast
        # 页面外侧背景可以整体统一，但红章等彩色内容必须保留。
        self.color_saturation_protect = color_saturation_protect
        self.color_protect_expand = color_protect_expand
        self.color_object_group_expand = color_object_group_expand
        # 最终残边校验不依赖黑边连通块：整行/整列明显暗于页面背景时，
        # 作为连续边缘暗带清除。
        self.residual_edge_contrast = residual_edge_contrast
        self.residual_neutral_ratio = residual_neutral_ratio

    def clean(self, input_path, output_path=None):
        try:
            with open(input_path, 'rb') as f:
                img_data = f.read()
            img_bgr = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
            if img_bgr is None:
                logger.error(f"图像去黑边-无法读取文件: {input_path}")
                raise ValueError(f"图像去黑边-无法读取文件: {input_path}")

        except FileNotFoundError as fe:
            logger.error(f"图像去黑边-图片不存在: {input_path}; 原因: {str(fe)}")
            return

        except PermissionError as pe:
            logger.error(f"图像去黑边-没有权限读取文件: {input_path}; 原因: {str(pe)}")
            return
        except Exception as e:
            logger.error(f"图像去黑边-读取图片失败; {input_path}; 原因: {str(e)}")
            return

        h, w = img_bgr.shape[:2]

        center_region = img_bgr[h // 4:h * 3 // 4, w // 4:w * 3 // 4]
        bg_color = np.median(center_region, axis=(0, 1)).astype(np.uint8).tolist()

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        channel_max = np.max(img_bgr, axis=2).astype(np.int16)
        channel_min = np.min(img_bgr, axis=2).astype(np.int16)
        chroma = channel_max - channel_min

        # 只检测低亮度且接近中性色的像素。红章即使亮度较低，通道色差仍然
        # 很大，因此不会进入黑边候选掩码。
        neutral_dark = (gray < self.shadow_threshold) & (chroma <= self.neutral_tolerance)
        dark_mask = neutral_dark.astype(np.uint8) * 255

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        closed_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)

        def detect_boundary(mask_strip, axis):
            projection = np.mean(mask_strip, axis=axis) / 255.0
            hits = projection > self.min_density
            max_gap = max(2, int(len(projection) * 0.02))
            last_hit = -1
            quiet_count = 0

            for i, hit in enumerate(hits):
                if hit:
                    last_hit = i
                    quiet_count = 0
                    continue

                if last_hit >= 0:
                    quiet_count += 1
                    if quiet_count > max_gap:
                        break

            if last_hit >= 0:
                # exterior_depth 截止到黑边最内侧；padded_depth 额外进入正文
                # 少量像素，只用于清除黑线内侧的灰色过渡。
                exterior_depth = min(last_hit + 1, len(projection))
                padded_depth = min(exterior_depth + self.padding, len(projection))
                return exterior_depth, padded_depth
            return 0, 0

        top_limit = int(h * self.scan_limit)
        top_mask = closed_mask[:top_limit, :]
        top_exterior_d, top_d = detect_boundary(top_mask, axis=1)

        bottom_limit = int(h * (1 - self.scan_limit))
        bottom_mask = closed_mask[bottom_limit:, :][::-1]
        bottom_exterior_d, bottom_d = detect_boundary(bottom_mask, axis=1)

        left_limit = int(w * self.scan_limit)
        left_mask = closed_mask[:, :left_limit]
        left_exterior_d, left_d = detect_boundary(left_mask, axis=0)

        right_limit = int(w * (1 - self.scan_limit))
        right_mask = closed_mask[:, right_limit:][:, ::-1]
        right_exterior_d, right_d = detect_boundary(right_mask, axis=0)

        # 原实现会把检测到的整条边缘直接覆盖为背景色，页边红章也会随之
        # 消失。现在只清除边缘区域中形成长连通块的近黑色像素。
        edge_region = np.zeros((h, w), dtype=bool)
        if top_d > 0:
            edge_region[:top_d, :] = True
        if bottom_d > 0:
            edge_region[h - bottom_d:, :] = True
        if left_d > 0:
            edge_region[:, :left_d] = True
        if right_d > 0:
            edge_region[:, w - right_d:] = True

        component_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        component_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, component_kernel)
        label_count, labels, stats, _ = cv2.connectedComponentsWithStats(
            component_mask,
            connectivity=8,
        )
        selected_labels = np.zeros(label_count, dtype=bool)
        min_horizontal_span = max(12, int(w * self.min_border_span))
        min_vertical_span = max(12, int(h * self.min_border_span))
        confirmed_top = False
        confirmed_bottom = False
        confirmed_left = False
        confirmed_right = False

        for label_index in range(1, label_count):
            x, y, component_w, component_h, _ = stats[label_index]
            touches_top = component_w >= min_horizontal_span and top_d > 0 and y < top_d
            touches_bottom = (
                component_w >= min_horizontal_span
                and bottom_d > 0
                and y + component_h > h - bottom_d
            )
            touches_left = component_h >= min_vertical_span and left_d > 0 and x < left_d
            touches_right = (
                component_h >= min_vertical_span
                and right_d > 0
                and x + component_w > w - right_d
            )
            horizontal_border = touches_top or touches_bottom
            vertical_border = touches_left or touches_right
            if horizontal_border or vertical_border:
                selected_labels[label_index] = True
                confirmed_top = confirmed_top or touches_top
                confirmed_bottom = confirmed_bottom or touches_bottom
                confirmed_left = confirmed_left or touches_left
                confirmed_right = confirmed_right or touches_right

        # 通过标签查表一次性生成掩码，避免对每个连通块扫描整张图片。
        border_components = selected_labels[labels]

        # 第一层先清除严格识别出的黑边核心。
        core_remove_mask = edge_region & border_components & neutral_dark

        # 第二层从黑边核心向外吸收有限范围内的中性灰阴影。阈值相对于页面
        # 背景亮度自适应，但彩色像素（尤其红章）会被色差条件排除。
        bg_luminance = (
            0.114 * float(bg_color[0])
            + 0.587 * float(bg_color[1])
            + 0.299 * float(bg_color[2])
        )
        shadow_luminance_limit = max(
            self.shadow_threshold,
            min(250, int(bg_luminance - self.shadow_contrast)),
        )
        neutral_shadow = (
            (gray < shadow_luminance_limit)
            & (chroma <= self.shadow_neutral_tolerance)
        )

        if self.shadow_expand > 0 and np.any(core_remove_mask):
            expand_size = self.shadow_expand * 2 + 1
            expand_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (expand_size, expand_size),
            )
            expanded_from_core = cv2.dilate(
                core_remove_mask.astype(np.uint8),
                expand_kernel,
            ).astype(bool)
        else:
            expanded_from_core = core_remove_mask

        cleanup_edge_region = np.zeros((h, w), dtype=bool)
        if top_d > 0:
            cleanup_edge_region[:min(h, top_d + self.shadow_expand), :] = True
        if bottom_d > 0:
            cleanup_edge_region[max(0, h - bottom_d - self.shadow_expand):, :] = True
        if left_d > 0:
            cleanup_edge_region[:, :min(w, left_d + self.shadow_expand)] = True
        if right_d > 0:
            cleanup_edge_region[:, max(0, w - right_d - self.shadow_expand):] = True

        shadow_remove_mask = cleanup_edge_region & expanded_from_core & neutral_shadow

        # 对已确认黑边朝图片物理边缘的一侧进行背景统一。与前面的 8 像素
        # 阴影扩展不同，这里会覆盖黑边外侧的整片灰色区域。
        exterior_region = np.zeros((h, w), dtype=bool)
        if confirmed_top and top_exterior_d > 0:
            exterior_region[:top_exterior_d, :] = True
        if confirmed_bottom and bottom_exterior_d > 0:
            exterior_region[h - bottom_exterior_d:, :] = True
        if confirmed_left and left_exterior_d > 0:
            exterior_region[:, :left_exterior_d] = True
        if confirmed_right and right_exterior_d > 0:
            exterior_region[:, w - right_exterior_d:] = True

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        protected_color = hsv[:, :, 1] >= self.color_saturation_protect
        original_color_pixels = protected_color.copy()
        # 对印章圆环等彩色轮廓填充其内部区域，避免只保留红色笔画、却把
        # 印章内部的浅色底纹误当作页面外侧背景覆盖。
        color_contours, _ = cv2.findContours(
            protected_color.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        filled_color_objects = protected_color.astype(np.uint8)
        for contour in color_contours:
            if cv2.contourArea(contour) >= 4:
                cv2.drawContours(
                    filled_color_objects,
                    [contour],
                    -1,
                    1,
                    thickness=cv2.FILLED,
                )
        protected_color = filled_color_objects.astype(bool)

        # 印章被图片边缘截断时，圆环轮廓不一定闭合。将临近的彩色笔画
        # 分组后，保护其整体包围框与边缘区域的交集，保留印章内部底色。
        if self.color_object_group_expand > 0 and np.any(original_color_pixels):
            group_size = self.color_object_group_expand * 2 + 1
            group_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (group_size, group_size),
            )
            grouped_color = cv2.dilate(
                original_color_pixels.astype(np.uint8),
                group_kernel,
            )
            group_count, group_labels, group_stats, _ = cv2.connectedComponentsWithStats(
                grouped_color,
                connectivity=8,
            )
            for group_index in range(1, group_count):
                x, y, group_w, group_h, _ = group_stats[group_index]
                group_roi = group_labels[y:y + group_h, x:x + group_w] == group_index
                exterior_roi = exterior_region[y:y + group_h, x:x + group_w]
                if not np.any(group_roi & exterior_roi):
                    continue
                protected_color[y:y + group_h, x:x + group_w] = True

        if self.color_protect_expand > 0 and np.any(protected_color):
            protect_size = self.color_protect_expand * 2 + 1
            protect_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (protect_size, protect_size),
            )
            protected_color = cv2.dilate(
                protected_color.astype(np.uint8),
                protect_kernel,
            ).astype(bool)

        exterior_remove_mask = exterior_region & ~protected_color

        # 独立残边校验。某些扫描黑边很细或整体偏灰，可能达不到严格黑色
        # 阈值，或者在连通块确认阶段被过滤。整列/整行中位亮度不受少量
        # 正文文字影响，适合识别这种贯穿页面边缘的连续暗带。
        residual_luminance_limit = bg_luminance - self.residual_edge_contrast

        def detect_residual_depth(gray_strip, protected_strip, axis):
            median_luminance = np.median(gray_strip, axis=axis)
            neutral_ratio = np.mean(~protected_strip, axis=axis)
            hits = (
                (median_luminance < residual_luminance_limit)
                & (neutral_ratio >= self.residual_neutral_ratio)
            )
            hit_indexes = np.flatnonzero(hits)
            return int(hit_indexes[-1] + 1) if hit_indexes.size else 0

        top_scan = max(1, int(h * self.scan_limit))
        bottom_start = h - top_scan
        left_scan = max(1, int(w * self.scan_limit))
        right_start = w - left_scan

        residual_top_d = detect_residual_depth(
            gray[:top_scan, :],
            protected_color[:top_scan, :],
            axis=1,
        )
        residual_bottom_d = detect_residual_depth(
            gray[bottom_start:, :][::-1],
            protected_color[bottom_start:, :][::-1],
            axis=1,
        )
        residual_left_d = detect_residual_depth(
            gray[:, :left_scan],
            protected_color[:, :left_scan],
            axis=0,
        )
        residual_right_d = detect_residual_depth(
            gray[:, right_start:][:, ::-1],
            protected_color[:, right_start:][:, ::-1],
            axis=0,
        )

        residual_region = np.zeros((h, w), dtype=bool)
        if residual_top_d > 0:
            residual_region[:residual_top_d, :] = True
        if residual_bottom_d > 0:
            residual_region[h - residual_bottom_d:, :] = True
        if residual_left_d > 0:
            residual_region[:, :residual_left_d] = True
        if residual_right_d > 0:
            residual_region[:, w - residual_right_d:] = True

        residual_remove_mask = residual_region & ~protected_color
        remove_mask = (
            core_remove_mask
            | shadow_remove_mask
            | exterior_remove_mask
            | residual_remove_mask
        )
        result = img_bgr.copy()
        result[remove_mask] = bg_color

        if output_path:
            success, encoded = cv2.imencode(Path(input_path).suffix, result)
            if success:
                with open(output_path, 'wb') as f:
                    f.write(encoded.tobytes())
                logger.info(
                    f"图像去黑边-处理成功: {Path(input_path).name} -> "
                    f"[顶:{top_d}, 底:{bottom_d}, 左:{left_d}, 右:{right_d}, "
                    f"外侧背景:{int(np.count_nonzero(exterior_remove_mask))}, "
                    f"残边校验:[顶:{residual_top_d}, 底:{residual_bottom_d}, "
                    f"左:{residual_left_d}, 右:{residual_right_d}], "
                    f"清除像素:{int(np.count_nonzero(remove_mask))}]"
                )
            else:
                logger.error(f"图像去黑边-图片保存失败: {output_path}")
