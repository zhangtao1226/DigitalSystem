# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : OCRDetector.py
# @Desc      : OCR识别
# @Time      : 2026/3/3 13:46
# @Software  : PyCharm
import os
import re
import time

from paddleocr import PaddleOCR

from src.core.settings import settings
from src.utils.LoggerDetector import logger

class OCRDetector:
    def __init__(self) -> None:

        # self.ocr = PaddleOCR(
        #     doc_orientation_classify_model_dir=f"{settings.ocr_path}/PP-LCNet_x1_0_doc_ori_infer",
        #     textline_orientation_model_dir=f"{settings.ocr_path}/PP-LCNet_x1_0_textline_ori_infer",
        #     doc_unwarping_model_dir=f"{settings.ocr_path}/UVDoc_infer",
        #     text_detection_model_dir=f"{settings.ocr_path}/PP-OCRv5_server_det_infer",
        #     text_recognition_model_dir=f"{settings.ocr_path}/PP-OCRv5_server_rec_infer",
        #     use_textline_orientation=True,
        #     enable_mkldnn=True,
        # )
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_textline_orientation=False,
            use_doc_unwarping=False,
            # doc_unwarping_model_dir=f"{settings.ocr_path}/UVDoc_infer",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=f"{settings.ocr_path}/PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            text_recognition_model_dir=f"{settings.ocr_path}/PP-OCRv5_mobile_rec",
            enable_mkldnn=True,
        )

    def detect(self, image, res_save=False):
        try:
            result = self.ocr.predict(image)
            for res in result:
                if res_save:
                    res.save_to_json(os.path.dirname(image))
                return res['rec_texts']
        except Exception as e:
            logger.exception(f"OCR失败; {str(e)}")
            return []