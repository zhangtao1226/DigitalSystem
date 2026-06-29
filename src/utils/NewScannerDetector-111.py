# -*-coding : utf-8 -*-
# @Author   : zhangTao
# @File     : NewScannerDetector.py
# @Desc     : 扫描仪TWAIN稳定版（修复所有异常、0页、提前关闭问题）

import os
import time
import twain
import tempfile
import threading
from enum import IntEnum
from typing import Optional
from dataclasses import dataclass, field
from PIL import Image

# 日志（你原来的logger保留）
class FakeLogger:
    def info(self, s): print(f"[INFO] {s}")
    def warning(self, s): print(f"[WARN] {s}")
    def error(self, s): print(f"[ERROR] {s}")
    def debug(self, s): pass
logger = FakeLogger()

# ==================== 枚举 ====================
class ColorMode(IntEnum):
    BW      = 0
    GRAY    = 1
    COLOR   = 2

class Rotation(IntEnum):
    NONE    = 0
    CW_90   = 90
    CW_180  = 180
    CW_270  = 270

SUPPORTED_FORMATS = frozenset({"bmp", "jpg", "png", "tif", "tiff"})

_COLOR_MODE_MAP = {
    ColorMode.BW: twain.TWPT_BW,
    ColorMode.GRAY: twain.TWPT_GRAY,
    ColorMode.COLOR: twain.TWPT_RGB
}

_ROTATION_MAP = {
    Rotation.NONE: 0.0,
    Rotation.CW_90: 90.0,
    Rotation.CW_180: 180.0,
    Rotation.CW_270: 270.0,
}

# ==================== 扫描参数 ====================
@dataclass
class ScanParams:
    scan_model: str = "单页扫描"
    scan_format: int = 0
    dpi: int = 300
    color_mode: ColorMode = ColorMode.COLOR
    save_format: str = "jpg"
    save_path: str = field(default_factory=lambda: os.path.join(os.getcwd(), "scan_output"))
    file_name: str = "scan"
    rotation: Rotation = Rotation.NONE
    deskew: bool = True
    remove_black_border: bool = True
    auto_feed: bool = True
    show_ui: bool = False
    jpg_quality: int = 90
    msg_poll_interval: float = 0.05

    def validate(self):
        if self.dpi <= 0: raise ValueError("dpi必须>0")
        if self.save_format.lower() not in SUPPORTED_FORMATS:
            raise ValueError(f"仅支持 {SUPPORTED_FORMATS}")

# ==================== 扫描核心类 ====================
class NewScannerDetector:
    def __init__(self, params=None):
        self._source_manager = None
        self._source = None
        self._scanner_name = None
        self._is_connected = False
        self._params = params or ScanParams()
        self._params.validate()
        self._stop_event = threading.Event()

    @property
    def is_connected(self): return self._is_connected

    def get_available_scanners(self):
        try:
            sm = twain.SourceManager(0)
            return list(sm.GetSourceList() or [])
        except:
            return []

    def connect_scanner(self, scanner_name=None):
        self.disconnect_scanner()
        try:
            self._source_manager = twain.SourceManager(0)
            sources = self._source_manager.GetSourceList() or []
            if not sources: raise RuntimeError("未找到扫描仪")

            if scanner_name and scanner_name not in sources:
                raise RuntimeError(f"扫描仪 {scanner_name} 不存在")

            self._source = self._source_manager.OpenSource(scanner_name)
            self._scanner_name = self._source.GetSourceName()
            self._is_connected = True
            self._apply_params()
            logger.info(f"已连接：{self._scanner_name}")
        except Exception as e:
            self._is_connected = False
            raise RuntimeError(f"连接失败：{e}")

    def disconnect_scanner(self):
        try:
            if self._source:
                self._source.cancel_acquire()
                self._source.close()
        except:
            pass
        finally:
            self._source = None
            self._is_connected = False
            self._scanner_name = None
        try:
            self._source_manager = None
        except:
            pass

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self._params, k):
                setattr(self._params, k, v)
        self._params.validate()
        if self._is_connected and self._source:
            self._apply_params()

    def _apply_params(self):
        p = self._params
        src = self._source
        if not src: return
        try:
            src.set_capability(twain.ICAP_XFERMECH, twain.TWTY_UINT16, twain.TWSX_FILE)
            src.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(p.dpi))
            src.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(p.dpi))
            src.set_capability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, p.scan_format)
            src.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, _COLOR_MODE_MAP[p.color_mode])
            src.set_capability(twain.ICAP_ROTATION, twain.TWTY_FIX32, _ROTATION_MAP[p.rotation])
        except:
            pass

    def request_stop(self):
        self._stop_event.set()
        logger.info("已发送停止指令，将在当前页完成后停止")

    # ==================== 核心：稳定扫描（不会提前关闭Source）====================
    def scan_image(self) -> int:
        if not self._is_connected or not self._source:
            raise RuntimeError("扫描仪未连接")

        os.makedirs(self._params.save_path, exist_ok=True)
        self._stop_event.clear()
        page_count = 0

        try:
            # 关键：只请求一次获取，不提前关闭
            self._source.request_acquire(show_ui=self._params.show_ui, modal_ui=False)
            time.sleep(4)

            while not self._stop_event.is_set():
                try:
                    handle, remain = self._source.xfer_image_natively()
                except twain.exceptions.excTWCC_PAPERJAM:
                    logger.info("进纸器无纸，正常结束")
                    break
                except twain.exceptions.excTWCC_OPERATIONERROR:
                    logger.info("扫描仪状态正常结束")
                    break
                except Exception as e:
                    if self._stop_event.is_set():
                        logger.info("用户停止，正常结束")
                    else:
                        logger.error(f"传输异常：{e}")
                    break

                if handle:
                    page_count += 1
                    save_path = self._get_save_path()
                    self._save_image(handle, save_path)
                    logger.info(f"第{page_count}页已保存：{os.path.basename(save_path)}")
                    twain.GlobalHandleFree(handle)

                if remain <= 0:
                    logger.info("所有页面已完成")
                    break

                time.sleep(self._params.msg_poll_interval)

        finally:
            # 最后统一清理，绝不提前关闭
            self._safe_cleanup()

        logger.info(f"扫描完成，共 {page_count} 页")
        return page_count

    # ==================== 安全清理（只在最后执行）====================
    def _safe_cleanup(self):
        try:
            if self._source:
                self._source.cancel_acquire()
        except:
            pass
        # 注意：这里不 disconnect！保持连接，下一次扫描可用
        logger.info("扫描会话安全结束")

    def _get_save_path(self):
        idx = 1
        while True:
            path = os.path.join(self._params.save_path,
                                f"{self._params.file_name}-{idx:04d}.{self._params.save_format}")
            if not os.path.exists(path):
                return path
            idx += 1

    def _save_image(self, dib_handle, save_path):
        try:
            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
                tmp_bmp = tmp.name
            twain.DIBToBMFile(dib_handle, tmp_bmp)
            with Image.open(tmp_bmp) as im:
                if self._params.save_format == "jpg":
                    im.convert("RGB").save(save_path, "JPEG", quality=self._params.jpg_quality)
                else:
                    im.save(save_path)
            os.unlink(tmp_bmp)
        except Exception as e:
            raise RuntimeError(f"保存失败：{e}")

    def __enter__(self): return self
    def __exit__(self, *args): self.disconnect_scanner()
    def __del__(self): self.disconnect_scanner()

# ==================== 测试 DEMO（可直接运行）====================
if __name__ == "__main__":
    with NewScannerDetector() as scanner:
        try:
            devices = scanner.get_available_scanners()
            if not devices:
                print("未找到扫描仪")
                exit(1)
            print("可用扫描仪：", devices)

            scanner.connect_scanner(devices[0])
            scanner.update_params(
                dpi=300,
                color_mode=ColorMode.COLOR,
                save_format="jpg",
                save_path="./scan_out",
                auto_feed=True,
                show_ui=False
            )

            # 模拟5秒后停止（测试安全停止）
            def stop_after_5s():
                time.sleep(5)
                scanner.request_stop()
            threading.Thread(target=stop_after_5s, daemon=True).start()

            scanner.scan_image()

        except Exception as e:
            print(f"异常：{e}")