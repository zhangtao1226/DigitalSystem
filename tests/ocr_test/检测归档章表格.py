# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : 检测归档章表格.py
# @Desc      : 
# @Time      : 2026/6/3 09:36
# @Software  : PyCharm

import cv2
import numpy as np


def has_stamp_table(image_path: str, debug=False) -> bool:
    """
    通用归档章检测：不依赖颜色，通过检测矩形表格线结构判断
    适用于红色、黑色、蓝色等各种颜色印章
    """
    img = cv2.imread(image_path)
    if img is None:
        return False

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── 步骤1：自适应二值化（对光照不均匀的扫描件更鲁棒）──
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15,
        C=10
    )

    if debug:
        cv2.imwrite("debug_binary.png", binary)

    # ── 步骤2：分别提取横线和竖线 ──
    h, w = binary.shape

    # 横线核：宽度至少占图片宽度的 3%
    h_kernel_len = max(30, w // 30)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

    # 竖线核：高度至少占图片高度的 1%
    v_kernel_len = max(15, h // 80)
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

    # ── 步骤3：合并横竖线，找交叉点（表格节点）──
    table_mask = cv2.add(horizontal_lines, vertical_lines)

    if debug:
        cv2.imwrite("debug_table_lines.png", table_mask)

    # ── 步骤4：膨胀连接断线，找完整轮廓 ──
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    table_mask = cv2.dilate(table_mask, kernel, iterations=2)

    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = h * w
    candidates = []

    for c in contours:
        area = cv2.contourArea(c)
        if area < 500:
            continue

        x, y, cw, ch = cv2.boundingRect(c)
        aspect_ratio = cw / ch if ch > 0 else 0
        area_ratio = area / img_area

        # 归档章特征：
        #   - 宽高比 1.5~8（宽扁矩形）
        #   - 面积占图片 0.05%~5%（不会太大也不会太小）
        #   - 通常在图片上半部分（y < 图片高度40%）
        in_upper_region = y < h * 0.4

        if (1.5 < aspect_ratio < 8
                and 0.0005 < area_ratio < 0.05
                and in_upper_region):
            candidates.append((area, x, y, cw, ch, aspect_ratio))
            if debug:
                print(f"  候选区域: x={x}, y={y}, w={cw}, h={ch}, "
                      f"ratio={aspect_ratio:.2f}, area_ratio={area_ratio:.4f}")
                # 在原图上画出候选框
                cv2.rectangle(img, (x, y), (x + cw, y + ch), (0, 255, 0), 2)

    if debug and candidates:
        cv2.imwrite("debug_candidates.png", img)

    return len(candidates) > 0


def detect_stamp_region(image_path: str, debug=False):
    """
    返回归档章裁剪区域（numpy array），未检测到返回 None
    同时兼容红色和黑色印章：先尝试颜色检测，失败则用结构检测
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]

    # ── 优先：颜色检测（红色/蓝色章更快更准）──
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    color_masks = {
        'red': (
            cv2.inRange(hsv, np.array([0, 30, 30]), np.array([15, 255, 255])) |
            cv2.inRange(hsv, np.array([160, 30, 30]), np.array([180, 255, 255]))
        ),
        'blue': cv2.inRange(hsv, np.array([100, 30, 30]), np.array([140, 255, 255])),
    }

    for color_name, mask in color_masks.items():
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [c for c in contours if cv2.contourArea(c) > 500]
        if valid:
            largest = max(valid, key=cv2.contourArea)
            x, y, cw, ch = cv2.boundingRect(largest)
            aspect = cw / ch if ch > 0 else 0
            if 1.5 < aspect < 8:
                pad = 20
                x1, y1 = max(0, x - pad), max(0, y - pad)
                x2, y2 = min(w, x + cw + pad), min(h, y + ch + pad)
                print(f"✅ 颜色检测成功（{color_name}章）")
                return img[y1:y2, x1:x2]

    # ── 降级：结构检测（黑色章 / 颜色检测失败时）──
    print("🔄 颜色检测未命中，切换为结构检测...")

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 10
    )

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, w // 30), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 80)))
    table_mask = cv2.add(
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel),
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
    )

    dilate_k = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    table_mask = cv2.dilate(table_mask, dilate_k, iterations=2)

    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 500:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = cw / ch if ch > 0 else 0
        if 1.5 < aspect < 8 and y < h * 0.4 and 0.0005 < area / (h * w) < 0.05:
            candidates.append((area, x, y, cw, ch))

    if not candidates:
        print("❌ 结构检测也未找到归档章")
        return None

    # 取面积最大的候选
    _, x, y, cw, ch = max(candidates, key=lambda t: t[0])
    pad = 20
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(w, x + cw + pad), min(h, y + ch + pad)
    print(f"✅ 结构检测成功（黑色/深色章）")
    return img[y1:y2, x1:x2]

if __name__ == '__main__':
    # 检测有无归档章（用于分件判断）
    found = has_stamp_table(r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/表格ocr.png", debug=True)

    # 获取裁剪区域（用于 OCR）
    # region = detect_stamp_region("scan_page.png", debug=True)