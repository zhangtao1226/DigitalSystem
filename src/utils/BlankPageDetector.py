# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : BlankPageDetector.py
# @Time     : 2026/6/15 10:08
# @Desc     : 空白页检测

import os
import re
import uuid

import cv2
import numpy as np

from src.utils.LoggerDetector import logger


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class BlankPageDetector:
    def __init__(
        self,
        std_threshold=18.0,
        mean_threshold_low=235,
        mean_threshold_high=250,
        dark_pixel_rate_threshold=0.003,
        ink_pixel_rate_threshold=0.03,
        edge_pixel_rate_threshold=0.015,
        crop_margin_ratio=0.04,
    ):
        self.std_threshold = std_threshold
        self.mean_threshold_low = mean_threshold_low
        self.mean_threshold_high = mean_threshold_high
        self.dark_pixel_rate_threshold = dark_pixel_rate_threshold
        self.ink_pixel_rate_threshold = ink_pixel_rate_threshold
        self.edge_pixel_rate_threshold = edge_pixel_rate_threshold
        self.crop_margin_ratio = crop_margin_ratio

    def is_blank(self, image_path):
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.error(f"无法读取图片: {image_path}")
            raise ValueError(f"无法读取图片: {image_path}")

        img = self._crop_content_area(img)
        mean_val = np.mean(img)
        std_val = np.std(img)

        dark_pixels = np.sum(img < 200)
        ink_pixels = np.sum(img < 230)
        total_pixels = img.size
        dark_ratio = dark_pixels / total_pixels
        ink_ratio = ink_pixels / total_pixels
        edge_ratio = self._edge_ratio(img)

        # 真实扫描空白页通常不是纯白，可能有灰底、轻微阴影或少量噪点。
        is_gray_blank = (
            std_val < self.std_threshold
            and mean_val > self.mean_threshold_low
            and dark_ratio < self.dark_pixel_rate_threshold
            and ink_ratio < self.ink_pixel_rate_threshold
            and edge_ratio < self.edge_pixel_rate_threshold
        )

        is_near_white_blank = (
            mean_val > self.mean_threshold_high
            and dark_ratio < self.dark_pixel_rate_threshold * 2
            and ink_ratio < self.ink_pixel_rate_threshold * 1.5
            and edge_ratio < self.edge_pixel_rate_threshold
        )

        is_blank_page = is_gray_blank or is_near_white_blank
        logger.info(
            f"空白页检测: {os.path.basename(image_path)}; "
            f"mean={mean_val:.2f}; std={std_val:.2f}; "
            f"dark={dark_ratio:.5f}; ink={ink_ratio:.5f}; "
            f"edge={edge_ratio:.5f}; blank={is_blank_page}"
        )

        return is_blank_page

    def _crop_content_area(self, img):
        h, w = img.shape[:2]
        margin_y = int(h * self.crop_margin_ratio)
        margin_x = int(w * self.crop_margin_ratio)

        if margin_y <= 0 or margin_x <= 0:
            return img
        if h - margin_y * 2 < 50 or w - margin_x * 2 < 50:
            return img

        return img[margin_y : h - margin_y, margin_x : w - margin_x]

    @staticmethod
    def _edge_ratio(img):
        try:
            blurred = cv2.GaussianBlur(img, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            return np.count_nonzero(edges) / edges.size
        except Exception as exc:
            logger.debug(f"空白页边缘检测失败，按 0 处理: {exc}")
            return 0.0

    def process_directory(
        self,
        dir_path,
        target_files=None,
        filename_prefix=None,
        start_index=1,
    ):
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"扫描目录不存在: {dir_path}")

        files = self._get_candidate_files(dir_path, target_files)
        deleted = []
        kept_files = []
        errors = []

        for f_name in files:
            f_path = os.path.join(dir_path, f_name)
            try:
                if self.is_blank(f_path):
                    os.remove(f_path)
                    deleted.append(f_name)
                    logger.info(f"已删除空白页: {f_path}")
                else:
                    kept_files.append(f_name)
            except Exception as exc:
                logger.error(f"空白页检测失败，保留文件: {f_path}; 原因: {exc}")
                errors.append({"file": f_name, "error": str(exc)})
                kept_files.append(f_name)

        rename = self._rename_in_order(
            dir_path=dir_path,
            files=kept_files,
            filename_prefix=filename_prefix,
            start_index=start_index,
        )
        kept_after_rename = [rename.get(name, name) for name in kept_files]

        return {
            "deleted": deleted,
            "rename": rename,
            "kept": kept_after_rename,
            "total_deleted": len(deleted),
            "total_kept": len(kept_after_rename),
            "errors": errors,
        }

    def _get_candidate_files(self, dir_path, target_files=None):
        if target_files is None:
            names = os.listdir(dir_path)
        else:
            names = [os.path.basename(name) for name in target_files]

        files = []
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            full_path = os.path.join(dir_path, name)
            if os.path.isfile(full_path) and self._is_supported_image(name):
                files.append(name)

        files.sort(key=self._sort_key)
        return files

    @staticmethod
    def _is_supported_image(file_name):
        return os.path.splitext(file_name)[1].lower() in IMAGE_EXTENSIONS

    @staticmethod
    def _sort_key(file_name):
        stem = os.path.splitext(os.path.basename(file_name))[0]
        matches = re.findall(r"(\d+)", stem)
        number = int(matches[-1]) if matches else 0
        return number, file_name

    def _rename_in_order(self, dir_path, files, filename_prefix=None, start_index=1):
        rename = {}
        if not files:
            return rename

        temp_token = uuid.uuid4().hex
        temp_items = []
        original_paths = {
            os.path.abspath(os.path.join(dir_path, name)) for name in files
        }

        for index, old_name in enumerate(files):
            old_path = os.path.join(dir_path, old_name)
            ext = os.path.splitext(old_name)[1]
            temp_name = f".blank_page_tmp_{temp_token}_{index:04d}{ext}"
            temp_path = os.path.join(dir_path, temp_name)
            os.rename(old_path, temp_path)
            temp_items.append((old_name, temp_path, ext))

        for offset, (old_name, temp_path, ext) in enumerate(temp_items):
            new_index = start_index + offset
            new_name = self._build_file_name(filename_prefix, new_index, ext)
            new_path = os.path.join(dir_path, new_name)
            abs_new_path = os.path.abspath(new_path)

            if os.path.exists(new_path) and abs_new_path not in original_paths:
                os.rename(temp_path, os.path.join(dir_path, old_name))
                raise FileExistsError(f"目标文件已存在，无法重命名: {new_path}")

            os.rename(temp_path, new_path)
            rename[old_name] = new_name
            if old_name != new_name:
                logger.info(f"扫描件重命名: {old_name} -> {new_name}")

        return rename

    @staticmethod
    def _build_file_name(filename_prefix, index, ext):
        if filename_prefix:
            return f"{filename_prefix}-{index:04d}{ext}"
        return f"{index:04d}{ext}"


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
