# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : login.py
# @Desc      : 登陆页面
# @Time      : 2025/11/21 17:00
# @Software  : PyCharm

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QLabel, QWidget, QComboBox, QPushButton
)
from PySide6.QtCore import Qt, QRect, QTimer, QSettings, QSize, QObject, QThread, Signal
from PySide6.QtGui import (
    QKeyEvent, QFont, QPixmap, QPainter,
    QBrush, QLinearGradient, QColor, QPen, QIcon
)
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash
from qfluentwidgets import (
    PrimaryPushButton, LineEdit, FluentIcon,
    setTheme, Theme
)
from qframelesswindow import FramelessWindow

from src.core.db import (
    initialize_database_tables,
)
from src.core.settings import settings
from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.user_service import UserService, user_service
from src.services.operation_service import operation_service
from src.utils.NotificationTool import show_error, show_warning, show_success, show_info

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, verbose=True, override=True)

if os.getenv("DATABASE_SWITCH") == "TRUE":
    DATABASE_SWITCH = True
else:
    DATABASE_SWITCH = False

def _res(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


class DatabaseUsernameLoader(QObject):
    finished = Signal(str, object)

    def run(self):
        service = None
        try:
            initialize_database_tables()
            service = UserService()
            usernames = [user.username for user in service.get_all_users()]
            self.finished.emit("success", usernames)
        except SQLAlchemyError as e:
            logger.warning(f"加载用户名下拉列表失败: {e}")
            self.finished.emit("database_error", str(e))
        except Exception as e:
            logger.warning(f"加载用户名下拉列表失败: {e}")
            self.finished.emit("init_error", str(e))
        finally:
            if service is not None:
                service.db.close()


class LoginWorker(QObject):
    finished = Signal(str, object)

    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        service = None
        try:
            initialize_database_tables()
            service = UserService()
            user = service.get_user_by_username(self.username)
            if not user:
                self.finished.emit("user_not_found", None)
                return

            if user.is_active is False:
                self.finished.emit("user_disabled", None)
                return

            if not check_password_hash(user.password, self.password):
                self.finished.emit("password_error", None)
                return

            role_names = [role.name for role in user.roles]
            user_info = {
                "username": self.username,
                "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "role": role_names[0] if role_names else "",
            }
            service.update_login_time(user.id)
            self.finished.emit("success", user_info)
        except SQLAlchemyError as e:
            logger.error(f"登录失败: 本地数据库异常; {e}")
            self.finished.emit("database_error", None)
        except Exception as e:
            logger.error(f"登录失败: {e}")
            self.finished.emit("login_error", None)
        finally:
            if service is not None:
                service.db.close()


class LoginPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        corner_pen = QPen(QColor(0, 220, 255, 255), 2)
        painter.setPen(corner_pen)
        g = QLinearGradient(rect.left(), 0, rect.right(), 0)
        g.setColorAt(0.0, QColor(0, 180, 255, 0))
        g.setColorAt(0.5, QColor(0, 220, 255, 160))
        g.setColorAt(1.0, QColor(0, 180, 255, 0))
        painter.setBrush(QBrush(g))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect.left(), rect.bottom() - 2, rect.width(), 5)


class LoginWindow(FramelessWindow):
    PANEL_W = 420
    PANEL_H = 360
    USERNAME_HISTORY_KEY = "login/username_history"
    USERNAME_HISTORY_LIMIT = 20

    def __init__(self):
        super().__init__()
        self._database_available = None
        self._username_loader_thread = None
        self._username_loader_worker = None
        self._login_thread = None
        self._login_worker = None
        self.setWindowTitle("系统登录")
        self.resize(1400, 850)
        self.set_center()
        setTheme(Theme.LIGHT)
        self._build_widgets()
        self._layout_widgets()

    def set_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        bg = QPixmap(_res(f"{settings.static_image_path}bG.png"))
        if not bg.isNull():
            painter.drawPixmap(self.rect(), bg)
        else:
            painter.fillRect(self.rect(), QColor(3, 14, 50))

    def _build_widgets(self):
        self.titleBar.setStyleSheet("background: transparent;")
        self._title_label = QLabel(self)
        self._title_label.setAttribute(Qt.WA_TranslucentBackground)
        title_px = QPixmap(_res(f"{settings.static_image_path}标题2.png"))
        if not title_px.isNull():
            self._title_label.setPixmap(
                title_px.scaledToHeight(50, Qt.SmoothTransformation)
            )
        else:
            self._title_label.setText("珥仁科技 | 智能OCR档案数字化加工管理系统")
            self._title_label.setStyleSheet(
                "color: white; font-size: 34px; font-weight: bold;"
            )
        self._title_label.adjustSize()
        self.panel = LoginPanel(self)
        self.panel.setFixedSize(self.PANEL_W, self.PANEL_H)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setAlignment(Qt.AlignHCenter)
        panel_layout.setSpacing(16)
        panel_layout.setContentsMargins(40, 28, 40, 32)

        sub = QLabel("用户登录")
        sub.setAlignment(Qt.AlignCenter)
        sub.setAttribute(Qt.WA_TranslucentBackground)
        sub.setStyleSheet(
            "color: white; font-size: 20px; font-weight: bold; letter-spacing: 4px;"
        )
        panel_layout.addWidget(sub)
        panel_layout.addSpacing(8)
        self.username_edit = self._make_icon_input(
            _res(f"{settings.static_image_path}用户名.png"), "用户名", combo=True
        )
        panel_layout.addWidget(self.username_edit)
        self.password_edit = self._make_icon_input(
            _res(f"{settings.static_image_path}密码.png"), "密码", password=True
        )
        panel_layout.addWidget(self.password_edit)
        panel_layout.addSpacing(12)
        self.login_button = PrimaryPushButton("登  录", self.panel)
        self.login_button.setFixedHeight(46)
        btn_font = QFont()
        btn_font.setPointSize(15)
        btn_font.setBold(True)
        self.login_button.setFont(btn_font)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setStyleSheet(
            "PrimaryPushButton {"
            "  background: qlineargradient("
            "    x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #3a5fa0, stop:0.5 #6050c8, stop:1 #3a5fa0"
            "  );"
            "  color: white; border: none; border-radius: 3px;"
            "  letter-spacing: 8px;"
            "}"
            "PrimaryPushButton:hover {"
            "  background: qlineargradient("
            "    x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #4a6fb0, stop:0.5 #7060d8, stop:1 #4a6fb0"
            "  );"
            "}"
            "PrimaryPushButton:pressed {"
            "  background: qlineargradient("
            "    x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #2a4f90, stop:0.5 #5040b8, stop:1 #2a4f90"
            "  );"
            "}"
        )
        panel_layout.addWidget(self.login_button)
        self.login_button.clicked.connect(self.handle_login)
        self._username_line().returnPressed.connect(self.focus_password_field)

        self._load_username_options()
        QTimer.singleShot(0, self._start_database_username_loader)
        self._password_line().setText("123456")


    def _layout_widgets(self):
        w, h = self.width(), self.height()
        title_y = int(h * 0.12)
        title_x = (w - self._title_label.width()) // 2
        self._title_label.move(title_x, title_y)
        panel_x = (w - self.PANEL_W) // 2
        panel_y = int(h * 0.5) - self.PANEL_H // 2 + int(h * 0.03)
        self.panel.move(panel_x, panel_y)
        self.titleBar.raise_()

    def _make_icon_input(self, icon_path: str, placeholder: str,
                         password: bool = False, combo: bool = False) -> QWidget:
        container = QWidget()
        container.setAttribute(Qt.WA_TranslucentBackground)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        icon_lbl = QLabel()
        px = QPixmap(icon_path)
        if not px.isNull():
            icon_lbl.setPixmap(
                px.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        icon_lbl.setFixedSize(42, 44)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "background: white;"
            "border-top: 1px solid #c8c8c8;"
            "border-left: 1px solid #c8c8c8;"
            "border-bottom: 1px solid #c8c8c8;"
            "border-right: none;"
        )

        if combo:
            edit = QComboBox()
            edit.setEditable(True)
            edit.setFixedHeight(44)
            edit.setInsertPolicy(QComboBox.NoInsert)
            edit.lineEdit().setPlaceholderText(placeholder)
            edit.lineEdit().setClearButtonEnabled(True)
            edit.setStyleSheet(
                "QComboBox {"
                "  border: 1px solid #c8c8c8;"
                "  border-right: none;"
                "  border-radius: 0px;"
                "  font-size: 15px;"
                "  padding-left: 6px;"
                "  background: white;"
                "}"
                "QComboBox:focus {"
                "  border: 1px solid #66aaff;"
                "}"
                "QComboBox::drop-down {"
                "  width: 0px;"
                "  border: none;"
                "}"
                "QComboBox::down-arrow {"
                "  image: none;"
                "}"
                "QComboBox QAbstractItemView {"
                "  background: white;"
                "  selection-background-color: #e6f4ff;"
                "  selection-color: #333333;"
                "}"
            )
        else:
            edit = LineEdit()
            edit.setPlaceholderText(placeholder)
            edit.setFixedHeight(44)
            edit.setClearButtonEnabled(True)
            if password:
                edit.setEchoMode(LineEdit.Password)
            edit.setStyleSheet(
                "LineEdit {"
                "  border: 1px solid #c8c8c8;"
                "  border-radius: 0px;"
                "  font-size: 15px;"
                "  padding-left: 6px;"
                "  background: white;"
                "}"
                "LineEdit:focus {"
                "  border: 1px solid #66aaff;"
                "}"
            )

        h_layout.addWidget(icon_lbl)
        h_layout.addWidget(edit)
        if combo:
            arrow_btn = self._make_combo_arrow_button(edit)
            h_layout.addWidget(arrow_btn)
            container._arrow_btn = arrow_btn
        container._edit = edit.lineEdit() if combo else edit
        container._combo = edit if combo else None
        return container

    def _make_combo_arrow_button(self, combo: QComboBox) -> QPushButton:
        arrow_btn = QPushButton()
        arrow_btn.setFixedSize(44, 44)
        arrow_btn.setCursor(Qt.PointingHandCursor)
        arrow_btn.setFocusPolicy(Qt.NoFocus)

        arrow_icon = self._fluent_down_icon()
        if not arrow_icon.isNull():
            arrow_btn.setIcon(arrow_icon)
            arrow_btn.setIconSize(QSize(18, 18))
        else:
            arrow_btn.setText("∨")
            arrow_btn.setFont(QFont("Microsoft YaHei", 17, QFont.Bold))

        arrow_btn.setStyleSheet(
            "QPushButton {"
            "  border: 1px solid #c8c8c8;"
            "  border-left: 1px solid #b8d4f4;"
            "  background: #eaf4ff;"
            "  color: #2f5f9f;"
            "  border-radius: 0px;"
            "}"
            "QPushButton:hover {"
            "  background: #d8ecff;"
            "}"
            "QPushButton:pressed {"
            "  background: #c7e2ff;"
            "}"
        )
        arrow_btn.clicked.connect(combo.showPopup)
        return arrow_btn

    def _fluent_down_icon(self) -> QIcon:
        for icon_name in ("CHEVRON_DOWN", "DOWN", "ARROW_DOWN"):
            icon = getattr(FluentIcon, icon_name, None)
            if icon and hasattr(icon, "icon"):
                return icon.icon()
        return QIcon()

    def _username_line(self):
        return self.username_edit._edit

    def _password_line(self) -> LineEdit:
        return self.password_edit._edit

    def _username_combo(self) -> QComboBox:
        return self.username_edit._combo

    def _show_database_connection_error(self, detail: str = ""):
        message = "本地数据库异常"
        if detail:
            message = f"{message}: {detail}"
        show_error(self, "提示", message, duration=8000)

    def _load_username_options(self):
        self._set_username_options(self._stored_username_history())

    def _start_database_username_loader(self):
        if self._username_loader_thread and self._username_loader_thread.isRunning():
            return

        self._username_loader_thread = QThread(self)
        self._username_loader_worker = DatabaseUsernameLoader()
        self._username_loader_worker.moveToThread(self._username_loader_thread)

        self._username_loader_thread.started.connect(self._username_loader_worker.run)
        self._username_loader_worker.finished.connect(self._on_database_username_options_loaded)
        self._username_loader_worker.finished.connect(self._username_loader_thread.quit)
        self._username_loader_worker.finished.connect(self._username_loader_worker.deleteLater)
        self._username_loader_thread.finished.connect(self._username_loader_thread.deleteLater)
        self._username_loader_thread.finished.connect(self._clear_username_loader)
        self._username_loader_thread.start()

    def _on_database_username_options_loaded(self, status: str, result):
        self._database_available = status == "success"
        if status == "success":
            self._set_username_options(self._stored_username_history() + list(result))
        elif status == "init_error":
            logger.warning(f"加载用户名下拉列表失败: 数据库初始化失败; {result}")
            show_error(self, "提示", f"数据库初始化失败: {result}", duration=8000)
        else:
            logger.warning(f"加载用户名下拉列表失败: 本地数据库异常; {result}")
            self._show_database_connection_error(result)

    def _clear_username_loader(self):
        self._username_loader_thread = None
        self._username_loader_worker = None

    def _set_username_options(self, usernames):
        current_username = self._username_line().text().strip()
        if current_username:
            usernames = [current_username] + list(usernames)

        if "admin" not in usernames:
            usernames.append("admin")

        unique_usernames = []
        for username in usernames:
            if username and username not in unique_usernames:
                unique_usernames.append(username)

        combo = self._username_combo()
        combo.clear()
        combo.addItems(unique_usernames)
        self._username_line().setText(current_username or (unique_usernames[0] if unique_usernames else "admin"))

    def _save_username_history(self, username: str):
        stored_usernames = self._stored_username_history()
        usernames = [username] + [name for name in stored_usernames if name != username]
        usernames = usernames[:self.USERNAME_HISTORY_LIMIT]
        QSettings("ERREN", "DigitalSystem").setValue(self.USERNAME_HISTORY_KEY, usernames)

    def _stored_username_history(self):
        value = QSettings("ERREN", "DigitalSystem").value(self.USERNAME_HISTORY_KEY, [])
        if isinstance(value, str):
            return [value] if value else []
        return list(value) if value else []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_widgets()

    def focus_password_field(self):
        self._password_line().setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.handle_login()
        else:
            super().keyPressEvent(event)

    def handle_login(self):
        username = self._username_line().text().strip()
        password = self._password_line().text().strip()

        if not username:
            show_error(self, "提示", "请输入账号")
            self._username_line().setFocus()
            return
        if not password:
            show_error(self, "提示", "请输入密码")
            self._password_line().setFocus()
            return

        if self._login_thread and self._login_thread.isRunning():
            return

        self.login_button.setEnabled(False)
        self.login_button.setText("登录中...")

        self._login_thread = QThread(self)
        self._login_worker = LoginWorker(username, password)
        self._login_worker.moveToThread(self._login_thread)

        self._login_thread.started.connect(self._login_worker.run)
        self._login_worker.finished.connect(self._on_login_finished)
        self._login_worker.finished.connect(self._login_thread.quit)
        self._login_worker.finished.connect(self._login_worker.deleteLater)
        self._login_thread.finished.connect(self._login_thread.deleteLater)
        self._login_thread.finished.connect(self._clear_login_worker)
        self._login_thread.start()

    def _on_login_finished(self, status: str, user_info):
        self.login_button.setEnabled(True)
        self.login_button.setText("登  录")

        if status == "database_error":
            self._database_available = False
            self._show_database_connection_error()
            return

        if status == "user_not_found":
            self._database_available = True
            show_error(self, "登录错误", "用户不存在！")
            return

        if status == "user_disabled":
            self._database_available = True
            show_warning(self, "警告提示", "该用户名已被禁用！")
            return

        if status == "password_error":
            self._database_available = True
            show_error(self, "登录错误", "账号或密码错误")
            self._password_line().clear()
            self._password_line().setFocus()
            return

        if status == "success":
            self._database_available = True
            global_cache.set("current_user", user_info)
            self._save_username_history(user_info["username"])
            logger.info(f"用户登录; username: {user_info['username']}; role: {user_info['role']}")
            self._open_main_window()
            return

        show_error(self, "登录错误", "登录失败，请稍后重试")

    def _clear_login_worker(self):
        self._login_thread = None
        self._login_worker = None


    def _open_main_window(self):
        from src.view.new_main_window import MainWindow
        self.main_window = MainWindow()
        self.main_window.showFullScreen()
        QTimer.singleShot(100, self.close)
