# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test2.py
# @Time     : 2026/4/15 13:55
# @Desc     : 

import os
from typing import List, Optional

import twain

class ScannerDetector:

    # 色彩模式常量定义
    COLOR_MODE_BW = 0  # 黑白/二值
    COLOR_MODE_GRAY = 1  # 灰度
    COLOR_MODE_COLOR = 2  # 彩色

    # 支持的保存格式
    SUPPORT_FORMATS = ['bmp', 'jpg', 'png', 'pdf', 'tiff']

    def __init__(self):
        self.source = twain.SourceManager(parent_window=0)
        self.is_connected = False

        self.default_params = {
            'dpi': 300,
            'color_mode': self.COLOR_MODE_COLOR,
            'save_format': 'jpg',
            'save_path': os.path.join(os.getcwd(), 'scan_output'),
            'file_name': 'scan_image',
            'auto_deskew': True,  # 自动纠偏
            'auto_remove_border': True,  # 自动去黑边
            'manual_border': None  # 手动裁剪 (left, top, right, bottom) 英寸
        }

    def get_list_sources(self) -> List[str]:
        return self.source.GetSourceList()

    def connect_scanner(self, scanner_name=None):

        try:
            scan_list = self.get_list_sources()
            if len(scan_list) == 0:
                raise ValueError(f"未找到可用扫描仪")

            if scanner_name:
                if scanner_name not in scan_list:
                    raise ValueError(f'指定扫描仪不存在; {scanner_name}')
                result = self.source.OpenSource(scanner_name)
            else:
                result = self.source.OpenSource()

            if result:
                self.is_connected = True
                print(f"扫描仪连接成功; {result.GetSourceName()}")
                return True
            else:
                print("无法连接扫描仪")
                return False
        except Exception as e:
            print(f"扫描仪连接失败: {str(e)}")
            self.is_connected = False
            return False

    def set_scan_params(self, **kwargs):
        if not self.is_connected:
            print("错误：请先连接扫描仪")
            return False

        for key, value in kwargs.items():
            if key in self.default_params:
                if key == 'dpi' and isinstance(value, int) and value > 0:
                    self.default_params[key] = value
                elif key == 'color_mode' and value in [0, 1, 2]:
                    self.default_params[key] = value
                elif key == 'save_format' and value.lower() in self.SUPPORT_FORMATS:
                    self.default_params[key] = value.lower()
                elif key == 'save_path':
                    self.default_params[key] = value
                elif key == 'file_name':
                    self.default_params[key] = value
                elif key == 'auto_deskew' and isinstance(value, bool):
                    self.default_params[key] = value
                elif key == 'auto_remove_border' and isinstance(value, bool):
                    self.default_params[key] = value
                elif key == 'manual_border' and isinstance(value, tuple) and len(value) == 4:
                    if all(isinstance(x, (int, float)) and x >= 0 for x in value):
                        self.default_params[key] = value
                    else:
                        print(f"警告：手动裁剪区域值必须为非负数，使用默认值")
                else:
                    print(f"警告：参数 {key} 的值 {value} 无效，使用默认值")
            else:
                print(f"警告：不支持的参数 {key}")








if __name__ == "__main__":

    scanner = ScannerDetector()

    scan_list = scanner.get_list_sources()
    print(f"可用扫描仪: {scan_list}")

    scanner.connect_scanner()
