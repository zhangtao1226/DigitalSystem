# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : BlankPageDetector.py
# @Time     : 2026/6/15 10:08
# @Desc     : 空白页检测

import os
import re
import cv2
import numpy as np

from src.utils.LoggerDetector import logger


EXTENSIONS = ["jpg", "jpeg", "png"]

class BlankPageDetector:
    def __init__(self, std_threshold=5.0, mean_threshold_low=245, mean_threshold_high=250,
                 dark_pixel_rate_threshold=0.001):
        self.std_threshold = std_threshold
        self.mean_threshold_low = mean_threshold_low
        self.mean_threshold_high = mean_threshold_high
        self.dark_pixel_rate_threshold = dark_pixel_rate_threshold

    def is_blank(self, image_path):
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.error(f"无法读取图片: {image_path}")
            raise ValueError(f"无法读取图片: {image_path}")

        mean_val = np.mean(img)
        std_val = np.std(img)

        dark_pixels = np.sum(img < 200)
        total_pixels = img.size
        dark_ratio = dark_pixels / total_pixels

        is_white_blank = (
            std_val < self.std_threshold
            and mean_val > self.mean_threshold_low
            and dark_ratio < self.dark_pixel_rate_threshold
        )

        return is_white_blank

    def process_directory(self, dir_path):
        files = [f for f in os.listdir(dir_path) if f.lower().endswith(EXTENSIONS)]

        def extract_num(file_name):
            match = re.search(r'(\d+)', file_name)
            return int(match.group(1)) if match else 0

        files.sort(key=extract_num)

        deleted = []
        kept_paths = []

        for f_name in files:
            f_path = os.path.join(dir_path, f_name)
            if self.is_blank(f_path):
                os.remove(f_path)
                deleted.append(f_name)
            else:
                kept_paths.append(f_name)

        rename = {}
        temp_paths = []
        for i, f_path in enumerate(kept_paths):
            ext = os.path.splitext(f_path)[1]
            temp_path = os.path.join(dir_path, f"__temp__{i:04d}{ext}")
            os.rename(f_path, temp_path)
            temp_paths.append((temp_path, ext))

        for i, (temp_path, ext) in enumerate(temp_paths, start=1):
            new_name = f"{i:04d}{ext}"
            new_path = os.path.join(dir_path, new_name)
            os.rename(temp_path, new_path)
            rename[temp_path] = new_name

        return {
            "deleted": deleted,
            "rename": rename,
            "total_kept": len(kept_paths),
        }


if __name__ == "__main__":
    detector = BlankPageDetector(
        std_threshold=5.0,
        mean_threshold_low=245,
        dark_pixel_rate_threshold=0.001,
    )

    result = detector.process_directory(r"")

    print(f"删除空白页数量: {len(result['deleted'])}")
    print(f"删除的文件: {result['deleted']}")
    print(f"保留并重命名后的文件数量: {result['total_kept']}")
