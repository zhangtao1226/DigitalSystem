# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : main.py
# @Desc      : 启动
# @Time      : 2025/11/21 14:09
# @Software  : PyCharm

import os
import shutil
import sys
import multiprocessing
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


RUNTIME_ROOT = get_runtime_root()
os.chdir(RUNTIME_ROOT)
sys.path.insert(0, str(RUNTIME_ROOT))
sys.path.insert(0, str(RUNTIME_ROOT / "src"))

load_dotenv(RUNTIME_ROOT / ".env", verbose=True)

import uvicorn
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QThread, QObject, Signal
from qfluentwidgets import setTheme, Theme, FluentTranslator


from license_core.machine import get_machine_code
from license_core.verify import get_default_license_path, verify_license_file
from src.api.api_server import APIServer
from src.view.login import LoginWindow
from src.utils.LoggerDetector import logger

if os.getenv("SERVICER_VERSION") == "TRUE":
    SERVICER_VERSION = True
else:
    SERVICER_VERSION = False


class LicenseRegisterDialog(QDialog):
    """
    启动前授权注册窗口。

    授权有效时 main() 会直接进入登录页；授权缺失、无效或过期时才显示该窗口。
    """

    def __init__(self, initial_message: str, parent=None):
        super().__init__(parent)
        self.machine_code = get_machine_code()
        self.setWindowTitle("软件注册")
        self.setModal(True)
        self.setMinimumWidth(680)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.status_label = QLabel(initial_message or "请导入 License.json 完成注册。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #B00020;")
        self.license_path_edit = QLineEdit(str(get_default_license_path()))
        self.license_path_edit.setReadOnly(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel("软件注册")
        title_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title_label)

        layout.addWidget(QLabel("当前机器码"))

        machine_code_edit = QPlainTextEdit()
        machine_code_edit.setPlainText(self.machine_code)
        machine_code_edit.setReadOnly(True)
        machine_code_edit.setFixedHeight(78)
        layout.addWidget(machine_code_edit)

        copy_button = QPushButton("复制机器码")
        copy_button.clicked.connect(self._copy_machine_code)
        layout.addWidget(copy_button)

        layout.addWidget(QLabel("授权文件保存位置"))
        layout.addWidget(self.license_path_edit)

        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        import_button = QPushButton("导入 License.json")
        import_button.clicked.connect(self._import_license)

        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.reject)

        button_layout.addWidget(import_button)
        button_layout.addWidget(exit_button)
        layout.addLayout(button_layout)

    def _copy_machine_code(self):
        QApplication.clipboard().setText(self.machine_code)
        self.status_label.setText("机器码已复制。")

    def _import_license(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 License.json",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        selected_path = Path(file_path)
        result = verify_license_file(selected_path)
        if not result.ok:
            self.status_label.setText(result.message)
            QMessageBox.critical(self, "授权失败", result.message)
            return

        target_path = get_default_license_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if selected_path.resolve() != target_path.resolve():
            shutil.copyfile(selected_path, target_path)

        saved_result = verify_license_file(target_path)
        if not saved_result.ok:
            self.status_label.setText(saved_result.message)
            QMessageBox.critical(self, "授权失败", saved_result.message)
            return

        QMessageBox.information(self, "授权成功", "注册完成，下次启动将不再弹出注册窗口。")
        self.accept()


def ensure_registered(parent=None) -> bool:
    result = verify_license_file()
    if result.ok:
        return True

    dialog = LicenseRegisterDialog(result.message, parent)
    return dialog.exec() == QDialog.Accepted


def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontUseNativeDialogs)
    app.setApplicationName("智能OCR档案数字化加工管理系统")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("珥仁科技")

    setTheme(Theme.AUTO)
    translator = FluentTranslator()
    app.installTranslator(translator)

    if not ensure_registered():
        return 1

    if SERVICER_VERSION:
        api_server = APIServer(host="0.0.0.0", port=8000)
        api_server.start()

        app.aboutToQuit.connect(api_server.stop)

    try:
        login_window = LoginWindow()
        login_window.showFullScreen()
        exit_code =  app.exec()

    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        exit_code = 1
    finally:
        if SERVICER_VERSION:
            api_server.stop()

    return exit_code

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
