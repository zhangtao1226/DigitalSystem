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
        self.ocr = self._create_ocr()

    @staticmethod
    def _create_ocr():
        # self.ocr = PaddleOCR(
        #     doc_orientation_classify_model_dir=f"{settings.ocr_path}/PP-LCNet_x1_0_doc_ori_infer",
        #     textline_orientation_model_dir=f"{settings.ocr_path}/PP-LCNet_x1_0_textline_ori_infer",
        #     doc_unwarping_model_dir=f"{settings.ocr_path}/UVDoc_infer",
        #     text_detection_model_dir=f"{settings.ocr_path}/PP-OCRv5_server_det_infer",
        #     text_recognition_model_dir=f"{settings.ocr_path}/PP-OCRv5_server_rec_infer",
        #     use_textline_orientation=True,
        #     enable_mkldnn=True,
        # )
        return PaddleOCR(
            use_doc_orientation_classify=False,
            use_textline_orientation=False,
            use_doc_unwarping=False,
            # doc_unwarping_model_dir=f"{settings.ocr_path}/UVDoc_infer",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=f"{settings.ocr_path}/PP-OCRv5_mobile_det",
            # server_rec 更适合密集印刷文档，并与随程序发布的服务端识别模型对应。
            text_recognition_model_name="PP-OCRv5_server_rec",
            text_recognition_model_dir=f"{settings.ocr_path}/PP-OCRv5_server_rec_infer",
            # Windows 下长时间复用 Paddle Predictor 时，MKL-DNN 偶发在
            # 第二次 predict() 抛出 RuntimeError: Unknown exception。
            # 关闭后性能略有下降，但连续 OCR 任务更稳定。
            enable_mkldnn=False,
        )

    def detect(self, image, res_save=False):
        try:
            return self._predict(image, res_save)
        except RuntimeError as e:
            logger.exception(f"OCR推理引擎异常，正在重建模型后重试; {str(e)}")
            try:
                self.ocr = self._create_ocr()
                return self._predict(image, res_save)
            except Exception as retry_error:
                logger.exception(f"OCR重试失败; {str(retry_error)}")
                return []
        except Exception as e:
            logger.exception(f"OCR失败; {str(e)}")
            return []

    def _predict(self, image, res_save=False):
        result = self.ocr.predict(image)
        for res in result:
            if res_save:
                res.save_to_json(os.path.dirname(image))
            return res['rec_texts']
        return []
