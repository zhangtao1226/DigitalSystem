# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : main.py
# @Desc      : 启动
# @Time      : 2025/11/21 14:09
# @Software  : PyCharm

import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import uvicorn
from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QThread, QObject, Signal
from qfluentwidgets import setTheme, Theme, FluentTranslator


from src.api.api_server import APIServer
from src.view.login import LoginWindow
from src.utils.LoggerDetector import logger

load_dotenv(verbose=True)
if os.getenv("SERVICER_VERSION") == "TRUE":
    SERVICER_VERSION = True
else:
    SERVICER_VERSION = False

def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontUseNativeDialogs)
    app.setApplicationName("智能OCR档案数字化加工管理系统")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("珥仁科技")

    setTheme(Theme.AUTO)
    translator = FluentTranslator()
    app.installTranslator(translator)

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
    sys.exit(main())