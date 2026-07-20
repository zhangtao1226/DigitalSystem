# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : dir_window.py
# @Desc      : 主窗口
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime

import pandas as pd
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QIcon,
    QImage,
    QIntValidator,
    QPainter,
    QPalette,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRubberBand,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    ElevatedCardWidget,
    FlowLayout,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SpinBox,
    StrongBodyLabel,
    TableWidget,
    TextEdit,
    Theme,
    TransparentToolButton,
    setTheme,
)
from qframelesswindow import FramelessWindow
from src.core.cache_manager import global_cache
from src.core.settings import settings
from src.services.director_service import director_service
from src.services.operation_service import operation_service
from src.services.register_service import register_service
from src.services.scan_service import scan_service
from src.services.task_service import task_service
from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_error, show_info, show_success, show_warning
from src.view.common.NavigationLabel import NavigationLabel


class ImageDirectoryTree(CardWidget):
    def __init__(self, parent=None, dir_paths=None):
        super().__init__(parent)
        self.current_selected_folder = None
        self.selected_folder_item = None
        self.dir_paths = dir_paths or []

        self.setBorderRadius(8)
        self.setStyleSheet("""
            CardWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
            }
        """)

        self.main_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        self.title_label = StrongBodyLabel("目录树")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 600;
                color: #333;
                padding: 2px 0;
            }
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        self.refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("刷新目录")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_tree)
        title_layout.addWidget(self.refresh_btn)
        layout.addLayout(title_layout)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0; height: 1px;")
        layout.addWidget(separator)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                padding: 8px;
            }
            QTreeWidget::item {
                height: 36px;
                padding: 6px 10px;
                border-radius: 6px;
                margin: 4px 0;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
                font-weight: 500;
                border: 1px solid #bbdefb;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTreeWidget::item:has-children {
                font-weight: 500;
            }
        """)

        self.tree_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_widget.itemClicked.connect(self.on_folder_selected)
        layout.addWidget(self.tree_widget)
        self.load_directory_tree()

    def refresh_tree(self):
        self.load_directory_tree()

    def load_directory_tree(self):
        self.tree_widget.clear()

        if not self.dir_paths:
            return

        self.default_expand_levels = 3

        for dir_path in self.dir_paths:
            print(f"dir_path: {dir_path}")
            if not os.path.exists(dir_path):
                dir_path = f"{os.getcwd()}/upload_images"

            root_item = QTreeWidgetItem(self.tree_widget)
            root_item.setText(0, os.path.basename(dir_path))
            root_item.setData(0, Qt.UserRole, dir_path)
            root_item.setIcon(0, self.get_folder_icon())

            root_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            self.load_subdirectories(root_item, dir_path, current_level=1)

        self.expand_to_level(self.default_expand_levels)

        if self.tree_widget.topLevelItemCount() > 0:
            root_item = self.tree_widget.topLevelItem(0)
            first_item = root_item.child(0) if root_item.childCount() > 0 else root_item
            first_item.setSelected(True)
            self.selected_folder_item = first_item
            self.current_selected_folder = first_item.data(0, Qt.UserRole)
            self.tree_widget.scrollToItem(first_item)

    def expand_to_level(self, max_level):
        def _expand(item, level):
            if level > max_level:
                return
            self.tree_widget.expandItem(item)
            for i in range(item.childCount()):
                _expand(item.child(i), level + 1)

        for i in range(self.tree_widget.topLevelItemCount()):
            _expand(self.tree_widget.topLevelItem(i), 1)

    def load_subdirectories(self, parent_item, path, current_level=1):
        try:
            dirs = []
            for item_name in os.listdir(path):
                if (
                    item_name in self.main_window.dir_name_list
                    or item_name[:-5] in self.main_window.dir_name_list
                ):
                    item_path = os.path.join(path, item_name)
                    if os.path.isdir(item_path):
                        dirs.append((item_name, item_path))

            dirs.sort(key=lambda x: x[0].lower())

            for item_name, item_path in dirs:
                # print(f"item_name: {item_name}; item_path: {item_path}")
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, item_name)
                child_item.setData(0, Qt.UserRole, item_path)
                child_item.setIcon(0, self.get_folder_icon())
                child_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

                if current_level + 1 <= self.default_expand_levels:
                    self.load_subdirectories(child_item, item_path, current_level + 1)

        except PermissionError:
            pass
        except Exception as e:
            print(f"加载目录时出错: {e}")

    def get_folder_icon(self):
        style = self.style()
        if style:
            return style.standardIcon(QStyle.SP_DirIcon)
        return QIcon()

    def set_folder_mark_state(self, folder_path: str, has_mark: bool):
        """
        根据完整路径在目录树中找到对应文件夹节点，显示/清除标记状态。
        被标记：文本前加 ⚑、字体变红加粗；取消：恢复原文本和样式。
        """
        root = self.tree_widget.invisibleRootItem()
        base_name = os.path.basename(folder_path)

        def _search(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.data(0, Qt.UserRole) == folder_path:
                    if has_mark:
                        child.setText(0, f"⚑ {base_name}")
                        child.setForeground(0, QColor("#e53935"))
                        f = child.font(0)
                        f.setBold(True)
                        child.setFont(0, f)
                    else:
                        child.setText(0, base_name)
                        child.setForeground(0, QColor("#333333"))
                        f = child.font(0)
                        f.setBold(False)
                        child.setFont(0, f)
                    return True
                if _search(child):
                    return True
            return False

        _search(root)

    def restore_all_folder_marks(self, marked_paths: set):
        """批量回显：遍历全部节点，路径在 marked_paths 中的显示标记，否则清除"""
        root = self.tree_widget.invisibleRootItem()

        def _walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                path = child.data(0, Qt.UserRole)
                base_name = os.path.basename(path) if path else ""
                if path in marked_paths:
                    child.setText(0, f"⚑ {base_name}")
                    child.setForeground(0, QColor("#e53935"))
                    f = child.font(0)
                    f.setBold(True)
                    child.setFont(0, f)
                else:
                    child.setText(0, base_name)
                    child.setForeground(0, QColor("#333333"))
                    f = child.font(0)
                    f.setBold(False)
                    child.setFont(0, f)
                _walk(child)

        _walk(root)

    def on_folder_selected(self, item):
        if self.selected_folder_item:
            self.selected_folder_item.setSelected(False)

        self.selected_folder_item = item
        folder_path = item.data(0, Qt.UserRole)
        self.current_selected_folder = folder_path
        item.setSelected(True)

        if item.childCount() == 0:
            self.load_subdirectories(item, folder_path)

        parent = self.parentWidget()
        while parent:
            if hasattr(parent, "load_images_from_folder"):
                parent.load_images_from_folder(folder_path)
                break
            parent = parent.parentWidget()


class SelectableImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        self.selection_rect = QRect()
        self.setMouseTracking(True)
        self.is_selecting = False
        self.is_resizing = False
        self.resize_edge = None
        self.min_size = 20
        self.actual_display_rect = QRect()

    def set_actual_display_rect(self, rect):
        self.actual_display_rect = rect

    def get_actual_display_rect(self):
        return self.actual_display_rect

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.is_selecting = True

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.selection_rect = QRect(
                self.origin, event.position().toPoint()
            ).normalized()
            self.rubber_band.setGeometry(self.selection_rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            main_window = self.window()
            if hasattr(main_window, "on_image_selection"):
                main_window.on_image_selection(self.selection_rect)

    def clear_selection(self):
        self.rubber_band.hide()
        self.selection_rect = QRect()

    def get_selection_rect(self):
        return self.selection_rect


class FocusAwareLineEdit(LineEdit):
    def __init__(self, parent=None, field_name=""):
        super().__init__(parent)
        self.field_name = field_name

        self.main_window = parent

    def setText(self, text):
        super().setText("" if pd.isnull(text) else str(text))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        main_window = self.window()
        if hasattr(main_window, "on_field_focus"):
            main_window.on_field_focus(self.field_name)


class FocusAwareTextEdit(TextEdit):
    contentChanged = Signal(str)

    def __init__(self, parent=None, field_name=""):
        super().__init__(parent)
        self.field_name = field_name
        self.main_window = parent

        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.textChanged.connect(self._emit_content_changed)

    def _emit_content_changed(self):
        self.contentChanged.emit(self.toPlainText())

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText("" if pd.isnull(text) else str(text))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        main_window = self.window()
        if hasattr(main_window, "on_field_focus"):
            main_window.on_field_focus(self.field_name)


class DirWindow(FramelessWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        self.setMinimumSize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)
        self.current_user = global_cache.get("current_user", None)
        self.current_data = global_cache.get("current_data", None)
        print(f"current_data = {self.current_data}")
        self.task_info = task_service.get_by_id(self.current_data[0])
        print(f"task_info = {self.task_info}")
        self.register_info = register_service.get_by_id(self.task_info.register_id)
        self.directior_data_list = director_service.get_director_by_registerId(
            self.task_info.register_id
        )
        print(f"directior_data_list = {self.directior_data_list}")
        self.scan_info_list = scan_service.get_scan_info(
            {"register_id": self.task_info.register_id}
        )
        print(f"scan_info = {self.scan_info_list}")
        self.dir_path_list = list(set([item.dir_path for item in self.scan_info_list]))
        print(f"dir_path_list = {self.dir_path_list}")

        self.dir_name_list = []
        for scan in self.scan_info_list:
            dir_name = scan.dir_name.split("/")
            print(222, dir_name)
            if dir_name[0] not in self.dir_name_list:
                self.dir_name_list.append(dir_name[0])

        self.current_image_list = []
        self.current_page = 1
        self.image_paths = self._get_valid_image_paths()
        self.total_images = len(self.image_paths)
        self.current_pixmap = None
        self.current_focused_field = None
        self.selected_temp_image = None
        self.actual_display_rect = QRect()

        self.current_folder_path = None
        self.archives_type = self.register_info.archive_type
        if self.register_info.category == "卷":
            self.archives_unit = "案卷级"
        elif self.register_info.category == "件":
            self.archives_unit = "文件级"

        self.df = pd.read_excel(
            settings.archives_template_path,
            sheet_name=f"{self.register_info.archive_type}-{self.archives_unit}",
        )
        self.fields = []
        for indes, series in self.df.iterrows():
            field_name = series.iloc[2]
            field_required = series.iloc[5]
            self.fields.append((field_name, f"请输入{field_name}", field_required))
        # print(f"档案字段信息: {self.fields}")
        self._is_navigation = False
        self._is_app_exiting = False

        self.parts_files_image = []

        # ── 标记气泡计数（当前任务未修复标记总数）──
        self._mark_total_count = 0

        self.ocr_detector = None

        # 1. 先建好界面组件，窗口立即显示
        self.init_ui()

        # 2. 窗口显示后，在【主线程】空闲时再加载 OCR
        #    PaddleOCR 的 C++ 引擎非线程安全，必须在主线程构造和使用，
        #    否则会触发 0xC0000005 访问违例。这里用 QTimer 延迟加载，
        #    既不阻塞窗口启动，又避免跨线程构造 Paddle。
        QTimer.singleShot(0, self._load_ocr)

    @staticmethod
    def _safe_text(value):
        return "" if pd.isnull(value) else str(value)

    @staticmethod
    def _is_multiline_field(field_name):
        return field_name == "题名" or "责任" in field_name

    def _load_ocr(self):
        """在主线程加载 OCR 模型（延迟执行，不阻塞窗口启动）。"""
        try:
            from src.utils.OCRDetector import OCRDetector

            self.ocr_detector = OCRDetector()
            logger.info("OCR模型预热完成")
        except Exception as e:
            self.ocr_detector = None
            logger.exception(f"OCR预热模型失败： {e}")
            show_warning(self, "提示", "OCR 模型加载失败， 识别功能可能不可用")

    def _get_valid_image_paths(self):
        valid_paths = []
        image_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
        placeholder_path = "placeholder.jpg"

        for folder_path in self.dir_path_list:
            if os.path.exists(folder_path):
                files = os.listdir(folder_path)

                for file_name in files:
                    if file_name.lower().endswith(image_extensions):
                        full_path = os.path.join(folder_path, file_name)
                        valid_paths.append(full_path)
            else:
                if not os.path.exists(placeholder_path):
                    self._create_placeholder_image(placeholder_path)
                valid_paths.append(placeholder_path)

        return valid_paths

    def _create_placeholder_image(self, path):
        image = QImage(800, 600, QImage.Format_RGB32)
        image.fill(Qt.lightGray)
        painter = QPainter(image)
        painter.setPen(Qt.gray)
        painter.setFont(QFont("Arial", 24))
        painter.drawText(image.rect(), Qt.AlignCenter, "图片占位符")
        painter.end()
        image.save(path)

    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_table_label = NavigationLabel("目录识别任务表", is_clickable=True)
        task_table_label.clicked.connect(self.back_table)
        parent_layout.addWidget(task_table_label)
        separator2 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator2)
        task_label = NavigationLabel("目录识别", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时， 请退出重新登录")
            time.sleep(1)
            from src.view.login import LoginWindow

            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.new_main_window import MainWindow

            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 30, 10, 10)
        self.setLayout(main_layout)
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignVCenter)
        top_layout.setSpacing(10)
        self.create_navigation_breadcrumb(top_layout)
        top_layout.addStretch(1)

        self.user_label = QLabel("")
        self.user_label.setStyleSheet("""
            QLabel {
                background-color: #e6f3ff;
                border: 1px solid #99ccff;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 14px;
                color: #0066cc;
                font-weight: bold;
                white-space: nowrap;
            }
        """)
        self.user_label.setFixedHeight(40)
        top_layout.addWidget(self.user_label)
        main_layout.addLayout(top_layout)
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
        watermark_layout = QHBoxLayout()
        watermark_layout.setSpacing(25)
        watermark_layout.setContentsMargins(0, 10, 0, 15)
        batch_watermark_layout = QHBoxLayout()
        batch_label = QLabel("批次号:")
        batch_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                min-width: 60px;
                font-weight: bold;
            }
        """)
        self.batch_value_label = LineEdit()
        self.batch_value_label.setText(self._safe_text(self.task_info.batch_number))
        self.batch_value_label.setEnabled(False)
        self.batch_value_label.setMinimumWidth(80)
        batch_watermark_layout.addWidget(batch_label)
        batch_watermark_layout.addWidget(self.batch_value_label)
        task_watermark_layout = QHBoxLayout()
        task_label = QLabel("任务号段:")
        task_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                min-width: 60px;
            }
        """)
        self.task_value_label = LineEdit()
        self.task_value_label.setText(
            f"{self.task_info.number_start}-{self.task_info.number_end}"
        )
        self.task_value_label.setEnabled(False)
        self.task_value_label.setMinimumWidth(90)
        task_watermark_layout.addWidget(task_label)
        task_watermark_layout.addWidget(self.task_value_label)
        path_watermark_layout = QHBoxLayout()
        path_label = QLabel("图片路径:")
        path_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                min-width: 60px;
            }
        """)
        self.image_path_label = LineEdit()
        self.image_path_label.setMinimumWidth(700)
        self.image_path_label.setEnabled(False)
        path_watermark_layout.addWidget(path_label)
        path_watermark_layout.addWidget(self.image_path_label)
        watermark_layout.addLayout(batch_watermark_layout)
        watermark_layout.addLayout(task_watermark_layout)
        watermark_layout.addLayout(path_watermark_layout)
        watermark_layout.addStretch(1)
        main_layout.addLayout(watermark_layout)
        operation_layout = QHBoxLayout()
        operation_layout.setSpacing(20)
        operation_layout.setContentsMargins(0, 0, 0, 10)
        archives_type_label = QLabel("档案类别:")
        archives_type_label.setStyleSheet(
            "font-size:16px; font-weight: bold; min-width: 80px;"
        )
        self.archives_value_line = LineEdit()
        self.archives_value_line.setText(self._safe_text(self.register_info.archive_type))
        self.archives_value_line.setEnabled(False)
        self.archives_value_line.setMaximumWidth(160)
        self.archives_unit_line = LineEdit()
        self.archives_unit_line.setText(self._safe_text(self.register_info.category))
        self.archives_unit_line.setEnabled(False)
        self.archives_unit_line.setMaximumWidth(60)
        self.parts_checkbox = CheckBox("启用分件")
        self.submit_btn = PrimaryPushButton("提交", self)
        self.submit_btn.clicked.connect(self.submit_status)
        self.submit_btn.setFixedSize(96, 36)
        self.submit_btn.setStyleSheet("""
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
        self.back_btn = PushButton("返回", self)
        self.back_btn.clicked.connect(self.back_table)
        self.back_btn.setFixedSize(96, 36)
        self.back_btn.setStyleSheet("""
            PushButton {
                background-color: #95a5a6;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            PushButton:hover {
                background-color: #7f8c8d;
            }
        """)

        # ── 标记按钮（带气泡数）──
        self.mark_btn = PushButton("⚑ 标记", self)
        self.mark_btn.clicked.connect(self.sing_message_fun)
        self.mark_btn.setFixedSize(96, 36)
        self.mark_btn.setToolTip("对当前目录信息添加质检标记")
        self.mark_btn.setStyleSheet("""
            PushButton {
                background-color: #e53935;
                color: white;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 500;
                border: none;
            }
            PushButton:hover { background-color: #c62828; }
        """)

        self.mark_btn_container = QWidget()
        self.mark_btn_container.setFixedSize(106, 44)
        self.mark_btn_container.setStyleSheet("background:transparent;")
        self.mark_btn.setParent(self.mark_btn_container)
        self.mark_btn.setGeometry(0, 8, 96, 36)

        self.mark_count_badge = QLabel("0", self.mark_btn_container)
        self.mark_count_badge.setAlignment(Qt.AlignCenter)
        self.mark_count_badge.setFixedSize(22, 16)
        self.mark_count_badge.move(80, 2)
        self.mark_count_badge.setStyleSheet("""
            QLabel {
                background-color: #ff1744; color: white;
                border-radius: 8px; font-size: 10px;
                font-weight: bold; font-family: 'Microsoft YaHei';
            }
        """)
        self.mark_count_badge.hide()
        self.mark_count_badge.raise_()

        operation_layout.addWidget(archives_type_label)
        operation_layout.addWidget(self.archives_value_line)
        operation_layout.addWidget(self.archives_unit_line)
        # operation_layout.addWidget(self.parts_checkbox)
        operation_layout.addStretch(1)
        operation_layout.addWidget(self.mark_btn_container)
        operation_layout.addWidget(self.back_btn)
        operation_layout.addWidget(self.submit_btn)
        main_layout.addLayout(operation_layout)
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(3)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                border-radius: 1px;
            }
            QSplitter::handle:hover {
                background-color: #bdbdbd;
            }
        """)
        main_splitter.setChildrenCollapsible(False)
        self.directory_tree = ImageDirectoryTree(self, self.dir_path_list)
        main_splitter.addWidget(self.directory_tree)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setSpacing(15)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        image_tip_layout = QHBoxLayout()
        image_tip_label = QLabel("提示：1.选择输入框获取焦点 2.拖动鼠标选择图片区域")
        image_tip_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                background-color: #f0f8ff;
                border: 1px solid #cce7ff;
                border-radius: 4px;
                padding: 8px 12px;
            }
        """)
        image_tip_layout.addWidget(image_tip_label)
        middle_layout.addLayout(image_tip_layout)
        self.image_container = SelectableImageLabel()
        self.image_container.setStyleSheet("""
            QLabel {
                border: 2px solid #dcdcdc;
                border-radius: 8px;
                background-color: #f8f8f8;
            }
        """)
        self.image_container.setAlignment(Qt.AlignCenter)
        self.image_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_container.setMinimumSize(400, 400)
        self.image_container.setCursor(Qt.CrossCursor)
        middle_layout.addWidget(self.image_container, stretch=1)
        bottom_operation_layout = QHBoxLayout()
        bottom_operation_layout.setSpacing(30)
        bottom_operation_layout.setContentsMargins(0, 10, 0, 5)
        page_control_layout = QHBoxLayout()
        page_control_layout.setSpacing(15)
        page_control_layout.setContentsMargins(0, 0, 0, 0)
        self.prev_btn = PushButton("上一页", self)
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(self.total_images > 1)
        page_label = QLabel("页码:")
        page_label.setStyleSheet("font-size:16px; font-weight: bold; color: #333;")
        self.page_input = LineEdit()
        self.page_input.setText(str(self.current_page))
        self.page_input.setFixedWidth(70)
        self.page_input.setFixedHeight(40)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setStyleSheet("""
            LineEdit {
                font-size: 16px;
                border-radius: 8px;
                border: 1px solid #dcdcdc;
                background-color: #fafafa;
            }
            LineEdit:focus {
                border-color: #0066cc;
                background-color: #fff;
            }
        """)
        int_validator = QIntValidator(1, 9999)
        self.page_input.setValidator(int_validator)
        self.page_input.returnPressed.connect(self.jump_to_page_by_lineedit)
        self.total_page_label = QLabel(f"/ {self.total_images}")
        self.total_page_label.setStyleSheet("font-size:16px; color: #666;")
        self.next_btn = PushButton("下一页", self)
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(self.total_images > 1)

        nav_btn_style = """
            PushButton {
                border-radius: 8px;
                padding: 0;
                background-color: #f0f5ff;
                color: #0066cc;
                border: 1px solid #cce0ff;
                font-weight: 500;
            }
            PushButton:hover {
                background-color: #e6f0ff;
                border-color: #99ccff;
            }
            PushButton:pressed {
                background-color: #d9e8ff;
                border-color: #66b3ff;
            }
            PushButton:disabled {
                background-color: #f5f5f5;
                color: #bbb;
                border-color: #eee;
            }
        """
        for btn in [self.prev_btn, self.next_btn]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Microsoft YaHei", 13))
            btn.setFixedSize(110, 40)
            btn.setStyleSheet(nav_btn_style)

        page_control_layout.addWidget(self.prev_btn)
        page_control_layout.addWidget(page_label)
        page_control_layout.addWidget(self.page_input)
        page_control_layout.addWidget(self.total_page_label)
        page_control_layout.addWidget(self.next_btn)
        function_btn_layout = QHBoxLayout()
        function_btn_layout.setSpacing(16)
        function_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.save_btn = PrimaryPushButton("保存", self)
        self.save_btn.setStyleSheet("""
            PrimaryPushButton {
                border-radius: 8px;
                padding: 0;
                background-color: #0066cc;
                font-weight: 600;
            }
            PrimaryPushButton:hover {
                background-color: #1a75d1;
            }
            PrimaryPushButton:pressed {
                background-color: #0052a3;
            }
        """)
        self.save_btn.clicked.connect(self.save_catalog)
        self.clear_selection_btn = PushButton("重置", self)
        self.clear_selection_btn.clicked.connect(self.reset_fun)
        self.clear_selection_btn.setStyleSheet("""
            PushButton {
                border-radius: 8px;
                padding: 0;
                background-color: #ffffff;
                color: #0066cc;
                border: 1px solid #cce0ff;
                font-weight: 600;
            }
            PushButton:hover {
                background-color: #f0f5ff;
                border-color: #99ccff;
            }
            PushButton:pressed {
                background-color: #e6f0ff;
                border-color: #66b3ff;
            }
        """)
        self.parts_btn = PushButton("分件", self)
        self.parts_btn.clicked.connect(self.parts_files)
        self.parts_btn.setStyleSheet("""
            PushButton {
                border-radius: 8px;
                padding: 0;
                background-color: #f5a623;
                color: #ffffff;
                border: 1px solid #f5a623;
                font-weight: 600;
            }
            PushButton:hover {
                background-color: #e0941b;
                border-color: #e0941b;
            }
            PushButton:pressed {
                background-color: #c98316;
                border-color: #c98316;
            }
        """)

        for btn in [self.save_btn, self.clear_selection_btn, self.parts_btn]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Microsoft YaHei", 13))
            btn.setFixedSize(120, 40)

        function_btn_layout.addWidget(self.save_btn)
        function_btn_layout.addWidget(self.clear_selection_btn)
        function_btn_layout.addWidget(self.parts_btn)
        bottom_operation_layout.addLayout(page_control_layout)
        bottom_operation_layout.addStretch(1)
        bottom_operation_layout.addLayout(function_btn_layout)
        middle_layout.addLayout(bottom_operation_layout)
        main_splitter.addWidget(middle_widget)

        right_widget = CardWidget()
        right_widget.setStyleSheet("""
            CardWidget {
                border-radius: 12px;
                background-color: #fff;
            }
        """)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_area = ScrollArea()
        scroll_area.setStyleSheet("border: none; background: transparent;")
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_area.setWidget(scroll_content)

        right_layout = QVBoxLayout(scroll_content)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        # 存储输入框和标签引用
        self.field_inputs = {}
        self.field_labels = {}
        self.field_edit_list = []
        # 记录档号字段的原始值, 用于判断是否被用户修改
        self._original_doc_number = ""

        label_style = """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333;
                min-width: 110px;
                max-width: 110px;
                padding-right: 8px;
            }
        """
        edit_style = """
            TextEdit {
                font-size: 14px;
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid #dcdcdc;
                background-color: #fafafa;
            }
            TextEdit:focus {
                border-color: #0066cc;
                background-color: #fff;
                outline: none;
            }
        """
        line_edit_style = """
            LineEdit {
                font-size: 14px;
                padding: 6px 14px;
                border-radius: 8px;
                border: 1px solid #dcdcdc;
                background-color: #fafafa;
            }
            LineEdit:focus {
                border-color: #0066cc;
                background-color: #fff;
                outline: none;
            }
        """

        for label_text, placeholder, _ in self.fields:
            field_layout = QHBoxLayout()
            field_layout.setSpacing(8)
            field_layout.setAlignment(Qt.AlignVCenter)

            # 标签
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            label.setStyleSheet(label_style)
            self.field_labels[label_text] = label

            is_multiline = self._is_multiline_field(label_text)
            if is_multiline:
                edit = FocusAwareTextEdit(field_name=label_text)
                edit.setStyleSheet(edit_style)
                edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                edit.setMinimumHeight(72)
            else:
                edit = FocusAwareLineEdit(field_name=label_text)
                edit.setStyleSheet(line_edit_style)
                edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                edit.setFixedHeight(38)

            edit.setPlaceholderText(placeholder)

            if label_text == "档号":
                edit.textChanged.connect(self._on_doc_number_changed)

            self.field_inputs[label_text] = edit
            field_layout.addWidget(label)
            field_layout.addWidget(edit, stretch=1)
            right_layout.addLayout(field_layout, stretch=1 if is_multiline else 0)
            self.field_edit_list.append(edit)

        # print(f"目录输入框: {self.field_inputs}")
        right_main_layout = QVBoxLayout(right_widget)
        right_main_layout.setSpacing(0)
        right_main_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.addWidget(scroll_area, stretch=1)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([280, 480, 600])
        main_layout.addWidget(main_splitter, stretch=1)
        self.update_image_display()
        self.update_user_label()
        self.update_value()
        # if self.directior_data_list:
        #     self.load_director_value(self.directior_data_list[0])

        self._check_task_status()

    def _on_doc_number_changed(self, new_text):
        new_text = new_text.strip()
        old_text = self._original_doc_number

        if new_text == old_text:
            return

        print(f"档号已修改: 原值={old_text!r}, 新值={new_text!r}")
        self.doc_number = new_text

        where = {
            "doc_number": new_text,
            "archive_type": self.archives_value_line.text().strip(),
            "category": "案卷级"
            if self.archives_unit_line.text().strip() == "卷"
            else "文件级",
        }
        print(f"where: {where}")
        dir_info = director_service.get_dir_info(where)
        print(f"dir_info: {dir_info}")
        if dir_info:
            # print(f"field_edit_list = {self.field_edit_list}")
            director_info = json.loads(dir_info[0].director_info)
            print(f"director_info: {director_info}")

            for field, edit in self.field_inputs.items():
                value = self._safe_text(director_info.get(field, ""))
                print(f"value: {value}")
                if field == "档号":
                    continue
                edit.setText(value)
        else:
            for field, edit in self.field_inputs.items():
                if field == "档号":
                    continue
                edit.setText("")

    def _check_task_status(self):
        self.can_do_task = None
        where = {
            "register_id": self.task_info.register_id,
            "task_name": "扫 描",
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

    def update_value(self):
        self.batch_value_label.setText(self._safe_text(self.register_info.batch_number))
        self.task_value_label.setText(
            f"{self.register_info.number_start}-{self.register_info.number_end}"
        )
        if self.scan_info_list:
            self.image_path_label.setText(self._safe_text(self.scan_info_list[0].dir_path))
        else:
            self.image_path_label.setText("")
        self.archives_value_line.setText(self._safe_text(self.register_info.archive_type))
        self.archives_unit_line.setText(self._safe_text(self.register_info.category))

    def load_director_value(self, data):
        director_info = json.loads(data.director_info or "{}")
        for field, edit in self.field_inputs.items():
            value = self._safe_text(director_info.get(field, ""))
            edit.setText(value)
            if field == "档号":
                self._original_doc_number = value

    def reset_fun(self):
        try:
            for key, value in self.field_inputs.items():
                print(f"{key}: {value}")
                value.setText("")

            show_success(self, "重置成功", "目录重置完成!")
        except Exception as e:
            show_error(self, "重置报错", f"目录重置失败: {str(e)}")

    def parts_files(self):

        if self.current_page == self.total_images:
            pages = self.current_page
            self.parts_files_image.append(self.current_image_path)
        else:
            pages = self.current_page - 1

        print(f"parts_files: {len(self.parts_files_image)}")
        print(
            f"current_page: {self.current_page}; total_images: {self.total_images}; pages: {pages}"
        )

        parts_folder = f"{self.current_folder_path}/{self.doc_number}"
        os.makedirs(parts_folder, exist_ok=True)
        moved_paths = []
        for image_path in self.parts_files_image[:pages]:
            target_path = os.path.join(parts_folder, os.path.basename(image_path))
            shutil.move(image_path, target_path)
            moved_paths.append(image_path)

        show_success(self, "分件成功", f"分件文件夹已创建: {self.doc_number}")

        self.parts_files_image.clear()
        self.directory_tree.refresh_tree()

        # 从图片列表中移除已分件的图片, 并重置页码/总数
        for image_path in moved_paths:
            if image_path in self.image_paths:
                self.image_paths.remove(image_path)

        self.total_images = len(self.image_paths)
        self.current_page = 1
        self.total_page_label.setText(f"/ {self.total_images}")
        self.page_input.blockSignals(True)
        self.page_input.setText(str(self.current_page))
        self.page_input.blockSignals(False)
        self.prev_btn.setEnabled(self.current_page > 1 and self.total_images > 1)
        self.next_btn.setEnabled(self.current_page < self.total_images)
        self.update_image_display()

    def load_images_from_folder(self, folder_path):
        if not os.path.exists(folder_path):
            show_warning(self, "提示", f"文件夹不存在: {folder_path}")
            return
        self.current_folder_path = folder_path

        print(f"当前选中文件夹路径: {self.current_folder_path}")
        image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]
        image_paths = []
        print(f"folder_path = {folder_path}")
        try:
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_paths.append(os.path.join(folder_path, file))
        except Exception as e:
            show_error(self, "图片加载失败", f"读取文件夹图片失败: {str(e)}")
            logger.error(f"读取文件夹图片失败: {e}")

            return
        image_paths.sort()
        self.image_paths = image_paths
        self.total_images = len(image_paths)
        self.current_page = 1
        self.total_page_label.setText(f"/ {self.total_images}")
        self.update_image_display()
        self.prev_btn.setEnabled(self.total_images > 1)
        self.next_btn.setEnabled(self.total_images > 1)

        if self.total_images > 0:
            show_success(self, "加载成功", f"已加载 {self.total_images} 张图片")
            logger.info(f"加载图片成功, 已经加载 {self.total_images} 张图片")
            for field, edit in self.field_inputs.items():
                edit.setText("")
        else:
            show_info(self, "警告", "该文件夹下没有图片")
            logger.warning(f"警告, 该文件夹下没有图片")
            for field, edit in self.field_inputs.items():
                edit.setText("")
            return

        self.doc_number = os.path.basename(self.current_folder_path)
        where = {
            "doc_number": self.doc_number,
            "register_id": self.register_info.id,
        }
        print(f"where: {where}")
        dir_info = director_service.get_dir_info(where=where)
        print(f"dir_info: {dir_info}")
        if dir_info:
            director_info = json.loads(dir_info[0].director_info)
            print(f"director_info: {director_info}")
            for field, edit in self.field_inputs.items():
                value = self._safe_text(director_info.get(field, ""))
                edit.setText(value)
                if field == "档号":
                    self._original_doc_number = value
        else:
            for field, edit in self.field_inputs.items():
                if field == "档号":
                    edit.setText(self.doc_number)
                    self._original_doc_number = self.doc_number
                if field == "页数":
                    edit.setText(str(self.total_images))

        # 切换目录后回显整棵目录树的标记状态 + 全局气泡计数
        self._restore_all_dir_marks()
        self._sync_mark_count_from_db()

    def on_field_focus(self, field_name):
        self.current_focused_field = field_name
        self.update_field_labels_highlight()

    def update_field_labels_highlight(self):
        for field_name, label in self.field_labels.items():
            if field_name == self.current_focused_field:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 16px;
                        font-weight: bold;
                        color: #0066cc;
                        min-width: 110px;
                        max-width: 110px;
                        text-align: right;
                        padding-right: 8px;
                        background-color: #f0f8ff;
                        border: 1px solid #cce7ff;
                        border-radius: 4px;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        font-size: 16px;
                        font-weight: bold;
                        color: #333;
                        min-width: 110px;
                        max-width: 110px;
                        text-align: right;
                        padding-right: 8px;
                    }
                """)

    def on_image_selection(self, selection_rect):
        if not self.current_focused_field:
            show_warning(self, "选择提示", "请先选择要填充的输入框，再选择图片区域")
            self.image_container.clear_selection()
            return

        actual_display_rect = self.image_container.get_actual_display_rect()
        if not actual_display_rect.contains(selection_rect):
            show_warning(self, "选择区域无效", "请确保选择区域在图片显示范围内")
            self.image_container.clear_selection()
            return

        if selection_rect.width() < 10 or selection_rect.height() < 10:
            show_warning(
                self, "选择区域过小", "请选择更大的区域（建议宽度和高度均大于20像素）"
            )
            self.image_container.clear_selection()
            return

        show_info(
            self,
            "选择成功",
            f"已选中图片区域中需要识别的区域，准备提取【{self.current_focused_field}】字段内容",
            2000,
        )

        if not self.current_focused_field:
            show_warning(self, "OCR识别失败", "请先选择要填充的输入框，再进行识别")
            return

        selection_rect = self.image_container.get_selection_rect()
        if (
            selection_rect.isNull()
            or selection_rect.width() < 10
            or selection_rect.height() < 10
        ):
            show_warning(self, "OCR识别失败", "请先在图片上选择有效的识别区域")
            return
        show_info(self, "识别中", "正在处理选中区域，请稍候...", 2000)
        QApplication.processEvents()

        temp_image_path = self.create_selected_temp_image()
        if not temp_image_path or not os.path.exists(temp_image_path):
            show_error(self, "OCR识别失败", "无法生成选中区域的临时图片")
            return

        try:
            ocr_result = self.ocr_recognize_image(temp_image_path)
        except Exception as e:
            show_error(self, "OCR识别失败", f"识别过程中出现错误：{str(e)}")
            logger.error(f"识别过程中出现错误：{str(e)}")
            return False

        if self.current_focused_field in self.field_inputs:
            current_text = self.field_inputs[self.current_focused_field].text()
            if current_text:
                new_text = f"{current_text} {ocr_result}"
            else:
                new_text = ocr_result

            self.field_inputs[self.current_focused_field].setText(new_text)

            show_success(
                self,
                "识别成功",
                f"已将识别结果填充到【{self.current_focused_field[:10]}】字段\n识别内容：{ocr_result}",
                2000,
            )
            logger.info(f"OCR识别成功; 识别内容：{ocr_result}")

            QTimer.singleShot(1000, self.clear_image_selection)

    def create_selected_temp_image(self):
        self.clean_temp_images()

        selection_rect = self.image_container.get_selection_rect()
        if not self.current_pixmap or selection_rect.isNull():
            return None

        print(f"选择区域: {selection_rect}")
        print(f"图片实际显示区域: {self.actual_display_rect}")

        if self.actual_display_rect.isNull():
            label_size = self.image_container.size()
            pixmap_size = self.current_pixmap.size()
            scaled_width = label_size.width()
            scaled_height = label_size.height()
            aspect_ratio = pixmap_size.width() / pixmap_size.height()

            if scaled_width / scaled_height > aspect_ratio:
                scaled_width = int(scaled_height * aspect_ratio)
            else:
                scaled_height = int(scaled_width / aspect_ratio)

            x_offset = (label_size.width() - scaled_width) // 2
            y_offset = (label_size.height() - scaled_height) // 2

            self.actual_display_rect = QRect(
                x_offset, y_offset, scaled_width, scaled_height
            )
            self.image_container.set_actual_display_rect(self.actual_display_rect)

        if not self.actual_display_rect.contains(selection_rect):
            show_warning(self, "选择区域无效", "选择区域超出了图片显示范围")
            logger.warning(f"选择区域超出了图片显示范围")
            return None

        pixmap_size = self.current_pixmap.size()
        display_rect = self.actual_display_rect

        scale_x = pixmap_size.width() / display_rect.width()
        scale_y = pixmap_size.height() / display_rect.height()

        print(f"缩放比例: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
        relative_x = selection_rect.x() - display_rect.x()
        relative_y = selection_rect.y() - display_rect.y()

        mapped_rect = QRect(
            int(relative_x * scale_x),
            int(relative_y * scale_y),
            int(selection_rect.width() * scale_x),
            int(selection_rect.height() * scale_y),
        )
        print(f"映射后的区域: {mapped_rect}")

        mapped_rect = mapped_rect.intersected(
            QRect(0, 0, pixmap_size.width(), pixmap_size.height())
        )

        if mapped_rect.width() < 5 or mapped_rect.height() < 5:
            show_warning(self, "选择区域过小", "映射后的区域太小，请选择更大的区域")
            logger.warning(f"映射后的区域太小，请选择更大的区域")
            return None

        selected_pixmap = self.current_pixmap.copy(mapped_rect)
        if selected_pixmap.isNull():
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        temp_filename = f"selected_area_page_{self.current_page}_{timestamp}.png"
        temp_path = os.path.join(settings.temp_path, temp_filename)

        os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        success = selected_pixmap.save(temp_path, "PNG", 95)
        if not success:
            print(f"保存临时图片失败: {temp_path}")
            return None

        print(f"临时图片保存成功: {temp_path}, 尺寸: {selected_pixmap.size()}")
        self.selected_temp_image = temp_path

        return temp_path

    def ocr_recognize_image(self, image_path):
        logger.info(f"【OCR识别】 正在处理图片: {image_path}")
        logger.info(
            f"【OCR识别】 图片大小: {os.path.getsize(image_path) / 1024:.2f} KB"
        )
        page = self.current_page
        field = self.current_focused_field
        print(f"page: {page}, field: {field}")

        if self.ocr_detector is None:
            print("初始化OCR")
            # from src.utils.OCRDetector import OCRDetector
            print(111)
            raise RuntimeError("OCR模型尚未加载完成， 请稍后再试")
            # self.ocr_detector = OCRDetector()
            # print(2222)

        result = self.ocr_detector.detect(image_path) or []
        print(f"result: {result}")
        return "".join(str(item) for item in result)

    def clear_image_selection(self):
        self.image_container.clear_selection()
        self.clean_temp_images()

    def clean_temp_images(self):
        if self.selected_temp_image and os.path.exists(self.selected_temp_image):
            try:
                os.remove(self.selected_temp_image)
                # show_success(self, "清除临时文件", "已清除临时文件")
            except Exception as e:
                show_error(self, "错误提示", f"清除临时文件失败; {str(e)}")
                logger.error(f"清除临时文件失败; {str(e)}")
        self.selected_temp_image = None

        try:
            temp_dir = settings.temp_path
            os.makedirs(temp_dir, exist_ok=True)
            now = datetime.now()
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if (now - file_mtime).total_seconds() > 1800:  # 1800秒=30分钟
                        os.remove(file_path)
        except Exception as e:
            print(f"清理过期临时图片失败：{e}")
            logger.error(f"清理过期临时图片失败：{e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_image_display)

    def update_image_display(self):
        if not self.image_paths:
            self.image_container.setPixmap(QPixmap())
            self.image_container.setText("无可用图片")
            return

        image_path = self.image_paths[self.current_page - 1]
        self.image_path_label.setText(os.path.dirname(image_path))
        self.current_image_path = image_path
        print(f"current_image_path: {self.current_image_path}")
        self.current_image_list.append(image_path)
        pixmap = QPixmap(image_path)
        self.current_pixmap = pixmap
        if not pixmap.isNull():
            container_size = self.image_container.size()

            pixmap_size = pixmap.size()
            scaled_width = container_size.width() - 10
            scaled_height = container_size.height() - 10
            aspect_ratio = pixmap_size.width() / pixmap_size.height()

            if scaled_width / scaled_height > aspect_ratio:
                scaled_width = int(scaled_height * aspect_ratio)
            else:
                scaled_height = int(scaled_width / aspect_ratio)

            x_offset = (container_size.width() - scaled_width) // 2
            y_offset = (container_size.height() - scaled_height) // 2

            self.actual_display_rect = QRect(
                x_offset, y_offset, scaled_width, scaled_height
            )
            self.image_container.set_actual_display_rect(self.actual_display_rect)

            scaled_pixmap = pixmap.scaled(
                scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            background = QPixmap(container_size)
            background.fill(Qt.lightGray)
            painter = QPainter(background)
            painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
            painter.end()

            self.image_container.setPixmap(background)
            self.image_container.setText("")
        else:
            self.image_container.setPixmap(QPixmap())
            self.image_container.setText("图片加载失败")

        self.image_container.clear_selection()
        self.clean_temp_images()

        self.page_input.blockSignals(True)
        self.page_input.setText(str(self.current_page))
        self.page_input.blockSignals(False)

        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_images)

    def prev_page(self):

        if self.current_page > 1:
            self.current_page -= 1
            self.update_image_display()

    def next_page(self):
        """下一页"""
        self.parts_files_image.append(self.current_image_path)

        if self.current_page < self.total_images:
            self.current_page += 1
            self.update_image_display()

    def jump_to_page_by_lineedit(self):
        """通过LineEdit输入页码跳转"""
        try:
            page = int(self.page_input.text().strip())
            if 1 <= page <= self.total_images:
                self.current_page = page
                self.update_image_display()
            else:
                show_warning(self, "页码无效", f"请输入1-{self.total_images}之间的页码")
                self.page_input.setText(str(self.current_page))
        except ValueError:
            show_error(self, "输入错误", "请输入有效的数字页码")
            self.page_input.setText(str(self.current_page))

    def jump_to_page(self, page):
        self.current_page = page
        self.update_image_display()

    # ──────────────────── 质检标记功能（目录质检） ────────────────────

    def sing_message_fun(self):
        """
        质检员对当前目录（doc_number）添加目录质检标记。
        标记对象为右侧填写的目录信息整体；若有聚焦字段，记录到 field_name。
        """
        if not self.current_user or self.current_user.get("role") not in [
            "管理员",
            "质检员",
        ]:
            show_warning(self, "警告", "非管理员或质检员不可标记")
            return
        if not self.task_info or not getattr(self.task_info, "is_do", False):
            show_warning(self, "提示", "当前任务未提交，暂不可标记！")
            return
        if not getattr(self, "current_folder_path", None) or not getattr(
            self, "doc_number", None
        ):
            show_warning(self, "提示", "请先在左侧目录树中选中要标记的目录")
            return

        doc_number = self.doc_number
        field_name = self.current_focused_field or None
        field_value = (
            self.field_inputs[field_name].toPlainText()
            if field_name
            and field_name in self.field_inputs
            and hasattr(self.field_inputs[field_name], "toPlainText")
            else (
                self.field_inputs[field_name].text()
                if field_name and field_name in self.field_inputs
                else None
            )
        )

        # ── 查历史标记（以 doc_number 为对象）──
        existing_marks = []
        try:
            from src.services.task_mark_service import task_mark_service

            existing_marks = task_mark_service.get_mark_info(
                {
                    "task_id": self.task_info.id,
                    "scan_file": doc_number,
                }
            )
        except Exception as e:
            logger.warning(f"查询已有标记失败: {e}")

        if existing_marks:
            from src.view.common.MarkHistoryDialog import MarkHistoryDialog

            history_dlg = MarkHistoryDialog(
                parent=self,
                image_name=doc_number,
                marks=existing_marks,
                task_info=self.task_info,
                current_user=self.current_user,
                on_mark_changed=lambda: (
                    self._refresh_dir_mark_state(),
                    self._sync_mark_count_from_db(),
                ),
            )
            if not history_dlg.exec():
                self._refresh_dir_mark_state()
                self._sync_mark_count_from_db()
                return

        from src.view.common.MarkIssueDialog import MarkIssueDialog

        dlg = MarkIssueDialog(
            target_name=field_name or doc_number, mark_stage="目录质检"
        )
        if dlg.exec():
            mark_data = dlg.get_data()
            if len(mark_data.get("description", "")) < 6:
                show_warning(self, "提示", "描述标记内容不得少于 6 个字！")
                return

            save_data = {
                "task_id": self.task_info.id,
                "batch_number": self.task_info.batch_number,
                "task_node": self.task_info.task_node,
                "mark_stage": 3,  # 目录质检
                "scan_file": doc_number,
                "mark_type": mark_data.get("mark_type", "其他"),
                "level": mark_data.get("level", "一般"),
                "description": mark_data.get("description", ""),
                "inspector": self.current_user.get("username", ""),
                "mark_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_fixed": False,
            }
            if field_name:
                save_data["field_name"] = field_name
                save_data["field_value_before"] = field_value

            try:
                from src.services.task_mark_service import task_mark_service

                task_mark_service.add_mark(save_data)
                self._set_dir_mark_state(True)
                self._mark_total_count += 1
                self._update_mark_count_badge()
                target_desc = (
                    f"字段【{field_name}】" if field_name else f"目录【{doc_number}】"
                )
                show_success(
                    self,
                    "标记成功",
                    f"已对 {target_desc} 标记【{mark_data.get('mark_type', '其他')}】",
                )
            except Exception as e:
                logger.error(f"标记保存失败: {e}")
                show_error(self, "失败", "标记保存失败，请重试")

    def _set_dir_mark_state(self, has_mark: bool):
        """
        在左侧目录树中标记当前目录文件夹（中间图片容器不再做标记提示）。
        """
        if hasattr(self, "directory_tree") and getattr(
            self, "current_folder_path", None
        ):
            self.directory_tree.set_folder_mark_state(
                self.current_folder_path, has_mark
            )

    def _refresh_dir_mark_state(self):
        """查库刷新当前目录是否仍有未修复标记，更新左侧目录树节点"""
        if not self.task_info or not getattr(self, "doc_number", None):
            return
        try:
            from src.services.task_mark_service import task_mark_service

            pending = task_mark_service.get_pending_marks_by_file(
                task_id=self.task_info.id,
                scan_file=self.doc_number,
            )
            self._set_dir_mark_state(bool(pending))
        except Exception as e:
            logger.warning(f"刷新目录标记状态失败: {e}")

    def _restore_all_dir_marks(self):
        """
        遍历目录树所有文件夹节点，查询哪些目录有未修复标记，批量回显 ⚑。
        在目录加载完成 / 标记变化后调用，确保整棵树标记状态正确。
        """
        if not self.task_info or not hasattr(self, "directory_tree"):
            return
        try:
            from src.services.task_mark_service import task_mark_service

            marked_paths = set()

            # 遍历树收集所有文件夹节点路径，逐个查未修复标记
            root = self.directory_tree.tree_widget.invisibleRootItem()

            def _collect(parent):
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    path = child.data(0, Qt.UserRole)
                    if path:
                        doc_no = os.path.basename(path)
                        pending = task_mark_service.get_pending_marks_by_file(
                            task_id=self.task_info.id,
                            scan_file=doc_no,
                        )
                        if pending:
                            marked_paths.add(path)
                    _collect(child)

            _collect(root)
            self.directory_tree.restore_all_folder_marks(marked_paths)
        except Exception as e:
            logger.warning(f"回显目录树标记失败: {e}")

    def _sync_mark_count_from_db(self):
        """从数据库查询当前任务未修复标记总数，刷新气泡"""
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
            self.mark_count_badge.setText("99+" if count > 99 else str(count))
            self.mark_count_badge.setFixedWidth(28 if count > 9 else 22)
            self.mark_count_badge.show()
            self.mark_count_badge.raise_()
        else:
            self.mark_count_badge.hide()

    def submit_status(self):
        # 提交前检查：存在未修复质检标记则阻止提交
        try:
            from src.services.task_mark_service import task_mark_service

            passed, pending_detail = task_mark_service.check_task_mark_pass(
                self.task_info.id
            )
            if not passed:
                detail_txt = "、".join(
                    f"{k} 还有 {v} 条未修改" for k, v in pending_detail.items()
                )
                show_warning(
                    self, "无法提交", f"当前任务存在未处理的质检标记：{detail_txt}"
                )
                return
        except Exception as e:
            logger.warning(f"提交前检查标记状态失败: {e}")

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
                    "task_id": self.task_info.id,
                    "task_name": "目录录入/校对",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": "目录录入/校对提交操作",
                }
                operation_service.save_data([operation_data])
                show_success(self, "提示", "提交成功")
            else:
                show_warning(self, "警告", f"{result['message']}")
                logger.error(f"目录录入/校对; 提交失败: {result['message']}")
        except Exception as e:
            logger.error(f"目录录入/校对; 提交失败: {str(e)}")
            show_error(self, "报错", "提交失败")

    def save_catalog(self):
        catalog_data = {}
        for field, edit in self.field_inputs.items():
            catalog_data[field] = edit.text().strip()

        # 验证必填字段
        required_fields = [field[0] for field in self.fields if field[2] == "是"]
        print(f"必填字段: {required_fields}")
        empty_fields = [field for field in required_fields if not catalog_data[field]]

        if empty_fields:
            show_error(
                self, "提交失败", f"以下必填字段不能为空：{', '.join(empty_fields)}"
            )
            logger.error(f"以下必填字段不能为空：{', '.join(empty_fields)}")
            return

        print(f"catalog_data: {catalog_data}")

        archive_type = self.archives_value_line.text().strip()
        category = (
            "案卷级" if self.archives_unit_line.text().strip() == "卷" else "文件级"
        )

        where = {
            "archive_type": archive_type,
            "category": category,
            "doc_number": catalog_data["档号"],
        }
        is_exist = director_service.get_dir_info(where)
        print(f"is_exist: {is_exist}")
        if is_exist:
            update = {
                "register_id": self.register_info.id,
                "title": catalog_data["题名"],
                "director_info": json.dumps(catalog_data, ensure_ascii=False),
                "source": "校对",
                "update_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator": self.current_user["username"],
            }
            try:
                result = director_service.update_director(is_exist[0].id, update)
                print(f"result: {result}")
                show_success(self, "提示", "保存成功!")
                operation_data = {
                    "task_id": self.task_info.id,
                    "task_name": "目录录入/校对",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"更新目录; 目录信息:{update}",
                }
                operation_service.save_data([operation_data])
            except Exception as e:
                logger.error(f"更新失败; 更新信息: {update}; 错误原因: {e}")
                show_error(self, "报错", "保存失败")
                return

        else:
            add_data = {
                "register_id": self.register_info.id,
                "doc_number": catalog_data["档号"],
                "title": catalog_data["题名"],
                "archive_type": archive_type,
                "category": category,
                "source": "自填",
                "director_info": json.dumps(catalog_data, ensure_ascii=False),
                "operator": self.current_user["username"],
                "create_date": datetime.now(),
                "update_date": datetime.now(),
            }

            try:
                inster_result = director_service.batch_add([add_data])
                if inster_result:
                    operation_data = {
                        "task_id": self.task_info.id,
                        "task_name": "目录录入/校对",
                        "operator": self.current_user["username"],
                        "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "operator_remark": f"保存目录; 目录信息:{add_data}",
                    }
                    operation_service.save_data([operation_data])
                    show_success(self, "保存成功", f"{self.doc_number} 目录信息已保存")
                    logger.info(f"{self.doc_number}目录信息已保存")
                    for field, edit in self.field_inputs.items():
                        edit.setText("")
            except Exception as e:
                logger.error(f"提交失败: {str(e)}")

    def back_table(self):
        self._is_navigation = True

        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出重新登录")
            time.sleep(1)
            from src.view.login import LoginWindow

            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.dir_recognition.dirTable_window import DirTableWindow

            dir_table_window = DirTableWindow()
            dir_table_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label.setText(f"👤 {username} ({userrole})")
        else:
            self.user_label.setText("未登录")

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        self.clean_temp_images()

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
                self.logout()
                from src.view.login import LoginWindow

                self.login_window = LoginWindow()
                self.login_window.showFullScreen()
                logger.info(f"退出系统, 当前用户信息: {self.current_user}")
            else:
                event.ignore()
        else:
            event.accept()

    def close_without_confirm(self):
        self._is_navigation = True
        QTimer.singleShot(100, self.close)
