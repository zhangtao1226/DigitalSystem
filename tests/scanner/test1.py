# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test1.py
# @Time     : 2026/4/15 10:16
# @Desc     : 

import os
import time
from typing import List, Optional
import logging


import twain
import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s)")
logger = logging.getLogger(__name__)

class Capability:
    ICAP_AUTOMATICDESKEW = getattr(twain, "ICAP_AUTOMATICDESKEW", 0x101E)
    ICAP_AUTOMATICBORDERDETECTION = getattr(twain, "ICAP_AUTOMATICBORDERDETECTION", 0x1019)
    ICAP_AUTOMATICCROPUSESFRAME = getattr(twain, "ICAP_AUTOMATICCROPUSESFRAME", 0x1027)
    ICAP_AUTODISCARDBLANKPAGES = getattr(twain, "ICAP_AUTODISCARDBLANKPAGES", 0x1023)

    ICAP_FEEDENABLED = getattr(twain, "ICAP_FEEDENABLED", 0x401)
    ICAP_PLATENABLED = getattr(twain, "ICAP_PLATENABLED", 0x402)
    ICAP_XRESOLUTION = getattr(twain, "ICAP_XRESOLUTION", 0x404)
    ICAP_YRESOLUTION = getattr(twain, "ICAP_YRESOLUTION", 0x406)

    ICAP_PIXELTYPE = getattr(twain, "ICAP_PIXELTYPE", 0x401)

    TWPT_BW = getattr(twain, "TWPT_BW", 0)
    TWPT_GRAY = getattr(twain, "TWPT_GRAY", 1)
    TWPT_RGB = getattr(twain, "TWPT_RGB", 2)
    CAP_AUTOSCAN = getattr(twain, "CAP_AUTOSCAN", 0x104)


class ScannerDetector:
    def __init__(self, parent_window=0):
        self.sm = twain.SourceManager(parent_window=parent_window)
        self.source = None
        self.images = []
        self.scan_complete = False
        self.error_message = None
        self.pending_pages = 0

    def list_sources(self) -> List[str]:
        return self.sm.GetSourceList()

    def select_source(self, source_name: Optional[str] = None) -> bool:
        try:
            if source_name:
                all_sources = self.list_sources()
                if source_name not in all_sources:
                    raise ValueError(f"源{source_name} 不存在， 可用源：{all_sources}")
                self.source = self.sm.OpenSource(source_name)
            else:
                self.source = self.sm.OpenSource()

            return self.source is not None
        except Exception as e:
            self.error_message = f"选择源失败: {e}"
            return False

    def set_feed_mode(self, use_adf: bool, auto_scan: bool = True):
        if not self.source:
            raise RuntimeError("未打开扫描源, 请先调用 select_source()")

        try:

            self.source.SetCapability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
            self.source.SetCapability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True)

            # self.source.SetCapability(Capability.ICAP_FEEDENABLED, twain.TWTY_BOOL, use_adf)
            # self.source.SetCapability(Capability.ICAP_PLATENABLED, twain.TWTY_BOOL, not use_adf)
            #
            # if use_adf and auto_scan:
            #     self.source.SetCapability(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True)
            #     self.source.SetCapability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)


        except Exception as e:
            logger.warning(f"设置进纸模式时出错: {e}")


    def set_resolution(self, dpi: int = 300):
        try:
            self.source.SetCapability(Capability.ICAP_XRESOLUTION, twain.TWTY_BOOL, dpi)
            self.source.SetCapability(Capability.ICAP_YRESOLUTION, twain.TWTY_BOOL, dpi)

        except Exception as e:
            logger.warning(f"设置分辨率时出错; {e}")

    def set_color_model(self, mode: str = "RGB"):
        try:
            if mode == "RGB":
                self.source.SetCapability(Capability.ICAP_PIXELTYPE, Capability.TWPT_RGB)
            elif mode == "Gray":
                self.source.SetCapability(Capability.ICAP_PIXELTYPE, Capability.TWPT_GRAY)
            elif mode == "BW":
                self.source.SetCapability(Capability.ICAP_PIXELTYPE, Capability.TWPT_BW)
            else:
                raise ValueError("不支持该颜色模式, 请使用 黑白/ 灰度 / 彩色")
        except Exception as e:
            logger.warning(f"设置颜色模式时出错: {e}")


    def set_auto_correction(self, enable_deskew: bool = True, enable_autocrop: bool = True,
                            discard_blank_pages: bool = True):
        if not self.source:
            raise RuntimeError(f"未打开扫描源, 请先调用 select_source()")

        if enable_deskew:
            try:
                self.source.SetCapability(Capability.ICAP_AUTOMATICDESKEW, True)
                logger.info("启动自动纠偏")
            except Exception as e:
                logger.warning(f"驱动可能不支持自动纠偏功能: {e}")

        if enable_autocrop:
            try:
                self.source.SetCapability(Capability.ICAP_AUTOMATICBORDERDETECTION, True)
                logger.info("已启用自动边框检测")
            except Exception as e:
                logger.warning(f"驱动可能不支持自动边框检测功能: {e}")

            try:
                self.source.SetCapability(Capability.ICAP_AUTOMATICCROPUSESFRAME, True)
                logger.info("已启用自动裁剪")
            except Exception as e:
                logger.warning(f"驱动可能不支持自动裁剪功能: {e}")
        else:
            try:
                self.source.SetCapability(Capability.ICAP_AUTOMATICBORDERDETECTION, False)
            except Exception:
                pass

            try:
                self.source.SetCapability(Capability.ICAP_AUTOMATICCROPUSESFRAME, False)
            except Exception:
                pass


        if discard_blank_pages:
            try:
                self.source.SetCapability(Capability.ICAP_AUTODISCARDBLANKPAGES, True)
                logger.info("已启用自动丢弃空白页")
            except Exception as e:
                logger.warning(f"驱动可能不支持自动丢弃空白页功能: {e}")

    def _twain_event_callback(self, msg):
        if msg == twain.MSG_XFERREADY:
            try:
                handle, count = self.source.XferImageNatively()
                if handle:
                    img = self._dib_to_pil(handle)
                    self.images.append(img)
                    logger.info(f"已接收第 {len(self.images)} 页图像")
                    self.source.EndXfer()
                else:
                    self.error_message = "XferImageNatively 返回空句柄"
            except Exception as e:
                self.error_message = f"XferImageNatively 调用失败: {e}"
                logger.error(self.error_message)
        elif msg == twain.MSG_CLOSEDSM:
            self.scan_complete = True
            logger.info("扫描完成")

        elif msg == twain.MSG_NULL:
            print("空闲")
            # pass

    def _dib_to_pil(self, dib_handle) -> Image.Image:
        temp_path = "_temp_scan.jpg"
        try:
            twain.DIBToBMFile(dib_handle, temp_path)
            img = Image.open(temp_path)
            return img
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            twain.DIBFree(dib_handle)

    def start_scan(self, show_ui: bool = True) -> List[Image.Image]:
        if not self.source:
            raise RuntimeError(f"未打卡扫描源, 请先调用 select_source()")

        self.images = []
        self.scan_complete = False
        self.error_message = None

        self.sm.SetCallback(self._twain_event_callback)

        if show_ui:
            self.source.SetCapability(twain.CAP_ENABLEDSUIONLY, True)
            self.source.SetCapability(show=True, modal=True)
        else:
            self.source.UserInterface(show=False, modal=False)

        self.source.RequestAcquire(0, 0)

        while not self.scan_complete and self.error_message is None:
            self.sm.PassMessage()
            time.sleep(0.05)

        self.source.CloseSource()
        self.sm.SetCallback(None)

        if self.error_message:
            raise RuntimeError(self.error_message)

    def scan_single_page(self) -> Optional[Image.Image]:
        if self.source:
            try:
                self.source.SetCapability(Capability.ICAP_FEEDENABLED, False)
                self.source.SetCapability(Capability.ICAP_PLATENABLED, True)
            except Exception:
                pass
        pages = self.start_scan(show_ui=False)
        return pages[0] if pages else None

    def scan_all_pages(self, show_ui: bool = False) -> List[Image.Image]:
        return self.start_scan(show_ui=show_ui)


    def close(self):
        if self.source:
            try:
                self.source.CloseSource()
            except:
                pass
        if self.sm:
            self.sm.destroy()
            self.sm = None


if __name__ == "__main__":
    scanner = ScannerDetector()

    sources = scanner.list_sources()
    print(f"可用扫描源: {sources}")

    if sources:
        scanner.select_source(sources[0])
    else:
        print("未找到可用扫描仪")
        exit(1)

    scanner.set_feed_mode(use_adf=True, auto_scan=True)

    scanner.set_resolution(dpi=300)
    scanner.set_color_model("RGB")

    scanner.set_auto_correction(enable_deskew=True, enable_autocrop=True, discard_blank_pages=False)

    try:
        images = scanner.scan_all_pages(show_ui=False)
        print(f"成功扫描 {len(images)}")

        for idx, img in enumerate(images):
            img.save(f"page_{idx + 1}.png")
            print(f"已保存第 {idx + 1} 页为 page_{idx + 1}.png")
    except Exception as e:
        print(f"扫描失败: {e}")

    scanner.close()
