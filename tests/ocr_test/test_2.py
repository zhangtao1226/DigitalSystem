# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : test_2.py
# @Desc      : 
# @Time      : 2026/6/3 09:19
# @Software  : PyCharm

# -*-coding  : utf-8 -*-
import cv2
import numpy as np
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_angle_cls=False,
    lang='ch',
)


def detect_red_stamp_region(image_path):
    """自动定位红色归档章区域 - 修复版"""
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 红色 HSV 范围
    lower_red1 = np.array([0, 30, 30])    # 降低阈值，覆盖更浅的红色
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([155, 30, 30])  # 扩大上界
    upper_red2 = np.array([180, 255, 255])

    mask = cv2.inRange(hsv, lower_red1, upper_red1) | \
           cv2.inRange(hsv, lower_red2, upper_red2)

    # 膨胀操作：将分散的红色像素连成整体
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask_dilated = cv2.dilate(mask, kernel, iterations=2)

    contours, _ = cv2.findContours(mask_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("⚠️ 未找到红色区域，使用全图")
        return img

    # 调试：查看所有轮廓大小，排查是否取错了轮廓
    for i, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)
        print(f"  轮廓 {i}: x={x}, y={y}, w={w}, h={h}, area={cv2.contourArea(c):.0f}")

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    # 增大 pad，确保文字不被截断
    pad = 20
    img_h, img_w = img.shape[:2]
    x = max(0, x - pad)
    y = max(0, y - pad)
    x2 = min(img_w, x + w + pad * 2)
    y2 = min(img_h, y + h + pad * 2)

    print(f"✅ 裁剪区域: x={x}, y={y}, x2={x2}, y2={y2}")

    # 保存裁剪结果用于调试
    crop = img[y:y2, x:x2]
    cv2.imwrite("debug_stamp_crop.png", crop)
    print("📁 裁剪图已保存为 debug_stamp_crop.png")

    return crop


def ocr_stamp(image_path):
    stamp_region = detect_red_stamp_region(image_path)

    # 放大
    scale = 3
    stamp_region = cv2.resize(
        stamp_region, None,
        fx=scale, fy=scale,
        interpolation=cv2.INTER_CUBIC
    )

    result = ocr.predict(stamp_region)

    texts = []
    for res in result:
        rec_texts = res['rec_texts']
        rec_scores = res['rec_scores']
        print(f"识别内容: {rec_texts}")
        print(f"置信度:   {[round(s, 3) for s in rec_scores]}")
        texts.extend(rec_texts)

    return texts


results = ocr_stamp(r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/表格ocr.png")