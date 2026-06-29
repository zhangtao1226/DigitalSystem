# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : new_main_window.py
# @Desc      : 档案数字化加工全流程管理系统-主界面
# @Time      : 2026/3/5 11:30
# @Software  : PyCharm

import os
import sys
import time
from dotenv import load_dotenv

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QHBoxLayout,
    QVBoxLayout, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSpacerItem, QSizePolicy, QDialog, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import (
    QPixmap, QFont, QPainter, QColor, QIcon,
    QPainterPath, QPen
)
from qfluentwidgets import MessageBox
from qframelesswindow import FramelessWindow

from src.core.settings import settings
from src.services.user_service import user_service
from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.role_service import role_service
from src.services.workflow_service import workflow_service
from src.utils.NotificationTool import show_warning, show_info, show_success, show_error

load_dotenv(verbose=True)


def res(name: str) -> str:
    if os.path.isabs(name):
        return name if os.path.exists(name) else ""


class BackgroundWidget(QWidget):
    def __init__(self, bg_path: str, parent=None):
        super().__init__(parent)
        self._bg = QPixmap(bg_path) if bg_path else QPixmap()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._bg.isNull():
            p.drawPixmap(self.rect(), self._bg)
        else:
            p.fillRect(self.rect(), QColor("#0a3060"))
        p.end()
        super().paintEvent(event)


class ImageCard(QLabel):
    clicked = Signal(str, bool)

    def __init__(self, img_path: str, name: str,
                 target_w: int, target_h: int,
                 active: bool = False,
                 radius: int = 12,
                 parent=None):
        super().__init__(parent)
        self.name = name
        self.active = active
        self.radius = radius
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(target_w, target_h)
        self.setAttribute(Qt.WA_Hover, True)

        self._pix = QPixmap()
        if img_path:
            raw = QPixmap(img_path)
            if not raw.isNull():
                self._pix = raw.scaled(
                    target_w, target_h,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 20, 60, 100))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        w, h, r = self.width(), self.height(), self.radius

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(clip)

        if not self._pix.isNull():
            p.drawPixmap(0, 0, self._pix)
        else:
            p.fillRect(0, 0, w, h, QColor("#e0eaf5"))

        if not self.active:
            p.fillRect(0, 0, w, h, QColor(128, 128, 128, 128))
        elif self._hovered:
            p.fillRect(0, 0, w, h, QColor(255, 255, 255, 30))

        p.setClipping(False)

        if not self.active:
            p.setPen(QPen(QColor(128, 128, 128, 128), 3))
            p.drawRoundedRect(1.5, 1.5, w - 3, h - 3, r, r)
        elif self._hovered:
            p.setPen(QPen(QColor(255, 255, 255, 180), 2))
            p.drawRoundedRect(1, 1, w - 2, h - 2, r, r)

        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.name, self.active)


class ArrowLabel(QLabel):
    def __init__(self, strip_path: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 22)
        full = QPixmap(strip_path)
        if not full.isNull():
            unit_w = full.width() // 7
            single = full.copy(unit_w * 2, 0, unit_w, full.height())
            self.setPixmap(single.scaled(18, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class AccountInfoDialog(QDialog):
    def __init__(self, username: str, role: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("账户信息")
        self.setFixedWidth(420)
        self._password_editing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(18)

        title = QLabel("账户信息")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1890ff;")
        layout.addWidget(title)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e8e8e8;")
        layout.addWidget(line)

        form = QFormLayout()
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignRight)

        self.username_edit = QLineEdit(username)
        self.username_edit.setReadOnly(True)
        form.addRow("用户名：", self.username_edit)

        self.role_edit = QLineEdit(role)
        self.role_edit.setReadOnly(True)
        form.addRow("角色：", self.role_edit)

        self.password_edit = QLineEdit("******")
        self.password_edit.setReadOnly(True)
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("密码：", self.password_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.modify_btn = QPushButton("修改密码")
        self.modify_btn.setCursor(Qt.PointingHandCursor)
        self.modify_btn.clicked.connect(self.enable_password_edit)
        btn_layout.addWidget(self.modify_btn)

        self.save_btn = QPushButton("保存")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setStyleSheet("""
            QDialog {
                background: white;
                border-radius: 8px;
            }
            QLineEdit {
                min-height: 32px;
                border: 1px solid #d9d9d9;
                border-radius: 6px;
                padding: 4px 8px;
                background: #f7f8fa;
                color: #333333;
            }
            QLineEdit:read-only {
                color: #666666;
            }
            QPushButton {
                min-width: 82px;
                min-height: 32px;
                border-radius: 6px;
                border: 1px solid #d9d9d9;
                background: #f5f5f5;
                color: #333333;
            }
            QPushButton:hover {
                background: #e8e8e8;
            }
        """)

    def enable_password_edit(self):
        self._password_editing = True
        self.password_edit.clear()
        self.password_edit.setReadOnly(False)
        self.password_edit.setPlaceholderText("请输入新密码（至少6位）")
        self.password_edit.setFocus()
        self.modify_btn.setEnabled(False)

    def is_password_editing(self) -> bool:
        return self._password_editing

    def new_password(self) -> str:
        return self.password_edit.text().strip()


class MainWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能OCR档案数字化加工管理系统")
        # self.resize(1400, 850)
        # self.set_center()
        self._is_navigation = False
        self._is_app_exiting = False

        self.current_user = global_cache.get("current_user", None)
        user_info = user_service.get_user_by_username(self.current_user['username'])
        self.permissions = []
        for role in user_info.roles:
            for permission in role.permissions:
                self.permissions.append(permission.work_name)

        self._style_title_bar()
        self.init_ui()

    def _style_title_bar(self):
        tb = self.titleBar
        tb.setStyleSheet("background: transparent;")

        _btn_base = """
            TitleBarButton {{
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 180);
            }}
            TitleBarButton:hover {{
                background: {hover_bg};
                color: white;
            }}
            TitleBarButton:pressed {{
                background: {pressed_bg};
            }}
        """

        normal_hover   = "rgba(255, 255, 255, 35)"
        normal_pressed = "rgba(255, 255, 255, 18)"
        close_hover    = "rgba(196, 43, 28, 210)"
        close_pressed  = "rgba(196, 43, 28, 140)"

        for btn in (tb.minBtn, tb.maxBtn):
            btn.setStyleSheet(_btn_base.format(
                hover_bg=normal_hover,
                pressed_bg=normal_pressed,
            ))

        tb.closeBtn.setStyleSheet(_btn_base.format(
            hover_bg=close_hover,
            pressed_bg=close_pressed,
        ))

    def set_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        fg = self.frameGeometry()
        fg.moveCenter(screen.center())
        self.move(fg.topLeft())

    def init_ui(self):
        bg_img = res(f"{settings.static_image_path}bg1.png")
        self.bg = BackgroundWidget(bg_img, self)
        main_layout = QVBoxLayout(self.bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._build_header())
        content_wrapper = QWidget()
        content_vbox = QVBoxLayout(content_wrapper)
        content_vbox.setContentsMargins(60, 0, 60, 60)
        content_vbox.addStretch(3)
        content_vbox.addWidget(self._build_top_row(), 0, Qt.AlignCenter)
        content_vbox.addSpacing(40)
        content_vbox.addWidget(self._build_bottom_row(), 0, Qt.AlignCenter)
        content_vbox.addStretch(2)
        main_layout.addWidget(content_wrapper, 1)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(100)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(45, 20, 45, 0)

        title_lbl = QLabel()
        tp = res(f"{settings.static_image_path}标题2.png")
        if tp:
            title_lbl.setPixmap(QPixmap(tp).scaled(600, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            title_lbl.setText("智能OCR档案数字化加工管理系统")
            title_lbl.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")

        lay.addWidget(title_lbl, 0, Qt.AlignVCenter)
        lay.addStretch(1)

        right_widget = QWidget()
        right_lay = QHBoxLayout(right_widget)
        right_lay.setSpacing(20)

        for img_name in ["矢量智能对象1.png", "矢量智能对象3.png"]:
            icon_lbl = QLabel()
            path = res(f"{settings.static_image_path}{img_name}")
            if path:
                icon_lbl.setPixmap(QPixmap(path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if img_name == "矢量智能对象3.png":
                icon_lbl.setCursor(Qt.PointingHandCursor)
                icon_lbl.mousePressEvent = self._show_account_info
            right_lay.addWidget(icon_lbl)

        uname = QLabel(f"{self.current_user['username']}【{self.current_user['role']}】")
        uname.setStyleSheet("color: white; font-size: 15px; margin-left: 5px;")
        right_lay.addWidget(uname)

        exit_btn = QPushButton()
        exit_btn.setFixedSize(30, 30)
        exit_btn.setCursor(Qt.PointingHandCursor)
        ep = res(f"{settings.static_image_path}退出.png")
        if ep:
            exit_btn.setIcon(QIcon(ep))
            exit_btn.setIconSize(QSize(24, 24))
            exit_btn.setStyleSheet("border: none; background: transparent;")
        else:
            exit_btn.setText("⏻")
            exit_btn.setStyleSheet("color: white; font-size: 22px; border: none; background: transparent;")
        exit_btn.clicked.connect(self.quit)
        right_lay.addWidget(exit_btn)

        lay.addWidget(right_widget, 0, Qt.AlignVCenter)
        return header

    def _build_top_row(self) -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setSpacing(8)

        top_row = [
            ("领卷1.png", "领卷登记", True),
            ("-s-拆卷.png", "拆卷/前处理", True),
            ("扫描.png", "扫 描", True),
            ("图处.png", "图像处理", True),
            ("分件.png", "分 件", True),
            ("成品转换.png", "成品转换/输出", True),
            ("装订.png", "装 订", True),
        ]

        cards_data = []
        for row in top_row:
            if row[1] in self.permissions:
                cards_data.append((row[0], row[1], True))
            else:
                cards_data.append((row[0], row[1], False))

        arrow_path = res(f"{settings.static_image_path}箭头.png")

        for i, (img, name, active) in enumerate(cards_data):
            card = ImageCard(
                img_path=res(settings.static_image_path + img),
                name=name,
                target_w=196,
                target_h=260,
                active=active
            )
            card.setCursor(Qt.PointingHandCursor if active else Qt.CustomCursor)
            card.clicked.connect(self._on_card_clicked)
            lay.addWidget(card)

            if i < len(cards_data) - 1:
                lay.addWidget(ArrowLabel(arrow_path))

        return container

    def _build_bottom_row(self) -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setSpacing(25)

        bottom_row = [
            ("目录录入.png", "目录录入/校对", True),
            ("任务分发.png", "任务分发", True),
            ("系统管理.png", "系统管理", True),
            ("统计.png", "统 计", True),
        ]

        cards_data = []
        for row in bottom_row:
            if row[1] in self.permissions:
                cards_data.append((row[0], row[1], True))
            else:
                cards_data.append((row[0], row[1], False))

        for img, name, active in cards_data:
            card = ImageCard(
                img_path=res(settings.static_image_path + img),
                name=name,
                target_w=320,
                target_h=140,
                active=active
            )
            card.setCursor(Qt.PointingHandCursor if active else Qt.CustomCursor)
            card.clicked.connect(self._on_card_clicked)
            lay.addWidget(card)

        return container

    def _on_card_clicked(self, name: str, active: bool):
        if name == "领卷登记" and active:
            self.coupon_registration()
        elif name == "拆卷/前处理" and active:
            self.unrolling_pretreatment()
        elif name == "扫 描" and active:
            self.scan()
        elif name == "图像处理" and active:
            self.image_processing()
        elif name == "分 件" and active:
            self.separate_parts()
        elif name == "成品转换/输出" and active:
            self.product_output()
        elif name == "装 订" and active:
            self.binding()
        elif name == "目录录入/校对" and active:
            self.input_proofread()
        elif name == "任务分发" and active:
            if self.current_user['role'] not in ["管理员"]:
                show_warning(self, "提示", f"当前用户角色为【{self.current_user['role']}】, 没有权限进行任务分发")
                return
            self.task_manage()
        elif name == "系统管理" and active:
            if self.current_user['role'] not in ["管理员"]:
                show_warning(self, "提示", f"当前用户角色为【{self.current_user['role']}】, 没有权限打开系统管理")
                return
            self.system_manage()
        elif name == "统 计" and active:
            self.statistics()
        else:
            show_warning(self, "提示", f"{name}未配置！", 1000)

    def _show_account_info(self, event):
        if event.button() != Qt.LeftButton:
            return

        user = user_service.get_user_by_username(self.current_user["username"])
        if not user:
            show_error(self, "提示", "未找到当前用户信息")
            return

        role_names = [role.name for role in user.roles]
        dialog = AccountInfoDialog(
            username=user.username,
            role="、".join(role_names) or self.current_user.get("role", ""),
            parent=self,
        )

        if not dialog.exec():
            return

        if not dialog.is_password_editing():
            return

        new_password = dialog.new_password()
        if not new_password:
            show_warning(self, "提示", "请输入新密码")
            return
        if len(new_password) < 6:
            show_warning(self, "提示", "密码至少需要6位")
            return

        update_data = {
            "username": user.username,
            "password": new_password,
            "roles": role_names,
            "is_active": user.is_active,
        }
        if user_service.update_user(user.id, update_data):
            show_success(self, "提示", "密码修改成功")
        else:
            show_error(self, "提示", "密码修改失败，请重试")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg.setGeometry(0, 0, self.width(), self.height())
        self.titleBar.raise_()

    def coupon_registration(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.register.registerTable_window import RegisterTableWindow
            RegisterTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)


    def unrolling_pretreatment(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.pretreatment.pretreatmentTable_window import PretreatmentTableWindow
            PretreatmentTableWindow().showFullScreen()
            PretreatmentTableWindow().activateWindow()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def scan(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.scan.scanTable_window import ScanTableWindow
            ScanTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def image_processing(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.image_process.imageProcessTable_window import ImageProcessTableWindow
            ImageProcessTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def binding(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.binding.bindingTable_window import BindingTableWindow
            BindingTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def product_output(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.product_output.productTable_window import ProductTableWindow
            ProductTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def separate_parts(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.bulk_breaking.bulkTable_window import BulkTableWindow
            BulkTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def task_manage(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.task_window.taskTable_window import TaskTableWindow
            TaskTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def system_manage(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.system.system_main import SystemMainWindow
            SystemMainWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def input_proofread(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.dir_recognition.dirTable_window import DirTableWindow
            DirTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def statistics(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.statistics.statistics_table import StatisticsTableWindow
            StatisticsTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def quit(self):
        if not self._is_app_exiting:
            box = MessageBox("确认退出", "确定要退出应用程序？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")

            if box.exec():
                self._is_app_exiting = True
                self.logout()
                from src.view.login import LoginWindow
                self.login_window = LoginWindow()
                self.login_window.showFullScreen()


    def closeEvent(self, event):
        if self._is_navigation:
            event.accept()
            return

        if not self._is_app_exiting:
            box = MessageBox("确认退出", "确定要退出应用程序？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")

            if box.exec():
                self._is_app_exiting = True
                event.accept()
                self.logout()
                from src.view.login import LoginWindow
                self.login_window = LoginWindow()
                self.login_window.showFullScreen()
            else:
                event.ignore()
        else:
            event.accept()

    def close_without_confirm(self):
        self._is_navigation = True
        QTimer.singleShot(100, self.close)
