# -*- coding: utf-8 -*-
import hashlib
import os
import platform
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict, List

try:
    from license_core.config import PRODUCT_NAME, PRODUCT_SALT
except ModuleNotFoundError:
    from config import PRODUCT_NAME, PRODUCT_SALT

FALLBACK_MACHINE_CODE = "WINDOWS-RUNTIME-MACHINE-CODE-UNAVAILABLE"
MACHINE_CODE_CACHE_FILENAME = "machine_code.txt"
MACHINE_CODE_PATTERN = re.compile(r"^[0-9A-F]{8}(-[0-9A-F]{8}){7}$")

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
    """Run a hardware query command without opening a console on Windows."""
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
    if not value:
        return ""

    value = value.strip()
    value = value.replace("\r", "")
    value = value.replace("\n", "")
    value = value.replace("\t", "")
    value = value.replace(" ", "")
    value = value.upper()
    compact_value = value.replace("-", "").replace("{", "").replace("}", "")

    if value in INVALID_VALUES or compact_value in INVALID_VALUES:
        return ""
    if compact_value and set(compact_value) in ({"0"}, {"F"}):
        return ""

    return value


def clean_lines(text: str, title: str = "") -> List[str]:
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

    return sorted(set(result))


def get_wmic_value(command: str, title: str) -> str:
    text = run_cmd(command)
    lines = clean_lines(text, title)
    return "|".join(lines)


def get_powershell_value(command: str) -> str:
    ps_command = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{command}"'
    text = run_cmd(ps_command)
    lines = clean_lines(text)
    return "|".join(lines)


def get_cpu_id() -> str:
    value = get_wmic_value("wmic cpu get ProcessorId", "ProcessorId")
    if value:
        return value
    return get_powershell_value("(Get-CimInstance Win32_Processor).ProcessorId")


def get_windows_machine_guid() -> str:
    if not sys.platform.startswith("win"):
        return ""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return normalize(str(value))
    except Exception:
        return ""


def get_baseboard_serial() -> str:
    value = get_wmic_value("wmic baseboard get SerialNumber", "SerialNumber")
    if value:
        return value
    return get_powershell_value("(Get-CimInstance Win32_BaseBoard).SerialNumber")


def get_bios_serial() -> str:
    value = get_wmic_value("wmic bios get SerialNumber", "SerialNumber")
    if value:
        return value
    return get_powershell_value("(Get-CimInstance Win32_BIOS).SerialNumber")


def get_disk_serial() -> str:
    value = get_wmic_value("wmic diskdrive get SerialNumber", "SerialNumber")
    if value:
        return value
    return get_powershell_value("(Get-CimInstance Win32_DiskDrive).SerialNumber")


def get_windows_uuid() -> str:
    value = get_wmic_value("wmic csproduct get UUID", "UUID")
    if value:
        return value
    return get_powershell_value("(Get-CimInstance Win32_ComputerSystemProduct).UUID")


def get_mac_address() -> str:
    try:
        mac = uuid.getnode()
        mac_text = f"{mac:012X}"
        if mac_text and mac_text not in INVALID_VALUES:
            return mac_text
    except Exception:
        pass

    return ""


def get_machine_info() -> Dict[str, str]:
    return {
        "os": normalize(platform.system()),
        "machine_guid": get_windows_machine_guid(),
        "cpu": get_cpu_id(),
        "baseboard": get_baseboard_serial(),
        "bios": get_bios_serial(),
        "disk": get_disk_serial(),
        "windows_uuid": get_windows_uuid(),
        "mac": get_mac_address(),
    }


def format_machine_code(code: str) -> str:
    return "-".join(
        [
            code[0:8],
            code[8:16],
            code[16:24],
            code[24:32],
            code[32:40],
            code[40:48],
            code[48:56],
            code[56:64],
        ]
    )


def is_valid_machine_code(code: str) -> bool:
    return bool(MACHINE_CODE_PATTERN.fullmatch(str(code).strip().upper()))


def get_machine_code_cache_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        cache_dir = Path(appdata) / PRODUCT_NAME
    else:
        cache_dir = Path.cwd() / PRODUCT_NAME
    return cache_dir / MACHINE_CODE_CACHE_FILENAME


def read_cached_machine_code() -> str:
    try:
        cache_path = get_machine_code_cache_path()
        if not cache_path.exists():
            return ""
        code = cache_path.read_text(encoding="utf-8").strip().upper()
        if is_valid_machine_code(code):
            return code
    except Exception:
        pass
    return ""


def write_cached_machine_code(code: str) -> None:
    if not is_valid_machine_code(code):
        return

    try:
        cache_path = get_machine_code_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(f"{code}\n", encoding="utf-8")
    except Exception:
        pass


def build_machine_code(info: Dict[str, str]) -> str:
    stable_values = [
        info.get("machine_guid", ""),
        info.get("windows_uuid", ""),
        info.get("baseboard", ""),
        info.get("bios", ""),
        info.get("cpu", ""),
    ]

    raw_parts = [
        PRODUCT_SALT,
        info.get("os", ""),
        *stable_values,
    ]

    if not any(stable_values):
        raw_parts.extend(
            [
                info.get("disk", ""),
                info.get("mac", ""),
            ]
        )

    raw = "|".join(raw_parts)
    code = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return format_machine_code(code)


def get_machine_code() -> str:
    """Generate the final machine code.
    """
    cached_code = read_cached_machine_code()
    if cached_code:
        return cached_code

    try:
        info = get_machine_info()
        code = build_machine_code(info)
        write_cached_machine_code(code)
        return code
    except Exception:
        return FALLBACK_MACHINE_CODE


if __name__ == "__main__":
    print("====== 机器码缓存路径 ======")
    print(get_machine_code_cache_path())
    print()

    print("====== 原始机器信息 ======")
    for key, value in get_machine_info().items():
        print(f"{key}: {value}")

    print()
    print("====== 机器码 ======")
    print(get_machine_code())
