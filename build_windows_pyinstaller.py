# -*- coding: utf-8 -*-
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence


APP_NAME = "珥仁科技-智能OCR档案数字加工管理系统"
# Paddle Inference 在 Windows 上无法稳定读取包含中文字符的模型路径。
# 发布目录保持纯 ASCII，最终 EXE 文件名仍使用上面的中文产品名。
BUILD_NAME = "DigitalSystem"

DATA_DIRS = [
    ("src/resources", "src/resources"),
]

DATA_FILES = [
    (".env", ".env"),
    ("public.sql", "public.sql"),
    ("app.ico", "app.ico"),
    ("placeholder.jpg", "placeholder.jpg"),
    ("src/core/scan_config.json", "src/core/scan_config.json"),
    ("src/core/档案模版.xlsx", "src/core/档案模版.xlsx"),
]

RUNTIME_DIRS = [
    "database",
    "download_images",
    "logs",
    "scan_file_back",
    "upload_images",
]

# 这些包包含字符串动态导入，PyInstaller 的静态分析无法完整发现。
COLLECT_SUBMODULE_PACKAGES = [
    "license_core",
    "src.view.system",
]

# PaddleX 3.3.x 的 OCR pipeline 通过 importlib.metadata 检查这些
# ocr-core extras。它们不是 paddlex 的普通依赖，递归复制不会自动包含。
OCR_CORE_METADATA_PACKAGES = [
    "imagesize",
    "opencv-contrib-python",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
]

# 上述 distributions 对应的实际 import 名称。
OCR_CORE_HIDDEN_IMPORTS = [
    "imagesize",
    "cv2",
    "pyclipper",
    "pypdfium2",
    "bidi",
    "shapely",
]


def add_data_arguments(command: List[str], project_root: Path) -> None:
    separator = os.pathsep

    for source, target in DATA_DIRS:
        source_path = project_root / source
        if source_path.exists():
            command.extend(["--add-data", f"{source_path}{separator}{target}"])

    for source, target in DATA_FILES:
        source_path = project_root / source
        if source_path.exists():
            # PyInstaller 的目标值是目录，不是目标文件名。
            # 例如 public.sql 必须使用目标 "."，否则会生成
            # _internal/public.sql/public.sql 这样的同名目录。
            target_parent = str(Path(target).parent)
            command.extend(["--add-data", f"{source_path}{separator}{target_parent}"])


def add_dynamic_import_arguments(command: List[str]) -> None:
    for package_name in COLLECT_SUBMODULE_PACKAGES:
        command.extend(["--collect-submodules", package_name])


def add_paddleocr_arguments(command: List[str]) -> None:
    # PaddleOCR 官方 PyInstaller 打包要求：PaddleX 数据、Paddle 动态库和依赖 metadata。
    # 使用 PyInstaller 的递归 metadata 收集，避免依赖 PaddleX 私有的 DEP_SPECS；
    # 该私有属性在 PaddleX 3.3.x 中已经不存在。
    command.extend(["--collect-data", "paddlex"])
    command.extend(["--collect-data", "paddleocr"])
    command.extend(["--collect-binaries", "paddle"])
    command.extend(["--recursive-copy-metadata", "paddlex"])
    command.extend(["--recursive-copy-metadata", "paddleocr"])
    command.extend(["--copy-metadata", "paddlepaddle"])

    for package_name in OCR_CORE_METADATA_PACKAGES:
        command.extend(["--copy-metadata", package_name])

    for module_name in OCR_CORE_HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])


def copy_runtime_files(project_root: Path, dist_dir: Path) -> None:
    # PyInstaller 的 --add-data 默认放入 _internal。原 Nuitka 构建则把这些
    # 资源放在 EXE 同级。这里保持原来的目录结构，并让需要更新的配置可写。
    for source, target in DATA_DIRS:
        source_path = project_root / source
        if source_path.exists():
            shutil.copytree(source_path, dist_dir / target, dirs_exist_ok=True)

    for source, target in DATA_FILES:
        source_path = project_root / source
        if source_path.exists():
            target_path = dist_dir / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    for dirname in RUNTIME_DIRS:
        (dist_dir / dirname).mkdir(parents=True, exist_ok=True)


def validate_dist(project_root: Path, dist_dir: Path) -> bool:
    """验证发布目录，而不是 PyInstaller 的中间工作目录。"""
    required_paths = [
        dist_dir / f"{APP_NAME}.exe",
        dist_dir / ".env",
        dist_dir / "public.sql",
        dist_dir / "src" / "core" / "scan_config.json",
        dist_dir / "src" / "core" / "档案模版.xlsx",
        dist_dir / "_internal",
        dist_dir / "_internal" / f"python{sys.version_info.major}{sys.version_info.minor}.dll",
        dist_dir / "_internal" / "paddlex",
    ]
    required_paths.extend(dist_dir / dirname for dirname in RUNTIME_DIRS)

    missing_paths = [path for path in required_paths if not path.exists()]
    internal_dir = dist_dir / "_internal"
    missing_metadata = []
    if internal_dir.exists():
        for package_name in OCR_CORE_METADATA_PACKAGES:
            normalized_name = package_name.replace("-", "_")
            if not any(internal_dir.glob(f"{normalized_name}-*.dist-info")):
                missing_metadata.append(package_name)

    model_root = dist_dir / "src" / "resources" / "ocr_model"
    required_model_dirs = [
        model_root / "PP-OCRv5_mobile_det",
        model_root / "PP-OCRv5_server_rec_infer",
    ]
    missing_paths.extend(path for path in required_model_dirs if not path.is_dir())
    for model_dir in required_model_dirs:
        for filename in ("inference.json", "inference.pdiparams", "inference.yml"):
            model_file = model_dir / filename
            if not model_file.is_file() or model_file.stat().st_size == 0:
                missing_paths.append(model_file)

    if missing_metadata:
        print("OCR core 依赖 metadata 未进入发布包：")
        for package_name in missing_metadata:
            print(f"  - {package_name}")

    if not missing_paths:
        return not missing_metadata

    print("发布目录校验失败，缺少以下文件或目录：")
    for path in missing_paths:
        print(f"  - {path}")
    print(f"源 .env 是否存在：{(project_root / '.env').exists()}")
    return False


def run_command(command: Sequence[str], cwd: Path) -> int:
    command = [str(item) for item in command]
    print(subprocess.list2cmdline(command))
    return subprocess.call(command, cwd=cwd)


def main() -> int:
    if platform.system().lower() != "windows":
        print("当前系统不是 Windows。PyInstaller 不能在 macOS 上交叉编译 Windows exe。")
        print("请在 Windows 环境执行：python build_windows_pyinstaller.py")
        return 1

    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    if not env_file.exists():
        print("未找到 .env。该文件是数据库等运行配置，必须放在项目根目录后再打包。")
        return 1

    main_file = project_root / "main.py"
    if not main_file.exists():
        print(f"未找到入口文件：{main_file}")
        return 1

    output_root = project_root / "dist_pyinstaller"
    # 此目录只有 PyInstaller 中间文件，其中的 exe 不可运行。
    # 使用点开头的目录名，避免与最终发布目录混淆。
    work_root = project_root / ".pyinstaller_work"

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        BUILD_NAME,
        "--distpath",
        str(output_root),
        "--workpath",
        str(work_root),
    ]

    icon_file = project_root / "app.ico"
    if icon_file.exists():
        command.extend(["--icon", str(icon_file)])

    add_data_arguments(command, project_root)
    add_dynamic_import_arguments(command)

    add_paddleocr_arguments(command)

    command.append(str(main_file))

    print("执行 PyInstaller 命令：")
    exit_code = run_command(command, project_root)
    if exit_code != 0:
        print()
        print("打包失败，请检查上方 PyInstaller 日志中的第一个 ERROR/Traceback。")
        print("确认当前环境已安装：pyinstaller、paddlepaddle、paddlex、paddleocr。")
        return exit_code

    dist_dir = output_root / BUILD_NAME
    if not dist_dir.exists():
        print(f"PyInstaller 打包完成，但没有找到输出目录：{dist_dir}")
        return 1

    copy_runtime_files(project_root, dist_dir)

    built_exe = dist_dir / f"{BUILD_NAME}.exe"
    published_exe = dist_dir / f"{APP_NAME}.exe"
    if BUILD_NAME != APP_NAME:
        if not built_exe.exists():
            print(f"未找到 PyInstaller 生成的程序：{built_exe}")
            return 1
        built_exe.rename(published_exe)

    if not validate_dist(project_root, dist_dir):
        print("请不要运行或发布此构建。")
        return 1

    paddlex_data_dir = dist_dir / "_internal" / "paddlex"
    print(f"打包完成：{dist_dir}")
    print(f"运行文件：{dist_dir / (APP_NAME + '.exe')}")
    print(f"PaddleX 资源：{paddlex_data_dir}")
    print(f"配置文件：{dist_dir / '.env'}")
    print(f"日志目录：{dist_dir / 'logs'}")
    print(f"注意：{work_root} 是中间目录，其中的 exe 不可运行。")
    print("发布时请整体复制 DigitalSystem 文件夹，不要只复制 exe。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
