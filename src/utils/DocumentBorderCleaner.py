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

    def __init__(self, shadow_threshold=170, padding=6, scan_limit=0.06, min_density=0.02):
        self.shadow_threshold = shadow_threshold
        self.padding = padding
        self.scan_limit = scan_limit
        self.min_density = min_density

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
        _, dark_mask = cv2.threshold(gray, self.shadow_threshold, 255, cv2.THRESH_BINARY_INV)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        closed_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)

        def detect_boundary(mask_strip, axis):
            projection = np.mean(mask_strip, axis=axis) / 255.0
            hits = projection > self.min_density
            max_gap = max(2, int(len(projection) * 0.02))
            leading_blank_limit = max(self.padding, max_gap)
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
                elif i >= leading_blank_limit:
                    break

            if last_hit >= 0:
                return min(last_hit + self.padding, len(projection))
            return 0

        top_limit = int(h * self.scan_limit)
        top_mask = closed_mask[:top_limit, :]
        top_d = detect_boundary(top_mask, axis=1)

        bottom_limit = int(h * (1 - self.scan_limit))
        bottom_mask = closed_mask[bottom_limit:, :][::-1]
        bottom_d = detect_boundary(bottom_mask, axis=1)

        left_limit = int(w * self.scan_limit)
        left_mask = closed_mask[:, :left_limit]
        left_d = detect_boundary(left_mask, axis=0)

        right_limit = int(w * (1 - self.scan_limit))
        right_mask = closed_mask[:, right_limit:][:, ::-1]
        right_d = detect_boundary(right_mask, axis=0)

        result = img_bgr.copy()
        if top_d > 0:
            result[:top_d, :] = bg_color
        if bottom_d > 0:
            result[h - bottom_d:, :] = bg_color
        if left_d > 0:
            result[:, :left_d] = bg_color
        if right_d > 0:
            result[:, w - right_d:] = bg_color

        if output_path:
            success, encoded = cv2.imencode(Path(input_path).suffix, result)
            if success:
                with open(output_path, 'wb') as f:
                    f.write(encoded.tobytes())
                logger.info(f"图像去黑边-处理成功: {Path(input_path).name} -> [顶:{top_d}, 底:{bottom_d}, 左:{left_d}, 右:{right_d}]")
            else:
                logger.error(f"图像去黑边-图片保存失败: {output_path}")