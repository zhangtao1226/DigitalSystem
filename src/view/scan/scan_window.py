# -*-coding: utf-8 -*-
# @Author    : zhangtao
# @File      : scan_window.py
# @Desc      : 扫描窗口
# @Time      : 2025/12/05
# @Software  : PyCharm
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CheckBox,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    Theme,
    setTheme,
)
from qframelesswindow import FramelessWindow

from src.controllers.common_controller import CommonController
from src.core.cache_manager import global_cache
from src.core.settings import settings
from src.services.archive_stamp_service import archive_stamp_service
from src.services.operation_service import operation_service
from src.services.register_service import register_service
from src.services.scan_images_service import scan_images_service
from src.services.scan_service import scan_service
from src.services.task_mark_service import task_mark_service
from src.services.task_service import task_service
from src.utils.ImageProcessor import ImageProcessor
from src.utils.LoggerDetector import logger
from src.utils.NewScannerDetector import NewScannerDetector
from src.utils.NotificationTool import show_error, show_info, show_success, show_warning
from src.view.common.PartsDialog import PartsDialog
from src.view.common.StampPreviewDialog import StampPreviewDialog
from src.view.common.StampPreviewWidget import StampPreviewWidget

load_dotenv(verbose=True)
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".pdf"}

if os.getenv("SINGLE_VERSION") == "TRUE":
    SINGLE_VERSION = True
else:
    SINGLE_VERSION = False

if os.getenv("SERVICER_VERSION") == "TRUE":
    SERVICER_VERSION = True
else:
    SERVICER_VERSION = False


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self._zoom_initialized = False
        self.init_ui()
        self.load_original_image()

    def init_ui(self):
        self.setWindowTitle("图片预览")
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(0, 0, 0, 180);
            }
        """)

        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        main_widget.setStyleSheet("""
            QWidget#mainWidget {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(Qt.black)
        shadow.setOffset(0, 0)
        main_widget.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #e0e0e0;
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 0, 10, 0)
        toolbar_layout.setSpacing(10)

        self.title_label = QLabel(os.path.basename(self.image_path))
        self.title_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #333;"
        )
        self.title_label.setAlignment(Qt.AlignCenter)

        close_btn = PushButton("X", self)
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            PushButton {
                background-color: #ff6b6b;
                color: white;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
            }
            PushButton:hover {
                background-color: #ff5252;
            }
        """)
        close_btn.clicked.connect(self.close_dialog)

        toolbar_layout.addWidget(self.title_label, 1)
        toolbar_layout.addWidget(close_btn)

        self.image_container = QWidget()
        self.image_container.setStyleSheet("background-color: white;")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                width: 12px;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
                min-width: 20px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #a0a0a0;
            }
        """)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: white;")
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scroll_area.setWidget(self.image_label)
        container_layout.addWidget(self.scroll_area)

        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.image_container, 1)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(20, 20, 20, 20)
        dialog_layout.addWidget(main_widget)

        self.resize(700, 900)

    def load_original_image(self):
        if os.path.exists(self.image_path):
            self.original_pixmap = QPixmap(self.image_path)
            if self.original_pixmap.isNull():
                self.show_error_image("图片加载失败")
            else:
                QTimer.singleShot(100, self.update_image_display)
        else:
            self.show_error_image("图片文件不存在")

    def show_error_image(self, message):
        error_pixmap = QPixmap(400, 300)
        error_pixmap.fill(Qt.white)
        painter = QPainter(error_pixmap)
        painter.setFont(QFont("Arial", 12))
        painter.setPen(Qt.red)
        painter.drawText(error_pixmap.rect(), Qt.AlignCenter, message)
        painter.end()
        self.original_pixmap = error_pixmap
        QTimer.singleShot(100, self.update_image_display)

    def update_image_display(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scroll_area_size = self.scroll_area.viewport().size()
            pixmap_size = self.original_pixmap.size()
            # 计算适应窗口的基准尺寸
            fit_size = pixmap_size.scaled(scroll_area_size, Qt.KeepAspectRatio)
            if not self._zoom_initialized:
                # 首次显示：以适应窗口为基准，zoom_factor 归 1
                self.zoom_factor = 1.0
                self._zoom_initialized = True
            # 按 zoom_factor 在基准尺寸上缩放
            scaled_size = QSize(
                int(fit_size.width() * self.zoom_factor),
                int(fit_size.height() * self.zoom_factor),
            )
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.resize(scaled_size)
            self.scroll_area.setWidgetResizable(False)
            self.scroll_area.setMinimumSize(QSize(0, 0))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口尺寸改变时重置缩放，重新适应窗口
        self._zoom_initialized = False
        QTimer.singleShot(50, self.update_image_display)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.update_image_display)

    def close_dialog(self):
        self.accept()

    def wheelEvent(self, event):
        """鼠标滚轮缩放：向上放大，向下缩小"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_factor = min(self.zoom_factor * 1.15, 10.0)  # 放大，最大 10x
        else:
            self.zoom_factor = max(self.zoom_factor / 1.15, 0.1)  # 缩小，最小 0.1x
        self.update_image_display()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close_dialog()
        else:
            super().keyPressEvent(event)


class QFlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(
            spacing
            if spacing != -1
            else self.style().pixelMetric(QLayout.SP_MarginRole)
        )
        self.item_list = []

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._calculate_layout(width, True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._calculate_layout(rect.width(), False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _calculate_layout(self, width, test_only):
        margins = self.contentsMargins()
        left = margins.left()
        top = margins.top()
        right = margins.right()
        bottom = margins.bottom()
        effective_width = width - left - right

        x = left
        y = top
        line_height = 0

        for item in self.item_list:
            widget = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            widget_size = widget.sizeHint()

            if widget_size.width() > effective_width:
                widget_size.setWidth(effective_width)

            next_x = x + widget_size.width() + space_x
            if next_x - space_x > effective_width and line_height > 0:
                x = left
                y += line_height + space_y
                next_x = x + widget_size.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), widget_size))

            x = next_x
            line_height = max(line_height, widget_size.height())

        return y + line_height + bottom


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫描设置")
        # self.setMinimumSize(750, 750)
        self.resize(780, 770)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
        """)
        self.main_window = parent
        self.init_ui()
        self.load_main_window_data()

    def load_main_window_data(self):
        if self.main_window:
            self.scanner_combo.clear()
            self.scanner_combo.addItems(self.main_window.scanner_list)
            self.scanner_combo.setCurrentText(self.main_window.scanner_device)

            self.path_edit.setText(self.main_window.save_dir_path)
            self.dir_name.setText(self.main_window.save_dir_name)
            self.checkbox.setChecked(self.main_window.is_checkbox)
            self.serial_number_edit.setText(self.main_window.serial_number)

            self.image_type_combo.setText(self.main_window.image_type)
            self.resolution_combo.setText(self.main_window.resolution_dpi)
            self.color_combo.setText(self.main_window.color_value)

    def init_ui(self):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_area.setWidget(scroll_widget)

        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        basic_container = QWidget()
        basic_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        basic_layout = QVBoxLayout(basic_container)
        basic_layout.setSpacing(15)
        basic_layout.setContentsMargins(0, 0, 0, 0)

        basic_title = QLabel("基础设置")
        basic_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #3498db;
                margin-bottom: 10px;
            }
        """)
        basic_title.setMinimumHeight(40)
        basic_layout.addWidget(basic_title)

        scanner_layout = QHBoxLayout()
        scanner_layout.setSpacing(10)
        scanner_label = QLabel("扫描仪选择:", self)
        scanner_label.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: #34495e;
                min-width: 100px;
            }
        """)
        scanner_label.setAlignment(Qt.AlignVCenter)

        self.scanner_combo = ComboBox(self)
        self.scanner_combo.addItems(
            ["默认扫描仪", "扫描仪1", "扫描仪2", "EPSON DS-530 Scanner"]
        )
        self.scanner_combo.setMinimumHeight(36)
        self.scanner_combo.setMinimumWidth(370)
        self.scanner_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        get_scanner_btn = PrimaryPushButton("获取扫描仪", self)
        get_scanner_btn.setFixedSize(120, 36)
        get_scanner_btn.setFont(QFont("Arial", 14))
        get_scanner_btn.setCursor(Qt.PointingHandCursor)
        get_scanner_btn.clicked.connect(self.select_scanner_fun)

        scanner_layout.addWidget(scanner_label)
        scanner_layout.addWidget(self.scanner_combo)
        scanner_layout.addWidget(get_scanner_btn)
        scanner_layout.addStretch(1)
        basic_layout.addLayout(scanner_layout)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        path_label = QLabel("保存路径:", self)
        path_label.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: #34495e;
                min-width: 100px;
            }
        """)
        path_label.setAlignment(Qt.AlignVCenter)

        self.path_edit = LineEdit(self)
        self.path_edit.setPlaceholderText("请选择保存路径")
        self.path_edit.setMinimumHeight(36)
        self.path_edit.setMinimumWidth(410)
        self.path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        browse_btn = PrimaryPushButton("浏览", self)
        browse_btn.setFixedSize(80, 36)
        browse_btn.setFont(QFont("Arial", 14))
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self.select_path)

        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        path_layout.addStretch(1)
        basic_layout.addLayout(path_layout)

        dir_serial_layout = QHBoxLayout()
        dir_serial_layout.setSpacing(20)

        dir_name_widget = QWidget()
        dir_name_widget.setStyleSheet("background-color: transparent;")
        dir_name_layout = QHBoxLayout(dir_name_widget)
        dir_name_layout.setSpacing(5)
        dir_name_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel("文件夹名称:", self)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: #34495e;
                min-width: 100px;
            }
        """)
        self.dir_name = LineEdit(self)
        self.dir_name.setMinimumHeight(36)
        self.dir_name.setMinimumWidth(200)
        self.dir_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dir_name.setPlaceholderText("例如：全宗号+年份等")
        self.dir_name.textChanged.connect(self.change_value_serial)

        serial_number_label = QLabel(" + ", self)
        serial_number_label.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: bold;
                color: #34495e;
            }
        """)

        self.checkbox = CheckBox("")
        self.checkbox.setMinimumHeight(36)
        self.checkbox.setMinimumWidth(36)

        self.serial_number_edit = LineEdit(self)
        self.serial_number_edit.setMinimumHeight(36)
        self.serial_number_edit.setMinimumWidth(150)
        self.serial_number_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.serial_number_edit.setPlaceholderText("例如：0001")

        file_name_example = QLabel("【4位流水号】")

        dir_name_layout.addWidget(name_label)
        dir_name_layout.addWidget(self.dir_name)
        dir_name_layout.addWidget(serial_number_label)
        dir_name_layout.addWidget(self.checkbox)
        dir_name_layout.addWidget(self.serial_number_edit)
        dir_name_layout.addWidget(file_name_example)
        dir_name_layout.addStretch(1)

        dir_serial_layout.addWidget(dir_name_widget)
        basic_layout.addLayout(dir_serial_layout)

        file_serial_layout = QHBoxLayout()
        file_serial_layout.setSpacing(20)

        file_name_widget = QWidget()
        file_name_widget.setStyleSheet("background-color: transparent;")
        file_name_layout = QHBoxLayout(file_name_widget)
        file_name_layout.setSpacing(5)
        file_name_layout.setContentsMargins(0, 0, 0, 0)

        example_label = QLabel("文件名： 文件夹名 + 4位流水号")
        example_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                background-color: #f5f5f5;
                border-radius: 6px;
                padding: 8px 12px;
                margin-top: 5px;
                border: none;
            }
        """)
        file_name_layout.addWidget(example_label)
        file_serial_layout.addWidget(file_name_widget)
        basic_layout.addLayout(file_serial_layout)
        main_layout.addWidget(basic_container)

        param_container = QWidget()
        param_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        param_layout = QVBoxLayout(param_container)
        param_layout.setSpacing(15)
        param_layout.setContentsMargins(0, 0, 0, 0)

        param_title = QLabel("扫描参数设置")
        param_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding-bottom: 10px;
                border-bottom: 2px solid #e67e22;
                margin-bottom: 10px;
            }
        """)
        param_title.setMinimumHeight(40)
        param_layout.addWidget(param_title)

        param_form_container = QWidget()
        param_form_container.setStyleSheet("background-color: transparent;")
        param_form_layout = QVBoxLayout(param_form_container)
        param_form_layout.setSpacing(15)
        param_form_layout.setContentsMargins(0, 0, 0, 0)

        param_row1_widget = QWidget()
        param_row1_widget.setStyleSheet("background-color: transparent;")
        param_row1 = QHBoxLayout(param_row1_widget)
        param_row1.setSpacing(30)
        param_row1.setContentsMargins(0, 0, 0, 0)

        format_widget = QWidget()
        format_widget.setStyleSheet("background-color: transparent;")
        format_layout = QHBoxLayout(format_widget)
        format_layout.setSpacing(5)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setAlignment(Qt.AlignLeft)

        format_label = QLabel("图片格式:", self)
        format_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #34495e;
                min-width: 80px;
            }
        """)
        self.image_type_combo = ComboBox(self)
        self.image_type_combo.addItems(["jpg", "jpeg", "bmp", "tiff", "pdf"])
        self.image_type_combo.setCurrentText("jpg")
        self.image_type_combo.setMinimumHeight(34)
        self.image_type_combo.setMinimumWidth(150)
        self.image_type_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        format_layout.addWidget(format_label)
        format_layout.addWidget(self.image_type_combo)
        format_layout.addStretch()

        dpi_widget = QWidget()
        dpi_widget.setStyleSheet("background-color: transparent;")
        dpi_layout = QHBoxLayout(dpi_widget)
        dpi_layout.setSpacing(5)
        dpi_layout.setContentsMargins(0, 0, 0, 0)
        dpi_layout.setAlignment(Qt.AlignRight)

        resolution_label = QLabel("分辨率(DPI):", self)
        resolution_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #34495e;
                min-width: 80px;
            }
        """)
        self.resolution_combo = ComboBox(self)
        self.resolution_combo.addItems(["75", "100", "150", "200", "300", "400", "600"])
        self.resolution_combo.setCurrentText("300")
        self.resolution_combo.setMinimumHeight(34)
        self.resolution_combo.setMinimumWidth(150)
        self.resolution_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        dpi_layout.addWidget(resolution_label)
        dpi_layout.addWidget(self.resolution_combo)
        dpi_layout.addStretch()
        param_row1.addWidget(format_widget)
        param_row1.addWidget(dpi_widget)
        param_row1.addStretch()

        param_row2_widget = QWidget()
        param_row2_widget.setStyleSheet("background-color: transparent;")
        param_row2 = QHBoxLayout(param_row2_widget)
        param_row2.setSpacing(30)
        param_row2.setContentsMargins(0, 0, 0, 0)

        color_widget = QWidget()
        color_widget.setStyleSheet("background-color: transparent;")
        color_layout = QHBoxLayout(color_widget)
        color_layout.setSpacing(5)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setAlignment(Qt.AlignLeft)
        color_label = QLabel("色彩模式:", self)
        color_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #34495e;
                min-width: 80px;
            }
        """)
        self.color_combo = ComboBox(self)
        self.color_combo.addItems(["黑白", "灰度", "彩色"])
        self.color_combo.setCurrentText("彩色")
        self.color_combo.setMinimumHeight(34)
        self.color_combo.setMinimumWidth(150)
        self.color_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        color_layout.addWidget(color_label)
        color_layout.addWidget(self.color_combo)
        color_layout.addStretch()

        scan_widget = QWidget()
        scan_widget.setStyleSheet("background-color: transparent;")
        scan_layout = QHBoxLayout(scan_widget)
        scan_layout.setSpacing(5)
        scan_layout.setContentsMargins(0, 0, 0, 0)
        scan_layout.setAlignment(Qt.AlignRight)

        scan_label = QLabel("扫描方式:", self)
        scan_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #34495e;
                min-width: 80px;
            }
        """)
        self.scan_combo = ComboBox(self)
        self.scan_combo.addItems(["单面扫描", "双面扫描"])
        self.scan_combo.setCurrentText("单面扫描")
        self.scan_combo.setMinimumHeight(34)
        self.scan_combo.setMinimumWidth(150)
        self.scan_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        scan_layout.addWidget(scan_label)
        scan_layout.addWidget(self.scan_combo)
        scan_layout.addStretch()

        param_row2.addWidget(color_widget)
        param_row2.addWidget(scan_widget)
        param_row2.addStretch()

        param_form_layout.addWidget(param_row1_widget)
        param_form_layout.addWidget(param_row2_widget)
        param_layout.addWidget(param_form_container)
        main_layout.addWidget(param_container)

        btn_container = QWidget()
        btn_container.setStyleSheet("background-color: transparent;")
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(20)
        btn_layout.setContentsMargins(0, 10, 0, 10)
        btn_layout.addStretch()
        self.ok_btn = PrimaryPushButton("确定", self)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setStyleSheet("""
            PrimaryPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            PrimaryPushButton:hover {
                background-color: #219653;
            }
        """)
        self.ok_btn.clicked.connect(self.ok_func)
        self.cancel_btn = PushButton("取消", self)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            PushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            PushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.ok_btn.setFixedSize(120, 40)
        self.cancel_btn.setFixedSize(120, 40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        main_layout.addWidget(btn_container)
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(scroll_area)

    def change_value_serial(self):
        self.serial_number_edit.setText("0001")

    def ok_func(self):
        error_messages = []
        scanner_text = self.scanner_combo.currentText().strip()
        if not scanner_text:
            error_messages.append("请选择扫描仪")

        save_path = self.path_edit.text().strip()
        if not save_path:
            error_messages.append("请选择保存路径")

        if not os.path.exists(save_path):
            error_messages.append(f"该路径【{save_path}】不存在")

        folder_name = self.dir_name.text().strip()
        if not folder_name:
            error_messages.append("请填写文件夹名称")

        is_exist = scan_service.get_dir_name(folder_name)
        if is_exist:
            msg_box = MessageBox(
                "提示", f"该文件夹名称【{folder_name}】已被提交, 是否继续", self
            )
            msg_box.yesButton.setText("继续")
            msg_box.cancelButton.setText("取消")

            if not msg_box.exec():
                return

        if error_messages:
            error_box = MessageBox("参数不完整", "\n".join(error_messages), self)
            error_box.yesButton.setText("我知道了")
            error_box.cancelButton.setVisible(False)
            error_box.exec()
            return

        if self.main_window:
            self.main_window.scanner_device = self.scanner_combo.currentText()
            self.main_window.save_dir_path = self.path_edit.text()
            self.main_window.save_dir_name = self.dir_name.text()
            self.main_window.is_checkbox = self.checkbox.isChecked()
            self.main_window.serial_number = self.serial_number_edit.text() or "0001"
            self.main_window.image_type = self.image_type_combo.currentText()
            self.main_window.resolution_dpi = self.resolution_combo.currentText()
            self.main_window.color_value = self.color_combo.currentText()
            self.main_window.scan_format_value = (
                0 if self.scan_combo.currentText() == "单面扫描" else 1
            )

            params_text = (
                f"格式: {self.main_window.image_type} | "
                f"分辨率: {self.main_window.resolution_dpi} | "
                f"色彩：{self.main_window.color_value} | "
                f"旋转：{self.main_window.angle_value} | "
                f"扫描：{'单面扫描' if self.main_window.scan_format_value == 0 else '双面扫描'} "
            )
            self.main_window.current_params_label.setText(params_text)
            self.main_window.save_dir_path_label.setText(
                f"保存路径: {self.path_edit.text()}"
            )
            self.main_window.current_folder_path = (
                f"{self.main_window.save_dir_path}/"
                f"{self.main_window.save_dir_name}{self.main_window.serial_number}"
            )

            scan_config = {
                "save_dir_name": self.dir_name.text(),
            }
            with open(settings.scan_config_path, "w") as f:
                f.write(json.dumps(scan_config))

        self.accept()

    def select_scanner_fun(self):
        scanner_list = self.main_window.scanner_manager.get_available_scanners()
        if scanner_list:
            self.scanner_combo.clear()
            scanner_list.insert(0, "请选择扫描仪")
            self.scanner_combo.addItems(scanner_list)
            self.main_window.scanner_list = scanner_list
        else:
            show_warning(self, "提示", "获取扫描仪列表失败")
            return

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if path:
            self.path_edit.setText(path)

    def select_input_file(self):

        try:
            file_path = QFileDialog.getOpenFileName()
            file_name, file_ext = os.path.splitext(file_path[0])
            print(f"file_path: {file_path}; file_name: {file_name}")
            if file_ext not in [".xlsx", ".xls"]:
                show_error(self, "警告", f"暂不支持当前文件格式; {file_ext}")
                return

            if file_path:
                self.input_edit.setText(file_name + file_ext)

        except Exception as e:
            logger.error(f"导入分件目录报错: {str(e)}")

    def prev_stamp_model(self):
        stamp_name = self.stamp_combo.currentText()
        if stamp_name == "请选择模版":
            show_warning(self, "预览失败", "请选择归档章模版再预览")
            return
        stamp_info = archive_stamp_service.get_by_name(stamp_name)

        dlg = StampPreviewDialog(stamp_info, self)
        dlg.exec()


class ScanModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择扫描模式")
        self.setFixedSize(350, 250)
        self.selected_mode = "单页扫描"
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")
        self.main_window = parent
        self.init_ui()
        self.load_main_window_data()

    def load_main_window_data(self):
        if self.main_window:
            if self.main_window.scan_mode == "单页扫描":
                self.signal_scan.setChecked(True)
            elif self.main_window.scan_mode == "替换扫描":
                self.replace_scan.setChecked(True)
            elif self.main_window.scan_mode == "插入扫描":
                self.inster_scan.setChecked(True)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 20)
        title_label = QLabel("请选择扫描模式", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0066CC;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        self.signal_scan = QRadioButton("单页扫描")
        self.replace_scan = QRadioButton("替换扫描")
        self.inster_scan = QRadioButton("插入扫描")
        for radio_btn in [self.signal_scan, self.replace_scan, self.inster_scan]:
            radio_btn.setStyleSheet("QRadioButton { font-size: 16px; color: #333; }")
        self.signal_scan.clicked.connect(self.on_mode_selected)
        self.replace_scan.clicked.connect(self.on_mode_selected)
        self.inster_scan.clicked.connect(self.on_mode_selected)
        main_layout.addWidget(self.signal_scan, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.replace_scan, alignment=Qt.AlignCenter)
        main_layout.addWidget(self.inster_scan, alignment=Qt.AlignCenter)
        btn_layout = QHBoxLayout()
        self.ok_btn = PrimaryPushButton("确定", self)
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn = PushButton("取消", self)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.setStyleSheet("""
            PrimaryPushButton {
                background-color: #27ae60; color: white;
                border-radius: 8px; font-size: 16px; font-weight: bold; border: none;
            }
            PrimaryPushButton:hover { background-color: #219653; }
        """)
        self.cancel_btn.setStyleSheet("""
            PushButton {
                background-color: #e74c3c; color: white;
                border-radius: 8px; font-size: 16px; font-weight: bold; border: none;
            }
            PushButton:hover { background-color: #c0392b; }
        """)
        self.ok_btn.setFixedSize(100, 36)
        self.cancel_btn.setFixedSize(100, 36)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def on_mode_selected(self):
        radio = self.sender()
        if radio.isChecked():
            self.selected_mode = radio.text()

    def accept(self):
        self.parent().scan_mode = self.selected_mode
        self.parent().current_mode_label.setText(f"当前模式: {self.selected_mode}")
        super().accept()


class ThumbnailLoader(QThread):
    thumbnail_ready = Signal(int, object)
    load_finished = Signal()

    THUMB_W = 200
    THUMB_H = 250

    def __init__(self, image_paths: list, parent=None):
        super().__init__(parent)
        self._paths = image_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for idx, path in enumerate(self._paths):
            if self._cancelled:
                break
            try:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        self.THUMB_W,
                        self.THUMB_H,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                else:
                    pixmap = None
            except Exception:
                pixmap = None
            self.thumbnail_ready.emit(idx, pixmap)
        self.load_finished.emit()


class ScanWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 扫描")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)

        self.total_scanned = 0
        self.total_pages = 0
        self.scan_mode = "单页扫描"
        self.is_scanning = False

        self.scanner_device = ""  # 扫描仪
        self.save_dir_path = ""  # 保存路径
        self.save_dir_name = ""  # 文件夹名称
        self.is_checkbox = False
        self.serial_number = "0001"  # 文件夹名流水号
        self.current_folder_name = ""  # 当前文件夹名称

        self.image_type = "jpg"  # 图片格式
        self.resolution_dpi = "300"  # 分辨率dpi值
        self.color_value = "彩色"  # 色彩模式
        self.angle_value = "无"  # 旋转角度
        self.scan_format_value = 0

        self.color_model = {"黑白": 0, "灰度": 1, "彩色": 2}

        self.selected_preview_widget = None
        self.selected_image_info = None
        self.preview_widgets = []
        self._path_to_widget: dict = {}
        self._thumb_loader: ThumbnailLoader = None

        self.current_folder_path = ""
        self.base_image_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        self.scan_image_paths = self._get_sample_image_paths()
        self.create_new_dirs_list = []
        self.current_scan_info: dict = {}
        self.scan_files_count = 0

        self.tree_root_path = ""
        self.dir_input_path = ""
        self.stamp_combo_value = "请选择模版"

        self.double_click_timer = QTimer()
        self.double_click_timer.setSingleShot(True)
        self.double_click_timer.timeout.connect(self.handle_single_click)
        self.last_clicked_widget = None
        self.last_click_time = 0

        self._is_navigation = False
        self._is_app_exiting = False

        self.scanner_list = []
        self.scanner_manager = NewScannerDetector()

        self._scan_params: dict = {}  # 当前扫描参数
        self._scan_page_count: int = 0  # 本次已扫描页数
        self._scan_timer = QTimer(self)  # 轮询 TWAIN 的定时器
        self._scan_timer.setInterval(100)  # 每 100ms 取一帧
        self._scan_timer.timeout.connect(self._on_scan_timer_tick)

        self.ocr_detector = None
        self.current_data = global_cache.get("current_data")
        self.batch_number = self.current_data[3] if self.current_data else ""
        self.category = self.current_data[2] if self.current_data else ""
        self.start_number = (
            self.current_data[5].split("-")[0] if self.current_data else ""
        )
        self.end_number = (
            self.current_data[5].split("-")[1] if self.current_data else ""
        )
        self.task_info = task_service.get_by_id(int(self.current_data[0]))
        print(self.task_info)

        self.current_user = global_cache.get("current_user")
        print(f"当前用户: {self.current_user}")
        self.stamp_list = [
            item.template_name for item in archive_stamp_service.get_all()
        ]
        self.stamp_list.insert(0, "请选择模版")

        self._get_scan_config()
        self.init_ui()

    def _get_scan_config(self):
        scan_config_path = settings.scan_config_path

        with open(scan_config_path, "r") as f:
            scan_config = json.load(f)
            print(f"scan_config: {scan_config}")

            if scan_config["save_dir_name"]:
                self.save_dir_name = scan_config["save_dir_name"]

        where = {
            "task_id": self.task_info.id,
            "register_id": self.task_info.register_id,
        }
        scan_info = scan_service.get_scan_info(where)

        if scan_info:
            self.save_dir_path = scan_info[-1].dir_path
            self.current_folder_path = self.save_dir_path

            if self.verify_dir_name(scan_info[-1].dir_name):
                self.serial_number = scan_info[-1].dir_name[-4:]

    def _get_sample_image_paths(self):
        sample_paths = []
        for i in range(1, 13):
            img_name = f"scan_image_{i:04d}.jpg"
            img_path = os.path.join(self.base_image_dir, img_name)
            sample_paths.append(img_path)
        return sample_paths

    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 30, 10, 10)
        main_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        top_container = QWidget()
        top_container.setStyleSheet("background-color: transparent;")
        top_layout = QHBoxLayout(top_container)
        top_layout.setSpacing(20)
        top_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.set_btn = PrimaryPushButton("设置", self)
        self.scan_model_btn = PrimaryPushButton("扫描模式", self)
        self.scan_start_btn = PrimaryPushButton("开始扫描", self)
        self.scan_btn = PrimaryPushButton("持续扫描", self)
        self.scan_stop_btn = PrimaryPushButton("停止扫描", self)

        btn_font = QFont()
        btn_font.setPointSize(16)
        btn_font.setBold(True)

        btn_style = """
            PrimaryPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            PrimaryPushButton:hover {
                background-color: #2980b9;
            }
        """

        for btn in [
            self.set_btn,
            self.scan_model_btn,
            self.scan_start_btn,
            self.scan_btn,
            self.scan_stop_btn,
        ]:
            btn.setFont(btn_font)
            btn.setFixedSize(110, 38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)

        self.set_btn.clicked.connect(self.show_settings)
        self.scan_model_btn.clicked.connect(self.show_scan_mode)
        self.scan_start_btn.clicked.connect(self.start_scan)
        self.scan_btn.clicked.connect(self.scan_fun)
        self.scan_stop_btn.clicked.connect(self.scan_stop_fun)
        # 初始状态：无扫描任务，停止按钮不可用
        self.scan_stop_btn.setEnabled(False)

        btn_layout.addWidget(self.set_btn)
        btn_layout.addWidget(self.scan_model_btn)
        btn_layout.addWidget(self.scan_start_btn)
        btn_layout.addWidget(self.scan_btn)
        btn_layout.addWidget(self.scan_stop_btn)
        top_layout.addLayout(btn_layout)

        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(8)
        batch_layout.setAlignment(Qt.AlignRight)

        number_label = QLabel("批次号:", self)
        self.number_value_label = QLabel(self.batch_number, self)
        self.number_nuit_label = QLabel(self.category, self)
        task_number_label = QLabel("任务起止号:", self)
        self.task_number_start_label = QLabel(self.start_number, self)
        task_number_f_label = QLabel("——", self)
        self.task_number_end_label = QLabel(self.end_number, self)

        info_labels = [number_label, task_number_label]
        value_labels = [
            self.number_value_label,
            self.number_nuit_label,
            self.task_number_start_label,
            self.task_number_end_label,
        ]

        for label in info_labels:
            label.setStyleSheet("font-size:16px; font-weight: bold; color: #333;")
            label.setFixedWidth(100 if label == task_number_label else 70)

        for label in value_labels:
            label.setStyleSheet("""
                QLabel {
                    border-radius: 4px; font-size: 16px; padding: 2px 6px;
                    background-color: white; text-align: center; color: #333; border: none;
                }
            """)
            label.setFixedHeight(40)
            if label == self.number_value_label:
                label.setFixedWidth(120)
            elif label == self.number_nuit_label:
                label.setFixedWidth(40)
            else:
                label.setFixedWidth(60)

        batch_layout.addWidget(number_label)
        batch_layout.addWidget(self.number_value_label)
        batch_layout.addWidget(self.number_nuit_label)
        batch_layout.addSpacing(20)
        batch_layout.addWidget(task_number_label)
        batch_layout.addWidget(self.task_number_start_label)
        batch_layout.addWidget(task_number_f_label)
        batch_layout.addWidget(self.task_number_end_label)

        top_layout.addLayout(batch_layout)
        top_layout.addStretch()

        self.user_label = QLabel("", self)
        self.user_label.setStyleSheet("""
            QLabel {
                background-color: #e6f3ff; border-radius: 12px; padding: 8px 16px;
                font-size: 14px; color: #0066cc; font-weight: bold; border: none;
            }
        """)
        self.user_label.setFixedHeight(40)
        top_layout.addWidget(self.user_label)
        main_layout.addWidget(top_container)

        param_button_layout = QHBoxLayout()
        param_button_layout.setSpacing(15)
        param_button_layout.setContentsMargins(0, 0, 0, 0)

        param_title = QLabel("扫描参数", self)
        param_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0066CC;")
        param_title.setFixedWidth(80)

        self.current_params_label = QLabel(
            "格式: JPG | 分辨率: 300DPI | 色彩：黑白 | 旋转：无", self
        )
        self.current_params_label.setStyleSheet("""
            QLabel {
                border-radius: 6px; padding: 6px 12px;
                background-color: #f0f8ff; font-size: 13px; color: #0066cc; border: none;
            }
        """)
        self.current_params_label.setFixedHeight(36)
        self.current_params_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )

        param_button_layout.addWidget(param_title)
        param_button_layout.addWidget(self.current_params_label)
        param_button_layout.addStretch(1)

        self.sign_btn = PushButton("⚑ 标记")
        self.scan_btn.setToolTip("对当前图片添加质检标记")
        self.delete_btn = PushButton("删除")
        # self.parts_btn = PushButton("分件")
        self.cancel_btn = PushButton("返回")
        self.submit_btn = PrimaryPushButton("提交")

        self.cancel_btn.setStyleSheet("""
            PushButton {
                background-color: #95a5a6; color: white; border-radius: 8px;
                font-size: 16px; font-weight: bold; border: none;
            }
            PushButton:hover { background-color: #7f8c8d; }
        """)
        self.submit_btn.setStyleSheet("""
            PrimaryPushButton {
                background-color: #27ae60; color: white; border-radius: 8px;
                font-size: 16px; font-weight: bold; border: none;
            }
            PrimaryPushButton:hover { background-color: #219653; }
        """)
        self.sign_btn.setStyleSheet("""
            PushButton { background-color:#e53935; color:white; border-radius:8px;
                font-size:15px; font-weight:500; border:none; }
            PushButton:hover { background-color:#c62828; }
        """)
        self.delete_btn.setStyleSheet("""
            PushButton {
                background-color: #f35746; color: white; border-radius: 8px;
                font-size: 16px; font-weight: bold; border: none;
            }
            PushButton:hover { background-color: #e63b25; }
        """)

        for btn in [
            self.submit_btn,
            self.cancel_btn,
            self.cancel_btn,
            self.sign_btn,
            self.delete_btn,
        ]:
            btn.setFixedSize(90, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Arial", 13))

        self.cancel_btn.clicked.connect(self.back_table)
        self.submit_btn.clicked.connect(self.submit_scan)
        # self.parts_btn.clicked.connect(self.part_file_dir)
        self.sign_btn.clicked.connect(self.sing_message_fun)
        self.delete_btn.clicked.connect(self.delete_scan_file)

        # param_button_layout.addWidget(self.parts_btn)
        param_button_layout.addWidget(self.cancel_btn)
        param_button_layout.addWidget(self.submit_btn)
        if self.current_user["role"] in ["管理员", "质检员"]:
            param_button_layout.addWidget(self.sign_btn)

        param_button_layout.addWidget(self.delete_btn)
        main_layout.addLayout(param_button_layout)

        preview_container = QWidget()
        preview_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 4px;
                padding: 15px;
            }
        """)
        preview_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setSpacing(12)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        preview_top_layout = QHBoxLayout()
        preview_title = QLabel("扫描预览", self)
        preview_title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #0066CC;"
        )

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        self.save_dir_path_label = QLabel(f"保存路径： {self.save_dir_path}", self)
        self.total_scanned_label = QLabel(
            f"已扫描文件数: {self.scan_files_count}", self
        )
        self.total_pages_label = QLabel(
            f" 当前文件夹: {self.current_folder_name if self.current_folder_name else '未选择'}, 总页数: {self.total_pages}",
            self,
        )
        self.current_mode_label = QLabel(f"当前模式: {self.scan_mode}", self)
        self.selected_image_label = QLabel("选中图片: 无", self)

        for label in [
            self.save_dir_path_label,
            self.total_scanned_label,
            self.total_pages_label,
            self.current_mode_label,
            self.selected_image_label,
        ]:
            label.setStyleSheet("""
                QLabel { font-size: 14px; font-weight: bold; color: #666; border: none; }
            """)
            label.setMinimumWidth(120)

        stats_layout.addStretch(1)
        stats_layout.addWidget(self.save_dir_path_label)
        stats_layout.addWidget(self.total_scanned_label)
        stats_layout.addWidget(self.total_pages_label)
        stats_layout.addWidget(self.current_mode_label)
        stats_layout.addWidget(self.selected_image_label)
        stats_layout.addStretch()

        preview_top_layout.addWidget(preview_title)
        preview_top_layout.addStretch(1)
        preview_top_layout.addLayout(stats_layout)
        preview_layout.addLayout(preview_top_layout)

        core_horizontal_splitter = QSplitter(Qt.Horizontal)
        core_horizontal_splitter.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        core_horizontal_splitter.setHandleWidth(5)
        core_horizontal_splitter.setStyleSheet("""
            QSplitter::handle { background-color: #e0e0e0; }
            QSplitter::handle:hover { background-color: #3498db; }
        """)

        tree_container = QWidget()
        tree_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 6px;
                padding: 10px;
                margin-right: 10px;
            }
        """)
        tree_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setSpacing(10)
        tree_layout.setContentsMargins(8, 8, 8, 8)

        tree_header_layout = QHBoxLayout()
        tree_title = QLabel("文件目录结构", self)
        tree_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0066CC;")

        self.refresh_tree_btn = PushButton("刷新", self)
        self.refresh_tree_btn.setFixedSize(100, 38)
        self.refresh_tree_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_tree_btn.setStyleSheet("""
            PushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; font-size: 16px;
                font-weight: bold;
            }
            PushButton:hover { background-color: #2980b9; }
        """)
        self.refresh_tree_btn.clicked.connect(self.refresh_file_tree)

        tree_header_layout.addWidget(tree_title)
        tree_header_layout.addStretch()
        tree_header_layout.addWidget(self.refresh_tree_btn)
        tree_layout.addLayout(tree_header_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setColumnCount(1)
        self.file_tree.setIndentation(18)
        self.file_tree.setAnimated(True)
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border-radius: 6px;
                border: 1px solid #e0e0e0;
                font-size: 13px;
                outline: none;
            }
            QTreeWidget::item {
                height: 30px;
                padding-left: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #e8f4fd;
                border-radius: 4px;
            }
            QTreeWidget::branch:has-siblings:!adjoins-item {
                border-image: none;
            }
            QTreeWidget::branch:has-siblings:adjoins-item {
                border-image: none;
            }
            QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
                border-image: none;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                image: none;
            }
        """)
        self.file_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.file_tree.itemClicked.connect(self.on_tree_item_clicked)

        tree_layout.addWidget(self.file_tree)
        core_horizontal_splitter.addWidget(tree_container)

        preview_container_right = QWidget()
        preview_container_right.setStyleSheet(
            "background-color: white; border-radius: 6px; border: 1px solid #e0e0e0;"
        )
        preview_container_right.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        preview_layout_right = QVBoxLayout(preview_container_right)
        preview_layout_right.setContentsMargins(0, 0, 0, 0)
        preview_layout_right.setSpacing(0)
        preview_scroll_widget = QWidget()
        preview_scroll_widget.setStyleSheet("background-color: transparent;")
        self.preview_flow_layout = QFlowLayout(
            preview_scroll_widget, margin=10, spacing=15
        )
        self.preview_flow_layout.setAlignment(Qt.AlignTop)

        self.preview_scroll_area = QScrollArea()
        self.preview_scroll_area.setWidgetResizable(True)
        self.preview_scroll_area.setWidget(preview_scroll_widget)
        self.preview_scroll_area.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical {
                border: none; background: #f0f0f0; width: 12px;
                border-radius: 6px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0; border-radius: 6px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #a0a0a0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none; background: none;
            }
        """)
        self.preview_scroll_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        preview_layout_right.addWidget(self.preview_scroll_area)
        core_horizontal_splitter.addWidget(preview_container_right)
        core_horizontal_splitter.setSizes([300, 900])
        core_horizontal_splitter.setStretchFactor(0, 1)
        core_horizontal_splitter.setStretchFactor(1, 3)
        preview_layout.addWidget(core_horizontal_splitter, stretch=1)
        main_layout.addWidget(preview_container, stretch=1)

        self.setLayout(main_layout)
        self.update_user_label()
        self._check_task_status()

        # 更新树
        if len(self.save_dir_path) > 0:
            self.update_file_tree_path(self.current_folder_path)

    def _check_task_status(self):
        self.can_do_task = None
        where = {
            "register_id": self.task_info.register_id,
            "task_name": "拆卷/前处理",
            "batch_number": self.task_info.batch_number,
        }
        all_pre_node_task_list = task_service.get_data(where)
        if all_pre_node_task_list:
            complete_number_list = []

            for task in all_pre_node_task_list:
                logger.info(f"complete_number: {task.complete_number}")
                if task.complete_number is not None:
                    complete_number_list.append(task.complete_number)

            logger.info(
                f"上一个节点已完成了:{len(complete_number_list)};  {complete_number_list};"
            )

            all_nums = []
            for item in complete_number_list:
                s, e = item.split("-")
                all_nums.extend([int(s), int(e)])

            base_min, base_max = min(all_nums), max(all_nums)

            t_start, t_end = map(
                int, (self.task_info.task_number_start, self.task_info.task_number_end)
            )

            if t_start <= base_min and t_end >= base_max:
                self.can_do_task = f"{str(base_min).zfill(4)}-{str(base_max).zfill(4)}"
            elif t_start >= base_min and t_end <= base_max:
                self.can_do_task = f"{self.task_info.task_number_start}-{self.task_info.task_number_end}"
            else:
                show_warning(self, "警告", "当前没有可以执行任务", 3000)
                return
        else:
            self.can_do_task = (
                f"{self.task_info.task_number_start}-{self.task_info.task_number_end}"
            )

    def _build_tree_item_folder(self, parent, folder_name, folder_path):

        item = QTreeWidgetItem(parent)
        item.setText(0, f"📁  {folder_name}")
        item.setData(0, Qt.UserRole, {"type": "folder", "path": folder_path})
        item.setForeground(0, QColor("#2c3e50"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        item.setFont(0, font)
        return item

    def _build_tree_item_file(self, parent, file_name, file_path):
        item = QTreeWidgetItem(parent)
        item.setText(0, f"🖼  {file_name}")
        item.setData(0, Qt.UserRole, {"type": "file", "path": file_path})
        item.setForeground(0, QColor("#555"))
        font = QFont()
        font.setPointSize(9)
        item.setFont(0, font)
        return item

    def update_file_tree_path(self, target_path):
        if not target_path or not os.path.exists(target_path):
            show_warning(self, "路径无效", "指定的保存路径不存在或无效")
            return

        self.tree_root_path = target_path
        self.file_tree.clear()

        root_name = os.path.basename(target_path) or target_path
        root_item = QTreeWidgetItem(self.file_tree)
        root_item.setText(0, f"🗂  {root_name}")
        root_item.setData(0, Qt.UserRole, {"type": "root", "path": target_path})
        root_item.setForeground(0, QColor("#1a6fac"))
        root_font = QFont()
        root_font.setBold(True)
        root_font.setPointSize(11)
        root_item.setFont(0, root_font)

        has_any = False
        try:
            entries = sorted(os.listdir(target_path))
        except PermissionError:
            show_error(self, "权限错误", "无法读取该目录，请检查权限")
            return

        for entry in entries:
            entry_path = os.path.join(target_path, entry)

            if os.path.isdir(entry_path):
                folder_item = self._build_tree_item_folder(root_item, entry, entry_path)
                has_any = True

                try:
                    sub_entries = sorted(os.listdir(entry_path))
                except PermissionError:
                    sub_entries = []

                for sub_entry in sub_entries:
                    sub_path = os.path.join(entry_path, sub_entry)
                    ext = os.path.splitext(sub_entry)[1].lower()

                    if os.path.isdir(sub_path):
                        sub_folder_item = self._build_tree_item_folder(
                            folder_item, sub_entry, sub_path
                        )
                        try:
                            for f3 in sorted(os.listdir(sub_path)):
                                f3_path = os.path.join(sub_path, f3)
                                if (
                                    os.path.isfile(f3_path)
                                    and os.path.splitext(f3)[1].lower()
                                    in IMG_EXTENSIONS
                                ):
                                    self._build_tree_item_file(
                                        sub_folder_item, f3, f3_path
                                    )
                        except PermissionError:
                            pass
                    elif ext in IMG_EXTENSIONS:
                        self._build_tree_item_file(folder_item, sub_entry, sub_path)

            elif os.path.isfile(entry_path):
                ext = os.path.splitext(entry)[1].lower()
                if ext in IMG_EXTENSIONS:
                    self._build_tree_item_file(root_item, entry, entry_path)
                    has_any = True

        self.file_tree.expandAll()

        if has_any:
            show_success(self, "目录更新", f"已加载目录：{root_name}", 1000)
        else:
            show_info(self, "目录为空", "当前保存路径下暂无文件夹或图片", 1000)

    def refresh_file_tree(self):
        if self.tree_root_path and os.path.exists(self.tree_root_path):
            self.update_file_tree_path(self.tree_root_path)
        else:
            show_warning(self, "刷新失败", "根路径无效，请先在设置中指定保存路径")

    def select_tree_item_by_path(self, target_path):
        root = self.file_tree.invisibleRootItem()

        def _search(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                data = child.data(0, Qt.UserRole)
                if data and data.get("path") == target_path:
                    self.file_tree.setCurrentItem(child)
                    self.file_tree.scrollToItem(child)
                    self.on_tree_item_clicked(child, 0)
                    return True
                if _search(child):
                    return True
            return False

        _search(root)

    def on_tree_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        item_type = data.get("type")
        item_path = data.get("path")

        if item_type == "root":
            return

        if item_type == "folder":
            folder_name = os.path.basename(item_path)
            is_bulk_dir_name = self.verify_dir_name(folder_name)
            if is_bulk_dir_name:
                self.save_dir_name = folder_name[:-5]
                self.serial_number = folder_name[-4:]
            else:
                self.save_dir_name = folder_name
                self.serial_number = "0001"

            self.current_folder_path = item_path
            self.refresh_folder_info()
            self.load_folder_images(item_path)
            self.total_pages_label.setText(
                f"当前文件夹: {folder_name}, 总页数: {self.count_files(self.current_folder_path)}"
            )
            show_success(self, "文件夹选择", f"已加载文件夹：{folder_name}", 1000)

        elif item_type == "file":
            folder_path = os.path.dirname(item_path)
            folder_name = os.path.basename(folder_path)
            is_bulk_dir_name = self.verify_dir_name(folder_name)

            if self.is_checkbox:
                if is_bulk_dir_name:
                    self.save_dir_name = folder_name[:-5]
                    self.serial_number = folder_name[-4:]
                else:
                    self.save_dir_name = folder_name
            else:
                if is_bulk_dir_name:
                    self.save_dir_name = folder_name[:-5]
                else:
                    self.save_dir_name = folder_name
                    self.serial_number = "0001"

            if self.current_folder_path != folder_path:
                self.current_folder_path = folder_path
                self.load_folder_images(folder_path)
                QTimer.singleShot(
                    50, lambda p=item_path: self.scroll_preview_to_path(p)
                )
            else:
                self.scroll_preview_to_path(item_path)

    def refresh_folder_info(self):
        if self.current_folder_path and os.path.exists(self.current_folder_path):
            img_count = 0
            try:
                for f in os.listdir(self.current_folder_path):
                    if os.path.isfile(os.path.join(self.current_folder_path, f)):
                        if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS:
                            img_count += 1
            except PermissionError:
                show_error(
                    self,
                    "报错",
                    f"没有权限: 当前选中的文件夹路径位：{self.current_folder_path}",
                )

    def _get_scan_dir_name_by_folder(self, folder_path):
        try:
            folder_path_obj = Path(folder_path).resolve()
            save_root_obj = Path(self.save_dir_path).resolve()
            return str(folder_path_obj.relative_to(save_root_obj))
        except Exception:
            return os.path.basename(folder_path)

    def _get_scan_record_by_folder(self, folder_path):
        if not folder_path or not self.task_info:
            return None
        dir_name = self._get_scan_dir_name_by_folder(folder_path)
        return scan_service.get_scan_by_folder(
            task_id=self.task_info.id,
            register_id=self.task_info.register_id,
            dir_path=self.save_dir_path,
            dir_name=dir_name,
        )

    def _get_db_image_paths_by_folder(self, folder_path):
        scan_info = self._get_scan_record_by_folder(folder_path)
        if not scan_info:
            return []
        return scan_images_service.get_image_paths_by_scan(scan_info, self.save_dir_path)

    def _get_fs_image_paths_by_folder(self, folder_path):
        image_paths = []
        try:
            for f in sorted(os.listdir(folder_path)):
                fp = os.path.join(folder_path, f)
                if (
                    os.path.isfile(fp)
                    and os.path.splitext(f)[1].lower() in IMG_EXTENSIONS
                ):
                    image_paths.append(fp)
        except PermissionError:
            show_error(self, "权限错误", "无法访问该文件夹，请检查权限")
        return image_paths

    def load_folder_images(self, folder_path):
        if self._thumb_loader and self._thumb_loader.isRunning():
            self._thumb_loader.cancel()
            self._thumb_loader.quit()
            # 延长等待时间，避免大图加载时线程未结束就被 GC 销毁
            if not self._thumb_loader.wait(5000):
                logger.warning("ThumbnailLoader 未能在 5 秒内退出")
            self._thumb_loader.deleteLater()
            self._thumb_loader = None

        self.clear_preview_area()
        self.total_scanned = 0
        self.total_pages = 0

        # 优先使用数据库中的 scan_images 顺序；数据库没有记录时回退读取文件夹。
        self.img_files = self._get_db_image_paths_by_folder(folder_path)
        if not self.img_files:
            self.img_files = self._get_fs_image_paths_by_folder(folder_path)

        if not self.img_files:
            return

        for img_path in self.img_files:
            self._add_preview_placeholder(img_path)

        self._thumb_loader = ThumbnailLoader(self.img_files, parent=self)
        self._thumb_loader.thumbnail_ready.connect(self._apply_thumbnail)
        self._thumb_loader.start()

        # ── 文件夹加载完成后，回显数据库中已有的未处理质检标记 ──
        QTimer.singleShot(600, lambda p=folder_path: self._restore_mark_states(p))

    @Slot(int, object)
    def _apply_thumbnail(self, index: int, pixmap):
        if index >= len(self.preview_widgets):
            return
        widget_info = self.preview_widgets[index]
        if not isinstance(widget_info, dict):
            return
        preview_label = widget_info.get("preview_label")
        if preview_label is None:
            return
        if pixmap is not None:
            preview_label.setPixmap(pixmap)
        else:
            img_path = widget_info.get("info", {}).get("path", "")
            self._draw_placeholder(
                preview_label, f"加载失败\n{os.path.basename(img_path)}"
            )

    def scroll_preview_to_path(self, image_path: str):
        print(f"1111, {image_path}")
        widget_info = self._path_to_widget.get(image_path)
        if not widget_info:
            return
        widget = widget_info.get("widget")
        info = widget_info.get("info")
        if widget and info:
            self.on_preview_clicked(widget, info)
            pos_in_scroll = widget.mapTo(
                self.preview_scroll_area.widget(), widget.rect().topLeft()
            )
            self.preview_scroll_area.ensureVisible(
                pos_in_scroll.x(), pos_in_scroll.y(), widget.width(), widget.height()
            )

    def clear_preview_area(self):
        for i in reversed(range(self.preview_flow_layout.count())):
            item = self.preview_flow_layout.takeAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.selected_preview_widget = None
        self.selected_image_info = None
        self.preview_widgets = []
        self._path_to_widget = {}
        self.selected_image_label.setText("选中图片: 无")

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.update_file_tree_path(self.save_dir_path)
            if self.current_folder_path and os.path.exists(self.current_folder_path):
                QTimer.singleShot(
                    100, lambda: self.select_tree_item_by_path(self.current_folder_path)
                )
            else:
                show_info(self, "设置完成", "扫描参数已更新，请选择文件夹开始扫描")
                return

    def show_scan_mode(self):
        dialog = ScanModeDialog(self)
        dialog.exec()

    def start_scan(self):
        if self.save_dir_path == "":
            show_error(self, "错误提示", "请先设置保存路径")
            return

        if self.save_dir_name == "":
            show_error(self, "错误提示", "请先设置文件夹名称")
            return

        if self.scan_mode in ["替换扫描", "插入扫描"]:
            if self.selected_image_info is None:
                show_warning(
                    self,
                    "警告提示",
                    f"当前扫描模式为：{self.scan_mode}, 请选择单页扫描模式",
                )
                return

        if self.is_checkbox:
            son_dir_name = (
                f"{self.save_dir_path}/{self.save_dir_name}-{self.serial_number}"
            )
            if os.path.exists(son_dir_name):
                self.serial_number = f"{(int(self.serial_number) + 1):04d}"

            self.current_folder_path = (
                f"{self.save_dir_path}/{self.save_dir_name}-{self.serial_number}"
            )
        else:
            self.current_folder_path = f"{self.save_dir_path}/{self.save_dir_name}"

        print(
            f"当前文件夹：{self.current_folder_path}; serial_number: {self.serial_number}"
        )
        os.makedirs(self.current_folder_path, exist_ok=True)

        self.update_file_tree_path(self.save_dir_path)
        QTimer.singleShot(
            150, lambda: self.select_tree_item_by_path(self.current_folder_path)
        )

        self.scan_fun()

    @Slot(str)
    def update_log(self, message):
        self.log_output.append(message)

    def scan_fun(self):

        # 校验当前扫描文件夹已保存扫描件数
        if os.path.exists(self.current_folder_path):
            current_folder_files_count = len(
                self.get_dir_all_images(self.current_folder_path)
            )
            if settings.folder_max_files - current_folder_files_count <= 100:
                show_info(
                    self,
                    "提示",
                    f"当前文件夹已经扫描了 {current_folder_files_count} 件, "
                    f"为保证文件夹操作正常, 请重新创建新文件夹",
                )
                return

        if not os.path.exists(self.current_folder_path):
            show_error(self, "错误提示", "请先点击开始扫描，然后才可以继续扫描")
            return

        if self.scan_mode in ["替换扫描", "插入扫描"]:
            if self.selected_image_info is None:
                show_warning(
                    self,
                    "警告提示",
                    f"当前扫描模式为：{self.scan_mode}, 请先选择{self.scan_mode}图片位置",
                )
                return

        if self.is_scanning:
            show_warning(self, "提示", "扫描正在进行中，请稍候……")
            return

        logger.info(
            f"扫描模式： {self.scan_mode}; 选择图片： {self.selected_image_info}"
        )

        if self.scan_mode == "替换扫描" and self.selected_image_info:
            file_name = self.selected_image_info["name"]
            os.remove(f"{self.selected_image_info['path']}")
        elif self.scan_mode == "插入扫描" and self.selected_image_info:
            name_before = self.selected_image_info["name"]
            name_after = os.path.basename(
                self.img_files[
                    self.img_files.index(f"{self.selected_image_info['path']}") + 1
                ]
            ).split(".")[0]
            file_name = self.get_inserted_name(name_before, name_after)
        else:
            file_name = f"{self.save_dir_name}"

        logger.info(f"file_name: {file_name}")

        self._scan_params = {
            "scanner_device": self.scanner_device,
            "scan_model": self.scan_mode,
            "scan_format": self.scan_format_value,
            "dpi": int(self.resolution_dpi),
            "color_mode": self.color_model[self.color_value],
            "save_format": self.image_type,
            "save_path": self.current_folder_path,
            "file_name": file_name,
            "deskew": True,
            "remove_black_border": True,
            "auto_feed": True,
            "scan_result": [],
        }

        self._set_scan_buttons_enabled(False)

        p = self._scan_params

        try:
            self.scanner_manager.connect_scanner(p["scanner_device"])
        except (ConnectionError, LookupError) as e:
            show_error(
                self, "连接失败", f"扫描仪 【{p['scanner_device']}】 连接失败: {e}"
            )
            self._set_scan_buttons_enabled(True)
            return
        except Exception as e:
            show_error(self, "连接失败", f"连接扫描仪时发生未知错误: {e}")
            self._set_scan_buttons_enabled(True)
            return

        # 2. 应用参数
        try:
            self.scanner_manager.update_params(
                scan_model=p["scan_model"],
                scan_format=p["scan_format"],
                dpi=p["dpi"],
                color_mode=p["color_mode"],
                save_format=p["save_format"],
                save_path=p["save_path"],
                file_name=p["file_name"],
                deskew=p.get("deskew", True),
                remove_black_border=p.get("remove_black_border", True),
                auto_feed=p.get("auto_feed", True),
                scan_result=p.get("scan_result", []),
            )
        except Exception as e:
            show_error(self, "参数错误", f"扫描参数设置失败: {e}")
            self.scanner_manager.disconnect_scanner()
            self._set_scan_buttons_enabled(True)
            return

        # 3. 发起采集请求（在主线程调用，驱动可能弹框也没问题）
        try:
            os.makedirs(p["save_path"], exist_ok=True)
            self.scanner_manager._source.request_acquire(show_ui=False, modal_ui=False)
        except Exception as e:
            show_error(self, "扫描失败", f"发起扫描请求失败: {e}")
            self.scanner_manager.disconnect_scanner()
            self._set_scan_buttons_enabled(True)
            return

        # 4. 延迟后再启动轮询，给扫描仪马达热身时间
        # 高速 ADF 扫描仪从 request_acquire 到图像就绪通常需要 3~5 秒
        # 用 QTimer.singleShot 在主线程延迟，不阻塞 UI
        self._scan_page_count = 0
        self.is_scanning = True
        warmup_ms = 3000  # 热身等待毫秒数，如仍扫到0页可改为 4000 或70005000
        logger.info(f"扫描请求已发出，等待扫描仪马达就绪（{warmup_ms}ms）·····")
        QTimer.singleShot(warmup_ms, self._start_scan_polling)

    def _start_scan_polling(self):
        """热身等待结束后，正式启动轮询 timer"""
        if not self.is_scanning:
            return  # 热身期间用户已取消
        logger.info("扫描仪马达就绪，开始轮询取帧·····")
        self._scan_timer.start()

    def _on_scan_timer_tick(self):
        """QTimer 每 100ms 触发一次，在主线程取一帧 TWAIN 图像"""
        p = self._scan_params
        _TWAIN_COUNT_UNKNOWN = 0xFFFF

        try:
            handle, count = self.scanner_manager._source.xfer_image_natively()
        except Exception as e:
            import twain as _twain

            if isinstance(e, _twain.exceptions.excTWCC_PAPERJAM):
                logger.warning("ADF 无纸/卡纸，扫描正常结束")
            else:
                logger.info(f"图像传输结束或中断: {e}")
            self._finish_scan()
            return

        # ---------------------------------------------------------------
        # 关键：先保存图像，再判断是否结束
        # count=0 表示这是最后一帧，handle 依然有效，必须先保存再 finish
        # 保存完成后在回调里判断是否调 _finish_scan，避免 Source 提前关闭
        # ---------------------------------------------------------------
        is_last_frame = (
            count == 0
            or (
                self.scanner_manager._stop_event.is_set()
                and count != _TWAIN_COUNT_UNKNOWN
            )
            or (
                count == _TWAIN_COUNT_UNKNOWN
                and self.scanner_manager._stop_event.is_set()
            )
        )

        if handle:
            self._scan_page_count += 1
            scan_model = p.get("scan_model", "单页扫描")
            if scan_model in ["替换扫描", "插入扫描"]:
                save_path = f"{p['save_path']}/{p['file_name']}.{p['save_format']}"
            else:
                save_path = self.scanner_manager._resolve_save_path(
                    p["file_name"], p["save_format"], p["save_path"]
                )
            p["scan_result"].append(os.path.basename(save_path))
            logger.info(f"成功取得第 {self._scan_page_count} 帧，准备保存: {save_path}")

            # 图像保存：同步执行（在主线程），保证 Source 关闭前保存完成
            # DIB handle 在 _save_image 内部通过 DIBToBMFile 使用，不依赖 Source 连接状态
            try:
                self.scanner_manager._save_image(handle, save_path)
                logger.info(f"图片保存完成: {save_path}")
            except Exception as save_err:
                logger.error(f"图片保存失败: {save_err}")
            finally:
                # 必须释放 DIB 句柄，否则内存泄漏
                try:
                    import twain as _twain

                    _twain.GlobalHandleFree(handle)
                except Exception:
                    pass

        if is_last_frame:
            self._finish_scan()

    def _finish_scan(self):
        """停止轮询，断开扫描仪，触发完成逻辑"""
        self._scan_timer.stop()
        self.is_scanning = False
        self.scanner_manager._reset_twain_session()
        self.scanner_manager.disconnect_scanner()

        scan_files_count = self._scan_page_count
        save_path = self._scan_params.get("save_path", "")
        scan_files_list = self._scan_params.get("scan_result", [])

        self.scan_files_count += scan_files_count
        logger.info(f"扫描完成，本次共 {scan_files_count} 页")

        self.clear_preview_area()
        self.load_folder_images(self.current_folder_path)
        self.refresh_file_tree()
        self.update_scan_total()
        self.manger_scan_files(
            dir_name=os.path.basename(save_path), files_list=scan_files_list
        )

        operation_data = {
            "task_id": self.current_data[0],
            "task_name": "扫描",
            "operator": self.current_user["username"],
            "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator_remark": (
                f"扫描档案; 扫描保存文件路径：{self.current_folder_path}; "
                f"本次扫描数: {scan_files_count}; "
                f"扫描方式: {'单面扫描' if self.scan_format_value == 0 else '双面扫描'}; "
                f"扫描模式: {self.scan_mode}"
            ),
        }
        if str(Path(self.current_folder_path)) not in self.create_new_dirs_list:
            self.create_new_dirs_list.append(str(Path(self.current_folder_path)))
        try:
            operation_service.save_data([operation_data])
        except Exception as oe:
            logger.error(f"添加操作日志失败: {oe}")

        self._set_scan_buttons_enabled(True)
        show_success(self, "扫描完成", f"本次共扫描 {scan_files_count} 页", 2000)

        # ── 替换扫描完成后，检测被替换图片是否有未处理的质检标记 ──
        if (
            self._scan_params.get("scan_model") == "替换扫描"
            and self.selected_image_info
        ):
            replaced_path = self.selected_image_info.get("path", "")
            if replaced_path:
                QTimer.singleShot(
                    400,
                    lambda p=replaced_path: self._check_and_close_mark_after_rescan(p),
                )

    def scan_stop_fun(self):
        if self.is_scanning:
            logger.info(f"【{self.current_user['username']}】 请求停止扫描")
            self.scanner_manager.request_stop()
            show_info(self, "停止扫描", "停止请求已发送，当前帧传输完毕后自动停止")
        else:
            self.scanner_manager.disconnect_scanner()
            self._set_scan_buttons_enabled(True)

    def _set_scan_buttons_enabled(self, enabled: bool):
        """扫描期间禁用/恢复开始 & 持续扫描按钮，始终保持停止按钮可用"""
        self.scan_start_btn.setEnabled(enabled)
        self.scan_btn.setEnabled(enabled)
        self.submit_btn.setEnabled(enabled)
        # self.parts_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(enabled)
        self.set_btn.setEnabled(enabled)
        self.scan_model_btn.setEnabled(enabled)
        # 停止按钮：扫描中可用，空闲时禁用
        self.scan_stop_btn.setEnabled(not enabled)

    def update_scan_total(self):
        print(f"扫描文件数: {self.scan_files_count}")
        self.total_scanned_label.setText(f"已扫描文件数: {self.scan_files_count}")
        self.total_pages_label.setText(
            f" 当前文件夹: {os.path.basename(self.current_folder_path)}, 总页数: {self.total_pages}"
        )

    def verify_dir_name(self, dir_name):
        pattern = r"\d{4}(?=\.|$)"
        if re.search(pattern, dir_name):
            return True
        return False

    def get_inserted_name(self, name_before, name_after):
        if name_after.startswith(name_before + "_"):
            suffix = name_after[len(name_before) + 1 :]
            return f"{name_before}_0{suffix}"

        return f"{name_before}_1"

    def count_current_dirs(self, current_dir):
        count = 0
        for dir_name in os.listdir(current_dir):
            if dir_name[: len(self.save_dir_name)] == self.save_dir_name:
                count += 1
        return count

    def count_files_in_current_dir(self, current_dir):
        return sum([len(files) for r, d, files in os.walk(current_dir)])

    def on_preview_clicked(self, widget, image_info):
        if self.selected_preview_widget and self.selected_preview_widget != widget:
            self.selected_preview_widget.setStyleSheet("""
                QWidget { background-color: white; border-radius: 6px; }
                QWidget:hover { background-color: #f0f8ff; }
            """)

        if self.selected_preview_widget == widget:
            self.selected_preview_widget = None
            self.selected_image_info = None
            self.selected_image_label.setText("选中图片: 无")
            widget.setStyleSheet("")
        else:
            self.selected_preview_widget = widget
            self.selected_image_info = image_info
            # 点击选中加边框
            widget.setStyleSheet("""
                QWidget { background-color: #e6f7ff; border-radius: 6px; border: 2px solid #3498db; }
            """)
            ext = image_info["path"].split(".")[-1] if "." in image_info["path"] else ""
            self.current_selected_image = f"{image_info['name']}.{ext}"
            self.selected_image_label.setText(f"选中图片: {self.current_selected_image}")

            if self.scan_mode == "替换扫描":
                show_info(self, "替换扫描模式", f"准备替换: {image_info['name']}")
            elif self.scan_mode == "插入扫描":
                show_info(self, "插入扫描模式", f"准备在 {image_info['name']} 后插入新图片")

    def on_preview_double_clicked(self, widget, image_info):
        dialog = ImagePreviewDialog(image_info["path"], self)
        dialog.exec()

    def handle_preview_click(self, widget, image_info):
        current_time = time.time() * 1000
        if (
            self.last_clicked_widget == widget
            and (current_time - self.last_click_time) < 300
        ):
            self.double_click_timer.stop()
            self.on_preview_double_clicked(widget, image_info)
        else:
            self.last_clicked_widget = widget
            self.last_click_time = current_time
            self.double_click_timer.start(300)

    def handle_single_click(self):
        if self.last_clicked_widget:
            for widget_info in self.preview_widgets:
                if (
                    isinstance(widget_info, dict)
                    and widget_info.get("widget") == self.last_clicked_widget
                ):
                    self.on_preview_clicked(
                        self.last_clicked_widget, widget_info.get("info")
                    )
                    break

    def _add_preview_placeholder(self, image_path: str):
        self.total_scanned += 1
        self.total_pages += 1

        preview_widget = QWidget()
        preview_widget.setObjectName("previewWidget")
        preview_widget.setStyleSheet("""
            QWidget#previewWidget { background-color: white; border-radius: 6px; }
            QWidget#previewWidget:hover { background-color: #f0f8ff; }
        """)
        preview_widget.setFixedSize(210, 280)
        preview_widget.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(preview_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        img_container = QWidget(preview_widget)
        img_container.setFixedSize(200, 250)
        img_container.setStyleSheet("background: transparent;")

        preview_label = QLabel(img_container)
        preview_label.setFixedSize(200, 250)
        preview_label.setStyleSheet(
            "QLabel { border-radius: 4px; background-color: #e8e8e8; }"
        )
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setText("...")  # 加载中提示

        mark_badge = QLabel("⚑ 已标记", img_container)
        mark_badge.setFixedSize(72, 22)
        mark_badge.move(4, 4)
        mark_badge.setAlignment(Qt.AlignCenter)
        mark_badge.setStyleSheet("""
            QLabel {
                background-color: #e53935; color: white;
                border-radius: 4px; font-size: 11px;
                font-weight: bold; font-family: 'Microsoft YaHei';
            }
        """)
        mark_badge.setVisible(False)
        mark_badge.raise_()

        img_name = os.path.splitext(os.path.basename(image_path))[0]
        name_label = QLabel(img_name)
        name_label.setStyleSheet("""
            QLabel { font-size: 12px; font-weight: bold; color: #333;
                     background-color: transparent; border: none; }
        """)
        name_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(img_container)
        layout.addWidget(name_label)

        image_info = {
            "name": img_name,
            "path": image_path,
            "index": self.total_scanned,
            "exists": os.path.exists(image_path),
            "widget": preview_widget,
            "name_label": name_label,
        }
        preview_widget.mousePressEvent = lambda e, w=preview_widget, info=image_info: (
            self.handle_preview_click(w, info)
        )

        widget_entry = {
            "widget": preview_widget,
            "info": image_info,
            "preview_label": preview_label,
            "mark_badge": mark_badge,
        }
        self.preview_widgets.append(widget_entry)
        self._path_to_widget[image_path] = widget_entry
        self.preview_flow_layout.addWidget(preview_widget)

    def add_scan_preview(self, custom_path=None):
        self.total_scanned += 1
        self.total_pages += 1

        preview_widget = QWidget()
        preview_widget.setObjectName("previewWidget")
        preview_widget.setStyleSheet("""
            QWidget#previewWidget { background-color: white; border-radius: 6px; }
            QWidget#previewWidget:hover { background-color: #f0f8ff; }
        """)
        preview_widget.setFixedSize(210, 280)
        preview_widget.setCursor(Qt.PointingHandCursor)

        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.setSpacing(4)

        img_container = QWidget(preview_widget)
        img_container.setFixedSize(200, 250)
        img_container.setStyleSheet("background: transparent;")

        preview_label = QLabel(img_container)
        preview_label.setFixedSize(200, 250)
        preview_label.setStyleSheet("""
            QLabel { border-radius: 4px; background-color: #f5f5f5; }
        """)
        preview_label.setAlignment(Qt.AlignCenter)

        if custom_path:
            image_path = custom_path
        else:
            image_index = (self.total_scanned - 1) % len(self.scan_image_paths)
            image_path = self.scan_image_paths[image_index]

        image_exists = os.path.exists(image_path)

        if image_exists:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                preview_label.setPixmap(
                    pixmap.scaled(
                        preview_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            else:
                self._draw_placeholder(
                    preview_label, f"加载失败\n{os.path.basename(image_path)}"
                )
        else:
            self._draw_placeholder(
                preview_label, f"文件不存在\n{os.path.basename(image_path)}"
            )

        mark_badge = QLabel("⚑ 已标记", img_container)
        mark_badge.setFixedSize(72, 22)
        mark_badge.move(4, 4)
        mark_badge.setAlignment(Qt.AlignCenter)
        mark_badge.setStyleSheet("""
            QLabel {
                background-color: #e53935; color: white;
                border-radius: 4px; font-size: 11px;
                font-weight: bold; font-family: 'Microsoft YaHei';
            }
        """)
        mark_badge.setVisible(False)
        mark_badge.raise_()

        batch_num = self.number_value_label.text()
        img_name = (
            os.path.splitext(os.path.basename(image_path))[0]
            if custom_path
            else f"{batch_num}_{self.total_scanned:04d}"
        )

        name_label = QLabel(img_name)
        name_label.setStyleSheet("""
            QLabel {
                font-size: 12px; font-weight: bold; color: #333;
                background-color: transparent; border: none;
            }
        """)
        name_label.setAlignment(Qt.AlignCenter)

        preview_layout.addWidget(img_container)
        preview_layout.addWidget(name_label)

        image_info = {
            "name": img_name,
            "path": image_path,
            "index": self.total_scanned,
            "batch_num": batch_num,
            "exists": image_exists,
            "widget": preview_widget,
            "name_label": name_label,
        }

        preview_widget.mousePressEvent = (
            lambda event, w=preview_widget, info=image_info: self.handle_preview_click(
                w, info
            )
        )

        widget_entry = {
            "widget": preview_widget,
            "info": image_info,
            "preview_label": preview_label,
            "mark_badge": mark_badge,
        }
        self.preview_widgets.append(widget_entry)
        self._path_to_widget[image_path] = widget_entry
        self.preview_flow_layout.addWidget(preview_widget)

    def _set_preview_mark_state(self, image_path: str, mark_type: str = None):
        widget_entry = self._path_to_widget.get(image_path)
        if not widget_entry:
            return

        info = widget_entry.get("info", {})
        widget = widget_entry.get("widget")
        mark_badge = widget_entry.get("mark_badge")
        name_label = info.get("name_label")

        has_mark = mark_type is not None

        if mark_badge:
            if has_mark:
                short_type = mark_type[:5] if len(mark_type) > 5 else mark_type
                mark_badge.setText(f"⚑ {short_type}")
            mark_badge.setVisible(has_mark)

        if name_label:
            color = "#e53935" if has_mark else "#333"
            name_label.setStyleSheet(f"""
                QLabel {{ font-size: 12px; font-weight: bold; color: {color};
                          background-color: transparent; border: none; }}
            """)

        if widget:
            if has_mark:
                widget.setStyleSheet("""
                    QWidget#previewWidget {
                        background-color: #fff5f5; border-radius: 6px;
                        border: 2px solid #e53935;
                    }
                    QWidget#previewWidget:hover { background-color: #ffebee; }
                """)
            else:
                widget.setStyleSheet("""
                    QWidget#previewWidget { background-color: white; border-radius: 6px; }
                    QWidget#previewWidget:hover { background-color: #f0f8ff; }
                """)

    def _set_tree_mark_state(self, file_path: str, has_mark: bool):
        """
        在文件树中对应的叶子节点前加 ⚑ 红色标识，或恢复正常样式。
        """
        root = self.file_tree.invisibleRootItem()

        def _search(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                data = child.data(0, Qt.UserRole) or {}
                if data.get("path") == file_path:
                    base = os.path.basename(file_path)
                    if has_mark:
                        child.setText(0, f"⚑  {base}")
                        child.setForeground(0, QColor("#e53935"))
                        f = child.font(0)
                        f.setBold(True)
                        child.setFont(0, f)
                    else:
                        child.setText(0, f"🖼  {base}")
                        child.setForeground(0, QColor("#555555"))
                        f = child.font(0)
                        f.setBold(False)
                        child.setFont(0, f)
                    return
                _search(child)

        _search(root)

    def _restore_mark_states(self, folder_path: str):
        """
        切换文件夹后，从数据库拉取该文件夹下未修复的质检标记并在缩略图/树上回显。
        在 load_folder_images 末尾通过 QTimer 延迟调用（等缩略图卡片创建完毕）。
        """
        if not self.task_info:
            return
        try:
            pending_marks = task_mark_service.get_pending_marks_by_folder(
                task_id=self.task_info.id,
                folder_path=folder_path,
            )
            for mark in pending_marks:
                img_path = os.path.join(folder_path, mark.scan_file)
                self._set_preview_mark_state(img_path, mark.mark_type)
                self._set_tree_mark_state(img_path, has_mark=True)
        except Exception as e:
            logger.warning(f"回显质检标记失败: {e}")

    def _check_and_close_mark_after_rescan(self, replaced_image_path: str):
        """
        替换扫描完成后调用：若被替换图片存在未修复的质检标记，
        弹框询问质检员是否将其标记为「已修改」，实现重扫闭环。
        """
        if not self.task_info:
            return
        file_name = os.path.basename(replaced_image_path)
        try:
            pending_marks = task_mark_service.get_pending_marks_by_file(
                task_id=self.task_info.id,
                scan_file=file_name,
            )
        except Exception as e:
            logger.warning(f"查询质检标记失败: {e}")
            return

        if not pending_marks:
            return

        mark_summary = "\n".join(
            f"  · [{m.mark_type}]  {(m.description or '')[:20]}{'…' if len(m.description or '') > 20 else ''}"
            for m in pending_marks
        )
        w = MessageBox(
            "完成标记修改",
            f"检测到 {file_name} 有以下未处理标记：\n{mark_summary}\n\n"
            f"重新扫描已完成，是否将以上标记标记为「已修改」？",
            self,
        )
        w.yesButton.setText("确认已修改")
        w.cancelButton.setText("暂不确认")

        if w.exec():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for m in pending_marks:
                try:
                    task_mark_service.mark_fixed(
                        m.id,
                        {
                            "is_fixed": True,
                            "fix_date": now,
                            "fix_remark": (
                                f"已通过替换扫描完成修复"
                                f"（操作人：{self.current_user['username']}）"
                            ),
                        },
                    )
                except Exception as e:
                    logger.error(f"更新标记状态失败 mark_id={m.id}: {e}")

            # 恢复缩略图和文件树正常外观
            self._set_preview_mark_state(replaced_image_path, mark_type=None)
            self._set_tree_mark_state(replaced_image_path, has_mark=False)
            show_success(self, "已完成", f"{file_name} 的质检标记已标记为修改完成")

    def _refresh_mark_state_for_file(self, image_path: str):
        """
        弹框操作完成后，重新查库刷新缩略图角标和文件树状态。
        有未修复标记 → 保持/更新角标；全部修复 → 清除角标。
        """
        if not self.task_info:
            return
        file_name = os.path.basename(image_path)
        try:
            pending = task_mark_service.get_pending_marks_by_file(
                task_id=self.task_info.id,
                scan_file=file_name,
            )
            if pending:
                self._set_preview_mark_state(image_path, pending[0].mark_type)
                self._set_tree_mark_state(image_path, has_mark=True)
            else:
                self._set_preview_mark_state(image_path, mark_type=None)
                self._set_tree_mark_state(image_path, has_mark=False)
        except Exception as e:
            logger.warning(f"刷新标记状态失败: {e}")

    def _draw_placeholder(self, label, text):
        size = label.size()
        img = QImage(size.width(), size.height(), QImage.Format_RGB32)
        img.fill(Qt.white)
        painter = QPainter(img)
        painter.setFont(QFont("Arial", 9))
        painter.setPen(Qt.gray)
        painter.drawText(img.rect(), Qt.AlignCenter, text)
        painter.end()
        label.setPixmap(QPixmap.fromImage(img))

    def submit_scan(self):
        if len(self.create_new_dirs_list) == 0:
            show_warning(self, "提交警告", "暂无扫描文件可提交")
            return

        box = MessageBox(
            "确认提交", f"确定要提交 {self.scan_files_count} 个扫描文件吗？", self
        )
        box.yesButton.setText("提交")
        box.cancelButton.setText("取消")

        if box.exec():
            print(
                f"SINGLE_VERSION = {SINGLE_VERSION}; SERVICER_VERSION = {SERVICER_VERSION}"
            )
            if SINGLE_VERSION and not SERVICER_VERSION:
                logger.info(f"扫描文件提交到服务器上;")
                self.upload_file_to_service()
            else:
                logger.info(
                    f"扫描文件保存到本机中; 保存文件夹路径: {self.save_dir_path}"
                )
                self.save_scan_info()

            show_info(self, "提示", "提交完成!")

            # 备份扫描文件
            self.back_scan_file()

            task_info = task_service.get_by_id(int(self.current_data[0]))

            update = {
                "complete_number": self.can_do_task,
            }
            task_service.update(task_info.id, update)
            task_service.execute_task_submission(
                task_info.id, self.can_do_task.split("-")[-1]
            )
            self.reset_scan_stats()

    def manger_scan_files(self, dir_name: str, files_list: list):
        """
        当前扫描文件信息：文件夹名：[扫描图片名, ·····]
        """

        if dir_name in self.current_scan_info.keys():
            origin_files = self.current_scan_info[dir_name]
            new_files = list(set(origin_files + files_list))
            self.current_scan_info[dir_name] = new_files
        else:
            self.current_scan_info[dir_name] = files_list

    def back_scan_file(self):
        """
        备份扫描文件: 将本次扫描产生的图像文件复制到根目录下的 scan_file_back 目录,
        按原扫描文件夹名分目录保存, 保持原有目录结构。
        """
        if len(self.create_new_dirs_list) == 0:
            logger.info("当前没有扫描文件, 无效备份")
            return

        backup_root = settings.scan_back_path
        try:
            os.makedirs(backup_root, exist_ok=True)
            backed_count = 0
            for src_dir in self.create_new_dirs_list:
                if not os.path.isdir(src_dir):
                    logger.warning(f"备份跳过, 源文件夹不存在: {src_dir}")
                    continue

                dest_dir = os.path.join(backup_root, os.path.basename(src_dir))
                os.makedirs(dest_dir, exist_ok=True)

                for file_name in os.listdir(src_dir):
                    src_file = os.path.join(src_dir, file_name)
                    if not os.path.isfile(src_file):
                        continue
                    if os.path.splitext(file_name)[1].lower() not in IMG_EXTENSIONS:
                        continue

                    shutil.copy2(src_file, os.path.join(dest_dir, file_name))
                    backed_count += 1

            logger.info(
                f"扫描文件备份完成, 共备份 {backed_count} 个文件到: {backup_root}"
            )
        except Exception as e:
            logger.error(f"扫描文件备份失败: {e}")

    def sing_message_fun(self):
        """质检员标记扫描件问题，保存后在缩略图和文件树上显示红色角标"""
        print("质检员标记信息")
        if self.current_user["role"] not in ["管理员", "质检员"]:
            show_warning(
                self,
                "警告",
                f"非管理员或质检员不可标记, 当前用户角色为: 【{self.current_user['role']}】",
            )
            return

        if not self.task_info.is_do:
            show_warning(self, "提示", "当前任务未提交, 暂不可标记!")
            return

        current_image_info = self.selected_image_label.text().strip().split(":")
        print(
            f"current_image_info: {current_image_info}; current_folder_name = {self.current_folder_name}"
        )
        if current_image_info[1].strip() == "无" and self.current_folder_name == "":
            show_warning(self, "提交", "请先选中标记对象, 比如：图片")
            return

        image_name = current_image_info[1].strip()
        image_path = (
            os.path.join(self.current_folder_path, image_name)
            if self.current_folder_path
            else ""
        )

        # ── 查询该扫描件是否已有标记记录 ──
        existing_marks = []
        try:
            if self.task_info:
                existing_marks = task_mark_service.get_mark_info({
                    "task_id":   self.task_info.id,
                    "scan_file": image_name,
                })
        except Exception as e:
            logger.warning(f"查询已有标记失败: {e}")

        if existing_marks:
            from src.view.common.MarkHistoryDialog import MarkHistoryDialog
            history_dlg = MarkHistoryDialog(
                parent=self,
                image_name=image_name,
                marks=existing_marks,
                task_info=self.task_info,
                current_user=self.current_user,
                on_mark_changed=lambda: self._refresh_mark_state_for_file(image_path),
            )
            if not history_dlg.exec():
                self._refresh_mark_state_for_file(image_path)
                return

        from src.view.common.MarkIssueDialog import MarkIssueDialog

        dlg = MarkIssueDialog(mark_stage="扫描质检", target_name=image_name)
        if dlg.exec():
            mark_data = dlg.get_data()

            print(f"mark_data: {mark_data}")

            if len(mark_data["description"]) == 0:
                show_warning(self, "提示", "描述标记内容不可为空!")
                return
            if len(mark_data.get("opt_edit", "")) == 0:
                show_warning(self, "提示", "需要操作内容不可为空!")
                return

            # ── 保存到数据库 ──
            save_data = {
                "task_id": self.task_info.id,
                "batch_number": self.task_info.batch_number,
                "task_node": self.task_info.task_node,
                "mark_stage": 1,  # 扫描质检
                "scan_file": image_name,
                "mark_type": mark_data.get("mark_type", "其他"),
                "level": mark_data.get("level", "一般"),
                "description": mark_data["description"],
                "inspector": self.current_user["username"],
                "mark_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_fixed": False,
            }

            print(f"save_data = {save_data}")
            try:
                task_mark_service.add_mark(save_data)
            except Exception as e:
                logger.error(f"标记保存失败: {e}")
                show_error(self, "失败", "标记保存失败，请重试")
                return

            if image_path:
                self._set_preview_mark_state(
                    image_path, mark_data.get("mark_type", "已标记")
                )
                self._set_tree_mark_state(image_path, has_mark=True)

            show_success(
                self,
                "标记成功",
                f"已对 {image_name} 标记【{mark_data.get('mark_type', '其他')}】",
            )

    def delete_scan_file(self):

        if self.current_user['role'] in ["管理员", "质检员"]:
            print("管理员 或 质检员")

            if not self.task_info.is_do:
                show_warning(self, "警告", f"该任务还未提交, 【{self.current_user['role']}】暂不可以操作")
                return

            # 检测是否标记
            image_path = os.path.join(self.current_folder_path, self.current_selected_image)
            print(f"image_path = {image_path}")

            widget_entry = self._path_to_widget.get(image_path)
            if not widget_entry:
                return

            mark_badge = widget_entry.get("mark_badge").isVisible()
            if mark_badge:
                print("删除图片并标记完成")
                file_name = self.current_selected_image
                try:
                    pending_marks = task_mark_service.get_pending_marks_by_file(
                        task_id=self.task_info.id,
                        scan_file=file_name
                    )
                    print(f"pending_marks: {pending_marks}")
                except Exception as e:
                    logger.warning(f"查询质检标记失败: {e}")
                    return

                if not pending_marks:
                    return

                mark_summary = "\n".join(
                    f"  · [{m.mark_type}]  {(m.description or '')[:20]}{'…' if len(m.description or '') > 20 else ''}"
                    for m in pending_marks
                )
                w = MessageBox(
                    "完成标记修改",
                    f"检测到 {file_name} 有以下未处理标记：\n{mark_summary}\n\n"
                    f"需要删除该扫描件，删除并将标记标记为「已修改」，删除后不可撤销 ？",
                    self,
                )
                w.yesButton.setText("确认已修改")
                w.cancelButton.setText("暂不确认")

                if w.exec():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for m in pending_marks:
                        print(f"m : {m}")
                        try:
                            task_mark_service.mark_fixed(
                                m.id,
                                {
                                    "is_fixed": True,
                                    "fix_date": now,
                                    "fix_remark": (
                                        f"已删除该扫描件"
                                        f"（操作人：{self.current_user['username']}）"
                                    ),
                                },
                            )
                            try:
                                os.remove(image_path)
                                logger.info(f"标签：【{m.mark_type}】, 删除该扫描件:{m.scan_file}")
                            except Exception as e:
                                logger.error(f"删除失败; {m.scan_file}; 原因：{e}")
                        except Exception as e:
                            logger.error(f"更新标记状态失败 mark_id={m.id}: {e}")

                    self.refresh_file_tree()
                    self.select_tree_item_by_path(self.current_folder_path)


            else:
                show_warning(self, "警告", "未标记不可删除")
                return

        else:
            if self.task_info.is_do:
                show_warning(self, "警告", "任务已提交不可再操作")
                return

            w = MessageBox("删除扫描件", "删除后不可撤销， 请确认是否删除？", self)
            w.yesButton.setText("删除")
            w.yesButton.setCursor(Qt.PointingHandCursor)
            w.cancelButton.setText("取消")
            w.cancelButton.setCursor(Qt.PointingHandCursor)

            if w.exec():
                had_selected_image = self.selected_image_label.text().strip()
                print(f"已经选中图片: {had_selected_image}")
                image_name = had_selected_image.split(":")[1].strip()
                print(f"已经选中图片名称: {image_name}")
                if image_name == "无":
                    show_warning(self, "提示", "请选中要删除的扫描件")
                    return

                os.remove(f"{self.current_folder_path}/{image_name}")

                self.refresh_file_tree()
                self.load_folder_images(self.current_folder_path)

                logger.info(
                    f"删除扫描件; 操作人: {self.current_user['username']}; "
                    f"删除扫描件路径: {self.current_folder_path}/{image_name}"
                )

    def part_file_dir(self):
        w = PartsDialog(
            self,
            current_dir_input_path=self.dir_input_path,
            current_stamp_value=self.stamp_combo_value,
        )

        if w.exec():
            dialog_values = w.get_values()
            selected_split_type = dialog_values["split_type"]
            images_list = self.get_dir_all_images(self.current_folder_path)

            if len(images_list) == 0:
                show_error(self, "分件失败", f"当前文件夹下没有任何图片")
                return

            from src.utils.PartsDetector import PartsDetector

            parts_detector = PartsDetector(dir_path=self.current_folder_path)

            if selected_split_type == "目录":
                # 目录分件
                self.dir_input_path = dialog_values["dir_input_path"]
                print(f"dir_input_path = {self.dir_input_path}")
                if not self.dir_input_path:
                    show_warning(self, "分件失败", "未导入分件目录，请先导入目录")
                    return
                if not os.path.exists(self.dir_input_path):
                    logger.warning(f"该目录不存在: {self.dir_input_path}")
                    show_warning(self, "警告", "导入分件目录不存在")
                    return

                result = parts_detector.catalog(self.dir_input_path)

                if result["code"] > 0:
                    show_success(self, "提示", result["message"])
                    self.refresh_file_tree()
                    self.load_folder_images(self.current_folder_path)
                else:
                    show_error(self, "分件失败", result["message"])
                return

            elif selected_split_type == "归档章":
                # 归档章分件
                self.stamp_combo_value = dialog_values["stamp_value"]
                print(f"stamp_combo_value = {self.stamp_combo_value}")
                if self.stamp_combo_value == "请选择模版":
                    show_warning(self, "分件失败", "未选择归档章模板，请先选择模板")
                    return

                result = parts_detector.stamp_parts(self.stamp_combo_value)

                if result["code"] > 0:
                    show_success(self, "提示", result["message"])
                    self.refresh_file_tree()
                    self.load_folder_images(self.current_folder_path)
                else:
                    show_error(self, "分件失败", result["message"])
                return

    def get_ocr_result(self, image_path):

        text_result = self.ocr_detector.detect(image_path)
        print(f"text_result: {text_result}")
        socre_pattern = r"全宗号|保管期限|件号|类别号|年度|机构"
        socre = len(re.findall(socre_pattern, "".join(text_result)))

        page_num = 0
        match = re.search(r"[共其具](\d+)(?:页)?", "".join(text_result))
        if match:
            page_num = match.group(1)

        print(f"socre = {socre}; page = {page_num}")
        return socre, int(page_num)

    def get_dir_all_images(self, dir_path):
        try:
            with os.scandir(dir_path) as entries:
                images_list = [
                    os.path.basename(entry.path)
                    for entry in entries
                    if entry.is_file(follow_symlinks=False)
                ]
        except FileNotFoundError as fe:
            print(f"没有文件; {str(fe)}")
            return []

        images_list = [os.path.basename(image) for image in images_list]
        return images_list

    def get_dir_count(self, dir_path):
        dir_count = 0
        for entry in os.scandir(dir_path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    dir_count += 1
            except PermissionError:
                pass
        return dir_count

    def move_image(self, images_list, target_path):

        for image in images_list:
            image_path = f"{self.current_folder_path}/{image}"
            logger.info(
                f"原图片地址: {image_path}; 目标图片地址: {target_path}/{image}"
            )
            try:
                if not os.path.exists(target_path):
                    os.makedirs(target_path, exist_ok=True)
                # 开始移动图片
                image_target_path = f"{target_path}/{image}"
                shutil.move(image_path, image_target_path)
                logger.info(f"图片移动成功;")
            except FileNotFoundError as fe:
                logger.error(f"原图片不存在; {str(fe)}")
            except PermissionError as pe:
                logger.error(f"没有权限访问图片; {str(pe)}")
            except Exception as e:
                logger.error(f"图片移动失败; {image_path}; 原因：{e}")

    def get_last_four_digits(self, filename):
        name_without_ext = filename.split(".")[0]
        last_four = name_without_ext
        return last_four

    def upload_file_to_service(self):
        for path_name in self.create_new_dirs_list:
            basename = os.path.basename(path_name)
            father_dir = os.path.dirname(path_name)

            if Path(father_dir) != Path(self.save_dir_path):
                dir_name = f"{self.save_dir_name}/{basename}"
            else:
                dir_name = basename

            print(f"dir_name: {dir_name}")
            image_dir_path = f"{self.save_dir_path}/{dir_name}"
            current_dir_file_total = self.count_files(path_name)
            data = {
                "dir_name": dir_name,
                "file_count": current_dir_file_total,
                "image_dir_path": image_dir_path,
                "status": True,
            }
            self.save_scan_images_info(data)

    def save_scan_images_info(self, save_data):
        task_info = task_service.get_by_id(int(self.current_data[0]))
        condition = {
            "task_id": task_info.id,
            "register_id": task_info.register_id,
            "dir_path": self.save_dir_path,
            "dir_name": save_data["dir_name"],
        }
        print(f"condition: {condition}")
        save_info = {
            "dir_path": self.save_dir_path,
            "dir_name": save_data["dir_name"],
            "task_id": task_info.id,
            "register_id": task_info.register_id,
            "file_count": save_data["file_count"],
            "scan_type": self.image_type,
            "scan_dpi": self.resolution_dpi,
            "scan_model": self.color_value,
            "operator": self.current_user["username"],
            "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(f"save_info: {save_info}")
        is_exist = scan_service.get_scan_info(condition)
        print(is_exist)
        scan_id = None
        if is_exist:
            scan_id = is_exist[0].id
            try:
                scan_service.update(scan_id, save_info)
                operation_data = {
                    "task_id": task_info.id,
                    "task_name": "扫描",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"提交扫描信息操作; 扫描信息: {save_info}",
                }
                operation_service.save_data([operation_data])
            except Exception as e:
                logger.error(f"更新扫描信息失败; {str(e)}")
        else:
            logger.info(f"准备保存扫描信息: {save_info}")
            try:
                result = scan_service.save_data([save_info])
                operation_data = {
                    "task_id": task_info.id,
                    "task_name": "扫描",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"提交扫描信息操作; 扫描信息: {save_info}",
                }
                operation_service.save_data([operation_data])
                scan_id = result[0].id
            except Exception as e:
                logger.error(f"扫描; 提交失败: {str(e)}")

        if scan_id is None:
            print(f"scan_id = {scan_id}")
            return

        image_dir_path = save_data["image_dir_path"]
        scan_images_service.sync_scan_images_from_folder(
            scan_id=scan_id,
            image_dir_path=image_dir_path,
            operator=self.current_user["username"],
            extensions=IMG_EXTENSIONS,
        )

        if save_data["status"]:
            # 上传图片文件到服务器
            con = CommonController()
            service_save_path = None
            for file in sorted(os.listdir(image_dir_path)):
                image_path = os.path.join(image_dir_path, file)
                if not os.path.isfile(image_path):
                    continue
                if os.path.splitext(file)[1].lower() not in IMG_EXTENSIONS:
                    continue

                save_upload_path = con.upload_image(
                    image_path=image_path, target_path=save_data["dir_name"]
                )
                if len(save_upload_path) == 0:
                    break
                service_save_path = os.path.dirname(save_upload_path)

            scan_update = {
                "server_save_path": service_save_path,
            }
            print(f"scan_update: {scan_update}; scan_id = {scan_id}")
            scan_service.update(scan_id, scan_update)

    def save_scan_info(self):
        for path_name in self.create_new_dirs_list:
            basename = os.path.basename(path_name)
            father_dir = os.path.dirname(path_name)

            if Path(father_dir) != Path(self.save_dir_path):
                dir_name = f"{self.save_dir_name}/{basename}"
            else:
                dir_name = basename

            print(f"dir_name: {dir_name}")
            image_dir_path = f"{self.save_dir_path}/{dir_name}"
            current_dir_file_total = self.count_files(path_name)
            data = {
                "dir_name": dir_name,
                "file_count": current_dir_file_total,
                "image_dir_path": image_dir_path,
                "status": False,
            }
            self.save_scan_images_info(data)

    def count_files(self, dir_path):
        files = [
            f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))
        ]
        return len(files)

    def reset_scan_stats(self):
        self.total_scanned = 0
        self.total_pages = 0
        self.scan_files_count = 0
        self.selected_image_label.setText("选中图片: 无")
        self.selected_preview_widget = None
        self.selected_image_info = None
        self.preview_widgets = []
        self.clear_preview_area()
        self.update_scan_total()
        self.create_new_dirs_list.clear()

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请关闭重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow

            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            if len(self.create_new_dirs_list) > 0:
                show_warning(self, "提示", "请提交当前扫面文件")
                return

            from src.view.scan.scanTable_window import ScanTableWindow

            scan_table_window = ScanTableWindow()
            scan_table_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label.setText(f"当前用户：【{username}】角色: 【{userrole}】")
        else:
            self.user_label.setText("未登录")
            global_cache.set("current_user", {"username": "admin", "role": "管理员"})
            self.update_user_label()

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        if self._is_navigation:
            event.accept()
            return

        if len(self.create_new_dirs_list) > 0:
            show_warning(self, "提示", "请提交当前扫描文件!")
            return

        if not self._is_app_exiting:
            box = MessageBox("确认退出", "确定要退出应用程序吗？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")

            if box.exec():
                self._is_app_exiting = True
                self._stop_scan_worker_before_close()
                event.accept()
                self.logout()
                from src.view.login import LoginWindow

                self.login_window = LoginWindow()
                self.login_window.showFullScreen()
            else:
                event.ignore()
        else:
            self._stop_scan_worker_before_close()
            event.accept()

    def _stop_scan_worker_before_close(self):
        """窗口关闭时停止正在进行的扫描（主线程 timer 方案，直接 stop 即可）"""
        if not self.is_scanning:
            return
        logger.info("窗口关闭: 正在停止扫描·····")
        self._scan_timer.stop()
        self.is_scanning = False
        try:
            self.scanner_manager._reset_twain_session()
            self.scanner_manager.disconnect_scanner()
        except Exception as e:
            logger.debug(f"关闭时断开扫描仪: {e}")
        # 图片保存已改为主线程同步，无需等待子线程
        logger.info("扫描已停止，窗口关闭")

    def close_without_confirm(self):
        self._is_navigation = True
        QTimer.singleShot(100, self.close)

    def keyPressEvent(self, event: QKeyEvent):
        """全局快捷键：F1 开始扫描，F2 持续扫描"""
        key = event.key()
        if key == Qt.Key_F1:
            if self.scan_start_btn.isEnabled():
                self.start_scan()
        elif key == Qt.Key_F2:
            if self.scan_btn.isEnabled():
                self.scan_fun()
        else:
            super().keyPressEvent(event)
