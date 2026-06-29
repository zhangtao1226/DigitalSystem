# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : bulk_window.py
# @Desc     : 分件
# @Time     : 2026/3/6 16:52
# @Software : PyCharm
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime

from PySide6.QtCore import QDir, QMimeData, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QIcon,
    QImage,
    QKeyEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
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
    CheckBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    Theme,
    setTheme,
)
from qframelesswindow import FramelessWindow
from src.core.cache_manager import global_cache
from src.core.db import SessionLocal
from src.core.settings import settings
from src.services.archive_stamp_service import archive_stamp_service
from src.services.operation_service import operation_service
from src.services.register_service import register_service
from src.services.scan_service import scan_service
from src.services.task_service import task_service
from src.utils.ImageProcessor import ImageProcessor
from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_error, show_info, show_success, show_warning

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class ImagePreviewDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.original_pixmap = None
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
            scaled_size = pixmap_size.scaled(scroll_area_size, Qt.KeepAspectRatio)
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.resize(scaled_size)
            self.scroll_area.setMinimumSize(scaled_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_image_display)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.update_image_display)

    def close_dialog(self):
        self.accept()

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


class BulkWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 分件")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)

        self.total_scanned = 0
        self.total_pages = 0
        self.is_scanning = False

        self.selected_preview_widget = None
        self.selected_image_info = None
        self.preview_widgets = []

        self.current_folder_path = ""
        self.current_image = None
        self.base_image_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        self.scan_image_paths = self._get_sample_image_paths()

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

        self.task_id = global_cache.get("task_id")
        self.current_user = global_cache.get("current_user", None)

        self.task_info = task_service.get_by_id(self.task_id)

        scan_task_where = {
            "register_id": self.task_info.register_id,
            "task_node": 2,
        }
        self.scan_task_info = task_service.get_data(scan_task_where)
        print(f"scan_task_info: {self.scan_task_info}")
        self.register_info = register_service.get_by_id(self.task_info.register_id)
        print(f"register_info: {self.register_info}")

        task_ids = [scan.id for scan in self.scan_task_info]
        print(f"task_ids: {task_ids}")
        scan_info = scan_service.get_scan_info_taskId(task_ids)
        print(f"11111, scan_info: {scan_info}")

        self.dir_name_list = []
        for scan in scan_info:
            dir_name = scan.dir_name.split("/")
            print(222, dir_name)
            if dir_name[0] not in self.dir_name_list:
                self.dir_name_list.append(dir_name[0])

        self.tree_root_path = scan_info[-1].dir_path
        if not os.path.exists(self.tree_root_path):
            self.tree_root_path = f"{os.getcwd()}/upload_images"

        self.batch_number = self.task_info.batch_number if self.task_info else ""
        self.category = self.register_info.category if self.register_info else ""
        self.number_start = self.task_info.number_start if self.task_info else ""
        self.number_end = self.task_info.number_end if self.task_info else ""

        self.ocr_detector = None

        # ── 缩略图尺寸（+ / - 缩放用）──
        self._thumb_size = 200  # 当前缩略图宽度
        self._THUMB_MIN = 80
        self._THUMB_MAX = 320
        self._THUMB_STEP = 20
        self._thumb_h_ratio = 1.25  # 高宽比

        # ── 路径 → 卡片 widget 映射（标记角标刷新用）──
        self._path_to_widget: dict = {}
        # ── 标记气泡计数（当前任务未修复标记总数）──
        self._mark_total_count: int = 0

        self.init_ui()
        self.refresh_file_tree()

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

        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(8)
        batch_layout.setAlignment(Qt.AlignRight)

        number_label = QLabel("批次号:", self)
        self.number_value_label = QLabel(self.batch_number, self)
        self.number_nuit_label = QLabel(self.category, self)
        task_number_label = QLabel("任务起止号:", self)
        self.task_number_start_label = QLabel(self.number_start, self)
        task_number_f_label = QLabel("——", self)
        self.task_number_end_label = QLabel(self.number_end, self)

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

        self.mark_btn = PushButton("⚑ 标记")
        self.parts_btn = PushButton("分件")
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
        self.mark_btn.setStyleSheet("""
            PushButton { background-color:#e53935; color:white; border-radius:8px;
                font-size:15px; font-weight:500; border:none; }
            PushButton:hover { background-color:#c62828; }
        """)

        for btn in [self.submit_btn, self.cancel_btn, self.parts_btn, self.mark_btn]:
            btn.setFixedSize(90, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Arial", 13))

        self.cancel_btn.clicked.connect(self.back_table)
        self.submit_btn.clicked.connect(self.submit_scan)
        self.parts_btn.clicked.connect(self.part_file_dir)
        self.mark_btn.clicked.connect(self.sing_message_fun)

        # ── 标记按钮容器（叠加气泡数字）──
        mark_btn_container = QWidget()
        mark_btn_container.setFixedSize(100, 44)
        mark_btn_container.setStyleSheet("background:transparent;")
        self.mark_btn.setParent(mark_btn_container)
        self.mark_btn.setGeometry(0, 8, 90, 36)

        self.mark_count_badge = QLabel("0", mark_btn_container)
        self.mark_count_badge.setAlignment(Qt.AlignCenter)
        self.mark_count_badge.setFixedSize(22, 16)
        self.mark_count_badge.move(74, 2)
        self.mark_count_badge.setStyleSheet("""
            QLabel {
                background-color: #ff1744; color: white;
                border-radius: 8px; font-size: 10px;
                font-weight: bold; font-family: 'Microsoft YaHei';
            }
        """)
        self.mark_count_badge.hide()
        self.mark_count_badge.raise_()

        param_button_layout.addStretch(1)
        param_button_layout.addWidget(mark_btn_container)
        param_button_layout.addWidget(self.parts_btn)
        param_button_layout.addWidget(self.cancel_btn)
        param_button_layout.addWidget(self.submit_btn)
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
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        preview_top_layout = QHBoxLayout()
        stats_layout = QHBoxLayout()
        self.dir_path_label = QLabel(f"文件夹路径: {self.tree_root_path}", self)
        self.dir_path_label.setStyleSheet("""
        QLabel {
            font-size: 16px; font-weight: bold; color: #0066CC;
        }""")
        self.total_pages_label = QLabel(f"总页数: {self.total_pages}", self)
        self.selected_image_label = QLabel("选中图片: 无", self)

        stats_layout.addWidget(self.dir_path_label)
        stats_layout.addStretch(1)
        stats_layout.addWidget(self.total_pages_label)
        stats_layout.addWidget(self.selected_image_label)

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
        self.refresh_tree_btn.setFixedSize(70, 38)
        self.refresh_tree_btn.setFont(QFont("Arial", 13))
        self.refresh_tree_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_tree_btn.setStyleSheet("""
            PushButton {
                background-color: #3498db; color: white;
                border-radius: 4px; font-size: 12px; border: none;
            }
            PushButton:hover { background-color: #2980b9; }
        """)
        self.refresh_tree_btn.clicked.connect(self.refresh_file_tree)

        tree_header_layout.addWidget(tree_title)
        tree_header_layout.addStretch()
        tree_header_layout.addWidget(self.refresh_tree_btn)
        tree_layout.addLayout(tree_header_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)  # 隐藏列头
        self.file_tree.setColumnCount(1)
        self.file_tree.setIndentation(18)  # 缩进宽度
        self.file_tree.setAnimated(True)  # 展开/折叠动画
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

        # ── 启用拖放：右侧图片拖到二级文件夹节点上完成移动 ──
        self.file_tree.setAcceptDrops(True)
        self.file_tree.setDragDropMode(QAbstractItemView.DropOnly)
        self.file_tree.viewport().setAcceptDrops(True)
        self._install_tree_drop_handlers()

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

        # ── 缩放工具栏（样式对齐 image_window.py）──
        zoom_bar = QWidget()
        zoom_bar.setFixedHeight(46)
        zoom_bar.setStyleSheet("background:transparent;")
        zoom_bar_lay = QHBoxLayout(zoom_bar)
        zoom_bar_lay.setContentsMargins(12, 6, 12, 6)
        zoom_bar_lay.setSpacing(8)
        zoom_bar_lay.addStretch()

        zoom_tip = QLabel("Ctrl + 滚轮缩放")
        zoom_tip.setStyleSheet(
            "font-size:11px;color:#aaa;font-family:'Microsoft YaHei';"
        )
        zoom_bar_lay.addWidget(zoom_tip)

        self._zoom_out_btn = PushButton("－")
        self._zoom_out_btn.setFixedSize(32, 32)
        self._zoom_out_btn.setToolTip("缩小（Ctrl + 鼠标滚轮向下）")
        self._zoom_out_btn.setCursor(Qt.PointingHandCursor)
        self._zoom_out_btn.setStyleSheet("""
            PushButton { font-size:18px; font-weight:bold;
                border-radius:6px; background:#f0f0f0; border:1px solid #ddd; }
            PushButton:hover { background:#e0e0e0; }
        """)
        self._zoom_out_btn.clicked.connect(self._zoom_out)
        zoom_bar_lay.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel(f"{self._thumb_size}px")
        self._zoom_label.setFixedWidth(52)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_label.setStyleSheet(
            "font-size:12px;color:#888;font-family:'Microsoft YaHei';"
        )
        zoom_bar_lay.addWidget(self._zoom_label)

        self._zoom_in_btn = PushButton("＋")
        self._zoom_in_btn.setFixedSize(32, 32)
        self._zoom_in_btn.setToolTip("放大（Ctrl + 鼠标滚轮向上）")
        self._zoom_in_btn.setCursor(Qt.PointingHandCursor)
        self._zoom_in_btn.setStyleSheet("""
            PushButton { font-size:18px; font-weight:bold;
                border-radius:6px; background:#f0f0f0; border:1px solid #ddd; }
            PushButton:hover { background:#e0e0e0; }
        """)
        self._zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_bar_lay.addWidget(self._zoom_in_btn)

        preview_layout_right.addWidget(zoom_bar)

        preview_scroll_widget = QWidget()
        preview_scroll_widget.setStyleSheet("background-color: transparent;")
        self.preview_flow_layout = QFlowLayout(
            preview_scroll_widget, margin=10, spacing=15
        )
        self.preview_flow_layout.setAlignment(Qt.AlignTop)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(preview_scroll_widget)
        self._scroll_area.setStyleSheet("""
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
        self._scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── 独立滚轮过滤器（Ctrl + 滚轮缩放）──
        from PySide6.QtCore import QEvent as _QEvent
        from PySide6.QtCore import QObject

        class _CtrlWheelFilter(QObject):
            def __init__(self, win):
                super().__init__(win)
                self._win = win

            def eventFilter(self, obj, event):
                if event.type() == _QEvent.Wheel and (
                    event.modifiers() & Qt.ControlModifier
                ):
                    if event.angleDelta().y() > 0:
                        self._win._zoom_in()
                    else:
                        self._win._zoom_out()
                    return True
                return False

        self._ctrl_wheel_filter = _CtrlWheelFilter(self)
        self._scroll_area.viewport().installEventFilter(self._ctrl_wheel_filter)

        preview_layout_right.addWidget(self._scroll_area)
        core_horizontal_splitter.addWidget(preview_container_right)

        core_horizontal_splitter.setSizes([300, 900])
        core_horizontal_splitter.setStretchFactor(0, 1)
        core_horizontal_splitter.setStretchFactor(1, 3)

        preview_layout.addWidget(core_horizontal_splitter, stretch=1)
        main_layout.addWidget(preview_container, stretch=1)

        self.setLayout(main_layout)
        self.update_user_label()
        self._check_task_status()

    def _check_task_status(self):
        self.can_do_task = None
        where = {
            "register_id": self.task_info.register_id,
            "task_name": "图像处理",
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
                show_warning(self, "警告", "当前没有可以执行任务", 5000)
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

        try:
            entries = sorted(os.listdir(target_path))
        except PermissionError:
            show_error(self, "权限错误", "无法读取该目录，请检查权限")
            return

        has_any = False

        for entry in entries:
            print(f"entry: {entry}")
            if entry in self.dir_name_list:
                entry_path = os.path.join(target_path, entry)
                print(f"entry_path = {entry_path}")

                if os.path.isdir(entry_path):
                    folder_item = self._build_tree_item_folder(
                        self.file_tree, entry, entry_path
                    )
                    has_any = True
                    try:
                        sub_entries = sorted(os.listdir(entry_path))
                    except PermissionError:
                        sub_entries = []

                    for sub_entry in sub_entries:
                        sub_path = os.path.join(entry_path, sub_entry)
                        ext = os.path.splitext(sub_entry)[1].lower()

                        if os.path.isdir(sub_path):
                            self._build_tree_item_folder(
                                folder_item, sub_entry, sub_path
                            )
                        elif ext in IMG_EXTENSIONS:
                            self._build_tree_item_file(folder_item, sub_entry, sub_path)

                elif os.path.isfile(entry_path):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in IMG_EXTENSIONS:
                        self._build_tree_item_file(self.file_tree, entry, entry_path)
                        has_any = True

        self.file_tree.expandAll()

        if has_any:
            show_success(
                self, "目录更新", f"已加载目录：{os.path.basename(target_path)}"
            )
            # 树构建完成后回显被标记的二级文件夹 + 刷新气泡
            QTimer.singleShot(150, self._restore_tree_folder_marks)
            QTimer.singleShot(150, self._sync_mark_count_from_db)
        else:
            show_info(self, "目录为空", "当前保存路径下暂无文件夹或图片")

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

        if item_type == "folder":
            folder_name = os.path.basename(item_path)
            self.current_folder_path = item_path
            self.refresh_folder_info()
            self.load_folder_images(item_path)
            self.current_image = None
            show_success(self, "文件夹选择", f"已加载文件夹：{folder_name}")

        elif item_type == "file":
            parent_path = os.path.dirname(item_path)
            if parent_path != self.current_folder_path:
                self.current_folder_path = parent_path
                self.load_folder_images(parent_path)

            file_name = os.path.splitext(os.path.basename(item_path))[0]
            print(f"选中文件夹： {file_name}")
            for widget_info in self.preview_widgets:
                if isinstance(widget_info, dict):
                    info = widget_info.get("info", {})
                    if info.get("path") == item_path:
                        self.on_preview_clicked(widget_info["widget"], info)
                        break

    def refresh_folder_info(self):
        if self.current_folder_path and os.path.exists(self.current_folder_path):
            img_count = 0
            try:
                for f in os.listdir(self.current_folder_path):
                    if os.path.isfile(os.path.join(self.current_folder_path, f)):
                        if os.path.splitext(f)[1].lower() in IMG_EXTENSIONS:
                            img_count += 1
            except PermissionError:
                show_error(self, "报错", f"{self.current_folder_path} 没有操作权限")
                return

    def load_folder_images(self, folder_path):
        self.clear_preview_area()
        self.total_scanned = 0
        self.total_pages = 0

        img_files = []
        try:
            for f in sorted(os.listdir(folder_path)):
                fp = os.path.join(folder_path, f)
                if (
                    os.path.isfile(fp)
                    and os.path.splitext(f)[1].lower() in IMG_EXTENSIONS
                ):
                    img_files.append(fp)
        except PermissionError:
            show_warning(self, "权限错误", "无法访问该文件夹，请检查权限")
            return

        for img_path in img_files:
            self.add_scan_preview(custom_path=img_path)
        self.total_pages_label.setText(f"总页数: {self.total_pages}")

        # 回显该文件夹下已有的未修复质检标记
        QTimer.singleShot(
            200, lambda p=folder_path: self._restore_folder_mark_states(p)
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
            self.current_image = None
        else:
            self.selected_preview_widget = widget
            self.selected_image_info = image_info
            widget.setStyleSheet("""
                QWidget { background-color: #e6f7ff; border-radius: 6px; border: 2px solid #3498db; }
            """)
            ext = image_info["path"].split(".")[-1] if "." in image_info["path"] else ""
            self.current_image = f"{image_info['name']}.{ext}"
            self.selected_image_label.setText(f"选中图片: {image_info['name']}.{ext}")

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

    def add_scan_preview(self, custom_path=None):
        self.total_pages += 1
        self.total_pages_label.setText(f"总页数: {self.total_pages}")

        tw = self._thumb_size
        th = int(tw * self._thumb_h_ratio)

        preview_widget = QWidget()
        preview_widget.setObjectName("previewWidget")
        preview_widget.setStyleSheet("""
            QWidget#previewWidget { background-color: white; border-radius: 6px; }
            QWidget#previewWidget:hover { background-color: #f0f8ff; }
        """)
        preview_widget.setFixedSize(tw + 10, th + 30)
        preview_widget.setCursor(Qt.PointingHandCursor)

        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.setSpacing(4)

        # 图片容器（叠加标记角标）
        img_container = QWidget(preview_widget)
        img_container.setFixedSize(tw, th)
        img_container.setStyleSheet("background:transparent;")

        preview_label = QLabel(img_container)
        preview_label.setFixedSize(tw, th)
        preview_label.setStyleSheet(
            "QLabel { border-radius: 4px; background-color: #f5f5f5; }"
        )
        preview_label.setAlignment(Qt.AlignCenter)

        # ── 标记角标（默认隐藏）──
        mark_badge = QLabel("⚑ 已标记", img_container)
        mark_badge.setFixedSize(66, 20)
        mark_badge.move(3, 3)
        mark_badge.setAlignment(Qt.AlignCenter)
        mark_badge.setStyleSheet("""
            QLabel { background:#e53935; color:white; border-radius:4px;
                font-size:10px; font-weight:bold; font-family:'Microsoft YaHei'; }
        """)
        mark_badge.setVisible(False)
        mark_badge.raise_()

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

        batch_num = (
            self.number_value_label.text()
            if hasattr(self, "number_value_label")
            else ""
        )
        img_name = (
            os.path.splitext(os.path.basename(image_path))[0]
            if custom_path
            else f"{batch_num}_{self.total_scanned:04d}"
        )

        name_label = QLabel(img_name)
        name_label.setStyleSheet("""
            QLabel { font-size: 12px; font-weight: bold; color: #333;
                background-color: transparent; border: none; }
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

        # ── 鼠标事件：兼顾 单击/双击 选中 与 拖动移动 ──
        preview_widget._drag_start_pos = None

        def _press(event, w=preview_widget, info=image_info):
            if event.button() == Qt.LeftButton:
                w._drag_start_pos = event.position().toPoint()
            self.handle_preview_click(w, info)

        def _move(event, w=preview_widget, info=image_info):
            if not (event.buttons() & Qt.LeftButton):
                return
            if w._drag_start_pos is None:
                return
            if (
                event.position().toPoint() - w._drag_start_pos
            ).manhattanLength() < QApplication.startDragDistance():
                return
            self._start_image_drag(w, info)

        preview_widget.mousePressEvent = _press
        preview_widget.mouseMoveEvent = _move

        widget_entry = {
            "widget": preview_widget,
            "info": image_info,
            "preview_label": preview_label,
            "mark_badge": mark_badge,
        }
        self.preview_widgets.append(widget_entry)
        self._path_to_widget[image_path] = widget_entry
        self.preview_flow_layout.addWidget(preview_widget)

    # ──────────────────── 拖放：图片 → 二级文件夹 ────────────────────

    def _start_image_drag(self, widget, image_info):
        """从右侧预览卡片发起拖动，携带图片路径。"""
        img_path = image_info.get("path", "")
        if not img_path or not os.path.exists(img_path):
            return
        if not os.path.isfile(img_path):
            return
        # 取消双击计时，避免拖动后误触发选中
        self.double_click_timer.stop()

        drag = QDrag(widget)
        mime = QMimeData()
        # 用自定义 mime 标识图片移动，避免与系统文件拖放混淆
        mime.setData("application/x-bulk-image", img_path.encode("utf-8"))
        mime.setText(img_path)
        drag.setMimeData(mime)

        # 拖动时显示缩略图
        thumb = QPixmap(img_path)
        if not thumb.isNull():
            thumb = thumb.scaled(120, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            drag.setPixmap(thumb)
            drag.setHotSpot(QPoint(thumb.width() // 2, thumb.height() // 2))

        drag.exec(Qt.MoveAction)

    def _install_tree_drop_handlers(self):
        """为 file_tree 安装拖放事件处理（仅允许放到二级文件夹节点上）。"""
        tree = self.file_tree
        win = self

        def _is_image_drag(event):
            md = event.mimeData()
            return md is not None and md.hasFormat("application/x-bulk-image")

        def _folder_item_at(pos):
            item = tree.itemAt(pos)
            if item is None:
                return None
            data = item.data(0, Qt.UserRole) or {}
            if data.get("type") != "folder":
                return None
            return item

        def dragEnterEvent(event):
            if _is_image_drag(event):
                event.acceptProposedAction()
            else:
                event.ignore()

        def dragMoveEvent(event):
            if not _is_image_drag(event):
                event.ignore()
                return
            item = _folder_item_at(event.position().toPoint())
            tree.setCurrentItem(item)  # 高亮目标文件夹
            if item is not None:
                event.acceptProposedAction()
            else:
                event.ignore()

        def dropEvent(event):
            if not _is_image_drag(event):
                event.ignore()
                return
            item = _folder_item_at(event.position().toPoint())
            if item is None:
                event.ignore()
                return
            data = item.data(0, Qt.UserRole) or {}
            target_folder = data.get("path", "")
            src_path = bytes(event.mimeData().data("application/x-bulk-image")).decode(
                "utf-8"
            )
            event.acceptProposedAction()
            win._handle_image_drop(src_path, target_folder)

        tree.dragEnterEvent = dragEnterEvent
        tree.dragMoveEvent = dragMoveEvent
        tree.dropEvent = dropEvent

    def _handle_image_drop(self, src_path, target_folder):
        """将拖动的图片移动到目标二级文件夹。"""
        if not src_path or not os.path.isfile(src_path):
            show_warning(self, "移动失败", "源图片不存在")
            return
        if not target_folder or not os.path.isdir(target_folder):
            show_warning(self, "移动失败", "目标文件夹无效")
            return

        file_name = os.path.basename(src_path)
        src_folder = os.path.dirname(src_path)

        # 已在目标文件夹，无需移动
        if os.path.normpath(src_folder) == os.path.normpath(target_folder):
            show_info(self, "提示", "图片已在该文件夹中")
            return

        target_path = os.path.join(target_folder, file_name)
        if os.path.exists(target_path):
            show_warning(self, "移动失败", f"目标文件夹已存在同名图片：{file_name}")
            return

        box = MessageBox(
            "确认移动",
            f"是否将图片【{file_name}】移动到\n文件夹【{os.path.basename(target_folder)}】？",
            self,
        )
        box.yesButton.setText("移动")
        box.cancelButton.setText("取消")
        if not box.exec():
            return

        try:
            shutil.move(src_path, target_path)
            logger.info(f"拖动移动图片成功: {src_path} -> {target_path}")
        except Exception as e:
            logger.error(f"拖动移动图片失败: {src_path} -> {target_path}; {e}")
            show_error(self, "移动失败", f"图片移动失败：{e}")
            return

        # 记录操作日志
        try:
            operation_data = {
                "task_id": self.task_info.register_id,
                "task_name": "分件",
                "operator": self.current_user["username"],
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": (
                    f"拖动移动图片; {file_name}: {src_folder} -> {target_folder}"
                ),
            }
            operation_service.save_data([operation_data])
        except Exception as e:
            logger.warning(f"记录拖动移动操作日志失败: {e}")

        show_success(
            self,
            "移动成功",
            f"已将 {file_name} 移动到 {os.path.basename(target_folder)}",
        )

        # 刷新目录树 + 重新加载当前文件夹图片
        self.refresh_file_tree()
        if self.current_folder_path and os.path.isdir(self.current_folder_path):
            self.load_folder_images(self.current_folder_path)

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
        if self.task_info.is_do:
            show_warning(self, "警告", "该批次分件任务已提交，不可重复提交!")
            return

        box = MessageBox("确认提交", f"确定要提交分件任务吗？", self)
        box.yesButton.setText("提交")
        box.cancelButton.setText("取消")

        if box.exec():
            try:
                result = task_service.execute_task_submission(
                    self.task_info.id, self.can_do_task.split("-")[1]
                )
                update = {
                    "complete_number": self.can_do_task,
                }
                task_service.update(self.task_info.id, update)
                if result["status"] == "success":
                    operation_data = {
                        "task_id": self.task_info.register_id,
                        "task_name": "分件",
                        "operator": self.current_user["username"],
                        "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "operator_remark": f"分件提交",
                    }
                    operation_service.save_data([operation_data])
                    show_success(self, "提交成功", "该批次分件任务已提交")
                else:
                    show_error(self, "提交失败", "分件任务提失败")

            except Exception as e:
                show_error(self, "提交失败", f"分件任务失败{str(e)}")

    def sing_message_fun(self):
        """
        质检员标记：
          - 若当前选中了图片（current_image）→ 标记该图片（分件质检，scan_file）
          - 若只选中了文件夹（current_folder_path，第二级目录）→ 标记该文件夹（folder_name）
        """
        if not self.current_user or self.current_user.get("role") not in [
            "管理员",
            "质检员",
        ]:
            show_warning(self, "警告", "非管理员或质检员不可标记")
            return
        if not self.task_info or not self.task_info.is_do:
            show_warning(self, "提示", "当前任务未提交或未开始，暂不可进行标记")
            return

        # 确定标记对象
        if self.current_image and self.current_folder_path:
            image_path = os.path.join(self.current_folder_path, self.current_image)
            image_name = os.path.basename(image_path)
            is_folder_mark = False
        elif self.current_folder_path:
            image_name = os.path.basename(self.current_folder_path)
            image_path = self.current_folder_path
            is_folder_mark = True
        else:
            show_warning(
                self, "警告", "请先在目录树中选中分件文件夹，或在右侧选中具体图片"
            )
            return

        # ── 查历史标记 ──
        existing_marks = []
        try:
            from src.services.task_mark_service import task_mark_service

            existing_marks = task_mark_service.get_mark_info(
                {
                    "task_id": self.task_info.id,
                    "scan_file": image_name,
                }
            )
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
                on_mark_changed=lambda: self._refresh_mark_state(
                    image_path, is_folder_mark
                ),
            )
            if not history_dlg.exec():
                self._refresh_mark_state(image_path, is_folder_mark)
                return

        from src.view.common.MarkIssueDialog import MarkIssueDialog

        dlg = MarkIssueDialog(target_name=image_name, mark_stage="分件质检")
        if dlg.exec():
            mark_data = dlg.get_data()
            if len(mark_data.get("description", "")) == 0:
                show_warning(self, "提示", "描述标记内容不可为空！")
                return

            save_data = {
                "task_id": self.task_info.id,
                "batch_number": self.task_info.batch_number,
                "task_node": self.task_info.task_node,
                "mark_stage": 4,  # 分件质检
                "scan_file": image_name,
                "mark_type": mark_data.get("mark_type", "其他"),
                "level": mark_data.get("level", "一般"),
                "description": mark_data.get("description", ""),
                "inspector": self.current_user.get("username", ""),
                "mark_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_fixed": False,
            }
            try:
                from src.services.task_mark_service import task_mark_service

                task_mark_service.add_mark(save_data)
                mark_type = mark_data.get("mark_type", "已标记")
                if is_folder_mark:
                    self._set_tree_folder_mark_state(image_path, has_mark=True)
                else:
                    self._set_preview_mark_state(image_path, mark_type)
                    self._set_tree_file_mark_state(image_path, has_mark=True)
                self._mark_total_count += 1
                self._update_mark_count_badge()
                show_success(
                    self,
                    "标记成功",
                    f"已对 {image_name} 标记【{mark_data.get('mark_type', '其他')}】",
                )
            except Exception as e:
                logger.error(f"标记保存失败: {e}")
                show_error(self, "失败", "标记保存失败，请重试")

    # ──────────────────── 缩放功能 ────────────────────

    def _zoom_in(self):
        if self._thumb_size < self._THUMB_MAX:
            self._thumb_size = min(self._thumb_size + self._THUMB_STEP, self._THUMB_MAX)
            self._resize_all_cards()

    def _zoom_out(self):
        if self._thumb_size > self._THUMB_MIN:
            self._thumb_size = max(self._thumb_size - self._THUMB_STEP, self._THUMB_MIN)
            self._resize_all_cards()

    def _resize_all_cards(self):
        """缩放：更新所有卡片尺寸并重新缩放已有图片（对齐 image_window.py 行为）"""
        tw = self._thumb_size
        th = int(tw * self._thumb_h_ratio)
        self._zoom_label.setText(f"{tw}px")
        for entry in self.preview_widgets:
            if not isinstance(entry, dict):
                continue
            w = entry.get("widget")
            pl = entry.get("preview_label")
            info = entry.get("info", {})
            if w:
                w.setFixedSize(tw + 10, th + 30)
            if pl:
                # preview_label 的父控件即 img_container
                pl.parent().setFixedSize(tw, th)
                pl.setFixedSize(tw, th)
                img_path = info.get("path", "")
                if img_path and os.path.exists(img_path):
                    px = QPixmap(img_path)
                    if not px.isNull():
                        pl.setPixmap(
                            px.scaled(
                                tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation
                            )
                        )

    # ──────────────────── 标记 UI 状态管理 ────────────────────

    def _set_preview_mark_state(self, image_path: str, mark_type: str = None):
        """显示/清除图片预览卡片的标记角标"""
        entry = self._path_to_widget.get(image_path)
        if not entry:
            # 尝试用文件名反查
            fname = os.path.basename(image_path)
            for p, e in self._path_to_widget.items():
                if os.path.basename(p) == fname:
                    entry = e
                    break
        if not entry:
            return
        has_mark = mark_type is not None
        mb = entry.get("mark_badge")
        w = entry.get("widget")
        info = entry.get("info", {})
        name_label = info.get("name_label")
        if mb:
            if has_mark:
                short = mark_type[:5] if len(mark_type) > 5 else mark_type
                mb.setText(f"⚑ {short}")
            mb.setVisible(has_mark)
        if name_label:
            color = "#e53935" if has_mark else "#333"
            name_label.setStyleSheet(
                f"font-size:12px;font-weight:bold;color:{color};"
                f"background-color:transparent;border:none;"
            )
        if w:
            if has_mark:
                w.setStyleSheet("""
                    QWidget#previewWidget { background-color:#fff5f5;
                        border-radius:6px; border:2px solid #e53935; }
                """)
            else:
                w.setStyleSheet("""
                    QWidget#previewWidget { background-color:white; border-radius:6px; }
                    QWidget#previewWidget:hover { background-color:#f0f8ff; }
                """)

    def _set_tree_file_mark_state(self, file_path: str, has_mark: bool):
        """在文件树的文件节点上显示/清除标记符号"""
        root = self.file_tree.invisibleRootItem()
        fname = os.path.basename(file_path)

        def _search(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                d = child.data(0, Qt.UserRole) or {}
                if (
                    d.get("type") == "file"
                    and os.path.basename(d.get("path", "")) == fname
                ):
                    if has_mark:
                        child.setText(0, f"⚑  {fname}")
                        child.setForeground(0, QColor("#e53935"))
                        f = child.font(0)
                        f.setBold(True)
                        child.setFont(0, f)
                    else:
                        child.setText(0, f"🖼  {fname}")
                        child.setForeground(0, QColor("#555"))
                        f = child.font(0)
                        f.setBold(False)
                        child.setFont(0, f)
                    return
                _search(child)

        _search(root)

    def _set_tree_folder_mark_state(self, folder_path: str, has_mark: bool):
        """在文件树的第二级文件夹节点上显示/清除标记符号"""
        root = self.file_tree.invisibleRootItem()
        fname = os.path.basename(folder_path)

        def _search(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                d = child.data(0, Qt.UserRole) or {}
                if (
                    d.get("type") == "folder"
                    and os.path.basename(d.get("path", "")) == fname
                ):
                    if has_mark:
                        child.setText(0, f"⚑  {fname}")
                        child.setForeground(0, QColor("#e53935"))
                        f = child.font(0)
                        f.setBold(True)
                        child.setFont(0, f)
                    else:
                        child.setText(0, f"📁  {fname}")
                        child.setForeground(0, QColor("#2c3e50"))
                        f = child.font(0)
                        f.setBold(True)
                        child.setFont(0, f)
                    return
                _search(child)

        _search(root)

    def _refresh_mark_state(self, path: str, is_folder: bool):
        """标记操作完成/弹框关闭后，查库刷新角标"""
        if not self.task_info:
            return
        fname = os.path.basename(path)
        try:
            from src.services.task_mark_service import task_mark_service

            pending = task_mark_service.get_pending_marks_by_file(
                task_id=self.task_info.id,
                scan_file=fname,
            )
            if is_folder:
                self._set_tree_folder_mark_state(path, bool(pending))
            else:
                mark_type = pending[0].mark_type if pending else None
                self._set_preview_mark_state(path, mark_type)
                self._set_tree_file_mark_state(path, bool(pending))
            # 刷新全局气泡计数
            self._sync_mark_count_from_db()
        except Exception as e:
            logger.warning(f"刷新标记状态失败: {e}")

    def _sync_mark_count_from_db(self):
        """从数据库查询当前任务的未修复标记总数，并刷新气泡"""
        if not self.task_info:
            return
        try:
            from src.services.task_mark_service import task_mark_service

            result = task_mark_service.count_by_task(self.task_info.id)
            self._mark_total_count = result.get("pending", 0)
        except Exception as e:
            logger.warning(f"同步标记计数失败: {e}")
        self._update_mark_count_badge()

    def _update_mark_count_badge(self):
        """刷新标记按钮上的气泡数字"""
        if not hasattr(self, "mark_count_badge"):
            return
        count = self._mark_total_count
        if count > 0:
            text = "99+" if count > 99 else str(count)
            self.mark_count_badge.setText(text)
            # 字数多时自动加宽
            self.mark_count_badge.setFixedWidth(28 if count > 9 else 22)
            self.mark_count_badge.show()
            self.mark_count_badge.raise_()
        else:
            self.mark_count_badge.hide()

    def _restore_folder_mark_states(self, folder_path: str):
        """
        加载文件夹后，从 DB 回显未修复标记：
          1) 回显当前文件夹下图片卡片的角标
          2) 回显目录树中文件节点 + 二级文件夹节点的标记状态
          3) 同步全局气泡计数
        """
        if not self.task_info:
            return
        try:
            from src.services.task_mark_service import task_mark_service

            pending_marks = task_mark_service.get_pending_marks_by_folder(
                task_id=self.task_info.id,
                folder_path=folder_path,
            )
            name_to_path = {os.path.basename(p): p for p in self._path_to_widget}
            for mark in pending_marks:
                if not mark.scan_file:
                    continue
                full = name_to_path.get(mark.scan_file)
                if full:
                    self._set_preview_mark_state(full, mark.mark_type)
                    self._set_tree_file_mark_state(full, has_mark=True)
            # 回显目录树中所有被标记的二级文件夹
            self._restore_tree_folder_marks()
            # 刷新任务全局未修复总数
            self._sync_mark_count_from_db()
        except Exception as e:
            logger.warning(f"回显标记状态失败: {e}")

    def _restore_tree_folder_marks(self):
        """
        遍历目录树的二级文件夹节点，查询每个文件夹是否有未修复标记，
        有则显示 ⚑ 标记符号（文件夹本身被标记，scan_file=文件夹名）。
        """
        if not self.task_info:
            return
        try:
            from src.services.task_mark_service import task_mark_service

            root = self.file_tree.invisibleRootItem()

            def _walk(parent):
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    d = child.data(0, Qt.UserRole) or {}
                    if d.get("type") == "folder":
                        folder_path = d.get("path", "")
                        folder_name = os.path.basename(folder_path)
                        pending = task_mark_service.get_pending_marks_by_file(
                            task_id=self.task_info.id,
                            scan_file=folder_name,
                        )
                        self._set_tree_folder_mark_state(folder_path, bool(pending))
                    _walk(child)

            _walk(root)
        except Exception as e:
            logger.warning(f"回显二级文件夹标记失败: {e}")

    def part_file_dir(self):
        # 自定义分件确认对话框（含分件方式下拉框）
        w = MessageBox("准备分件", "请选择分件方式，确认后开始分件。", self)
        w.yesButton.setText("分件")
        w.yesButton.setCursor(Qt.PointingHandCursor)
        w.cancelButton.setText("取消")
        w.cancelButton.setCursor(Qt.PointingHandCursor)

        # 在 MessageBox 内容区域插入下拉框
        split_type_label = QLabel("分件方式:")
        split_type_label.setStyleSheet("font-size: 14px; color: #333; margin-top: 8px;")
        split_type_combo = ComboBox()
        split_type_combo.addItems(settings.parts_selects)
        split_type_combo.setMinimumWidth(160)
        split_type_combo.setMinimumHeight(32)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(10)
        combo_row.addWidget(split_type_label)
        combo_row.addWidget(split_type_combo)
        combo_row.addStretch(1)

        combo_widget = QWidget()
        combo_widget.setLayout(combo_row)

        # 将下拉行插入到 MessageBox 的文本标签下方
        w.textLayout.addWidget(combo_widget)

        input_path_edit = LineEdit()
        input_path_edit.setReadOnly(True)
        input_path_edit.setPlaceholderText("请选择目录 Excel 文件")
        input_path_edit.setMinimumWidth(240)
        input_path_edit.setText(self.dir_input_path)

        input_button = PushButton("导入目录")
        input_button.setCursor(Qt.PointingHandCursor)

        def select_input_file():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入分件目录", "", "Excel 文件 (*.xlsx *.xls)"
            )
            if not file_path:
                return

            _, file_ext = os.path.splitext(file_path)
            if file_ext.lower() not in [".xlsx", ".xls"]:
                show_error(self, "警告", f"暂不支持当前文件格式; {file_ext}")
                return

            input_path_edit.setText(file_path)

        input_button.clicked.connect(select_input_file)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        input_row.addWidget(QLabel("目录文件:"))
        input_row.addWidget(input_path_edit)
        input_row.addWidget(input_button)
        input_row.addStretch(1)

        input_widget = QWidget()
        input_widget.setLayout(input_row)
        w.textLayout.addWidget(input_widget)

        stamp_list = [
            item.template_name for item in archive_stamp_service.get_all()
        ]
        stamp_list.insert(0, "请选择模版")

        stamp_combo = ComboBox()
        stamp_combo.addItems(stamp_list)
        stamp_combo.setMinimumWidth(160)
        stamp_combo.setMinimumHeight(32)
        if self.stamp_combo_value in stamp_list:
            stamp_combo.setCurrentText(self.stamp_combo_value)

        stamp_row = QHBoxLayout()
        stamp_row.setSpacing(10)
        stamp_row.addWidget(QLabel("归档章模板:"))
        stamp_row.addWidget(stamp_combo)
        stamp_row.addStretch(1)

        stamp_widget = QWidget()
        stamp_widget.setLayout(stamp_row)
        w.textLayout.addWidget(stamp_widget)

        def update_option_visible(split_type):
            input_widget.setVisible(split_type == "目录")
            stamp_widget.setVisible(split_type == "归档章")

        split_type_combo.currentTextChanged.connect(update_option_visible)
        update_option_visible(split_type_combo.currentText())

        if w.exec():
            selected_split_type = split_type_combo.currentText()
            images_list = self.get_dir_all_images(self.current_folder_path)

            if len(images_list) == 0:
                show_error(self, "分件失败", f"当前文件夹下没有任何图片")
                return

            from src.utils.PartsDetector import PartsDetector

            parts_detector = PartsDetector(dir_path=self.current_folder_path)

            if selected_split_type == "目录":
                # 目录分件
                self.dir_input_path = input_path_edit.text().strip()
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
                self.stamp_combo_value = stamp_combo.currentText()
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

    def get_dir_all_images(self, dir_path):
        try:
            with os.scandir(dir_path) as entries:
                images_list = [
                    os.path.basename(entry.path)
                    for entry in entries
                    if entry.is_file(follow_symlinks=False)
                ]
        except FileNotFoundError as fe:
            print(f"没有文件；{str(fe)}")

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

    def get_ocr_result(self, image_path):
        text_result = self.ocr_detector.detect(image_path)
        socre_pattern = r"全宗号|保管期限|件号|类别号|年度|机构"
        socre = len(re.findall(socre_pattern, "".join(text_result)))

        page_num = 0
        for item in text_result:
            match = re.search(r"[共其具](\d+)(?:页)?", item)
            if match:
                page_num = match.group(1)

        print(f"socre = {socre}; page = {page_num}")
        return socre, int(page_num)

    def get_last_four_digits(self, filename):
        name_without_ext = filename.split(".")[0]
        last_four = name_without_ext[-4:]
        return int(last_four)

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请重新登录!")
            time.sleep(1)

            from src.view.login import LoginWindow

            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

        from src.view.bulk_breaking.bulkTable_window import BulkTableWindow

        bulk_table_window = BulkTableWindow()
        bulk_table_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label.setText(f"当前用户：【{username}】角色: 【{userrole}】")
        else:
            self.user_label.setText("未登录")

    def closeEvent(self, event):
        if self._is_navigation:
            event.accept()
            return

        if not self._is_app_exiting:
            box = MessageBox("确认退出", "确定要退出应用程序吗？", self)
            box.yesButton.setText("退出")
            box.cancelButton.setText("取消")

            if box.exec():
                self._is_app_exiting = True
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
