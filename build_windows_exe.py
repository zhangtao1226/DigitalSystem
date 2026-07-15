# -*- coding: utf-8 -*-
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


APP_NAME = "DigitalSystem"

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

HIDDEN_IMPORT_PACKAGES = [
    # 系统管理页面在 system_main.py 中通过 importlib.import_module() 懒加载。
    # Nuitka 无法稳定追踪字符串动态导入，必须显式包含这个包。
    "src.view.system",
]


def add_data_arguments(command: List[str], project_root: Path) -> None:
    for source, target in DATA_DIRS:
        source_path = project_root / source
        if source_path.exists():
            command.append(f"--include-data-dir={source_path}={target}")

    for source, target in DATA_FILES:
        source_path = project_root / source
        if source_path.exists():
            command.append(f"--include-data-file={source_path}={target}")


def add_hidden_import_arguments(command: List[str]) -> None:
    for package_name in HIDDEN_IMPORT_PACKAGES:
        command.append(f"--include-package={package_name}")


def find_dist_dir(output_root: Path) -> Optional[Path]:
    dist_dirs = sorted(output_root.glob("*.dist"), key=lambda path: path.stat().st_mtime)
    if not dist_dirs:
        return None
    return dist_dirs[-1]


def copy_runtime_files(project_root: Path, dist_dir: Path) -> None:
    env_file = project_root / ".env"
    if env_file.exists():
        shutil.copy2(env_file, dist_dir / ".env")

    for dirname in RUNTIME_DIRS:
        target_dir = dist_dir / dirname
        target_dir.mkdir(parents=True, exist_ok=True)


def run_command(command: Sequence[str], cwd: Path) -> int:
    command = [str(item) for item in command]
    command_line = subprocess.list2cmdline(command)
    print(command_line)

    if platform.system().lower() == "windows":
        # PyCharm Debug 会向 Python 子进程注入 --port 等调试参数。
        # 通过 cmd.exe 启动 Nuitka，可避免调试器改写 python -m nuitka 子进程参数。
        return subprocess.call(["cmd.exe", "/d", "/c", command_line], cwd=cwd)

    return subprocess.call(command, cwd=cwd)


def validate_nuitka_command(command: Sequence[str], main_file: Path) -> bool:
    positional_args = []
    for arg in command[3:]:
        arg_text = str(arg)
        if arg_text.startswith("-"):
            continue
        positional_args.append(arg_text)

    expected_main = str(main_file)
    if positional_args == [expected_main]:
        return True

    print("Nuitka 命令参数异常：")
    print("Nuitka 只能有一个入口文件参数，也就是 main.py。")
    print("当前被识别为位置参数的内容：")
    for item in positional_args:
        print(f"  - {item}")
    print()
    print("请确认命令中不存在类似以下错误片段：")
    print("  --output-dir={output_root} D:\\...\\dist_nuitka")
    print("正确格式应该是一个参数：")
    print("  --output-dir=D:\\...\\dist_nuitka")
    return False


def main() -> int:
    if platform.system().lower() != "windows":
        print("当前系统不是 Windows。Nuitka 不能在 macOS 上交叉编译 Windows exe。")
        print("请把项目复制到 Windows 后执行：python build_windows_exe.py")
        return 1

    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    if not env_file.exists():
        print("未找到 .env。该文件是数据库等运行配置，必须放在项目根目录后再打包。")
        return 1

    output_root = project_root / "dist_nuitka"
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=standalone",
        "--assume-yes-for-downloads",
        "--windows-console-mode=disable",
        "--enable-plugin=pyside6",
        "--include-package=license_core",
        "--include-package=qfluentwidgets",
        f"--output-filename={APP_NAME}.exe",
        f"--output-dir={output_root}",
    ]
    add_data_arguments(command, project_root)
    add_hidden_import_arguments(command)
    main_file = project_root / "main.py"
    command.append(str(main_file))

    print("执行 Nuitka 命令：")
    if not validate_nuitka_command(command, main_file):
        return 1

    exit_code = run_command(command, project_root)
    if exit_code != 0:
        print()
        print("打包失败提示：")
        print("1. 如果日志里出现 Failed to download winlibs/gcc，说明当前 Windows 环境无法从 GitHub 下载 Nuitka 需要的 C 编译器。")
        print("2. 处理方式一：按 Nuitka 日志给出的 URL 手动下载 zip，并复制到日志提示的 Cache 目录。")
        print("3. 处理方式二：安装 Visual Studio Build Tools 的 C++ 编译工具，然后可在脚本中改用 --msvc=latest。")
        print("4. 不建议在 PyCharm Debug 模式下打包，优先使用普通终端运行 python build_windows_exe.py。")
        print("5. 如果日志里出现 module.pymupdf.mupdf.o 或 cc1.exe: out of memory，请同步最新代码并卸载旧的 PyMuPDF/pymupdf 依赖后重试。")
        return exit_code

    dist_dir = find_dist_dir(output_root)
    if dist_dir is None:
        print("Nuitka 打包完成，但没有找到 .dist 输出目录，请检查构建日志。")
        return 1

    copy_runtime_files(project_root, dist_dir)
    print(f"打包完成：{dist_dir}")
    print(f"运行文件：{dist_dir / (APP_NAME + '.exe')}")
    print("发布时请整体复制该 .dist 文件夹，不要只复制 exe。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
