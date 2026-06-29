# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : DocumentContentDeskew.py
# @Time     : 2026/3/26 8:53
# @Desc     : 扫描件内容纠偏
import os
import cv2
import numpy as np
from pathlib import Path
from deskew import determine_skew
from skimage.transform import rotate

from src.utils.LoggerDetector import logger

class DocumentContentDeskew:
    def deskew_image(self, input_path: str, output_path: str) -> None:

        if not os.path.exists(input_path):
            logger.error(f"图片纠偏-文件不存在; {input_path}")
            return

        try:
            with open(input_path, "rb") as f:
                img_data = f.read()
            image = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.COLOR_BGR2GRAY)
        except Exception as e:
            logger.error(f"图片纠偏-cv2 读取图片失败; {str(e)}")
            return

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        angle = determine_skew(gray)
        logger.info(f"图片纠偏-检测到的倾斜角: {angle:.2f}; 修正图片路径:{input_path}")

        rotated = rotate(image, angle, resize=True, cval=1, mode='constant')
        rotated = (rotated * 255).astype(np.uint8)

        if output_path:
            success, encoded = cv2.imencode(Path(input_path).suffix, rotated)
            if success:
                with open(output_path, 'wb') as f:
                    f.write(encoded.tobytes())
                logger.info(f"图片纠偏-处理成功: {Path(input_path).name}, 修正倾斜角为：{angle:.2f}")
            else:
                logger.error(f"图片纠偏-图片保存失败: {output_path}")


if __name__ == "__main__":
    input_file = r"D:\scan_files\0008-WS-2027·Y·BGS\0008-WS-2027·Y·BGS-0005.jpg"
    output_file = r"D:\scan_files\0008-WS-2027·Y·BGS\0008-WS-2027·Y·BGS-0005_deskew.jpg"

    deskew = DocumentContentDeskew()
    deskew.deskew_image(input_file, output_file)
