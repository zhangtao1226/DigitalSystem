# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : test_1.py
# @Desc      : 
# @Time      : 2026/6/3 08:57
# @Software  : PyCharm
import time

import cv2
import numpy as np
# from paddleocr import PaddleOCR
#
# ocr = PaddleOCR(
#     # use_angle_cls=False,
#     lang='ch',
# )


def detect_red_stamp_region(image_path, debug=True):
    """自动定位红色归档章区域，debug=True 时保存中间结果"""
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 红色 HSV 范围
    lower_red1 = np.array([0, 30, 30])    # 放宽阈值，避免漏检
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([160, 30, 30])  # 放宽阈值
    upper_red2 = np.array([180, 255, 255])

    mask = cv2.inRange(hsv, lower_red1, upper_red1) | \
           cv2.inRange(hsv, lower_red2, upper_red2)

    # 形态学处理：闭运算填充印章内部空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    if debug:
        cv2.imwrite("debug_mask.png", mask_closed)  # 查看红色区域检测效果

    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("⚠️ 未检测到红色区域，使用全图")
        return img

    # 过滤太小的轮廓（噪点），取面积最大的
    valid = [c for c in contours if cv2.contourArea(c) > 500]
    if not valid:
        print("⚠️ 有效轮廓为空，使用全图")
        return img

    largest = max(valid, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    print(f"📍 检测到印章区域: x={x}, y={y}, w={w}, h={h}")

    # 扩大裁剪边距
    pad = 20
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img.shape[1], x + w + pad)
    y2 = min(img.shape[0], y + h + pad)

    crop = img[y1:y2, x1:x2]

    if debug:
        cv2.imwrite("debug_crop.png", crop)  # 查看裁剪结果

    return crop


def preprocess(img):
    """图像预处理：适度放大 + 锐化"""
    # 放大 2 倍（不要太大，避免模糊）
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 锐化卷积核
    sharpen_kernel = np.array([
        [0, -1,  0],
        [-1, 5, -1],
        [0, -1,  0]
    ])
    img = cv2.filter2D(img, -1, sharpen_kernel)

    return img


def parse_result(result):
    """兼容新旧版本 PaddleOCR 结果解析"""
    texts = []
    if not result:
        return texts

    for res in result:
        # 新版 predict() 返回字典列表
        if isinstance(res, dict):
            rec_texts = res.get('rec_texts', [])
            rec_scores = res.get('rec_scores', [])
            for text, score in zip(rec_texts, rec_scores):
                if text.strip():
                    texts.append((text.strip(), score))

        # 旧版 ocr() 返回嵌套列表
        elif isinstance(res, list):
            for item in res:
                if item and len(item) >= 2:
                    text = item[1][0]
                    score = item[1][1]
                    if text.strip():
                        texts.append((text.strip(), score))

    return texts


def ocr_stamp(image_path):
    print(f"\n🔍 处理图片: {image_path}")

    # 1. 裁剪归档章区域
    stamp_region = detect_red_stamp_region(image_path, debug=True)

    # 2. 预处理
    stamp_region = preprocess(stamp_region)

    # 3. OCR 识别
    # result = ocr.predict(stamp_region)

    # 4. 解析结果
    # texts = parse_result(result)

    # print("\n📋 识别结果:")
    # for text, conf in texts:
    #     print(f"  内容: {text:<15} 置信度: {conf:.3f}")
    #
    # return texts


# ---- 主程序 ----
if __name__ == "__main__":
    t0 = time.time()
    images_list = [
        r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/12.jpg",
        # r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/img_9.png",
        # r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/img_10.png",
        # r"/Volumes/Projects/projects/ERREN/DigitalSystem/tests/ocr_test/images/img_11.png",

    ]

    for image in images_list:
        results = ocr_stamp(image)

    print(f"耗时: {time.time()-t0}")