# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : archive_splitter.py
# @Desc      : 归档章检测 → 自动分件
# @Time      : 2026/6/3
# @Software  : PyCharm

import os
import shutil
import cv2
import numpy as np
from pathlib import Path


def has_red_stamp(image_path: str, debug=False) -> bool:
    """
    检测图片中是否存在红色归档章（红色矩形表格）
    返回 True/False
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"⚠️ 无法读取图片: {image_path}")
        return False

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 红色 HSV 范围（两段）
    mask = cv2.inRange(hsv, np.array([0, 30, 30]), np.array([15, 255, 255])) | \
           cv2.inRange(hsv, np.array([160, 30, 30]), np.array([180, 255, 255]))

    # 闭运算：填充印章内部空洞，使轮廓完整
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 过滤条件：面积 + 宽高比（归档章是宽扁矩形）
    img_area = img.shape[0] * img.shape[1]
    for c in contours:
        area = cv2.contourArea(c)
        if area < 500:
            continue
        x, y, w, h = cv2.boundingRect(c)
        aspect_ratio = w / h if h > 0 else 0

        # 归档章通常宽 > 高，宽高比 1.5~6 之间
        if 1.5 < aspect_ratio < 6 and area > img_area * 0.001:
            if debug:
                print(f"  ✅ 检测到归档章: area={area:.0f}, ratio={aspect_ratio:.2f}, "
                      f"x={x}, y={y}, w={w}, h={h}")
            return True

    if debug:
        print(f"  ❌ 未检测到归档章")
    return False


def split_archives(input_dir: str, output_dir: str, debug=False):
    """
    遍历 input_dir 中的图片，根据归档章检测结果分件

    逻辑：
      - 检测到归档章 → 创建新文件夹（新档案起点，当前页归入此文件夹）
      - 未检测到归档章 → 归入最近一次创建的文件夹

    Args:
        input_dir:  输入图片目录（按页码顺序命名，如 001.jpg, 002.jpg ...）
        output_dir: 输出根目录
        debug:      是否打印调试信息
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 按文件名排序（确保页码顺序正确）
    image_files = sorted(
        [f for f in input_path.iterdir()
         if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')],
        key=lambda f: f.name
    )

    if not image_files:
        print("⚠️ 未找到图片文件")
        return

    print(f"📂 共找到 {len(image_files)} 张图片，开始处理...\n")

    current_folder = None  # 当前档案文件夹
    archive_index = 0  # 档案编号
    page_count = 0  # 当前档案页数

    for img_file in image_files:
        stamp_found = has_red_stamp(str(img_file), debug=debug)

        if stamp_found:
            # 新档案起点：创建新文件夹
            archive_index += 1
            folder_name = f"archive_{archive_index:03d}"
            current_folder = output_path / folder_name
            current_folder.mkdir(exist_ok=True)
            page_count = 0
            print(f"📁 新建档案文件夹: {folder_name}  ← {img_file.name} (含归档章)")
        else:
            if current_folder is None:
                # 第一张图片就没有归档章，放入 uncategorized
                current_folder = output_path / "uncategorized"
                current_folder.mkdir(exist_ok=True)
                print(f"📁 创建未分类文件夹: uncategorized")

            print(f"  ↳ 归入 {current_folder.name}  ← {img_file.name}")

        # 复制图片到目标文件夹
        dest = current_folder / img_file.name
        shutil.copy2(str(img_file), str(dest))
        page_count += 1

    print(f"\n✅ 处理完成！共分出 {archive_index} 份档案，输出至: {output_dir}")


# ---- 主程序 ----
if __name__ == "__main__":
    INPUT_DIR = r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/stamp_test"
    OUTPUT_DIR = r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/stamp_output"

    split_archives(INPUT_DIR, OUTPUT_DIR, debug=True)