# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : NewScannerDetector.py
# @Time     : 2026/4/13 15:31
# @Desc     : 扫描仪连接

import os
import time
import twain
import tempfile
import threading
from enum import IntEnum
from pydantic import Field
from typing import Optional, List
from dataclasses import dataclass, field

import twain
import win32gui
import numpy as np
from PIL import Image

from src.utils.LoggerDetector import logger


class ColorMode(IntEnum):
    BW      = 0
    GRAY    = 1
    COLOR   = 2

class Rotation(IntEnum):
    NONE    = 0
    CW_90   = 90
    CW_180  = 180
    CW_270  = 270

SUPPORTED_FORMATS: frozenset[str] = frozenset({"bmp", "jpg", "png", "tif", "tiff"})

_COLOR_MODE_MAP: dict[ColorMode, int] = {
    ColorMode.BW: twain.TWPT_BW,
    ColorMode.GRAY: twain.TWPT_GRAY,
    ColorMode.COLOR: twain.TWPT_RGB
}

_ROTATION_MAP: dict[Rotation, int] = {
    Rotation.NONE: 0.0,
    Rotation.CW_90: 90.0,
    Rotation.CW_180: 180.0,
    Rotation.CW_270: 270.0,
}

@dataclass
class ScanParams:
    scan_model: str = "单页扫描"
    scan_format: int = 0    # 单面扫描： 0； 双面扫描: 1
    dpi: int = 300
    color_mode: ColorMode = ColorMode.COLOR
    save_format: str = "jpg"
    scan_file_pages: int = 0
    save_path: str = field(default_factory=lambda: os.path.join(os.getcwd(), "scan_output"))
    file_name: str = "scan_image"
    rotation: Rotation = Rotation.NONE
    deskew: bool = False
    remove_black_border: bool = False
    auto_feed: bool = False
    show_ui: bool = False
    jpg_quality: int = 95
    xfer_timeout: float = 60.0
    msg_poll_interval: float = 0.05
    scan_result:List = Field(default_factory=list)

    def validate(self) -> None:
        if not isinstance(self.dpi, int) or self.dpi <= 0:
            raise ValueError(f"[ScanParams] dpi={self.dpi} 无效， 必须为正整数")

        valid_color = list(ColorMode)
        if self.color_mode not in valid_color:
            raise ValueError(f"[ScanParams] color_mode={self.color_mode!r} 无效, 合法值：{valid_color}")

        fmt = self.save_format.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(
                f"[ScanParams] save_format={self.save_format!r} 无效, 合法值: {sorted(SUPPORTED_FORMATS)}"
            )

        self.save_format = fmt

        valid_rot = list(Rotation)
        if self.rotation not in valid_rot:
            raise ValueError(f"[ScanParams] rotation={self.rotation!r} 无效, 合法值: {valid_rot}")

        if not (1 <= self.jpg_quality <= 95):
            raise ValueError(f"[ScanParams] jpg_quality={self.jpg_quality!r} 无效, 合法值范围: 1 ~ 95")

class NewScannerDetector:

    def __init__(self, params: Optional[ScanParams] = None) -> None:
        self._source_manager: Optional[twain.SourceManager] = None
        self._source: Optional[twain.Source] = None
        self._scanner_name: Optional[str] = None
        self._is_connected: bool = False

        self._params: ScanParams = params or ScanParams()
        self._params.validate()

        # 停止扫描标志，线程安全
        self._stop_event: threading.Event = threading.Event()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def scanner_name(self) -> Optional[str]:
        return self._scanner_name

    @property
    def params(self) -> ScanParams:
        return self._params

    def get_available_scanners(self) -> list[str]:
        try:
            if self._source_manager is not None:
                return list(self._source_manager.GetSourceList() or [])

            sm = twain.SourceManager(0)
            try:
                return list(sm.GetSourceList() or [])
            finally:
                sm = None

        except Exception as exc:
            raise ConnectionError(f"获取扫描仪失败: {exc}") from exc

    def connect_scanner(self, scanner_name: Optional[str]) -> None:
        try:
            self._source_manager = twain.SourceManager(0)
            sources: list[str] = list(self._source_manager.GetSourceList() or [])

            if not sources:
                raise LookupError(f"未检出到任何可用扫描仪, 请检查设备连接")

            if scanner_name:
                if scanner_name not in sources:
                    raise LookupError(f"找不到名称 {scanner_name} 的扫描仪")

                self._source = self._source_manager.OpenSource(scanner_name)
            else:
                self._source = self._source_manager.OpenSource()

            if not self._source:
                raise ConnectionError(f"返回空对象, 请检查驱动")

            self._scanner_name = self._source.GetSourceName()
            self._is_connected = True
            logger.info(f"成功连接扫描仪: {self._scanner_name}")

        except (LookupError, ConnectionError):
            raise
        except Exception as exc:
            self._is_connected = False
            logger.error(f"连接扫描仪时发生未知错误: {exc}")
            raise ConnectionError(f"连接扫描仪时发生未知错误: {exc}") from exc


    def disconnect_scanner(self) -> None:

        try:
            if self._source:
                self._source.close()
        except Exception as exc:
            logger.debug(f"disconnect_scanner / source.close: {exc}")
        finally:
            self._source = None
            self._is_connected = False
            self._scanner_name = None

        try:
            self._source_manager = None
        except Exception as exc:
            logger.debug(f"disconnect_scanner / source_manager release: {exc}")

        logger.info("扫描仪已断开连接")

    def update_params(self, **kwargs) -> None:
        self._require_connected()

        for key, value in kwargs.items():
            if not hasattr(self._params, key):
                raise AttributeError(f"ScanParams 不存在字段 {key!r}")

            object.__setattr__(self._params, key, value)

        self._params.validate()
        self._apple_twain_setting()
        logger.info(f"扫描参数已更行:{kwargs}")

    def _apple_twain_setting(self) -> None:
        p = self._params
        src = self._source

        src.set_capability(twain.ICAP_XFERMECH, twain.TWTY_UINT16, twain.TWSX_FILE)
        src.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(p.dpi))
        src.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(p.dpi))

        src.set_capability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, p.scan_format)

        src.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, _COLOR_MODE_MAP[p.color_mode])

        src.set_capability(twain.ICAP_ROTATION, twain.TWTY_FIX32, _ROTATION_MAP[p.rotation])

        if p.deskew:
            try:
                self._try_set_cap(twain.ICAP_AUTOMATICDESKEW, twain.TWTY_BOOL, True, "自动纠偏")
            except twain.exceptions.excTWCC_UNKNOWN as tee:
                logger.warning(f"不支持自动纠偏; {tee}")

            try:
                self._try_set_cap(twain.ICAP_AUTOMATICROTATE, twain.TWTY_BOOL, True, "自动旋转")
            except twain.exceptions.excTWCC_UNKNOWN as tee:
                logger.warning(f"不支持自动旋转; {tee}")

        if p.remove_black_border:
            try:
                self._try_set_cap(twain.ICAP_AUTOMATICBORDERDETECTION, twain.TWTY_BOOL, True, "自动去黑边")
            except twain.exceptions.excTWCC_UNKNOWN as tee:
                logger.warning(f"不支持自动去黑边; {tee}")

        if p.auto_feed:
            self._try_set_cap(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True, "开启进纸器")
            self._try_set_cap(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True, "开启自动进纸")
            self._try_set_cap(twain.CAP_AUTOSCAN, twain.TWTY_BOOL, True, "开启自动扫描")
            self._try_set_cap(twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1, "设置连续扫描")


    def _try_set_cap(self, cap_id: int, cap_type: int, value, desc:str = "") -> bool:
        try:
            self._source.set_capability(cap_id, cap_type, value)
            return True
        except Exception as exc:
            logger.warning(f"设备不支持{desc}, 已跳过（原因：{str(exc)}）")
            return False

    def request_stop(self) -> None:
        self._stop_event.set()
        logger.info("已发出停止扫描请求（等待当前页传输完成后生效）")

    def scan_image(self):
        self._require_connected()
        p = self._params
        logger.info(f"扫描参数: {self._params}")
        os.makedirs(p.save_path, exist_ok=True)

        self._stop_event.clear()
        scan_files_count = self._acquire_images()
        return scan_files_count

    _TWAIN_COUNT_UNKNOWN: int = 0xFFFF

    def _acquire_images(self):
        p = self._params
        print(f"p = {p}")
        self._source.request_acquire(show_ui=False, modal_ui=False)
        time.sleep(4)
        logger.info("正在唤醒扫描仪马达, 等待中·····")
        page = 0
        try:
            while True:
                try:
                    handle, count = self._source.xfer_image_natively()
                    logger.debug(f"handle={handle}, count={count}")
                except twain.exceptions.excTWCC_PAPERJAM:
                    logger.warning("ADF 无纸/卡纸, 扫描正常结束")
                    break
                except twain.exceptions.excTWCC_OPERATIONERROR as e:
                    logger.error(f"传输操作异常: {e}")
                    break
                except Exception as e:
                    if self._stop_event.is_set():
                        logger.info(f"扫描已被用户停止（传输中断，属正常）: {e}")
                    else:
                        logger.error(f"传输发生未知异常: {e}")
                    break

                if handle:
                    page += 1
                    if p.scan_model in ["替换扫描", "插入扫描"]:
                        save_path = f"{p.save_path}/{p.file_name}.{p.save_format}"
                    elif p.scan_model == "单页扫描":
                        save_path = self._resolve_save_path(p.file_name, p.save_format, p.save_path)

                    self._save_image(handle, save_path)
                    p.scan_result.append(os.path.basename(save_path))
                    logger.info(f"成功扫描第 {page} 页; 保存路径: {save_path}")
                    twain.GlobalHandleFree(handle)

                if count == 0:
                    if self._stop_event.is_set():
                        logger.info(f"停止请求已响应，当前批次 {page} 页全部传输完毕，退出")
                    else:
                        logger.info("扫描队列已空, 正在停止······")
                    break

                if count == self._TWAIN_COUNT_UNKNOWN:
                    if self._stop_event.is_set():
                        logger.info("停止请求: ADF 模式（count=65535），正在取消剩余传输…")
                        break
                    continue

                if self._stop_event.is_set():
                    logger.info(f"停止请求: 缓冲区还有 {count} 张已扫描图像，传完后退出……")

        except twain.exceptions.SequenceError as tes:
            logger.error(f"扫描状态序列异常: {tes}")
        finally:
            self._reset_twain_session()

        return page

    def _reset_twain_session(self) -> None:
        if not self._source:
            return

        try:
            self._source.close()
            logger.info("TWAIN 会话已重置（Source 已关闭），下次扫描将重新打开")
        except Exception as e:
            logger.debug(f"_reset_twain_session / source.close: {e}")
        finally:
            self._source = None
            self._is_connected = False
            self._scanner_name = None

    def _require_connected(self) -> None:
        if not self._is_connected or not self._source:
            raise RuntimeError(f"扫描仪尚未连接")

    @staticmethod
    def _resolve_save_path(name: str, ext:str, directory:str) -> str:
        idx = 1
        while True:
            candidate = os.path.join(directory, f"{name}-{idx:04d}.{ext}")
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def _save_image(self, dib_handle, save_path: str) -> None:
        p = self._params
        ext = p.save_format

        try:
            if (ext == 'bmp' and not p.deskew and not p.remove_black_border and p.rotation == Rotation.NONE):
                twain.DIBToBMFile(dib_handle, save_path)
                return

            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                twain.DIBToBMFile(dib_handle, tmp_path)
                with Image.open(tmp_path) as img:
                    img.load()
                    self._write_image(img, save_path, ext, p)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except OSError:
            raise
        except Exception as exc:
            raise OSError(f"扫描图像保存失败; {save_path}: {exc}") from exc

    @staticmethod
    def _write_image(img: Image.Image, path: str, ext: str, p:"ScanParams") -> None:
        if ext in ("jpg", "pdf") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        writers = {
            "jpg": lambda: img.save(path, "JPEG", quality=p.jpg_quality, optimize=True),
            "png": lambda: img.save(path, "PNG", optimize=True),
            "bmp": lambda: img.save(path, "BMP"),
            "tiff": lambda: img.save(path, "TIFF", compression="lxw", dpi=(p.dpi, p.dpi)),
            "pdf": lambda: img.save(path, "PDF", resolution=p.dpi),
        }
        writer = writers.get(ext)
        if writer is None:
            raise ValueError(f"暂不支持当前格式: {ext!r}")

        writer()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect_scanner()
        return False

    def __del__(self):
        self.disconnect_scanner()

if __name__ == "__main__":

    with NewScannerDetector() as sm:

        print(f"可用扫描仪: {sm.get_available_scanners()}")
        scanners_list = sm.get_available_scanners()

        sm.connect_scanner(scanners_list[0])
        sm.update_params(
            dpi = 300,
            color_mode = ColorMode.COLOR,
            scan_format=0,
            save_format = "jpg",
            save_path = "D:/scan_files",
            file_name = f"my_scan_document",
            scan_file_pages = 6,
            deskew = True,
            remove_black_border = True,
            auto_feed=True,
            jpg_quality = 90,
            xfer_timeout = 60.0,
            msg_poll_interval=0.51,
        )

        try:
            sm.scan_image()


        except RuntimeError as e:
            print(f"扫描失败; {e}")

        except OSError as e:
            print(f"保存失败; {e}")

        finally:
            sm.disconnect_scanner()