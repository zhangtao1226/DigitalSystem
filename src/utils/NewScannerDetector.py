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
        if self.scan_format not in (0, 1):
            raise ValueError(
                f"[ScanParams] scan_format={self.scan_format!r} 无效，"
                "单面扫描必须为 0，双面扫描必须为 1"
            )

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
        # KODAK 的残余黑边处理优先使用驱动自定义 TWAIN 能力；驱动拒绝
        # 时才创建软件清理器，并在同一批高速扫描中复用。
        self._kodak_edge_fill_enabled = False
        self._border_cleaner = None

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
                self._kodak_edge_fill_enabled = False
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

        # 高速 ADF 驱动（包括 KODAK i3000）会根据当前进纸模式动态开放
        # 自动裁边等图像处理能力，因此必须先启用进纸器，再设置图像能力。
        if p.auto_feed:
            self._try_set_cap(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True, "开启进纸器")
            self._try_set_cap(twain.CAP_AUTOFEED, twain.TWTY_BOOL, True, "开启自动进纸")
            self._try_set_cap(twain.CAP_AUTOSCAN, twain.TWTY_BOOL, True, "开启自动扫描")
            self._try_set_cap(twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1, "设置连续扫描")

        native_xfer = getattr(twain, "TWSX_NATIVE", 0)
        self._try_set_cap(
            twain.ICAP_XFERMECH,
            twain.TWTY_UINT16,
            native_xfer,
            "设置 Native 传输模式",
        )
        src.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(p.dpi))
        src.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(p.dpi))

        self._set_duplex_mode(p.scan_format)

        src.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, _COLOR_MODE_MAP[p.color_mode])

        src.set_capability(twain.ICAP_ROTATION, twain.TWTY_FIX32, _ROTATION_MAP[p.rotation])

        # TWAIN 规范要求自动边界检测/自动旋转与“未定义图像尺寸”配套使用。
        # 仅设置 ICAP_AUTOMATICBORDERDETECTION 时，部分 KODAK 驱动虽然不报错，
        # 但仍按固定纸张幅面输出，从而在页面边缘保留黑边。
        needs_undefined_size = p.remove_black_border or p.deskew
        undefined_size_cap = getattr(twain, "ICAP_UNDEFINEDIMAGESIZE", 0x112D)
        undefined_size_enabled = self._try_set_cap(
            undefined_size_cap,
            twain.TWTY_BOOL,
            needs_undefined_size,
            "接收自动检测后的可变图像尺寸",
        )

        border_detection_enabled = False
        if p.remove_black_border:
            border_detection_enabled = self._try_set_cap(
                getattr(twain, "ICAP_AUTOMATICBORDERDETECTION", 0x1150),
                twain.TWTY_BOOL,
                True,
                "自动检测页面边界并去黑边",
            )

        if p.deskew:
            self._try_set_cap(
                getattr(twain, "ICAP_AUTOMATICDESKEW", 0x1151),
                twain.TWTY_BOOL,
                True,
                "自动检测并纠偏",
            )
            self._try_set_cap(
                getattr(twain, "ICAP_AUTOMATICROTATE", 0x1152),
                twain.TWTY_BOOL,
                True,
                "自动旋转",
            )

        auto_size_enabled = False
        if p.remove_black_border:
            auto_size_enabled = self._try_set_cap(
                getattr(twain, "ICAP_AUTOSIZE", 0x1156),
                twain.TWTY_UINT16,
                getattr(twain, "TWAS_AUTO", 1),
                "按文档实际边界自动确定图像尺寸",
            )
            self._try_set_cap(
                getattr(twain, "ICAP_AUTOMATICLENGTHDETECTION", 0x1158),
                twain.TWTY_BOOL,
                True,
                "自动检测文档长度",
            )
            if undefined_size_enabled and (
                border_detection_enabled or auto_size_enabled
            ):
                logger.info("已启用扫描仪标准自动边界检测")
            else:
                logger.warning(
                    "扫描仪未完整接受自动裁边能力，请确认 KODAK TWAIN 驱动中"
                    "“文档=自动检测并纠偏、图像=整个文档”可用"
                )

            if self._is_kodak_scanner():
                self._apply_kodak_border_settings()

        # KODAK 的正反面图像处理参数可能重新加载摄像头配置，因此所有
        # 自定义能力下发完成后再次锁定并校验最终单双面状态。
        self._set_duplex_mode(p.scan_format)

    def _set_duplex_mode(self, scan_format: int) -> None:
        duplex_enabled = scan_format == 1
        mode_text = "双面扫描" if duplex_enabled else "单面扫描"
        cap_id = getattr(twain, "CAP_DUPLEXENABLED", 0x1013)

        if not self._try_set_cap(
            cap_id,
            twain.TWTY_BOOL,
            duplex_enabled,
            f"设置{mode_text}",
        ):
            raise RuntimeError(f"扫描仪未接受{mode_text}设置，已取消本次扫描")

        current = self._get_cap_current_value(cap_id)
        if current is not None and bool(current) != duplex_enabled:
            current_text = "双面扫描" if bool(current) else "单面扫描"
            raise RuntimeError(
                f"扫描仪当前仍为{current_text}，无法切换到{mode_text}，"
                "已取消本次扫描"
            )

        logger.info(
            f"扫描方式已确认: {mode_text}; "
            f"CAP_DUPLEXENABLED={duplex_enabled}"
        )

    def _is_kodak_scanner(self) -> bool:
        scanner_name = (self._scanner_name or "").casefold()
        return "kodak" in scanner_name or "alaris" in scanner_name

    def _apply_kodak_border_settings(self) -> None:
        """
        启用 KODAK 文档扫描仪驱动自带的残余边框处理。

        这些能力来自 KODAK Document Scanner TWAIN 自定义能力定义：
        - ICAP_CROPPINGMODE 0x8022 / TWCR_AGGRESSIVEAUTOCROP 3
        - ICAP_IMAGEEDGEFILL 0x8095 / TWIE_AUTOMATIC 3
        """
        # KODAK 的部分图像能力按正反面摄像头分别保存；关闭“正反面设置
        # 不同”后，本次设置会同时应用到单面及双面扫描。
        self._try_set_cap(
            0x80B7,  # CAP_SIDESDIFFERENT
            twain.TWTY_BOOL,
            False,
            "KODAK 正反面使用相同图像处理参数",
        )
        aggressive_crop_enabled = self._try_set_cap(
            0x8022,  # ICAP_CROPPINGMODE
            twain.TWTY_UINT16,
            3,  # TWCR_AGGRESSIVEAUTOCROP
            "KODAK 强力自动裁切",
        )
        self._kodak_edge_fill_enabled = self._try_set_cap(
            0x8095,  # ICAP_IMAGEEDGEFILL
            twain.TWTY_UINT16,
            3,  # TWIE_AUTOMATIC
            "KODAK 自动图像边缘填充",
        )

        if aggressive_crop_enabled and self._kodak_edge_fill_enabled:
            logger.info("KODAK i3000 驱动级去黑边已启用（强力裁切 + 自动边缘填充）")
        elif self._kodak_edge_fill_enabled:
            logger.info("KODAK 自动图像边缘填充已启用")
        else:
            logger.warning(
                "KODAK 驱动未接受自动图像边缘填充，将使用扫描图片残余黑边清理"
            )


    def _try_set_cap(self, cap_id: int, cap_type: int, value, desc:str = "") -> bool:
        if cap_id is None:
            logger.warning(f"当前 TWAIN 库未定义{desc}能力, 已跳过")
            return False

        try:
            self._source.set_capability(cap_id, cap_type, value)
            current = self._get_cap_current_value(cap_id)
            if current is None:
                logger.info(f"{desc}已下发到扫描仪")
            else:
                logger.info(f"{desc}已生效，驱动当前值: {current!r}")
            return True
        except Exception as exc:
            # 部分 TWAIN 驱动会在接受设置后返回 CHECKSTATUS。读取当前值，
            # 若已经等于目标值，就不能把它误判为“不支持”。
            current = self._get_cap_current_value(cap_id)
            if self._cap_value_matches(current, value):
                logger.info(
                    f"{desc}已由驱动接受（返回状态: {exc}），当前值: {current!r}"
                )
                return True
            logger.warning(f"设备不支持{desc}, 已跳过（原因：{exc!r}）")
            return False

    def _get_cap_current_value(self, cap_id: int):
        getter = getattr(self._source, "get_capability_current", None)
        if not callable(getter):
            return None

        try:
            result = getter(cap_id)
        except Exception as exc:
            logger.debug(f"读取 TWAIN 能力 {cap_id:#06x} 当前值失败: {exc}")
            return None

        # pytwain 返回 (TWTY_*, value)，这里提取实际的当前值。
        if isinstance(result, tuple) and len(result) == 2:
            return result[1]
        if isinstance(result, dict):
            return result.get("CurrentValue")
        return result

    @staticmethod
    def _cap_value_matches(current, expected) -> bool:
        if current is None:
            return False
        if isinstance(expected, bool):
            try:
                return bool(current) is expected
            except (TypeError, ValueError):
                return False
        return current == expected

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
                if p.remove_black_border and not self._kodak_edge_fill_enabled:
                    self._clean_residual_black_border(save_path)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except OSError:
            raise
        except Exception as exc:
            raise OSError(f"扫描图像保存失败; {save_path}: {exc}") from exc

    def _clean_residual_black_border(self, image_path: str) -> None:
        """
        清理由扫描仪自动裁边后残留在页面四周的窄黑边。

        当设备不支持 KODAK 自定义自动边缘填充时，复用项目现有的边缘
        连通块算法，只检查靠近图片边缘的区域，并保护红章等高色差内容。
        清理失败时保留驱动原始扫描件，不中断高速扫描批次。
        """
        try:
            if self._border_cleaner is None:
                from src.utils.DocumentBorderCleaner import DocumentBorderCleaner

                # KODAK 官方 Border Remove 处理约 0.1 英寸的残余边框。
                # 300 DPI 时约为 30 像素，2.5% 的检测带足以覆盖常用
                # A4/A3 扫描尺寸，同时避免深入正文区域。
                self._border_cleaner = DocumentBorderCleaner(
                    scan_limit=0.025,
                    padding=3,
                    shadow_expand=5,
                )

            self._border_cleaner.clean(
                input_path=image_path,
                output_path=image_path,
            )
        except Exception as exc:
            logger.warning(
                f"扫描图片残余黑边清理失败，已保留原始图片: "
                f"{os.path.basename(image_path)}; 原因: {exc!r}"
            )

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
