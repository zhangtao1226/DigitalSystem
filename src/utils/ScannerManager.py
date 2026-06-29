# -*-coding: utf-8 -*-
# @Author   : zhangtao
# @FileName : scanner_manager.py
# @Desc     : 扫描仪操作管理类，支持参数配置和多种格式保存
# @Time     : 2025/12/8 18:03
# @Software : PyCharm
import twain
import os
import tempfile
from ctypes import c_void_p, c_int, c_long, c_float
from PIL import Image


class ScannerManager:
    """
    扫描仪管理类，封装TWAIN接口
    """
    # 色彩模式常量定义
    COLOR_MODE_BW = 0  # 黑白/二值
    COLOR_MODE_GRAY = 1  # 灰度
    COLOR_MODE_COLOR = 2  # 彩色

    # 支持的保存格式
    SUPPORT_FORMATS = ['bmp', 'jpg', 'png', 'pdf', 'tiff', 'jpeg']

    # TWAIN 核心常量
    # Capability IDs
    ICAP_XRESOLUTION = 65784
    ICAP_YRESOLUTION = 65785
    ICAP_PIXELTYPE = 65793
    ICAP_FEEDERENABLED = 65807
    ICAP_AUTOFEED = 65808
    ICAP_DESKEW = 65797  # 自动纠偏
    ICAP_AUTOMATICBORDERDETECTION = 65801
    ICAP_CROP = 65798  # 自动去黑边（兼容）
    ICAP_FRAME = 65796  # 手动裁剪

    # Data Types
    TWTY_BOOL = 1
    TWTY_FIX32 = 3
    TWTY_UINT16 = 5
    TWTY_FRAME = 6

    # Container Types
    TWON_ONEVALUE = 1.0

    # Pixel Types
    TWPT_BW = 0
    TWPT_GRAY = 1
    TWPT_RGB = 2

    # Return Codes
    TWRC_SUCCESS = 0

    def __init__(self):
        self.source_manager = None
        self.source = None
        self.scanner_name = None
        self.is_connected = False

        # 默认扫描参数
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

    def get_available_scanners(self):
        """获取系统中所有可用的扫描仪列表"""
        try:
            if not self.source_manager:
                self.source_manager = twain.SourceManager(0)
            scanner_list = self.source_manager.GetSourceList()

            if scanner_list:
                print(f"检测到 {len(scanner_list)} 台可用扫描仪：")
                # for idx, name in enumerate(scanner_list, 1):
                #     print(f"  {idx}. {name}")
            else:
                print("未检测到任何可用的扫描仪")
            return scanner_list
        except Exception as e:
            print(f"获取扫描仪列表失败：{str(e)}")
            return []

    def connect_scanner(self, scanner_name=None):
        """连接扫描仪"""
        try:
            scanner_list = self.get_available_scanners()
            if not scanner_list:
                return False

            if scanner_name:
                if scanner_name not in scanner_list:
                    raise ValueError(f"错误：指定的扫描仪 '{scanner_name}' 不存在")
                self.source = self.source_manager.OpenSource(scanner_name)
            else:
                self.source = self.source_manager.OpenSource()

            if self.source:
                self.scanner_name = self.source.GetSourceName()
                self.is_connected = True
                print(f"成功连接扫描仪：{self.scanner_name}")
                return True
            else:
                print("错误：无法打开扫描仪")
                return False
        except Exception as e:
            print(f"连接扫描仪失败：{str(e)}")
            self.is_connected = False
            return False

    def set_scan_params(self, **kwargs):
        """设置扫描参数"""
        if not self.is_connected:
            print("错误：请先连接扫描仪")
            return False

        try:
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

            self._apply_scan_settings()
            return True
        except Exception as e:
            print(f"设置扫描参数失败：{str(e)}")
            return False

    def _apply_basic_settings(self):
        """应用基础扫描设置（分辨率、色彩、进纸）"""
        # 设置分辨率
        self._set_capability_simple(self.ICAP_XRESOLUTION, self.TWTY_FIX32, self.default_params['dpi'])
        self._set_capability_simple(self.ICAP_YRESOLUTION, self.TWTY_FIX32, self.default_params['dpi'])

        # 设置色彩模式
        color_mapping = {
            self.COLOR_MODE_BW: self.TWPT_BW,
            self.COLOR_MODE_GRAY: self.TWPT_GRAY,
            self.COLOR_MODE_COLOR: self.TWPT_RGB
        }
        self._set_capability_simple(self.ICAP_PIXELTYPE, self.TWTY_UINT16, color_mapping[self.default_params['color_mode']])

        # 设置自动进纸
        try:
            self._set_capability_simple(self.ICAP_FEEDERENABLED, self.TWTY_BOOL, True)
            self._set_capability_simple(self.ICAP_AUTOFEED, self.TWTY_BOOL, True)
        except:
            pass

    def _apply_correction_settings(self):
        """应用纠偏和去黑边设置"""
        # 1. 自动纠偏
        if self.default_params['auto_deskew']:
            success = self._set_capability_simple(self.ICAP_DESKEW, self.TWTY_BOOL, True)
            print(f"自动纠偏设置：{'成功' if success else '失败（设备不支持）'}")
        else:
            self._set_capability_simple(self.ICAP_DESKEW, self.TWTY_BOOL, False)
            print("自动纠偏已关闭")

        # 2. 去黑边
        if self.default_params['manual_border']:
            # 手动裁剪区域（直接调用底层接口）
            try:
                frame = self.default_params['manual_border']
                # 构造 TW_FRAME 结构（左、上、右、下，单位英寸）
                tw_frame = (c_float(frame[0]), c_float(frame[1]), c_float(frame[2]), c_float(frame[3]))
                self.source.SetCapability(self.ICAP_FRAME, self.TWON_ONEVALUE, self.TWTY_FRAME, tw_frame)
                print(f"手动裁剪区域设置成功：{frame}")
            except Exception as e:
                print(f"手动裁剪设置失败：{str(e)}")
        elif self.default_params['auto_remove_border']:
            # 自动去黑边 - 先试标准参数
            success = self._set_capability_simple(self.ICAP_AUTOMATICBORDERDETECTION, self.TWTY_BOOL, True)
            if not success:
                # 兼容模式
                success = self._set_capability_simple(self.ICAP_CROP, self.TWTY_BOOL, True)
            print(f"自动去黑边设置：{'成功' if success else '失败（设备不支持）'}")
        else:
            self._set_capability_simple(self.ICAP_AUTOMATICBORDERDETECTION, self.TWTY_BOOL, False)
            print("自动去黑边已关闭")

    def _set_capability_simple(self, cap_id, data_type, value):
        try:
            # 不同数据类型的适配处理
            if data_type == self.TWTY_BOOL:
                # 布尔值转TWAIN_BOOL（1=True, 0=False）
                set_value = 1 if value else 0
            elif data_type == self.TWTY_FIX32:
                # 浮点数转FIX32格式
                set_value = c_float(value).value
            else:
                set_value = value

            print(f"set_value = {set_value}")

            result = self.source.SetCapability(cap_id, data_type, set_value)
            return result == self.TWRC_SUCCESS
        except Exception as e:
            print(f"设置失败：{str(e)}")
            return False

    def _apply_scan_settings(self):
        """应用所有扫描设置"""
        if not self.source:
            return
        self._apply_basic_settings()
        # self._apply_correction_settings()

    def scan_image(self):
        """执行扫描并保存图片"""
        if not self.is_connected:
            print("错误：请先连接扫描仪")
            return None

        try:
            os.makedirs(self.default_params['save_path'], exist_ok=True)
            self.source.RequestAcquire(0, 0)
            rv = self.source.XferImageNatively()

            if not rv:
                print("扫描取消或失败")
                return None

            handle, count = rv
            file_ext = self.default_params['save_format']
            file_name = f"{self.default_params['file_name']}.{file_ext}"
            save_path = os.path.join(self.default_params['save_path'], file_name)

            # 保存逻辑
            if file_ext == 'bmp':
                twain.DIBToBMFile(handle, save_path)
            else:
                temp_bmp = tempfile.mktemp(suffix='.bmp')
                twain.DIBToBMFile(handle, temp_bmp)
                with Image.open(temp_bmp) as img:
                    if file_ext in ['jpg', 'jpeg']:
                        img.save(save_path, 'JPEG', quality=95)
                    elif file_ext == 'png':
                        img.save(save_path, 'PNG')
                    elif file_ext == 'pdf':
                        img.save(save_path, 'PDF', resolution=self.default_params['dpi'])
                os.remove(temp_bmp)

            print(f"扫描完成，文件保存至：{save_path}")
            return save_path
        except Exception as e:
            print(f"扫描失败：{str(e)}")
            return None

    def disconnect_scanner(self):
        """断开扫描仪连接"""
        try:
            if self.source:
                self.source.close()
                self.source = None
            if self.source_manager:
                self.source_manager = None
            self.is_connected = False
            print("已断开扫描仪连接")
        except Exception as e:
            print(f"断开连接失败：{str(e)}")

    def __del__(self):
        """析构函数"""
        self.disconnect_scanner()


if __name__ == "__main__":
    scanner = ScannerManager()
    available_scanners = scanner.get_available_scanners()

    if available_scanners:
        if scanner.connect_scanner():
            scanner.set_scan_params(
                dpi=600,
                color_mode=scanner.COLOR_MODE_COLOR,
                save_format='jpg',
                save_path='D:/scan_files',
                file_name='my_scan_20251208_9',
                auto_deskew=True,
                auto_remove_border=False
            )
            scan_result = scanner.scan_image()
            if scan_result:
                print(f"扫描成功！文件路径：{scan_result}")
            scanner.disconnect_scanner()