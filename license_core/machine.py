# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : machine.py
# @Desc      : 
# @Time      : 2026/7/5 15:44
# @Software  : PyCharm

import hashlib
import platform
import subprocess
import sys
import uuid
from typing import List, Dict


# 软件唯一标识
PRODUCT_SALT = "DigitalSystem-2026-License"


INVALID_VALUES = {
    "",
    "NONE",
    "NULL",
    "UNKNOWN",
    "NA",
    "N/A",
    "NOTAVAILABLE",
    "NOTAPPLICABLE",

    "SYSTEMSERIALNUMBER",
    "TBR",
    "TOBEFILLEDBYO.E.M.",
    "TOBEFILLEDBYOEM",
    "TOBEFILLED",
    "DEFAULTSTRING",
    "DEFAULT",
    "OEM",
    "OEMSTRING",

    "00000000",
    "0000000000000000",
    "FFFFFFFF",
    "FFFFFFFFFFFFFFFF",
}


def run_cmd(command: str) -> str:
    """
    执行系统命令。
    打包成 Windows exe 后，不弹出黑窗口。
    """
    try:
        creationflags = 0

        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW

        output = subprocess.check_output(
            command,
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            encoding="utf-8",
            errors="ignore",
        )

        return output.strip()

    except Exception:
        return ""


def normalize(value: str) -> str:
    """
    统一格式，避免大小写、空格、换行影响机器码。
    同时过滤无效硬件值。
    """
    if not value:
        return ""

    value = value.strip()
    value = value.replace("\r", "")
    value = value.replace("\n", "")
    value = value.replace("\t", "")
    value = value.replace(" ", "")
    value = value.upper()

    if value in INVALID_VALUES:
        return ""

    return value


def clean_lines(text: str, title: str = "") -> List[str]:
    """
    清理 wmic / powershell 输出。
    """
    result = []

    for line in text.splitlines():
        line = normalize(line)

        if not line:
            continue

        if title and line == normalize(title):
            continue

        if line in INVALID_VALUES:
            continue

        result.append(line)

    # 去重、排序，避免多硬盘顺序变化导致机器码变化
    return sorted(set(result))


def get_wmic_value(command: str, title: str) -> str:
    """
    通过 wmic 获取硬件信息。
    """
    text = run_cmd(command)
    lines = clean_lines(text, title)

    return "|".join(lines)


def get_powershell_value(command: str) -> str:
    """
    通过 PowerShell 获取硬件信息，作为 wmic 的补充。
    """
    ps_command = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{command}"'
    text = run_cmd(ps_command)
    lines = clean_lines(text)

    return "|".join(lines)


def get_cpu_id() -> str:
    """
    CPU ID
    """
    value = get_wmic_value(
        "wmic cpu get ProcessorId",
        "ProcessorId"
    )

    if value:
        return value

    return get_powershell_value(
        "(Get-CimInstance Win32_Processor).ProcessorId"
    )


def get_baseboard_serial() -> str:
    """
    主板序列号
    """
    value = get_wmic_value(
        "wmic baseboard get SerialNumber",
        "SerialNumber"
    )

    if value:
        return value

    return get_powershell_value(
        "(Get-CimInstance Win32_BaseBoard).SerialNumber"
    )


def get_bios_serial() -> str:
    """
    BIOS 序列号
    """
    value = get_wmic_value(
        "wmic bios get SerialNumber",
        "SerialNumber"
    )

    if value:
        return value

    return get_powershell_value(
        "(Get-CimInstance Win32_BIOS).SerialNumber"
    )


def get_disk_serial() -> str:
    """
    硬盘序列号。
    """
    value = get_wmic_value(
        "wmic diskdrive get SerialNumber",
        "SerialNumber"
    )

    if value:
        return value

    return get_powershell_value(
        "(Get-CimInstance Win32_DiskDrive).SerialNumber"
    )


def get_windows_uuid() -> str:
    """
    Windows 设备 UUID
    """
    value = get_wmic_value(
        "wmic csproduct get UUID",
        "UUID"
    )

    if value:
        return value

    return get_powershell_value(
        "(Get-CimInstance Win32_ComputerSystemProduct).UUID"
    )


def get_mac_address() -> str:
    """
    MAC 地址
    """
    try:
        mac = uuid.getnode()
        mac_text = f"{mac:012X}"

        if mac_text and mac_text not in INVALID_VALUES:
            return mac_text

    except Exception:
        pass

    return ""


def get_machine_info() -> Dict[str, str]:
    """
    获取原始硬件信息
    """
    info = {
        "os": normalize(platform.system()),
        "cpu": get_cpu_id(),
        "baseboard": get_baseboard_serial(),
        "bios": get_bios_serial(),
        "disk": get_disk_serial(),
        "windows_uuid": get_windows_uuid(),
        "mac": get_mac_address(),
    }

    return info


def format_machine_code(code: str) -> str:
    """
    把 64 位 SHA256 结果分段，方便复制和人工查看。
    """
    return "-".join([
        code[0:8],
        code[8:16],
        code[16:24],
        code[24:32],
        code[32:40],
        code[40:48],
        code[48:56],
        code[56:64],
    ])


def get_machine_code() -> str:
    """
    生成最终机器码。
    """
    info = get_machine_info()

    raw = "|".join([
        PRODUCT_SALT,
        info.get("os", ""),
        info.get("cpu", ""),
        info.get("baseboard", ""),
        info.get("bios", ""),
        info.get("disk", ""),
        info.get("windows_uuid", ""),
        info.get("mac", ""),
    ])

    code = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()

    return format_machine_code(code)


if __name__ == "__main__":
    print("====== 原始机器信息 ======")

    info = get_machine_info()
    for key, value in info.items():
        print(f"{key}: {value}")

    print()
    print("====== 机器码 ======")
    print(get_machine_code())
