# -*- coding: utf-8 -*-
import base64
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

try:
    from license_core.config import APP_VERSION, PRODUCT_NAME
    from license_core.machine import get_machine_code
    from license_core.public_key import PUBLIC_KEY_PEM
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from license_core.config import APP_VERSION, PRODUCT_NAME
    from license_core.machine import get_machine_code
    from license_core.public_key import PUBLIC_KEY_PEM


@dataclass
class LicenseResult:
    ok: bool
    message: str
    payload: Optional[Dict[str, Any]] = None
    license_path: Optional[str] = None
    current_machine_code: Optional[str] = None


def get_default_license_dir() -> Path:
    """Return the writable license directory used by the packaged app."""
    appdata = os.getenv("APPDATA")

    if appdata:
        license_dir = Path(appdata) / PRODUCT_NAME
    else:
        license_dir = Path.cwd() / PRODUCT_NAME

    license_dir.mkdir(parents=True, exist_ok=True)
    return license_dir


def get_default_license_path() -> Path:
    return get_default_license_dir() / "license.json"


def load_public_key():
    return serialization.load_pem_public_key(PUBLIC_KEY_PEM)


def build_payload_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def parse_datetime(value: str) -> datetime:
    value = str(value).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            pass

    raise ValueError(f"无法识别时间格式：{value}")


def validate_license_structure(license_data: dict) -> tuple[bool, str]:
    if not isinstance(license_data, dict):
        return False, "授权文件格式错误"
    if "payload" not in license_data:
        return False, "授权文件缺少 payload"
    if "signature" not in license_data:
        return False, "授权文件缺少 signature"

    payload = license_data.get("payload")
    signature = license_data.get("signature")

    if not isinstance(payload, dict):
        return False, "payload 格式错误"
    if not isinstance(signature, str) or not signature.strip():
        return False, "signature 格式错误"

    required_fields = [
        "product",
        "machine_code",
        "expire_at",
    ]
    for field in required_fields:
        if field not in payload:
            return False, f"授权文件缺少字段：{field}"

    return True, "ok"


def verify_signature(payload: dict, signature_b64: str) -> tuple[bool, str]:
    try:
        payload_bytes = build_payload_bytes(payload)
        signature = base64.b64decode(signature_b64)
        public_key = load_public_key()
        public_key.verify(signature, payload_bytes)
        return True, "签名验证成功"
    except InvalidSignature:
        return False, "授权文件签名无效，可能被修改或不是正规授权"
    except Exception as e:
        return False, f"签名验证失败：{e}"


def verify_product(payload: dict) -> tuple[bool, str]:
    product = str(payload.get("product", "")).strip()
    if product != PRODUCT_NAME:
        return False, "授权文件不属于当前软件"
    return True, "产品验证成功"


def verify_version(payload: dict) -> tuple[bool, str]:
    license_version = str(payload.get("version", "")).strip()
    if not license_version:
        return True, "授权文件未限制版本"
    if license_version != APP_VERSION:
        return False, f"授权版本不匹配，授权版本：{license_version}，当前版本：{APP_VERSION}"
    return True, "版本验证成功"


def verify_machine_code(
    payload: dict,
    current_machine_code: Optional[str] = None,
) -> tuple[bool, str, str]:
    if current_machine_code is None:
        current_machine_code = get_machine_code()

    current_machine_code = current_machine_code.strip().upper()
    license_machine_code = str(payload.get("machine_code", "")).strip().upper()

    if not license_machine_code:
        return False, "授权文件缺少机器码", current_machine_code
    if current_machine_code != license_machine_code:
        return False, "授权文件不属于当前电脑", current_machine_code

    return True, "机器码验证成功", current_machine_code


def verify_expire_time(payload: dict) -> tuple[bool, str]:
    expire_at_text = payload.get("expire_at")
    if not expire_at_text:
        return False, "授权文件缺少过期时间"

    try:
        expire_at = parse_datetime(expire_at_text)
    except Exception as e:
        return False, f"授权过期时间格式错误：{e}"

    now = datetime.now()
    if now > expire_at:
        return False, f"授权已过期，过期时间：{expire_at.strftime('%Y-%m-%d %H:%M:%S')}"

    return True, "授权未过期"


def verify_issued_time(payload: dict) -> tuple[bool, str]:
    issued_at_text = payload.get("issued_at")
    if not issued_at_text:
        return True, "授权文件未包含签发时间"

    try:
        issued_at = parse_datetime(issued_at_text)
    except Exception:
        return True, "签发时间格式无法识别，跳过检查"

    now = datetime.now()
    if issued_at.timestamp() - now.timestamp() > 300:
        return False, "授权文件签发时间异常"

    return True, "签发时间正常"


def verify_license_file(license_path: Optional[Union[str, Path]] = None) -> LicenseResult:
    if license_path is None:
        license_path = get_default_license_path()

    license_path = Path(license_path)
    current_machine_code = get_machine_code()

    if not license_path.exists():
        return LicenseResult(
            ok=False,
            message=f"未找到授权文件：{license_path}",
            license_path=str(license_path),
            current_machine_code=current_machine_code,
        )

    try:
        with open(license_path, "r", encoding="utf-8") as f:
            license_data = json.load(f)
    except Exception as e:
        return LicenseResult(
            ok=False,
            message=f"读取授权文件失败：{e}",
            license_path=str(license_path),
            current_machine_code=current_machine_code,
        )

    ok, msg = validate_license_structure(license_data)
    if not ok:
        return LicenseResult(
            ok=False,
            message=msg,
            license_path=str(license_path),
            current_machine_code=current_machine_code,
        )

    payload = license_data["payload"]
    signature_b64 = license_data["signature"]

    checks = [
        lambda: verify_signature(payload, signature_b64),
        lambda: verify_product(payload),
        lambda: verify_version(payload),
        lambda: verify_issued_time(payload),
        lambda: verify_expire_time(payload),
    ]

    for check in checks:
        ok, msg = check()
        if not ok:
            return LicenseResult(
                ok=False,
                message=msg,
                payload=payload,
                license_path=str(license_path),
                current_machine_code=current_machine_code,
            )

    ok, msg, current_machine_code = verify_machine_code(payload, current_machine_code)
    if not ok:
        return LicenseResult(
            ok=False,
            message=msg,
            payload=payload,
            license_path=str(license_path),
            current_machine_code=current_machine_code,
        )

    return LicenseResult(
        ok=True,
        message="授权验证成功",
        payload=payload,
        license_path=str(license_path),
        current_machine_code=current_machine_code,
    )


def has_module(payload: dict, module_name: str) -> bool:
    if not payload:
        return False

    modules = payload.get("modules", [])
    if not isinstance(modules, list):
        return False

    module_name = module_name.strip()
    return "all" in modules or module_name in modules


def get_license_payload() -> Optional[dict]:
    result = verify_license_file()
    if result.ok:
        return result.payload
    return None


if __name__ == "__main__":
    result = verify_license_file()
    print("====== License 验证结果 ======")
    print("是否成功：", result.ok)
    print("提示信息：", result.message)
    print("授权路径：", result.license_path)
    print("当前机器码：", result.current_machine_code)

    if result.payload:
        print()
        print("====== 授权信息 ======")
        print(json.dumps(result.payload, indent=2, ensure_ascii=False))
