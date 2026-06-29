# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : ImageProcessor.py
# @Time     : 2026/3/20 8:47
# @Desc     : 图片截取
import os
from PIL import Image

class ImageProcessor:
    def __init__(self, image_path):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"找不到图片文件:{image_path}")

        self.image_path = image_path
        self.image = Image.open(image_path)
        self.original_size = self.image.size

    def extract_top(self, target_height: int):
        width, height = self.image.size

        if target_height >= height:
            return self

        box = (0, 0, width, target_height)
        self.image = self.image.crop(box)
        return self

    def extract_bottom(self, target_height: int):
        width, height = self.image.size
        if target_height >= height:
            return self
        box = (0, height - target_height, width, height)
        self.image = self.image.crop(box)
        return self

    def save(self, output_path: str):
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        self.image.save(output_path)