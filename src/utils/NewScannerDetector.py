# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : NewScannerDetector.py
# @Time     : 2026/4/13 15:31
# @Desc     : 扫描仪连接

import os
import gc
import time
import twain
import tempfile
import threading
from enum import IntEnum
from typing import Optional, List
from dataclasses import dataclass, field

import twain
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
    scan_result: List = field(default_factory=list)

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
        self._last_disconnect_time: float = 0.0
        self._reconnect_delay: float = 1.5

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
        # 上一次扫描结束后部分 TWAIN 驱动需要一点时间释放 Source。
        # 连接前先统一清理旧会话，避免 OpenSource 报 ConditionCode = 0。
        self.disconnect_scanner(log_message=False)
        self._wait_for_driver_release()
        self.clear_stop_request()

        last_exc = None
        for attempt in range(1, 3):
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
                return

            except (LookupError, ConnectionError):
                self.disconnect_scanner(log_message=False)
                raise
            except Exception as exc:
                last_exc = exc
                self._is_connected = False
                logger.warning(
                    f"连接扫描仪失败，第 {attempt} 次尝试; 原因: {exc}"
                )
                self.disconnect_scanner(log_message=False)
                if attempt < 2:
                    time.sleep(self._reconnect_delay)

        logger.error(f"连接扫描仪时发生未知错误: {last_exc}")
        raise ConnectionError(f"连接扫描仪时发生未知错误: {last_exc}") from last_exc


    def disconnect_scanner(self, log_message: bool = True) -> None:

        self._release_source(cancel=False)
        self._release_source_manager()
        self._last_disconnect_time = time.time()
        gc.collect()

        if log_message:
            logger.info("扫描仪已断开连接")

    def _wait_for_driver_release(self) -> None:
        elapsed = time.time() - self._last_disconnect_time
        if elapsed < self._reconnect_delay:
            time.sleep(self._reconnect_delay - elapsed)

    def _release_source(self, cancel: bool = False) -> bool:
        released = False
        src = self._source
        if not src:
            self._source = None
            self._is_connected = False
            self._scanner_name = None
            return False

        if cancel:
            for method_name in ("cancel_acquire", "CancelAcquire"):
                cancel_method = getattr(src, method_name, None)
                if not callable(cancel_method):
                    continue
                try:
                    cancel_method()
                    released = True
                    logger.info(f"已调用扫描仪取消采集接口: {method_name}")
                    break
                except Exception as exc:
                    logger.warning(f"调用扫描仪取消采集接口失败 {method_name}: {exc}")

        try:
            src.close()
            released = True
        except Exception as exc:
            logger.debug(f"释放扫描仪 Source 失败: {exc}")
        finally:
            self._source = None
            self._is_connected = False
            self._scanner_name = None

        return released

    def _release_source_manager(self) -> None:
        sm = self._source_manager
        if sm:
            for method_name in ("close", "destroy", "Destroy"):
                release_method = getattr(sm, method_name, None)
                if not callable(release_method):
                    continue
                try:
                    release_method()
                    break
                except Exception as exc:
                    logger.debug(f"释放 SourceManager 失败 {method_name}: {exc}")

        self._source_manager = None

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

        native_xfer = getattr(twain, "TWSX_NATIVE", 0)
        self._try_set_cap(
            twain.ICAP_XFERMECH,
            twain.TWTY_UINT16,
            native_xfer,
            "设置 Native 传输模式",
        )
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

    def request_feeder_stop(self) -> bool:
        self._stop_event.set()
        stopped = False

        if not self._source:
            logger.info("已记录停止扫描请求，当前没有活动扫描 Source")
            return False

        for cap_id, desc in (
            (getattr(twain, "CAP_AUTOSCAN", None), "停止自动扫描"),
            (getattr(twain, "CAP_AUTOFEED", None), "停止自动进纸"),
        ):
            if cap_id is None:
                continue
            stopped = (
                self._try_set_cap(cap_id, twain.TWTY_BOOL, False, desc) or stopped
            )

        if stopped:
            logger.info("已请求扫描仪停止继续进纸，等待驱动传输已扫描页面")
        else:
            logger.info("已发出停止扫描请求，等待当前 TWAIN 传输自然结束")

        return stopped

    def request_stop(self, cancel_driver: bool = False) -> bool:
        self._stop_event.set()
        logger.info("已发出停止扫描请求")
        if cancel_driver:
            return self.abort_active_scan()
        return self.request_feeder_stop()

    def clear_stop_request(self) -> None:
        self._stop_event.clear()
        logger.debug("扫描停止标志已清除")

    def abort_active_scan(self) -> bool:
        """
        主动取消当前 TWAIN 采集。
        仅设置 stop_event 无法让部分高速 ADF 立即停纸，这里显式调用驱动取消并关闭 Source。
        """
        cancelled = self._release_source(cancel=True)
        self._release_source_manager()
        self._last_disconnect_time = time.time()
        gc.collect()
        self.clear_stop_request()
        if cancelled:
            logger.info("已强制结束当前 TWAIN 采集会话")
        return cancelled

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

        logger.info("正在请求扫描仪采集图像·····")
        try:
            self._source.request_acquire(show_ui=False, modal_ui=False)
            logger.info("无UI模式：等待扫描仪马达就绪·····")
            _deadline = time.time() + 8.0
            while time.time() < _deadline:
                if self._stop_event.is_set():
                    logger.info("等待期间收到停止请求，中止扫描")
                    return 0
                time.sleep(0.2)
        except Exception as req_err:
            logger.warning(f"无UI采集请求失败，回退到有UI模式: {req_err}")
            try:
                self._source.request_acquire(show_ui=True, modal_ui=True)
                logger.info("有UI模式：扫描界面已关闭，开始传输图像·····")
            except Exception as e2:
                logger.error(f"扫描请求失败: {e2}")
                return 0

        page = 0
        first_frame_deadline = time.time() + max(10.0, p.xfer_timeout)
        last_transfer_error = None
        try:
            while True:
                try:
                    handle, count = self._source.xfer_image_natively()
                    logger.debug(f"handle={handle}, count={count}")
                except twain.exceptions.excTWCC_PAPERJAM:
                    logger.warning("ADF 无纸/卡纸, 扫描正常结束")
                    break
                except twain.exceptions.excTWCC_OPERATIONERROR as e:
                    if page == 0 and time.time() < first_frame_deadline:
                        last_transfer_error = e
                        logger.debug(f"首帧未就绪，继续等待: {e}")
                        time.sleep(max(0.1, p.msg_poll_interval))
                        continue
                    logger.error(f"传输操作异常: {e}")
                    break
                except Exception as e:
                    if self._stop_event.is_set():
                        logger.info(f"扫描已被用户停止（传输中断，属正常）: {e}")
                    elif page == 0 and time.time() < first_frame_deadline:
                        last_transfer_error = e
                        logger.debug(f"首帧未就绪，继续等待: {e}")
                        time.sleep(max(0.1, p.msg_poll_interval))
                        continue
                    else:
                        logger.error(f"传输发生未知异常: {e}")
                    break

                if handle:
                    page += 1
                    if p.scan_model in ["替换扫描", "插入扫描"]:
                        save_path = f"{p.save_path}/{p.file_name}.{p.save_format}"
                    elif p.scan_model == "单页扫描":
                        save_path = self._resolve_save_path(p.file_name, p.save_format, p.save_path)

                    try:
                        self._save_image(handle, save_path)
                        p.scan_result.append(os.path.basename(save_path))
                        logger.info(f"成功扫描第 {page} 页; 保存路径: {save_path}")
                    finally:
                        twain.GlobalHandleFree(handle)

                if count == 0:
                    if self._stop_event.is_set():
                        logger.info(f"停止请求已响应，当前批次 {page} 页全部传输完毕，退出")
                    else:
                        logger.info("扫描队列已空, 正在停止······")
                    break

                if count == self._TWAIN_COUNT_UNKNOWN:
                    if self._stop_event.is_set():
                        logger.info("停止请求: ADF 模式（count=65535），继续接收驱动缓存页")
                    continue

                if self._stop_event.is_set():
                    logger.info(f"停止请求: 缓冲区还有 {count} 张已扫描图像，传完后退出……")

        except twain.exceptions.SequenceError as tes:
            if page == 0 and time.time() < first_frame_deadline:
                logger.warning(f"扫描状态暂未就绪，但已退出循环: {tes}")
            else:
                logger.error(f"扫描状态序列异常: {tes}")
        finally:
            self._reset_twain_session()

        if page == 0 and last_transfer_error is not None:
            logger.error(f"首帧等待超时，未取得扫描图像: {last_transfer_error}")

        return page

    def _reset_twain_session(self) -> None:
        if self._release_source(cancel=False):
            logger.info("TWAIN 会话已重置（Source 已关闭），下次扫描将重新打开")

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
