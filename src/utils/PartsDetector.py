# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : PartsDetector.py
# @Time     : 2026/6/1 8:47
# @Desc     : 分件

import os
import time
import shutil
from queue import Queue

import cv2
import numpy as np
import pandas as pd
from pathlib import Path

from paddle.base.libpaddle.eager.ops.legacy import pir_run_program

from src.core.settings import settings

from src.utils.LoggerDetector import logger
from src.utils.ResultDetector import Result
from src.utils.ImageProcessor import ImageProcessor
from src.utils.StampTableCheck import StampTableCheck

from src.services.archive_stamp_service import archive_stamp_service


class PartsDetector:

    def __init__(self, dir_path:str):
        self.dir_path = dir_path

        self.images_queue = Queue()
        self._get_dir_images()

    def _get_dir_images(self):
        try:
            with os.scandir(self.dir_path) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        self.images_queue.put(os.path.basename(entry.path))

        except FileNotFoundError as e:
            logger.warning(f"当前文件夹未检测到扫描文件, 分件失败; 当前文件夹路径: {self.dir_path}; {str(e)}")


    def catalog(self, catalog_path:str) -> Result:
        """
        目录分件
        """
        # 校验导入目录的档案数
        df = pd.read_excel(catalog_path)
        # 筛选相关档号
        dir_name = os.path.basename(self.dir_path)
        dir_name_list = df[df["档号"].str.contains(dir_name)]
        if dir_name_list.empty:
            logger.warning(f"没有匹配到相关档号: 【{dir_name}】;")
            return Result.fail(message=f"没有匹配到相关档号: 【{dir_name}】;")

        catalog_list = dir_name_list[dir_name_list["密级"] == "否"]
        pages = catalog_list["页数"].sum()
        files_count = self.get_dir_files_count()

        if pages != files_count:
            logger.warning(f"导入目录页数与扫描件数不匹配")
            return Result.fail(message="导入目录页数与扫描件数不匹配")

        try:
            for index, series in catalog_list.iterrows():
                target_path = f"{self.dir_path}/{series.iloc[1]}"
                if not os.path.exists(target_path):
                    os.makedirs(target_path, exist_ok=True)
                self.move_images(target_path, series.iloc[7])
            return Result.success(code=1, message="分件成功")
        except PermissionError as e:
            logger.warning(f"没有权限访问图片; {str(e)}")
            return Result.fail(message="没有权限访问图片")
        except Exception as e:
            logger.warning(f"图片移动失败; {str(e)} ")
            return Result.fail(message="分件失败")

    def move_images(self, images_target_path:str, move_count:int):
        print(f"move_count: {move_count}")

        for i in range(move_count):
            print(i)
            image_name = self.images_queue.get()
            image_path = os.path.join(self.dir_path, image_name)
            target_path = os.path.join(images_target_path, image_name)
            print(f"image_path:{image_path}", f"target_path: {target_path}", sep='/')
            shutil.move(image_path, target_path)


    def get_dir_files_count(self):
        dir_count = 0
        for entry in os.scandir(self.dir_path):
            try:
                if entry.is_file(follow_symlinks=False):
                    dir_count += 1
            except PermissionError:
                pass
        return dir_count

    def stamp_parts(self, stamp_model):
        """
        归档章分件
        """
        # stamp_model_info = archive_stamp_service.get_by_name(stamp_model)
        # print(f"归档章模版信息： {stamp_model_info}")

        stamp_check = StampTableCheck()

        serial_number = 0
        current_folder = None
        while not self.images_queue.empty():
            image_path = self.images_queue.get()
            print(f"image_path: {image_path}")
            output_image = self.cut_image(image_path, area=1)

            stamp_result = stamp_check.has_stamp(output_image)

            if stamp_result:
                serial_number += 1
                dir_name = f"{os.path.basename(self.dir_path)}-{serial_number:04d}"
                current_folder = f"{self.dir_path}/{dir_name}"
                os.makedirs(current_folder, exist_ok=True)
            else:
                if current_folder is None:
                    current_folder = f"{self.dir_path}/uncategorized"
                    os.makedirs(current_folder, exist_ok=True)
                    logger.info(f"创建未分件文件夹: uncategorized")
            origin_image_path = f"{self.dir_path}/{image_path}"
            target_image_path = f"{current_folder}/{image_path}"
            shutil.move(origin_image_path, target_image_path)

            # os.remove(output_image)

        return Result.success(message="分件完成")

    def cut_image(self, image:str, area:int):
        image_process = ImageProcessor(f"{self.dir_path}/{image}")

        output_file_top = f"{settings.temp_path}/parts_temp_{image.split('.')[0][-4:]}_{int(time.time())}.jpg"
        if area == 1:
            image_process.extract_top(500).save(output_file_top)
        else:
            image_process.extract_bottom(500).save(output_file_top)
        return output_file_top

    def has_red_stamp(self, image_path:str):
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"无法读取图片: {image_path}")
            return False

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, np.array([0, 30, 30]), np.array([15, 255, 255])) | \
            cv2.inRange(hsv, np.array([160, 30, 30]), np.array([180, 255, 255]))

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        cv2.imwrite("mask.jpg", mask)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        print(f"contours: {len(contours)}")

        print(f"image_shape = {img.shape}")

        img_area = img.shape[0] * img.shape[1]

        print(f"img_area = {img_area}")
        for c in contours:
            area = cv2.contourArea(c)
            print(f"area = {area}")
            if area < 500:
                continue
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = w / h if h > 0 else 0

            print(f"aspect_ratio: {aspect_ratio};")

            if 1.5 < aspect_ratio < 6 and area > img_area * 0.001:
                logger.info(f"检测到归档章: area={area:.0f}, ratio={aspect_ratio:.2f}, x={x}, y={y}, w={w}, h={h}")
                return True

        logger.info("未检测到归档章!")
        return False

if __name__ == "__main__":
    dir_path = r"D:\ZT_Projects\scna_test\001\0008-WS-2025·Y·BGS"
    parts_detector = PartsDetector(dir_path=dir_path)

    images = parts_detector.stamp_parts(dir_path)
    for image in images:
        print(image, sep='/')

