# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : common_controller.py
# @Time     : 2026/4/27 9:40
# @Desc     :
import os
from fileinput import filename

import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote

from src.utils.LoggerDetector import logger
from src.core.settings import settings

load_dotenv(verbose=True)

SERVER_HOST = os.getenv("SERVER_HOST")
SERVER_PORT = os.getenv("SERVER_PORT")

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

class CommonController:

    def upload_image(self, image_path: str, target_path: Optional[str] = None):

        url = f'{BASE_URL}/api/v1/upload/image'
        try:
            with open(image_path, "rb") as image_file:
                files = {'file': image_file}
                data = {"target_path": target_path}
                response = requests.post(url, files=files, data=data)

            if response.status_code != 200:
                logger.error(f"上传图片失败; {response.status_code};")
                return ""
            else:
                logger.info(f"图片同步成功; code: {response.status_code}; message: {response.json()}")
                return response.json()["data"]["file_path"]

        except Exception as e:
            logger.error(f"图片同步到服务器失败;image_path: {image_path}; target_path: {target_path}; error: {e}")
            return ""

    def download_image(self, target_path: str, save_path: Optional[str] = None):
        url = f'{BASE_URL}/api/v1/image/view/{target_path}'
        print(f"url: {url}")
        response = requests.get(url)

        if response.status_code != 200:
            logger.error(f"下载图片到本地失败; status_code: {response.status_code}; message: {response.json()}; image_path: {target_path}")
            return ""
        if save_path is None:
            save_path = settings.local_save_path
        with open(save_path, "wb") as file:
            file.write(response.content)
            logger.info(f"下载图片成功; save_path: {target_path}")

        return save_path

    def image_ocr(self, image_path: str, is_save: bool = False):
        url = f'{BASE_URL}/api/v1/ocr'

        with open(image_path, "rb") as image_file:
            files = {'file': image_file}
            data = {"is_save": is_save}

            response = requests.post(url, files=files, data=data)
            print('response', response.json())

            # if response.status_code == 200:
            #     response = response.json()
            #     return response["data"]["file_path"]
            # else:
            #     logger.error(f"OCR 识别失败; status_code: {response.status_code}; message: {response.json()}")
            #     return ""







if __name__ == "__main__":
    cc = CommonController()
    # target_path = "0008-WS-2022·Y·BGS-0001"
    image_path = r'D:\ZT_Projects\scna_test\01_test\0008-WS-2026·Y·BGS\0008-WS-2026·Y·BGS-0001.jpg'

    # cc.upload_image(image_path, target_path)

    target_path = r'E:\ZTProject\DigitalSystem\uploads'
    dir_name = r'0008-WS-2027·Y·BGS-0001'
    filename = f'0008-WS-2021·Y·BGS-0001.jpg'
    save_path = r"D:\ZT_Projects\scna_test\test\0008-WS-2026·Y·BGS\0008-WS-2026·Y·BGS-0001.jpg"

    # cc.download_image(
    #     r"D:\ZT_Projects\scna_test\01_test\0008-WS-2026·Y·BGS\0008-WS-2026·Y·BGS-0001.jpg", save_path)

    cc.image_ocr(image_path=image_path, is_save=True)




