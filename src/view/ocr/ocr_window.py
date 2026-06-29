# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : ocr_window.py
# @Desc      : OCR 窗口
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
import time
import tempfile
import numpy as np
from datetime import datetime
from paddleocr import PaddleOCR
from PySide6.QtGui import (QFont, QPixmap, QImage, QTransform, QPalette, QPainter,
                           QIntValidator, QCursor, QTextCursor, QPen, QColor)
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView, QScrollArea, QFrame,
                               QLabel, QWidget, QLineEdit, QComboBox, QTableWidgetItem, QDialog, QSizePolicy,
                               QMessageBox, QRubberBand, QTextEdit, QGridLayout)
from PySide6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QSize, QTimer, QRect, QEvent, Signal

from qfluentwidgets import (setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton, ScrollArea,
                            LineEdit, ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition, ElevatedCardWidget,
                            SpinBox, TextEdit, FlowLayout, CaptionLabel, CheckBox)

from qframelesswindow import FramelessWindow


# 模拟缓存管理器
class GlobalCache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key, None)

    def set(self, key, value):
        self.cache[key] = value

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]


global_cache = GlobalCache()

# 模拟测试图片路径（实际使用时可替换为真实路径列表）
TEST_IMAGE_PATHS = [
    r"/Users/zhangtao/Desktop/识别图片/1.png",
    r"/Users/zhangtao/Desktop/识别图片/2.png",
    r"/Users/zhangtao/Desktop/识别图片/3.png",
    r"/Users/zhangtao/Desktop/识别图片/4.png",
    r"/Users/zhangtao/Desktop/识别图片/5.png",
    r"/Users/zhangtao/Desktop/识别图片/6.png",
    r"/Volumes/Projects/projects/DigitalSystem/tests/images/Snipaste_2025-12-01_17-26-12.png",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500002.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500003.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500004.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500005.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500006.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500007.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500008.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500009.jpg",
    # r"/Volumes/Projects/projects/DigitalSystem/tests/images/20211106-01500010.jpg",
]

# 临时文件夹配置
TEMP_DIR = os.path.join(tempfile.gettempdir(), "DigitalSystem_OCR_Temp")
os.makedirs(TEMP_DIR, exist_ok=True)  # 确保临时文件夹存在


class OCRResultTextEdit(QTextEdit):
    """OCR结果显示文本框，支持自动调整高度和选中行信号"""
    line_selected = Signal(int)  # 选中行号信号
    selection_cleared = Signal()  # 取消选中信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                background-color: #f8f8f8;
                padding: 15px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: 14px;
                color: #333;
                line-height: 1.6;
            }
            QTextEdit:focus {
                border-color: #0066cc;
                background-color: #fff;
            }
        """)
        self.current_selected_line = -1
        self.raw_ocr_data = []  # 保存原始OCR数据（包含坐标）

    def set_ocr_data(self, raw_data, text):
        """设置OCR识别数据和文本"""
        self.clear()
        self.raw_ocr_data = raw_data
        if text:
            # 格式化文本，去除行号
            formatted_text = self.format_ocr_text(text)
            self.setText(formatted_text)
            # 自动调整高度
            self.adjust_height()

    def format_ocr_text(self, text):
        """格式化OCR识别文本，去除行号"""
        lines = text.strip().split('\n')
        formatted_lines = []
        for line in lines:
            if line.strip():  # 非空行
                # 去除行号（如果存在的话）
                line_text = line.strip()
                # 如果行首是数字加点加空格的格式（如"1. "），则去除
                if line_text and line_text[0].isdigit():
                    # 找到第一个非数字字符的位置
                    i = 0
                    while i < len(line_text) and line_text[i].isdigit():
                        i += 1
                    # 如果后面是点或顿号等分隔符，则跳过
                    if i < len(line_text) and line_text[i] in ['.', '、', '。', '，']:
                        # 跳过分隔符
                        i += 1
                        # 跳过分隔符后的空格
                        while i < len(line_text) and line_text[i].isspace():
                            i += 1
                        line_text = line_text[i:]
                formatted_lines.append(line_text)
        return '\n'.join(formatted_lines)

    def adjust_height(self):
        """根据内容自动调整高度"""
        document_height = self.document().size().height()
        # 添加一些边距
        new_height = min(int(document_height) + 30, 400)  # 最大高度限制为400px
        self.setMinimumHeight(new_height)

    def clear_text(self):
        """清空文本"""
        self.clear()
        self.raw_ocr_data = []
        self.current_selected_line = -1
        self.setMinimumHeight(150)  # 恢复默认最小高度
        self.selection_cleared.emit()

    def mouseReleaseEvent(self, event):
        """重写鼠标释放事件，检测选中的行"""
        super().mouseReleaseEvent(event)
        self.detect_selected_line()

    def keyReleaseEvent(self, event):
        """重写键盘释放事件，检测选中的行（方向键、Shift等）"""
        super().keyReleaseEvent(event)
        if event.key() in [Qt.Key_Shift, Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                           Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
            self.detect_selected_line()

    def detect_selected_line(self):
        """检测选中的文本行，并发送信号"""
        cursor = self.textCursor()

        # 如果没有选中内容
        if cursor.selectionStart() == cursor.selectionEnd():
            self.current_selected_line = -1
            self.selection_cleared.emit()
            return

        # 获取选中的行号
        cursor.select(QTextCursor.LineUnderCursor)
        selected_text = cursor.selectedText().strip()
        if not selected_text:
            self.current_selected_line = -1
            self.selection_cleared.emit()
            return

        # 计算选中的行在文本中的位置
        document = self.document()
        start_block = document.findBlock(cursor.selectionStart())
        line_number = start_block.blockNumber()

        # 验证行号有效性
        if 0 <= line_number < len(self.raw_ocr_data):
            self.current_selected_line = line_number
            self.line_selected.emit(line_number)
        else:
            self.current_selected_line = -1
            self.selection_cleared.emit()


class ImageDisplayLabel(QLabel):
    """图片显示标签，支持绘制选中的文本框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #dcdcdc;
                border-radius: 8px;
                background-color: #f8f8f8;
            }
        """)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 400)
        self.setCursor(Qt.ArrowCursor)

        # 绘制相关属性
        self.original_pixmap = None  # 原始图片
        self.scaled_pixmap = None  # 缩放后的图片
        self.ocr_boxes = []  # OCR检测框列表
        self.selected_box_index = -1  # 选中的框索引
        self.scale_ratio = 1.0  # 缩放比例
        self.offset_x = 0  # X偏移
        self.offset_y = 0  # Y偏移

    def set_image(self, pixmap):
        """设置显示的图片"""
        self.original_pixmap = pixmap
        self.update_display()

    def set_ocr_boxes(self, boxes):
        """设置OCR检测框"""
        self.ocr_boxes = boxes
        self.selected_box_index = -1
        self.update_display()

    def select_box(self, index):
        """选中指定索引的检测框"""
        if 0 <= index < len(self.ocr_boxes):
            self.selected_box_index = index
        else:
            self.selected_box_index = -1
        self.update_display()

    def clear_selection(self):
        """清除选中状态"""
        self.selected_box_index = -1
        self.update_display()

    def update_display(self):
        """更新图片显示（包含选中框）"""
        if self.original_pixmap is None or self.original_pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText("图片加载失败")
            return

        # 计算缩放尺寸
        container_size = self.size()
        pixmap_size = self.original_pixmap.size()

        # 关键优化：计算保持宽高比的缩放
        scaled_width = container_size.width() - 10
        scaled_height = container_size.height() - 10
        aspect_ratio = pixmap_size.width() / pixmap_size.height()

        # 计算保持宽高比的尺寸
        if scaled_width / scaled_height > aspect_ratio:
            scaled_width = int(scaled_height * aspect_ratio)
        else:
            scaled_height = int(scaled_width / aspect_ratio)

        # 计算缩放比例和偏移
        self.scale_ratio = scaled_width / pixmap_size.width()
        self.offset_x = (container_size.width() - scaled_width) // 2
        self.offset_y = (container_size.height() - scaled_height) // 2

        # 缩放图片
        self.scaled_pixmap = self.original_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 创建背景并绘制
        background = QPixmap(container_size)
        background.fill(Qt.lightGray)
        painter = QPainter(background)

        # 绘制缩放后的图片
        painter.drawPixmap(self.offset_x, self.offset_y, self.scaled_pixmap)

        # 绘制OCR检测框
        self.draw_ocr_boxes(painter)

        painter.end()
        self.setPixmap(background)

    def draw_ocr_boxes(self, painter):
        """绘制OCR检测框"""
        if not self.ocr_boxes:
            return

        # 绘制所有检测框（灰色）
        normal_pen = QPen(QColor(100, 149, 237), 2, Qt.SolidLine)
        painter.setPen(normal_pen)

        for i, box in enumerate(self.ocr_boxes):
            if box and len(box) >= 4:
                # 转换坐标到显示位置
                points = []
                for point in box:
                    x = int(point[0] * self.scale_ratio) + self.offset_x
                    y = int(point[1] * self.scale_ratio) + self.offset_y
                    points.append(QPoint(x, y))

                # 绘制四边形
                if len(points) == 4:
                    painter.drawPolygon(points)

        # 绘制选中的框（红色）
        if 0 <= self.selected_box_index < len(self.ocr_boxes):
            selected_box = self.ocr_boxes[self.selected_box_index]
            if selected_box and len(selected_box) >= 4:
                selected_pen = QPen(QColor(255, 0, 0), 3, Qt.SolidLine)
                painter.setPen(selected_pen)

                points = []
                for point in selected_box:
                    x = int(point[0] * self.scale_ratio) + self.offset_x
                    y = int(point[1] * self.scale_ratio) + self.offset_y
                    points.append(QPoint(x, y))

                if len(points) == 4:
                    painter.drawPolygon(points)

    def resizeEvent(self, event):
        """重写大小改变事件"""
        super().resizeEvent(event)
        self.update_display()


class DirWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1200, 800)
        self.setMinimumSize(1200, 800)

        # 初始化核心属性
        self.current_page = 1
        self.image_paths = self._get_valid_image_paths()
        self.total_images = len(self.image_paths)
        self.current_pixmap = None
        self.ocr_full_results = {}  # 存储每张图片的完整OCR结果（包含坐标）
        self.ocr_text_results = {}  # 存储每张图片的纯文本结果

        # 初始化窗口
        self.center()
        setTheme(Theme.LIGHT)
        self.init_ui()

        # 关闭类型标志位
        self._is_navigation = False
        self._is_app_exiting = False

        # 初始化 PaddleOCR 实例（简化配置，适配标准版本）
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir="/Volumes/Projects/projects/DigitalSystem/src/resources/ocr_model/PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            text_recognition_model_dir="/Volumes/Projects/projects/DigitalSystem/src/resources/ocr_model/PP-OCRv5_mobile_rec",
            enable_mkldnn=True,
        )

    def _get_valid_image_paths(self):
        """获取有效图片路径（过滤不存在的文件）"""
        valid_paths = []
        for path in TEST_IMAGE_PATHS:
            if os.path.exists(path):
                valid_paths.append(path)
            else:
                placeholder_path = "placeholder.jpg"
                if not os.path.exists(placeholder_path):
                    self._create_placeholder_image(placeholder_path)
                valid_paths.append(placeholder_path)
        return valid_paths

    def _create_placeholder_image(self, path):
        """创建图片占位符"""
        image = QImage(800, 600, QImage.Format_RGB32)
        image.fill(Qt.lightGray)
        painter = QPainter(image)
        painter.setPen(Qt.gray)
        painter.setFont(QFont("Arial", 24))
        painter.drawText(image.rect(), Qt.AlignCenter, "图片占位符")
        painter.end()
        image.save(path)

    def center(self):
        """将窗口居中显示在屏幕上"""
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        """初始化主界面（完全自适应布局）"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 30, 10, 10)
        self.setLayout(main_layout)

        # === 顶部区域：用户信息 + 水印信息 ===
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)
        top_layout.setContentsMargins(0, 0, 0, 15)

        # 左侧水印信息区域
        watermark_layout = QHBoxLayout()
        watermark_layout.setSpacing(25)

        # 批次号水印
        batch_watermark_layout = QHBoxLayout()
        batch_label = QLabel('批次号:')
        batch_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                min-width: 60px;
                font-weight: bold;
            }
        """)
        self.batch_value_label = LineEdit()
        self.batch_value_label.setText("B000001")
        self.batch_value_label.setEnabled(False)
        self.batch_value_label.setMinimumWidth(80)
        batch_watermark_layout.addWidget(batch_label)
        batch_watermark_layout.addWidget(self.batch_value_label)

        # 任务号段水印
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
        self.task_value_label.setText("00001 - 000013")
        self.task_value_label.setEnabled(False)
        self.task_value_label.setMinimumWidth(90)
        task_watermark_layout.addWidget(task_label)
        task_watermark_layout.addWidget(self.task_value_label)

        # 图片路径水印
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
        self.image_path_label.setMinimumWidth(500)
        self.image_path_label.setEnabled(False)
        path_watermark_layout.addWidget(path_label)
        path_watermark_layout.addWidget(self.image_path_label)

        watermark_layout.addLayout(batch_watermark_layout)
        watermark_layout.addLayout(task_watermark_layout)
        watermark_layout.addLayout(path_watermark_layout)
        watermark_layout.addStretch(1)

        # 用户信息（右上角）
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

        top_layout.addLayout(watermark_layout, stretch=1)
        top_layout.addWidget(self.user_label)
        main_layout.addLayout(top_layout)

        # === 操作按钮区域 ===
        operation_layout = QHBoxLayout()
        operation_layout.setSpacing(20)
        operation_layout.setContentsMargins(0, 0, 0, 10)

        archives_type_label = QLabel("档案类别:")
        archives_type_label.setStyleSheet("font-size:16px; font-weight: bold; min-width: 80px;")
        self.archives_value_line = LineEdit()
        self.archives_value_line.setText("文书档案")
        self.archives_value_line.setEnabled(False)
        self.archives_value_line.setMaximumWidth(160)
        self.archives_unit_line = LineEdit()
        self.archives_unit_line.setText("卷")
        self.archives_unit_line.setEnabled(False)
        self.archives_unit_line.setMaximumWidth(60)

        # 功能按钮
        self.recognize_btn = PrimaryPushButton("识别", self)
        self.recognize_btn.clicked.connect(self.on_recognize_clicked)
        self.submit_btn = PrimaryPushButton("提交", self)
        self.back_btn = PushButton("返回", self)
        self.back_btn.clicked.connect(self.back_table)

        # 统一按钮样式和大小
        btn_list = [self.recognize_btn, self.submit_btn, self.back_btn]
        for btn in btn_list:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Arial", 16))
            btn.setFixedSize(110, 42)

        operation_layout.addWidget(archives_type_label)
        operation_layout.addWidget(self.archives_value_line)
        operation_layout.addWidget(self.archives_unit_line)
        operation_layout.addStretch(1)
        operation_layout.addWidget(self.recognize_btn)
        operation_layout.addWidget(self.submit_btn)
        operation_layout.addWidget(self.back_btn)

        main_layout.addLayout(operation_layout)

        # === 核心区域：左右布局（1:1占比）===
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(0, 0, 0, 15)

        # ---------------------- 左侧图片展示区 ----------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 图片显示容器（使用自定义的ImageDisplayLabel）
        self.image_container = ImageDisplayLabel()

        left_layout.addWidget(self.image_container, stretch=1)

        # ---------------------- 右侧OCR结果显示区 ----------------------
        right_widget = ElevatedCardWidget()
        right_widget.setStyleSheet("""
            ElevatedCardWidget {
                border-radius: 12px;
                padding: 25px;
                background-color: #fff;
            }
        """)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # OCR结果标题和状态区域（水平布局）
        ocr_header_layout = QHBoxLayout()
        ocr_header_layout.setSpacing(15)
        ocr_header_layout.setContentsMargins(0, 0, 0, 10)

        # OCR标题
        ocr_title_label = QLabel("OCR识别结果")
        ocr_title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #0066cc;
            }
        """)
        ocr_header_layout.addWidget(ocr_title_label)

        # 清空按钮
        self.clear_result_btn = PushButton("清空结果", self)
        self.clear_result_btn.setFixedSize(100, 35)
        self.clear_result_btn.setStyleSheet("""
            PushButton {
                border-radius: 6px;
                background-color: #ff6b6b;
                color: white;
                font-weight: bold;
            }
            PushButton:hover {
                background-color: #ff5252;
            }
        """)
        self.clear_result_btn.clicked.connect(self.clear_ocr_results)
        ocr_header_layout.addWidget(self.clear_result_btn)

        # 状态和耗时信息（放在最右侧）
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setSpacing(5)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        self.ocr_status_label = QLabel("状态：等待识别")
        self.ocr_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 3px 8px;
                background-color: #f0f0f0;
                border-radius: 4px;
                min-width: 120px;
            }
        """)

        self.ocr_time_label = QLabel("耗时：--")
        self.ocr_time_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 3px 8px;
                background-color: #f0f0f0;
                border-radius: 4px;
                min-width: 120px;
            }
        """)

        stats_layout.addWidget(self.ocr_status_label)
        stats_layout.addWidget(self.ocr_time_label)

        ocr_header_layout.addStretch(1)
        ocr_header_layout.addWidget(stats_widget)

        right_layout.addLayout(ocr_header_layout)

        # OCR结果显示区域（填充剩余空间）
        self.ocr_result_text = OCRResultTextEdit()
        self.ocr_result_text.setPlaceholderText("OCR识别结果将显示在这里...")
        self.ocr_result_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 连接选中行信号
        self.ocr_result_text.line_selected.connect(self.on_text_line_selected)
        self.ocr_result_text.selection_cleared.connect(self.on_text_selection_cleared)
        right_layout.addWidget(self.ocr_result_text, stretch=1)

        # 核心区域布局
        content_layout.addWidget(left_widget, stretch=1)
        content_layout.addWidget(right_widget, stretch=1)
        main_layout.addLayout(content_layout, stretch=1)

        # === 底部操作按钮区域 ===
        bottom_operation_layout = QHBoxLayout()
        bottom_operation_layout.setSpacing(30)
        bottom_operation_layout.setContentsMargins(0, 0, 0, 5)

        # 左侧翻页控制区域
        page_control_layout = QHBoxLayout()
        page_control_layout.setSpacing(15)
        page_control_layout.setContentsMargins(0, 0, 0, 0)

        self.prev_btn = PushButton("上一页", self)
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(self.total_images > 1)

        page_label = QLabel("页码:")
        page_label.setStyleSheet("font-size:16px; font-weight: bold;")

        self.page_input = LineEdit()
        self.page_input.setText(str(self.current_page))
        self.page_input.setFixedWidth(80)
        self.page_input.setStyleSheet("font-size:16px; text-align: center;")
        int_validator = QIntValidator(1, 9999)
        self.page_input.setValidator(int_validator)
        self.page_input.returnPressed.connect(self.jump_to_page_by_lineedit)

        self.total_page_label = QLabel(f"/ {self.total_images}")
        self.total_page_label.setStyleSheet("font-size:16px;")

        self.next_btn = PushButton("下一页", self)
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(self.total_images > 1)

        # 统一翻页按钮样式
        for btn in [self.prev_btn, self.next_btn]:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Arial", 16))
            btn.setFixedSize(120, 45)
            btn.setStyleSheet("""
                PushButton {
                    border-radius: 8px;
                    padding: 0;
                    background-color: #f0f5ff;
                    color: #0066cc;
                    border: 1px solid #cce0ff;
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
                    color: #999;
                    border-color: #ddd;
                }
            """)

        page_control_layout.addWidget(self.prev_btn)
        page_control_layout.addWidget(page_label)
        page_control_layout.addWidget(self.page_input)
        page_control_layout.addWidget(self.total_page_label)
        page_control_layout.addWidget(self.next_btn)

        # 右侧功能按钮区域
        function_btn_layout = QHBoxLayout()
        function_btn_layout.setSpacing(20)
        function_btn_layout.setContentsMargins(0, 0, 0, 0)

        # 底部整体布局
        bottom_operation_layout.addLayout(page_control_layout)
        bottom_operation_layout.addStretch(1)
        bottom_operation_layout.addLayout(function_btn_layout)
        main_layout.addLayout(bottom_operation_layout)

        # 初始化显示
        self.update_image_display()
        self.update_user_label()
        self.update_ocr_result_display()

    def _convert_numpy_to_list(self, obj):
        """递归将numpy数组转换为Python列表"""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, list):
            return [self._convert_numpy_to_list(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_numpy_to_list(item) for item in obj)
        elif isinstance(obj, dict):
            return {k: self._convert_numpy_to_list(v) for k, v in obj.items()}
        else:
            return obj

    def on_recognize_clicked(self):
        """识别按钮点击事件"""
        start_time = time.time()

        # 更新状态
        self.ocr_status_label.setText("状态：正在识别...")
        self.ocr_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #ff9900;
                padding: 3px 8px;
                background-color: #fff7e6;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
        """)
        QApplication.processEvents()  # 更新UI

        # 识别整张图片
        if self.current_page - 1 < len(self.image_paths):
            image_path = self.image_paths[self.current_page - 1]
            source_type = "整张图片"
        else:
            InfoBar.warning(
                title="识别失败",
                content="没有找到可识别的图片",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        try:
            # 执行OCR识别
            result = self.ocr.predict(image_path)

            # 转换所有numpy数组为Python列表，避免后续判断歧义
            result = self._convert_numpy_to_list(result)

            # 解析OCR结果（兼容多种返回格式）
            full_ocr_data = []
            recognized_text = ""

            for res in result:

                rec_texts = res.get('rec_texts', [])
                rec_polys = res.get('rec_polys', [])

                # 确保文本和坐标数量匹配
                min_length = min(len(rec_texts), len(rec_polys))

                # 构建完整的OCR数据结构
                for i in range(min_length):
                    text = rec_texts[i]
                    box = rec_polys[i] if i < len(rec_polys) else []

                    # 安全判断：避免numpy数组判断歧义
                    if text and isinstance(box, (list, tuple)) and len(box) >= 4:
                        # 确保每个坐标点都是有效的
                        valid_box = []
                        for point in box[:4]:  # 只取前4个点
                            if isinstance(point, (list, tuple)) and len(point) >= 2:
                                valid_box.append([float(point[0]), float(point[1])])

                        if len(valid_box) == 4:
                            full_ocr_data.append({
                                'box': valid_box,
                                'text': text,
                                'confidence': 1.0  # 兼容原有数据结构，默认置信度
                            })
                            recognized_text += f"{text}\n"

            # 保存完整结果和文本结果
            self.ocr_full_results[self.current_page] = full_ocr_data
            self.ocr_text_results[self.current_page] = recognized_text

            # 计算耗时
            elapsed_time = time.time() - start_time

            # 更新显示
            self.update_ocr_result_display()
            self.ocr_time_label.setText(f"耗时：{elapsed_time:.2f}秒")

            # 更新状态
            self.ocr_status_label.setText("状态：识别完成")
            self.ocr_status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #00cc66;
                    padding: 3px 8px;
                    background-color: #e6ffe6;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 120px;
                }
            """)

            InfoBar.success(
                title="识别成功",
                content=f"已识别{source_type}中的文本，共{len(full_ocr_data)}行",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000
            )

        except Exception as e:
            # 打印详细错误信息便于调试
            import traceback
            print(f"OCR识别错误详情: {traceback.format_exc()}")

            # 更新状态
            self.ocr_status_label.setText("状态：识别失败")
            self.ocr_status_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #ff3333;
                    padding: 3px 8px;
                    background-color: #ffe6e6;
                    border-radius: 4px;
                    font-weight: bold;
                    min-width: 120px;
                }
            """)

            InfoBar.error(
                title="识别失败",
                content=f"OCR识别时发生错误: {str(e)}",
                parent=self,
                position=InfoBarPosition.TOP
            )

    def on_text_line_selected(self, line_number):
        """文本行选中事件处理"""
        if self.current_page in self.ocr_full_results:
            full_data = self.ocr_full_results[self.current_page]
            if 0 <= line_number < len(full_data):
                # 提取所有检测框
                boxes = [item['box'] for item in full_data]
                # 更新图片显示的检测框并选中指定行
                self.image_container.set_ocr_boxes(boxes)
                self.image_container.select_box(line_number)

    def on_text_selection_cleared(self):
        """文本选中取消事件处理"""
        self.image_container.clear_selection()

    def update_ocr_result_display(self):
        """更新OCR结果显示"""
        if self.current_page in self.ocr_text_results and self.current_page in self.ocr_full_results:
            text_result = self.ocr_text_results[self.current_page]
            full_data = self.ocr_full_results[self.current_page]

            # 设置文本和原始数据
            self.ocr_result_text.set_ocr_data(full_data, text_result)

            # 更新图片显示的检测框
            # boxes = [item['box'] for item in full_data]
            # self.image_container.set_ocr_boxes(boxes)

            self.ocr_time_label.setText(self.ocr_time_label.text())  # 保持耗时显示
        else:
            self.ocr_result_text.clear_text()
            self.image_container.set_ocr_boxes([])
            self.ocr_time_label.setText("耗时：--")

    def clear_ocr_results(self):
        """清空当前页的OCR结果"""
        self.ocr_result_text.clear_text()
        self.image_container.set_ocr_boxes([])

        if self.current_page in self.ocr_text_results:
            del self.ocr_text_results[self.current_page]
        if self.current_page in self.ocr_full_results:
            del self.ocr_full_results[self.current_page]

        self.ocr_status_label.setText("状态：等待识别")
        self.ocr_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 3px 8px;
                background-color: #f0f0f0;
                border-radius: 4px;
                min-width: 120px;
            }
        """)

        self.ocr_time_label.setText("耗时：--")

        InfoBar.info(
            title="已清空",
            content="当前页OCR结果已清空",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=1500
        )

    def resizeEvent(self, event):
        """重写窗口大小改变事件"""
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_image_display)

    def update_image_display(self):
        """更新当前页图片显示（优化版本）"""
        if not self.image_paths:
            self.image_container.set_image(QPixmap())
            self.image_container.setText("无可用图片")
            return

        # 加载图片
        image_path = self.image_paths[self.current_page - 1]
        self.image_path_label.setText(os.path.dirname(image_path))

        pixmap = QPixmap(image_path)
        self.current_pixmap = pixmap

        # 设置图片到自定义显示控件
        self.image_container.set_image(pixmap)

        # 更新页码
        self.page_input.blockSignals(True)
        self.page_input.setText(str(self.current_page))
        self.page_input.blockSignals(False)

        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_images)

        # 更新OCR结果显示
        self.update_ocr_result_display()

    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_image_display()
            self.ocr_status_label.setText("状态：等待识别")
            self.ocr_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 3px 8px;
                background-color: #f0f0f0;
                border-radius: 4px;
                min-width: 120px;
            }
            """)

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_images:
            self.current_page += 1
            self.update_image_display()
            self.ocr_status_label.setText("状态：等待识别")
            self.ocr_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 3px 8px;
                background-color: #f0f0f0;
                border-radius: 4px;
                min-width: 120px;
            }
            """)

    def jump_to_page_by_lineedit(self):
        """通过LineEdit输入页码跳转"""
        try:
            page = int(self.page_input.text().strip())
            if 1 <= page <= self.total_images:
                self.current_page = page
                self.update_image_display()
            else:
                InfoBar.warning(
                    title="页码无效",
                    content=f"请输入1-{self.total_images}之间的页码",
                    parent=self,
                    position=InfoBarPosition.TOP
                )
                self.page_input.setText(str(self.current_page))
        except ValueError:
            InfoBar.error(
                title="输入错误",
                content="请输入有效的数字页码",
                parent=self,
                position=InfoBarPosition.TOP
            )
            self.page_input.setText(str(self.current_page))

    def jump_to_page(self, page):
        """兼容旧的跳转方法"""
        self.current_page = page
        self.update_image_display()

    def back_table(self):
        """返回按钮逻辑"""
        self._is_navigation = True
        QTimer.singleShot(100, self.close)

        try:
            # 注释掉避免运行错误，实际使用时取消注释
            # from src.view.dir_recognition.dirTable_window import DirTableWindow
            # dir_table_window = DirTableWindow()
            # dir_table_window.show()
            InfoBar.info(
                title="返回",
                content="将返回列表页面",
                parent=self,
                position=InfoBarPosition.TOP
            )
        except ImportError:
            InfoBar.warning(
                title="提示",
                content="返回窗口模块未找到，将返回登录界面",
                parent=self,
                position=InfoBarPosition.TOP
            )
            self.logout()

    def update_user_label(self):
        """更新右上角用户标签"""
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label.setText(f"当前用户：【{username}】角色: 【{userrole}】")
        else:
            self.user_label.setText("未登录")

    def clean_temp_images(self):
        """清理临时图片文件"""
        try:
            if os.path.exists(TEMP_DIR):
                for filename in os.listdir(TEMP_DIR):
                    file_path = os.path.join(TEMP_DIR, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(TEMP_DIR)
        except Exception as e:
            print(f"清理临时文件时出错: {e}")

    def logout(self):
        """退出登录"""
        global_cache.delete("current_user")
        self.clean_temp_images()
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        """重写关闭事件"""
        # 清理临时文件
        self.clean_temp_images()

        if self._is_navigation:
            event.accept()
            return

        if not self._is_app_exiting:
            box = MessageBox(
                '确认退出',
                '确定要退出应用程序吗？',
                self
            )
            box.yesButton.setText('退出')
            box.cancelButton.setText('取消')

            if box.exec():
                self._is_app_exiting = True
                event.accept()
                self.logout()
                # 注释掉避免运行错误，实际使用时取消注释
                # from src.view.login import LoginWindow
                # self.login_window = LoginWindow()
                # self.login_window.show()
            else:
                event.ignore()
        else:
            event.accept()

    def close_without_confirm(self):
        """不显示确认对话框直接关闭窗口"""
        self._is_navigation = True
        QTimer.singleShot(100, self.close)


if __name__ == '__main__':
    # 创建测试图片目录
    if not os.path.exists("test_images"):
        os.makedirs("test_images")

    # 确保临时文件夹存在
    os.makedirs(TEMP_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    main_window = DirWindow()
    main_window.show()
    app.exec()