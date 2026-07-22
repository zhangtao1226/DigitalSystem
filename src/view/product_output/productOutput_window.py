# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : product_output_window.py
# @Desc      : 成品转换
# @Time      : 2025/11/22
# @Software  : PyCharm

import os
import sys
import json
import multiprocessing
import queue
from datetime import datetime
from PySide6.QtGui import (
    QFont, QPixmap, QIcon, QPainter, QDesktopServices,
    QColor, QPen, QBrush, QPolygonF
)
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QWidget, QSizePolicy, QAbstractItemView, QStyle,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QSplitter, QTextEdit, QStackedWidget, QFileDialog,
    QTreeWidget, QTreeWidgetItem, QGraphicsPolygonItem
)
from PySide6.QtCore import QObject, Qt, QUrl, QRectF, QTimer, Signal, QPointF
from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton,
    PrimaryPushButton, ScrollArea, PrimaryToolButton, FluentIcon,
    FlowLayout, CardWidget, TransparentToolButton, LineEdit
)

from src.utils.LoggerDetector import logger
from qframelesswindow import FramelessWindow
from src.core.cache_manager import global_cache
from src.services.scan_service import scan_service
from src.services.task_service import task_service
from src.services.operation_service import operation_service
from src.services.register_service import register_service
from src.utils.NotificationTool import show_error, show_success, show_warning, show_info
from src.view.common.CommonProgressBar import CommonProgressDialog

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


class ProductOcrWorker(QObject):
    progress_changed = Signal(int, int, str)
    finished = Signal(int, int)
    failed = Signal(str)

    def __init__(self, image_paths, detector=None):
        super().__init__()
        self.image_paths = image_paths
        self.detector = detector

    def run(self):
        try:
            from src.utils.OCRDetector import OCRDetector

            success_count = 0
            failed_count = 0
            total = len(self.image_paths)
            for index, image_path in enumerate(self.image_paths, start=1):
                image_name = os.path.basename(image_path)
                self.progress_changed.emit(index - 1, total, f"正在识别 {index}/{total}: {image_name}")
                try:
                    ocr_path = self._get_ocr_path(image_path)
                    if not ocr_path or not os.path.exists(ocr_path):
                        if self.detector is None:
                            self.detector = OCRDetector()
                        self.detector.detect(image_path, res_save=True)
                        if not os.path.exists(ocr_path):
                            raise RuntimeError("OCR推理完成但未生成结果文件")
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"OCR识别失败: {image_path}; {e}")
                self.progress_changed.emit(index, total, f"已完成 {index}/{total}: {image_name}")
            self.finished.emit(success_count, failed_count)
        except Exception as e:
            logger.error(f"OCR线程执行失败: {e}")
            self.failed.emit(str(e))

    @staticmethod
    def _get_ocr_path(image_path: str) -> str:
        if not image_path:
            return ""
        return os.path.splitext(image_path)[0] + "_res.json"


class ProductDualPdfWorker(QObject):
    progress_changed = Signal(int, int, str)
    finished = Signal(list, int)
    failed = Signal(str)

    def __init__(self, source_folders, pdf_save_path_value, ocr_detector=None):
        super().__init__()
        self.source_folders = source_folders
        self.pdf_save_path_value = pdf_save_path_value
        self.ocr_detector = ocr_detector

    def run(self):
        try:
            from src.utils.DualLayerPDFGenerator import DualLayerPDFGenerator
            from src.utils.OCRDetector import OCRDetector

            self.progress_changed.emit(0, 100, "正在准备OCR和PDF生成任务...")
            pdf_generator = DualLayerPDFGenerator()
            ocr_detector = self.ocr_detector
            success_paths = []
            failed_count = 0
            total_images = sum(len(self._image_files_in_folder(folder)) for folder in self.source_folders)
            progress_total = 100
            ocr_done = 0

            for folder_index, source_folder in enumerate(self.source_folders, start=1):
                image_paths = self._image_files_in_folder(source_folder)
                if not image_paths:
                    continue

                save_dir = self.pdf_save_path_value or source_folder
                os.makedirs(save_dir, exist_ok=True)
                folder_name = os.path.basename(source_folder)
                pdf_path = os.path.join(save_dir, f"{folder_name}.pdf")

                try:
                    if os.path.exists(pdf_path):
                        logger.info(f"PDF已存在，将使用最新 OCR 坐标重新生成: {pdf_path}")

                    raw_results = []
                    for image_index, image_path in enumerate(image_paths, start=1):
                        image_name = os.path.basename(image_path)
                        ocr_progress = int(ocr_done / max(1, total_images) * 90)
                        self.progress_changed.emit(
                            ocr_progress,
                            progress_total,
                            f"正在OCR {folder_index}/{len(self.source_folders)} - {image_index}/{len(image_paths)}: {image_name}",
                        )
                        result, ocr_detector = self._ensure_image_ocr_result(image_path, ocr_detector)
                        self.ocr_detector = ocr_detector
                        raw_results.append(result)
                        ocr_done += 1
                        self.progress_changed.emit(
                            int(ocr_done / max(1, total_images) * 90),
                            progress_total,
                            f"OCR完成 {ocr_done}/{total_images}: {image_name}",
                        )

                    self.progress_changed.emit(
                        95,
                        progress_total,
                        f"正在生成PDF {folder_index}/{len(self.source_folders)}: {folder_name}",
                    )
                    pdf_result = pdf_generator.image_to_pdf(
                        image_paths=image_paths,
                        output_pdf_path=pdf_path,
                        raw_result=raw_results,
                    )
                    pdf_done = bool(pdf_result) or os.path.exists(pdf_path)
                    pdf_progress = int(90 + folder_index / max(1, len(self.source_folders)) * 10)
                    if pdf_done:
                        success_paths.append(pdf_path)
                        self.progress_changed.emit(
                            pdf_progress,
                            progress_total,
                            f"PDF生成完成 {folder_index}/{len(self.source_folders)}: {folder_name}",
                        )
                    else:
                        failed_count += 1
                        self.progress_changed.emit(
                            pdf_progress,
                            progress_total,
                            f"PDF生成失败 {folder_index}/{len(self.source_folders)}: {folder_name}",
                        )
                except Exception as e:
                    if os.path.exists(pdf_path):
                        success_paths.append(pdf_path)
                        self.progress_changed.emit(
                            int(90 + folder_index / max(1, len(self.source_folders)) * 10),
                            progress_total,
                            f"PDF已生成 {folder_index}/{len(self.source_folders)}: {folder_name}",
                        )
                    else:
                        logger.error(f"生成双层PDF失败: {source_folder}; {e}")
                        failed_count += 1
            if success_paths:
                self.progress_changed.emit(100, progress_total, "双层PDF生成完成")
            self.finished.emit(success_paths, failed_count)
        except Exception as e:
            logger.error(f"生成双层PDF线程执行失败: {e}")
            self.failed.emit(str(e))

    def _image_files_in_folder(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return []
        try:
            return [
                os.path.join(folder_path, name)
                for name in sorted(os.listdir(folder_path))
                if os.path.isfile(os.path.join(folder_path, name))
                and os.path.splitext(name)[1].lower() in IMG_EXTENSIONS
            ]
        except PermissionError:
            logger.warning(f"无权限读取文件夹: {folder_path}")
            return []

    @staticmethod
    def _get_ocr_path(image_path: str) -> str:
        if not image_path:
            return ""
        return os.path.splitext(image_path)[0] + "_res.json"

    def _ensure_image_ocr_result(self, image_path, ocr_detector):
        ocr_path = self._get_ocr_path(image_path)
        if ocr_path and os.path.exists(ocr_path):
            try:
                with open(ocr_path, "r", encoding="utf-8") as f:
                    return json.load(f), ocr_detector
            except Exception as e:
                logger.warning(f"OCR结果读取失败, 将重新识别: {ocr_path}; {e}")

        if ocr_detector is None:
            from src.utils.OCRDetector import OCRDetector

            ocr_detector = OCRDetector()
        ocr_detector.detect(image_path, res_save=True)
        if ocr_path and os.path.exists(ocr_path):
            with open(ocr_path, "r", encoding="utf-8") as f:
                return json.load(f), ocr_detector
        raise RuntimeError(f"OCR推理完成但未生成结果文件: {image_path}")


def _run_product_process(command_queue, message_queue):
    """长驻成品处理子进程：OCR 与双层 PDF 共享同一模型实例。"""
    detector = None
    while True:
        command = command_queue.get()
        if command is None:
            break
        task_type = command[0]
        if task_type == "ocr":
            worker = ProductOcrWorker(command[1], detector)
            worker.progress_changed.connect(
                lambda current, total, message: message_queue.put(
                    ("ocr", "progress", current, total, message)
                )
            )
            worker.finished.connect(
                lambda success_count, failed_count: message_queue.put(
                    ("ocr", "finished", success_count, failed_count)
                )
            )
            worker.failed.connect(
                lambda message: message_queue.put(("ocr", "failed", message))
            )
            worker.run()
            detector = worker.detector
        elif task_type == "pdf":
            worker = ProductDualPdfWorker(command[1], command[2], detector)
            worker.progress_changed.connect(
                lambda current, total, message: message_queue.put(
                    ("pdf", "progress", current, total, message)
                )
            )
            worker.finished.connect(
                lambda success_paths, failed_count: message_queue.put(
                    ("pdf", "finished", success_paths, failed_count)
                )
            )
            worker.failed.connect(
                lambda message: message_queue.put(("pdf", "failed", message))
            )
            worker.run()
            detector = worker.ocr_detector


class FlowImageWidget(QWidget):
    def __init__(self, img_path: str, image_width: int = 200, image_height: int = 250, parent=None):
        super().__init__(parent)
        self.img_path = img_path
        self.is_selected = False
        self._is_deleted = False
        self.original_pixmap = None
        self.image_border_width  = image_width  or 200
        self.image_border_height = image_height or 250
        self._init_ui()

    def _init_ui(self):
        self.setFixedSize(self.image_border_width, self.image_border_height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self.img_label = QLabel()
        self.img_label.setFixedSize(self.image_border_width - 5, self.image_border_height - 30)
        self.img_label.setAlignment(Qt.AlignCenter)
        self._load_image()

        self.name_label = QLabel(os.path.basename(self.img_path))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(30)
        self.name_label.setStyleSheet("QLabel { border:0px; color:#333; font-size:11px; padding:2px; }")

        layout.addWidget(self.img_label)
        layout.addWidget(self.name_label)
        self.setCursor(Qt.PointingHandCursor)

    def _load_image(self):
        if os.path.exists(self.img_path):
            px = QPixmap(self.img_path)
            if not px.isNull():
                self.original_pixmap = px
                self._refresh_scaled()
        else:
            self.img_label.setText("图片\n不存在")
            self.img_label.setStyleSheet("""
                QLabel {
                    border:1px solid #e0e0e0; border-radius:4px;
                    background:#f5f5f5; color:#999; font-size:14px;
                }
            """)

    def _refresh_scaled(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(
                self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.img_label.setPixmap(scaled)

    def apply_zoom(self, width: int, height: int):
        self.image_border_width  = width
        self.image_border_height = height
        self.setFixedSize(width, height)
        self.img_label.setFixedSize(width - 5, height - 30)
        self._refresh_scaled()

    def mousePressEvent(self, event):
        if self._is_deleted or not self.isVisible():
            return
        try:
            parent = self.parentWidget()
            while parent:
                if hasattr(parent, 'on_image_selected'):
                    parent.on_image_selected(self, self.img_path)
                    break
                parent = parent.parentWidget()
        except RuntimeError:
            pass

    def set_selected(self, selected: bool):
        if self._is_deleted:
            return
        try:
            self.is_selected = selected
            color = "#0066CC" if selected else "transparent"
            self.img_label.setStyleSheet(f"""
                QLabel {{
                    border:2px solid {color}; border-radius:6px;
                    background:#f5f5f5; padding:5px;
                }}
            """)
        except RuntimeError:
            self._is_deleted = True

    def cleanup(self):
        self._is_deleted = True
        self.img_label = None
        self.name_label = None
        self.original_pixmap = None

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass

class SingleImageViewer(QWidget):
    request_switch = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._annotation_items: list = []
        self._current_image_path: str = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.view  = QGraphicsView(self.scene)
        self.view.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.view.setStyleSheet("""
            QGraphicsView {
                border: none;
                background-color: #e8e8e8;
            }
            QScrollBar:vertical {
                border:none; background:#f0f0f0; width:10px; border-radius:5px;
            }
            QScrollBar::handle:vertical {
                background:#cccccc; border-radius:5px; min-height:30px;
            }
            QScrollBar::handle:vertical:hover { background:#999; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { border:none; background:none; height:0; }
            QScrollBar:horizontal {
                border:none; background:#f0f0f0; height:10px; border-radius:5px;
            }
            QScrollBar::handle:horizontal {
                background:#cccccc; border-radius:5px; min-width:30px;
            }
            QScrollBar::handle:horizontal:hover { background:#999; }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal { border:none; background:none; width:0; }
        """)
        self.view.wheelEvent = self._on_wheel

        self.pixmap_item = QGraphicsPixmapItem()
        self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.pixmap_item)

        self.counter_label = QLabel("", self)
        self.counter_label.setStyleSheet("""
            QLabel {
                background: rgba(0,0,0,0.50);
                color: white;
                border-radius: 10px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        self.counter_label.hide()

        layout.addWidget(self.view)

    def load_image(self, path: str):
        self._current_image_path = path
        self.clear_annotations()
        if not path or not os.path.exists(path):
            self.pixmap_item.setPixmap(QPixmap())
            return
        px = QPixmap(path)
        if not px.isNull():
            self.pixmap_item.setPixmap(px)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap_item.pixmap() and not self.pixmap_item.pixmap().isNull():
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self._reposition_counter()

    def _reposition_counter(self):
        self.counter_label.adjustSize()
        self.counter_label.move(
            self.width()  - self.counter_label.width()  - 12,
            self.height() - self.counter_label.height() - 12)

    def set_counter(self, current: int, total: int):
        self.counter_label.setText(f"  {current} / {total}  ")
        self._reposition_counter()
        self.counter_label.show()
        self.counter_label.raise_()

    def zoom_in(self):
        self.view.scale(1.25, 1.25)

    def zoom_out(self):
        self.view.scale(0.8, 0.8)

    def fit_view(self):
        if self.pixmap_item.pixmap() and not self.pixmap_item.pixmap().isNull():
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def _on_wheel(self, event):
        if event.modifiers() == Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.view.scale(factor, factor)
        else:
            direction = -1 if event.angleDelta().y() > 0 else 1
            self.request_switch.emit(direction)

    def draw_line_box(self, boxes, color: str = "#1565C0"):
        self._remove_items_by_tag("line")
        polygon = self._to_polygon(boxes)
        if polygon is None:
            return

        pen = QPen(QColor(color))
        pen.setWidth(3)
        pen.setCosmetic(True)
        brush = QBrush(QColor(21, 101, 192, 40))

        item = QGraphicsPolygonItem(polygon)
        item.setPen(pen)
        item.setBrush(brush)
        item.setData(0, "line")
        self.scene.addItem(item)
        self._annotation_items.append(item)
        self.view.ensureVisible(item, 80, 80)

    def clear_annotations(self):
        for item in self._annotation_items:
            if item.scene():
                self.scene.removeItem(item)
        self._annotation_items.clear()

    def _remove_items_by_tag(self, tag: str):
        to_rm = [i for i in self._annotation_items if i.data(0) == tag]
        for item in to_rm:
            if item.scene():
                self.scene.removeItem(item)
            self._annotation_items.remove(item)

    @staticmethod
    def _to_polygon(boxes) -> QPolygonF | None:
        try:
            if isinstance(boxes[0], (list, tuple)):
                return QPolygonF([QPointF(float(p[0]), float(p[1])) for p in boxes])
            else:
                x1, y1, x2, y2 = (float(v) for v in boxes[:4])
                return QPolygonF([
                    QPointF(x1, y1), QPointF(x2, y1),
                    QPointF(x2, y2), QPointF(x1, y2),
                ])
        except (IndexError, TypeError, ValueError) as e:
            logger.error(f"坐标解析失败: {e}  boxes={boxes}")
            return None

class InfoDisplayWidget(CardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.setStyleSheet("CardWidget { background-color:#ffffff; border:1px solid #e0e0e0; }")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title_layout = QHBoxLayout()
        title = StrongBodyLabel("内容展示")
        title.setStyleSheet("font-size:18px; font-weight:600; color:#333;")
        self.save_btn = PushButton("保存")
        self.save_btn.setFixedSize(96, 38)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
                    PushButton {
                        background:#5a8ee5; color:white;
                        border-radius:8px; font-size:15px; font-weight:bold;
                    }
                    PushButton:hover { background:#105db7; }
                """)
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        title_layout.addWidget(self.save_btn)

        layout.addLayout(title_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background:#e0e0e0; height:1px;")
        layout.addWidget(sep)

        self.hint_label = QLabel("💡 选中文字可在图片中高亮对应位置(Ctrl + Z 可撤销操作)")
        self.hint_label.setStyleSheet("""
            QLabel {
                font-size:12px; color:#888;
                background:#f0f4ff; border-radius:6px; padding:4px 8px;
            }
        """)
        self.hint_label.hide()
        layout.addWidget(self.hint_label)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(False)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                border:1px solid #e0e0e0; border-radius:6px;
                padding:8px; font-size:14px; background:#f9f9f9;
                line-height:1.8;
                selection-background-color: #bbdefb;
                selection-color: #1565c0;
            }
        """)
        layout.addWidget(self.text_edit)
        self.set_info("未选择图片")

    def set_info(self, text: str):
        self.text_edit.setPlainText(text)
        self.hint_label.setVisible(bool(text.strip()))

    set_image_info = set_info

class ImageDirectoryTree(CardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_folder = None
        self.selected_folder_item    = None
        self.setBorderRadius(8)
        self.setStyleSheet("CardWidget { background-color:#ffffff; border:1px solid #e0e0e0; }")
        self.main_window = parent

        self.current_data = global_cache.get("current_data", None)
        self.current_user = global_cache.get("current_user", None)

        self.task_info = task_service.get_by_id(self.current_data[0])
        print(f"task_info: {self.task_info}")

        scan_where = {
            "register_id": self.task_info.register_id,
            "task_id": 2,
        }
        self.scan_task_info = task_service.get_data(scan_where)
        self.register_info = register_service.get_by_id(self.task_info.register_id)

        task_ids = [scan.id for scan in self.scan_task_info]
        scan_info = scan_service.get_scan_info_taskId(task_ids)
        print(f"scan_info: {scan_info}")

        self.dir_path = scan_info[-1].dir_path

        self.dir_name_list = []
        for scan in scan_info:
            dir_name = scan.dir_name.split("/")
            print(222, dir_name)
            if dir_name[0] not in self.dir_name_list:
                self.dir_name_list.append(dir_name[0])


        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        title = StrongBodyLabel("目录树")
        title.setStyleSheet("font-size:18px; font-weight:600; color:#333; padding:2px 0;")
        row.addWidget(title)
        row.addStretch()
        self.refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setToolTip("刷新目录")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._refresh_tree)
        row.addWidget(self.refresh_btn)
        layout.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background:#e0e0e0; height:1px;")
        layout.addWidget(sep)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background:white; border:1px solid #e0e0e0;
                border-radius:6px; font-size:14px; padding:8px;
            }
            QTreeWidget::item {
                height:36px; padding:6px 10px;
                border-radius:6px; margin:4px 0;
            }
            QTreeWidget::item:selected {
                background-color:#e3f2fd; color:#1565c0;
                font-weight:500; border:1px solid #bbdefb;
            }
            QTreeWidget::item:hover { background-color:#f5f5f5; }
        """)
        self.tree_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_widget.itemClicked.connect(self._on_folder_selected)
        layout.addWidget(self.tree_widget)
        self._load_tree()

    def _refresh_tree(self):
        root = None
        if self.tree_widget.topLevelItemCount() > 0:
            data = self.tree_widget.topLevelItem(0).data(0, Qt.UserRole)
            root = data.get("path") if isinstance(data, dict) else data
        self._load_tree(root)

    def _load_tree(self, root_path=None):
        root_path = root_path or self.dir_path
        if not os.path.exists(root_path):
            root_path = f"{os.getcwd()}/upload_images"

        self.tree_widget.clear()
        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, os.path.basename(root_path))
        root_item.setData(0, Qt.UserRole, {"type": "folder", "path": root_path})
        root_item.setIcon(0, self._folder_icon())
        self._load_subs(root_item, root_path)
        self.tree_widget.expandItem(root_item)
        root_item.setSelected(True)
        self.selected_folder_item    = root_item
        self.current_selected_folder = root_path

    def _load_subs(self, parent_item, path):
        try:
            entries = sorted(os.listdir(path), key=lambda x: x.lower())
            for name in entries:
                fp = os.path.join(path, name)
                if os.path.isdir(fp):
                    if parent_item.parent() is None and name not in self.dir_name_list and name[:-5] not in self.dir_name_list:
                        continue
                    child = QTreeWidgetItem(parent_item)
                    child.setText(0, name)
                    child.setData(0, Qt.UserRole, {"type": "folder", "path": fp})
                    child.setIcon(0, self._folder_icon())
                    self._load_subs(child, fp)
                elif os.path.isfile(fp) and os.path.splitext(name)[1].lower() in IMG_EXTENSIONS:
                    child = QTreeWidgetItem(parent_item)
                    child.setText(0, name)
                    child.setData(0, Qt.UserRole, {"type": "file", "path": fp})
                    child.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
        except PermissionError:
            logger.error(f"Permission Error: {path}")
        except Exception as e:
            logger.error(f"加载目录时出错: {e}")

    def _folder_icon(self) -> QIcon:
        s = self.style()
        return s.standardIcon(QStyle.SP_DirIcon) if s else QIcon()

    def _on_folder_selected(self, item, _col):
        if self.selected_folder_item:
            self.selected_folder_item.setSelected(False)
        self.selected_folder_item = item
        data = item.data(0, Qt.UserRole)
        item_type = data.get("type") if isinstance(data, dict) else "folder"
        fp = data.get("path") if isinstance(data, dict) else data
        self.current_selected_folder = fp
        item.setSelected(True)
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, 'load_images_from_folder'):
                if item_type == "file":
                    parent.load_images_from_folder(os.path.dirname(fp))
                    parent.select_image_by_path(fp)
                else:
                    parent.load_images_from_folder(fp)
                break
            parent = parent.parentWidget()

class ImageGalleryWidget(CardWidget):

    VIEW_GALLERY = 0
    VIEW_SINGLE  = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.setStyleSheet("CardWidget { background-color:#ffffff; border:1px solid #e0e0e0; }")
        self._view_mode = self.VIEW_GALLERY
        self._init_ui()

    def _init_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(15, 15, 15, 15)
        main.setSpacing(12)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.title_label = StrongBodyLabel("图片画廊")
        self.title_label.setStyleSheet(
            "font-size:18px; font-weight:600; color:#333; padding:2px 0;")
        row.addWidget(self.title_label)
        row.addStretch()

        self.single_show_btn = PushButton("单页显示")
        self.single_show_btn.setCursor(Qt.PointingHandCursor)
        self.single_show_btn.setFixedHeight(34)
        self.single_show_btn.setStyleSheet("""
            PushButton {
                background:#afbbea; color:white;
                border-radius:10px; padding:4px 14px; font-size:13px;
            }
            PushButton:hover { background:#8fa0d8; }
        """)

        self.reduce_btn = PrimaryToolButton(FluentIcon.ZOOM_OUT)
        self.reduce_btn.setCursor(Qt.PointingHandCursor)
        self.reduce_btn.setToolTip("缩小（画廊模式缩小缩略图 / 单图模式缩小视图）")

        self.big_btn = PrimaryToolButton(FluentIcon.ZOOM_IN)
        self.big_btn.setCursor(Qt.PointingHandCursor)
        self.big_btn.setToolTip("放大（画廊模式放大缩略图 / 单图模式放大视图）")

        self.fit_btn = PrimaryToolButton(FluentIcon.FULL_SCREEN)
        self.fit_btn.setCursor(Qt.PointingHandCursor)
        self.fit_btn.setToolTip("适应窗口（单图模式）")
        self.fit_btn.hide()

        self.image_count_label = QLabel("共 0 张")
        self.image_count_label.setStyleSheet("""
            QLabel {
                background:#f0f0f0; color:#999; border-radius:12px;
                padding:6px 14px; font-size:13px; font-weight:500;
            }
        """)

        for w in [self.single_show_btn, self.reduce_btn,
                  self.big_btn, self.fit_btn, self.image_count_label]:
            row.addWidget(w)
        main.addLayout(row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background:#e0e0e0; height:1px;")
        main.addWidget(sep)

        self.stacked = QStackedWidget()

        gallery_page = QWidget()
        gp = QVBoxLayout(gallery_page)
        gp.setContentsMargins(0, 0, 0, 0)

        self.scroll_container = QWidget()
        self.scroll_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.flow_layout = FlowLayout(self.scroll_container)
        self.flow_layout.setSpacing(20)
        self.flow_layout.setContentsMargins(10, 10, 10, 10)
        self.flow_layout.setHorizontalSpacing(25)
        self.flow_layout.setVerticalSpacing(25)

        self.gallery_scroll = ScrollArea()
        self.gallery_scroll.setWidget(self.scroll_container)
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("""
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical {
                border:none; background:#f0f0f0; width:10px; border-radius:5px;
            }
            QScrollBar::handle:vertical {
                background:#cccccc; border-radius:5px; min-height:30px;
            }
            QScrollBar::handle:vertical:hover { background:#999; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { border:none; background:none; height:0; }
            QScrollBar:horizontal {
                border:none; background:#f0f0f0; height:10px; border-radius:5px;
            }
            QScrollBar::handle:horizontal {
                background:#cccccc; border-radius:5px; min-width:30px;
            }
            QScrollBar::handle:horizontal:hover { background:#999; }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal { border:none; background:none; width:0; }
        """)
        gp.addWidget(self.gallery_scroll)

        self.single_viewer = SingleImageViewer()

        self.stacked.addWidget(gallery_page)
        self.stacked.addWidget(self.single_viewer)
        main.addWidget(self.stacked, stretch=1)

    def switch_to_gallery(self):
        self._view_mode = self.VIEW_GALLERY
        self.stacked.setCurrentIndex(self.VIEW_GALLERY)
        self.single_show_btn.setText("单页显示")
        self.title_label.setText("图片画廊")
        self.fit_btn.hide()

    def switch_to_single(self, image_path: str = ""):
        self._view_mode = self.VIEW_SINGLE
        if image_path:
            self.single_viewer.load_image(image_path)
        self.stacked.setCurrentIndex(self.VIEW_SINGLE)
        self.single_show_btn.setText("画廊模式")
        self.title_label.setText("单图预览  （滚轮切换 · Ctrl+滚轮缩放）")
        self.fit_btn.show()

    @property
    def is_single_view(self) -> bool:
        return self._view_mode == self.VIEW_SINGLE

    def clear_gallery(self):
        self._safe_del_widgets()
        self.update_image_count(0)

    def _safe_del_widgets(self):
        to_del = []
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            if item and item.widget():
                to_del.append(item.widget())
        for w in to_del:
            try:
                if hasattr(w, 'cleanup'):
                    w.cleanup()
                w.hide()
                self.flow_layout.removeWidget(w)
                w.deleteLater()
            except RuntimeError:
                pass
        self.flow_layout.update()

    def apply_gallery_zoom(self, width: int, height: int):
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            if item and isinstance(item.widget(), FlowImageWidget):
                item.widget().apply_zoom(width, height)
        self.flow_layout.update()
        self.scroll_container.updateGeometry()

    def update_image_count(self, count: int):
        self.image_count_label.setText(f"共 {count} 张")
        color = "#2e7d32" if count > 0 else "#999"
        bg    = "#e8f5e9" if count > 0 else "#f0f0f0"
        self.image_count_label.setStyleSheet(f"""
            QLabel {{
                background:{bg}; color:{color};
                border-radius:12px; padding:6px 14px;
                font-size:13px; font-weight:500;
            }}
        """)

    def draw_line_box(self, boxes, color="#1565C0"):
        self.single_viewer.draw_line_box(boxes, color)

    def clear_annotations(self):
        self.single_viewer.clear_annotations()

class ProductOutputWindow(FramelessWindow):

    THUMB_MIN_W = 100
    THUMB_MIN_H = 130
    THUMB_MAX_W = 600
    THUMB_MAX_H = 700
    THUMB_STEP  = 30

    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)

        self._is_navigation  = False
        self._is_app_exiting = False
        self.selected_image_widget = None
        self.total_images    = 0

        self._image_paths:   list = []
        self._current_index: int  = -1

        self.current_user  = global_cache.get("current_user", None)
        self.current_data  = global_cache.get("current_data", None)

        self.task_info = task_service.get_by_id(self.current_data[0])
        print(f"task_info: {self.task_info}")

        scan_task_where = {
            "register_id": self.task_info.register_id,
            "task_id": 2,
        }
        self.scan_task_info = task_service.get_data(scan_task_where)
        self.register_info = register_service.get_by_id(self.task_info.register_id)

        where = {
            "register_id": self.task_info.register_id,
            "task_id": self.scan_task_info[0].id
        }
        scan_info = scan_service.get_scan_info(where)
        print(f"scan_info: {scan_info}")

        self.current_pdf_path      = None
        self.current_selected_path = None
        self.current_dir_path      = None
        self.current_selected_image = None
        self.pdf_save_path_value = None
        self._progress_dialog = None
        self._ocr_thread = None
        self._ocr_worker = None
        self._pdf_thread = None
        self._pdf_worker = None
        self._product_process = None
        self._product_command_queue = None
        self._product_message_queue = None
        self._active_product_task = None
        self._product_poll_timer = QTimer(self)
        self._product_poll_timer.setInterval(100)
        self._product_poll_timer.timeout.connect(self._poll_product_process)
        self.image_width  = 200
        self.image_height = 250

        self._annotation_timer = QTimer(self)
        self._annotation_timer.setSingleShot(True)
        self._annotation_timer.timeout.connect(self._do_annotation)

        self.ocr_detector = None

        self._init_ui()

    def center(self):
        geo = QApplication.primaryScreen().availableGeometry()
        fg  = self.frameGeometry()
        fg.moveCenter(geo.center())
        self.move(fg.topLeft())

    def _init_ui(self):
        self.setStyleSheet("FramelessWindow { background-color:#f5f5f7; }")
        main = QVBoxLayout(self)
        main.setSpacing(12)
        main.setContentsMargins(10, 30, 10, 10)
        self.setLayout(main)

        main.addWidget(self._build_top_bar())
        main.addWidget(self._build_btn_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet("""
            QSplitter::handle { background:#e0e0e0; border-radius:1px; }
            QSplitter::handle:hover { background:#bdbdbd; }
        """)
        splitter.setChildrenCollapsible(False)

        self.directory_tree = ImageDirectoryTree(self)
        splitter.addWidget(self.directory_tree)

        self.gallery_widget = ImageGalleryWidget()
        splitter.addWidget(self.gallery_widget)

        self.info_widget = InfoDisplayWidget()
        splitter.addWidget(self.info_widget)
        self.info_widget.save_btn.clicked.connect(self.save_new_content)

        splitter.setSizes([300, 780, 480])
        main.addWidget(splitter, stretch=1)

        self.gallery_widget.single_show_btn.clicked.connect(self._toggle_view)
        self.gallery_widget.big_btn.clicked.connect(self.image_to_big)
        self.gallery_widget.reduce_btn.clicked.connect(self.image_to_reduce)
        self.gallery_widget.fit_btn.clicked.connect(
            self.gallery_widget.single_viewer.fit_view)

        self.gallery_widget.single_viewer.request_switch.connect(
            self._switch_image_by_delta)

        self.info_widget.text_edit.selectionChanged.connect(
            lambda: self._annotation_timer.start(150))

        self._check_task_status()

    def _check_task_status(self):
        self.can_do_task = None
        _, complete_number_list = self._get_pre_node_complete_numbers("分 件")

        # 分件未提交完成段时，使用目录录入/校对的完成段。
        if not complete_number_list:
            _, complete_number_list = self._get_pre_node_complete_numbers("目录录入/校对")

        if not complete_number_list:
            if self.task_info.is_ready:
                self.can_do_task = f"{self.task_info.task_number_start}-{self.task_info.task_number_end}"
            else:
                show_warning(self, "警告", "前置任务尚未完成，请等待", 5000)
            return

        logger.info(f"上一个节点已完成了:{len(complete_number_list)};  {complete_number_list};")

        all_nums = []
        for item in complete_number_list:
            s, e = item.split('-')
            all_nums.extend([int(s), int(e)])

        base_min, base_max = min(all_nums), max(all_nums)

        t_start, t_end = map(int, (self.task_info.task_number_start, self.task_info.task_number_end))

        if t_start <= base_min and t_end >= base_max:
            self.can_do_task = f"{str(base_min).zfill(4)}-{str(base_max).zfill(4)}"
        elif t_start >= base_min and t_end <= base_max:
            self.can_do_task = f"{self.task_info.task_number_start}-{self.task_info.task_number_end}"
        else:
            show_warning(self, "警告", "当前没有可以执行任务", 5000)

    def _get_pre_node_complete_numbers(self, task_name: str):
        where = {
            "register_id": self.task_info.register_id,
            "task_name": task_name,
            "batch_number": self.task_info.batch_number,
        }
        pre_node_tasks = task_service.get_data(where)
        complete_number_list = []

        for task in pre_node_tasks:
            logger.info(f"{task_name} complete_number: {task.complete_number}")
            if task.complete_number and "-" in task.complete_number:
                complete_number_list.append(task.complete_number)

        return bool(pre_node_tasks), complete_number_list

    def _build_top_bar(self) -> CardWidget:
        bar = CardWidget()
        bar.setBorderRadius(8)
        bar.setFixedHeight(65)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(30)

        def mk_box(*widgets):
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(8)
            for item in widgets:
                if item == "stretch":
                    l.addStretch()
                else:
                    l.addWidget(item)
            return w

        self.number_value_label = self._mk_val("B000001", 120)
        self.number_nuit_label  = self._mk_val("卷", 40)
        layout.addWidget(mk_box(self._mk_lbl("批次号:"),
                                self.number_value_label,
                                self.number_nuit_label, "stretch"))

        self.task_number_start_label = self._mk_val("0001", 60)
        self.task_number_end_label   = self._mk_val("0010", 60)
        layout.addWidget(mk_box(self._mk_lbl("任务号段:"),
                                self.task_number_start_label,
                                self._mk_lbl("——"),
                                self.task_number_end_label, "stretch"))

        path_box = QWidget()
        path_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        pl = QHBoxLayout(path_box)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(8)
        pl.addWidget(self._mk_lbl("文件路径:"))
        self.image_path_label = QLabel("")
        self.image_path_label.setFont(QFont("Arial", 12))
        self.image_path_label.setStyleSheet("color:#555; font-size:13px;")
        pl.addWidget(self.image_path_label, stretch=1)
        layout.addWidget(path_box, stretch=2)

        self.update_user_label()
        self.user_label.setStyleSheet("""
            QLabel {
                background:#e6f3ff; border-radius:12px;
                padding:8px 16px; font-size:14px;
                color:#0066cc; font-weight:bold;
            }
        """)
        self.user_label.setFixedHeight(40)
        layout.addWidget(self.user_label)
        return bar

    def _mk_lbl(self, t: str) -> QLabel:
        l = QLabel(t)
        l.setStyleSheet("font-size:15px; font-weight:bold; color:#333;")
        return l

    def _mk_val(self, t: str, w: int = 80) -> QLabel:
        l = QLabel(t)
        l.setFixedSize(w, 40)
        l.setStyleSheet("""
            QLabel {
                border-radius:4px; font-size:15px; padding:2px 6px;
                background:white; color:#333; border:none;
            }
        """)
        return l

    def _build_btn_bar(self) -> CardWidget:
        bar = CardWidget()
        bar.setBorderRadius(8)
        bar.setFixedHeight(72)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        defs = [
            ("ocr_batch_btn",   "OCR识别",     "#e3f2fd","#1565c0","#bbdefb", self.ocr_batch_fun),
            ("dual_pdf_btn",    "生成双层PDF", "#e3f2fd","#1565c0","#bbdefb", self.dual_pdf_fun),
            # ("product_out_btn", "成品一键转换","#f3e5f5","#7b1fa2","#e1bee7", self.product_out_fun),
            ("check_path",      "查看PDF",     "#f3e5f5","#7b1fa2","#e1bee7", self.check_path_fun),
            ("open_dir",      "打开文件文件夹",     "#f3e5f5","#7b1fa2","#e1bee7", self.open_dir_fun),
            ("select_save_path", "选择PDF保存路径", "#f3e5f5","#7b1fa2","#e1bee7", self.select_save_path_fun)
        ]
        for attr, text, bg, fg, hbg, slot in defs:
            btn = PushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(130, 38)
            btn.setStyleSheet(f"""
                PushButton {{
                    background:{bg}; color:{fg}; border:1px solid {hbg};
                    border-radius:8px; font-size:14px; font-weight:500;
                }}
                PushButton:hover {{ background:{hbg}; }}
            """)
            btn.clicked.connect(slot)
            setattr(self, attr, btn)
            layout.addWidget(btn)

        self.pdf_save_path = LineEdit()
        self.pdf_save_path.setPlaceholderText("PDF 保存路径")
        self.pdf_save_path.setEnabled(False)
        self.pdf_save_path.setMinimumWidth(260)
        self.pdf_save_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pdf_save_path.setStyleSheet("""
            LineEdit {
                font-size:14px;
                border-radius:4px;
                padding:8px 16px;
                font-weight:bold;
            }
        """)

        self.back_btn = PushButton("返回")
        self.back_btn.setFixedSize(96, 38)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setStyleSheet("""
            PushButton {
                background:#95a5a6; color:white;
                border-radius:8px; font-size:15px; font-weight:bold;
            }
            PushButton:hover { background:#7f8c8d; }
        """)
        self.back_btn.clicked.connect(self.back_table)

        self.submit_btn = PrimaryPushButton("提交")
        self.submit_btn.setFixedSize(96, 38)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.setStyleSheet("""
            PrimaryPushButton {
                background:#27ae60; color:white;
                border-radius:8px; font-size:15px; font-weight:bold;
            }
            PrimaryPushButton:hover { background:#219653; }
        """)
        self.submit_btn.clicked.connect(self.submit_fun)

        layout.addWidget(self.pdf_save_path)
        layout.addStretch()

        layout.addWidget(self.back_btn)
        layout.addWidget(self.submit_btn)
        return bar

    def _toggle_view(self):
        if self.gallery_widget.is_single_view:
            self.gallery_widget.switch_to_gallery()
        else:
            path = self.current_selected_path
            if not os.path.isfile(path) and self._image_paths:
                idx  = max(0, self._current_index)
                path = self._image_paths[idx]
            self.gallery_widget.switch_to_single(path)
            self._refresh_counter()

    def _switch_image_by_delta(self, delta: int):
        if not self._image_paths or not self.gallery_widget.is_single_view:
            return

        new_idx = self._current_index + delta
        if new_idx < 0 or new_idx >= len(self._image_paths):
            return

        self._current_index = new_idx
        new_path = self._image_paths[new_idx]

        self.gallery_widget.single_viewer.load_image(new_path)
        self._refresh_counter()

        self.current_selected_path = new_path
        self.image_path_label.setText(new_path)

        self._sync_gallery_selection(new_path)

        self._load_ocr_to_info(new_path)

        self.gallery_widget.clear_annotations()

    def _refresh_counter(self):
        if self._image_paths and self._current_index >= 0:
            self.gallery_widget.single_viewer.set_counter(
                self._current_index + 1, len(self._image_paths))

    def _sync_gallery_selection(self, target: str):
        for i in range(self.gallery_widget.flow_layout.count()):
            item = self.gallery_widget.flow_layout.itemAt(i)
            if item and isinstance(item.widget(), FlowImageWidget):
                w = item.widget()
                is_t = (w.img_path == target)
                w.set_selected(is_t)
                if is_t:
                    self.selected_image_widget = w
                    self.gallery_widget.gallery_scroll.ensureWidgetVisible(w)

    def _do_annotation(self):
        selected = self.info_widget.text_edit.textCursor().selectedText().strip()
        if not selected or not os.path.isfile(self.current_selected_path):
            self.gallery_widget.clear_annotations()
            return

        ocr_path = self._get_ocr_path(self.current_selected_path)
        if not ocr_path or not os.path.exists(ocr_path):
            return

        try:
            with open(ocr_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            logger.error(f"读取 OCR 文件失败: {e}")
            return

        rec_texts     = content.get('rec_texts',     [])
        rec_boxes     = content.get('rec_boxes',     [])

        line_idx = None
        for i, t in enumerate(rec_texts):
            if t.strip() == selected:
                line_idx = i
                break
        if line_idx is None:
            for i, t in enumerate(rec_texts):
                if selected in t:
                    line_idx = i
                    break
        if line_idx is None:
            self.gallery_widget.clear_annotations()
            return

        if not self.gallery_widget.is_single_view:
            self.gallery_widget.switch_to_single(self.current_selected_path)
            self._refresh_counter()
        elif (self.gallery_widget.single_viewer._current_image_path
              != self.current_selected_path):
            self.gallery_widget.single_viewer.load_image(self.current_selected_path)

        if line_idx < len(rec_boxes):
            self.gallery_widget.draw_line_box(rec_boxes[line_idx], "#1565C0")

    @staticmethod
    def _extract_char_boxes(word_info: list, full_line: str, selected: str) -> list:
        if not word_info:
            return []

        chars = list(full_line)
        boxes = word_info

        if len(chars) != len(boxes):
            length = min(len(chars), len(boxes))
            chars  = chars[:length]
            boxes  = boxes[:length]

        start = full_line.find(selected)
        if start == -1:
            return []
        end = start + len(selected)

        return [boxes[i] for i in range(start, min(end, len(boxes)))]

    def image_to_big(self):
        if self.gallery_widget.is_single_view:
            self.gallery_widget.single_viewer.zoom_in()
        else:
            nw = self.image_width  + self.THUMB_STEP
            nh = self.image_height + self.THUMB_STEP
            if nw > self.THUMB_MAX_W:
                show_warning(self, "提示", "缩略图已放大到最大")
                return
            self.image_width, self.image_height = nw, nh
            self.gallery_widget.apply_gallery_zoom(nw, nh)

    def image_to_reduce(self):
        if self.gallery_widget.is_single_view:
            self.gallery_widget.single_viewer.zoom_out()
        else:
            nw = self.image_width  - self.THUMB_STEP
            nh = self.image_height - self.THUMB_STEP
            if nw < self.THUMB_MIN_W:
                show_warning(self, "提示", "缩略图已缩小到最小")
                return
            self.image_width, self.image_height = nw, nh
            self.gallery_widget.apply_gallery_zoom(nw, nh)

    def load_images_from_folder(self, folder_path: str, width: int = None, height: int = None):
        if not os.path.exists(folder_path):
            show_warning(self, "提示", f"文件夹不存在: {folder_path}")
            return

        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        paths = sorted([
            os.path.join(root, f)
            for root, _, files in os.walk(folder_path)
            for f in files
            if os.path.splitext(f)[1].lower() in exts
        ])

        self._image_paths   = paths
        self._current_index = 0 if paths else -1
        self.total_images   = len(paths)

        self.gallery_widget.switch_to_gallery()
        self.gallery_widget.clear_gallery()

        w = width  or self.image_width
        h = height or self.image_height

        for img_path in paths:
            widget = FlowImageWidget(
                img_path=img_path, image_width=w, image_height=h,
                parent=self.gallery_widget.scroll_container)
            self.gallery_widget.flow_layout.addWidget(widget)

        self.gallery_widget.update_image_count(self.total_images)
        self.image_path_label.setText(paths[0] if paths else folder_path)
        self.info_widget.set_image_info("")
        self.current_selected_path = paths[0] if paths else folder_path
        self.current_dir_path = folder_path
        self.current_selected_image = None

        if paths:
            self.gallery_widget.single_viewer.load_image(paths[0])

        show_info(self, "加载完成", f"已加载 {self.total_images} 张图片")

    def on_image_selected(self, image_widget, img_path: str = None):
        actual = img_path or (
            image_widget.img_path
            if image_widget and hasattr(image_widget, 'img_path') else None)
        if not actual:
            return

        if self.selected_image_widget:
            try:
                self.selected_image_widget.set_selected(False)
            except RuntimeError:
                self.selected_image_widget = None

        self.selected_image_widget = image_widget
        try:
            image_widget.set_selected(True)
        except RuntimeError:
            self.selected_image_widget = None

        self.image_path_label.setText(actual)
        self.current_selected_path = actual
        self.current_selected_image = actual

        if actual in self._image_paths:
            self._current_index = self._image_paths.index(actual)

        self.gallery_widget.single_viewer.load_image(actual)
        if self.gallery_widget.is_single_view:
            self._refresh_counter()

        self._load_ocr_to_info(actual)
        self.gallery_widget.clear_annotations()

    def select_image_by_path(self, img_path: str):
        for i in range(self.gallery_widget.flow_layout.count()):
            item = self.gallery_widget.flow_layout.itemAt(i)
            widget = item.widget() if item else None
            if widget and getattr(widget, "img_path", None) == img_path:
                self.on_image_selected(widget, img_path)
                return
        self.current_selected_path = img_path
        self.current_selected_image = img_path
        self.image_path_label.setText(img_path)
        self.gallery_widget.single_viewer.load_image(img_path)
        self._load_ocr_to_info(img_path)

    def _load_ocr_to_info(self, image_path: str):
        ocr_path = self._get_ocr_path(image_path)
        if ocr_path and os.path.exists(ocr_path):
            try:
                with open(ocr_path, 'r', encoding='utf-8') as f:
                    text = "\n".join(json.load(f).get('rec_texts', []))
                self.info_widget.set_image_info(text)
                return
            except Exception as e:
                logger.error(f"读取 OCR 失败: {e}")
        self.info_widget.set_image_info("")

    def submit_fun(self):
        if self.task_info.is_do:
            show_warning(self, "警告", "该批次成品转换/输出任务已提交，不可重复提交!")
            return

        box = MessageBox(
            "确认提交",
            f"确定要提交成品转换/输出吗？",
            self
        )
        box.yesButton.setText('提交')
        box.cancelButton.setText('取消')

        if box.exec():
            result = task_service.execute_task_submission(self.task_info.id, self.can_do_task.split('-')[1])
            update = {
                "complete_number": self.can_do_task,
            }
            task_service.update(self.task_info.id, update)

            if result['status'] == "success":
                show_success(self, "提交成功", "该批次成品转换/输出任务已提交")
                operation_data = {
                    "task_id": self.task_info.register_id,
                    "task_name": "成品转换/输出",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"成品转换/输出提交"
                }
                operation_service.save_data([operation_data])
            else:
                logger.error(f"成品转换/输出提交报错; {result['message']}")
                show_error(self, "错误", f"{result['message']}")

    def save_new_content(self):
        if not os.path.isfile(self.current_selected_path):
            show_warning(self, "提示", "请先选择一张图片")
            return
        ocr_path = self._get_ocr_path(self.current_selected_path)
        if not ocr_path or not os.path.exists(ocr_path):
            show_warning(self, "提示", "未找到对应 OCR 结果文件")
            return
        try:
            new_lines = self.info_widget.text_edit.toPlainText().split('\n')
            with open(ocr_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            old = content.get('rec_texts', [])
            if len(new_lines) != len(old):
                show_warning(
                    self,
                    "提示",
                    f"OCR 行数不能改变（原 {len(old)} 行，现 {len(new_lines)} 行），"
                    "否则文本会与坐标框错位。",
                )
                return
            content['rec_texts'] = new_lines
            with open(ocr_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            show_success(self, "保存成功", "OCR 文本已更新")
        except Exception as e:
            logger.error(f"保存失败: {e}")
            show_error(self, "保存失败", str(e))

    def ocr_batch_fun(self):
        image_paths = self._selected_image_paths()
        if not image_paths:
            show_warning(self, "警告", "请先选择包含扫描图片的文件或文件夹")
            return

        progress_dialog = self._create_progress_dialog(
            "OCR识别进度",
            f"准备识别 {len(image_paths)} 张图片...",
            len(image_paths),
        )
        self.ocr_batch_btn.setEnabled(False)
        self._ensure_product_process()
        self._active_product_task = "ocr"
        self._product_command_queue.put(("ocr", image_paths))
        self._product_poll_timer.start()

    def dual_pdf_fun(self):
        selected_path = self._selected_output_path()
        source_folders = self._collect_pdf_source_folders(selected_path)
        if not source_folders:
            show_warning(self, "警告", f"该目录下没有扫描件: {selected_path}")
            return

        if self.pdf_save_path_value is None:
            box = MessageBox(
                "提示",
                "未选择 PDF 保存路径，生成的双层 PDF 将保存到当前扫描文件所在文件夹。\n是否继续生成？",
                self,
            )
            box.yesButton.setText("继续")
            box.cancelButton.setText("取消")
            if not box.exec():
                return

        total_images = sum(len(self._image_files_in_folder(folder)) for folder in source_folders)
        progress_dialog = self._create_progress_dialog(
            "生成双层PDF进度",
            f"准备生成 {len(source_folders)} 个PDF...",
            max(1, total_images + len(source_folders)),
        )
        self.dual_pdf_btn.setEnabled(False)
        self._ensure_product_process()
        self._active_product_task = "pdf"
        self._product_command_queue.put(
            ("pdf", source_folders, self.pdf_save_path_value)
        )
        self._product_poll_timer.start()

    def check_path_fun(self):
        if self.current_pdf_path and os.path.exists(self.current_pdf_path):
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_pdf_path)):
                show_error(self, "打开失败", "请检查文件路径是否存在")
        else:
            show_warning(self, "提示", "尚未生成 PDF，请先执行「生成双层 PDF」")

    def open_dir_fun(self):
        target_dir = self.pdf_save_path_value
        if not target_dir and self.current_pdf_path:
            target_dir = os.path.dirname(self.current_pdf_path)
        if not target_dir:
            target_dir = self.current_dir_path

        if target_dir and os.path.isdir(target_dir):
            url = QUrl.fromLocalFile(target_dir)
            if QDesktopServices.openUrl(url):
                show_info(self, "提示", f"已打开: {target_dir}", 1000)
            else:
                show_error(self, "报错", f"无法打开：{target_dir}")
        else:
            show_error(self, "错误", f"该文件夹： {target_dir} 路径不存在！")
            return

    def select_save_path_fun(self):
        try:
            path = QFileDialog.getExistingDirectory(self, "选择 PDF 保存路径")
            if path:
                self.pdf_save_path.setText(f"【PDF】 保存路径: {path}")
                self.pdf_save_path_value = path
        except Exception as e:
            logger.error(f"PDF 保存路径设置报错: {str(e)}")

    @staticmethod
    def _get_ocr_path(image_path: str) -> str:
        if not image_path:
            return ""
        return os.path.splitext(image_path)[0] + '_res.json'

    def _selected_output_path(self):
        if self.current_selected_image and os.path.isfile(self.current_selected_image):
            return os.path.dirname(self.current_selected_image)
        if self.current_selected_path and os.path.isfile(self.current_selected_path):
            return os.path.dirname(self.current_selected_path)
        return self.current_dir_path or self.current_selected_path

    def _image_files_in_folder(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return []
        try:
            return [
                os.path.join(folder_path, name)
                for name in sorted(os.listdir(folder_path))
                if os.path.isfile(os.path.join(folder_path, name))
                and os.path.splitext(name)[1].lower() in IMG_EXTENSIONS
            ]
        except PermissionError:
            logger.warning(f"无权限读取文件夹: {folder_path}")
            return []

    def _collect_pdf_source_folders(self, selected_path):
        if not selected_path:
            return []
        if os.path.isfile(selected_path):
            selected_path = os.path.dirname(selected_path)
        if not os.path.isdir(selected_path):
            return []

        source_folders = []
        for root, dirs, files in os.walk(selected_path):
            dirs.sort()
            if any(os.path.splitext(name)[1].lower() in IMG_EXTENSIONS for name in files):
                source_folders.append(root)
        return source_folders

    def _selected_image_paths(self):
        if self.current_selected_image and os.path.isfile(self.current_selected_image):
            return [self.current_selected_image]
        selected_path = self._selected_output_path()
        image_paths = []
        for source_folder in self._collect_pdf_source_folders(selected_path):
            image_paths.extend(self._image_files_in_folder(source_folder))
        return image_paths

    def _create_progress_dialog(self, title, message, total):
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        progress_dialog = CommonProgressDialog(title=title, message=message, show_cancel=False, parent=self)
        progress_dialog.set_progress(0, max(1, total), message)
        progress_dialog.show()
        progress_dialog.raise_()
        progress_dialog.activateWindow()
        progress_dialog.repaint()
        QApplication.processEvents()
        self._progress_dialog = progress_dialog
        return progress_dialog

    def _update_progress(self, progress_dialog, current, total, message):
        if progress_dialog:
            progress_dialog.set_progress(current, max(1, total), message)

    def _poll_product_process(self):
        terminal_message = False
        if self._product_message_queue is not None:
            while True:
                try:
                    message = self._product_message_queue.get_nowait()
                except queue.Empty:
                    break

                task_type, message_type = message[:2]
                if message_type == "progress":
                    self._update_progress(self._progress_dialog, *message[2:])
                elif task_type == "ocr" and message_type == "finished":
                    terminal_message = True
                    self._on_ocr_finished(self._progress_dialog, *message[2:])
                elif task_type == "ocr" and message_type == "failed":
                    terminal_message = True
                    self._on_ocr_failed(self._progress_dialog, message[2])
                elif task_type == "pdf" and message_type == "finished":
                    terminal_message = True
                    self._on_dual_pdf_finished(self._progress_dialog, *message[2:])
                elif task_type == "pdf" and message_type == "failed":
                    terminal_message = True
                    self._on_dual_pdf_failed(self._progress_dialog, message[2])

        if terminal_message:
            self._product_poll_timer.stop()
            self._active_product_task = None
        elif self._product_process is not None and not self._product_process.is_alive():
            exit_code = self._product_process.exitcode
            message = f"OCR服务子进程异常退出，退出码: {exit_code}"
            if self._active_product_task == "pdf":
                self._on_dual_pdf_failed(self._progress_dialog, message)
            else:
                self._on_ocr_failed(self._progress_dialog, message)
            self._shutdown_product_process()

    def _ensure_product_process(self):
        if self._product_process is not None and self._product_process.is_alive():
            return
        self._shutdown_product_process()
        context = multiprocessing.get_context("spawn")
        self._product_command_queue = context.Queue()
        self._product_message_queue = context.Queue()
        self._product_process = context.Process(
            target=_run_product_process,
            args=(self._product_command_queue, self._product_message_queue),
            daemon=True,
        )
        self._product_process.start()

    def _shutdown_product_process(self):
        self._product_poll_timer.stop()
        if self._product_process is not None:
            if (
                self._product_process.is_alive()
                and self._product_command_queue is not None
            ):
                self._product_command_queue.put(None)
                self._product_process.join(timeout=1.0)
            if self._product_process.is_alive():
                self._product_process.terminate()
                self._product_process.join(timeout=1.0)
        if self._product_command_queue is not None:
            self._product_command_queue.close()
        if self._product_message_queue is not None:
            self._product_message_queue.close()
        self._product_process = None
        self._product_command_queue = None
        self._product_message_queue = None
        self._active_product_task = None

    def _close_progress(self, progress_dialog, message="处理完成"):
        if progress_dialog:
            progress_dialog.finish(message)
            QTimer.singleShot(800, progress_dialog.close)
            if self._progress_dialog is progress_dialog:
                QTimer.singleShot(800, lambda: setattr(self, "_progress_dialog", None))

    def _on_ocr_finished(self, progress_dialog, success_count, failed_count):
        self._close_progress(progress_dialog, "OCR识别完成")
        self.ocr_batch_btn.setEnabled(True)
        if self.current_selected_image:
            self._load_ocr_to_info(self.current_selected_image)
        if success_count:
            show_success(
                self,
                "OCR识别完成",
                f"成功 {success_count} 张" + (f"，失败 {failed_count} 张" if failed_count else ""),
            )
        else:
            show_error(self, "OCR识别失败", "未成功识别任何图片")

    def _on_ocr_failed(self, progress_dialog, message):
        self._close_progress(progress_dialog, "OCR识别失败")
        self.ocr_batch_btn.setEnabled(True)
        show_error(self, "OCR识别失败", message)

    def _clear_ocr_worker_refs(self):
        self._ocr_worker = None
        self._ocr_thread = None

    def _on_dual_pdf_finished(self, progress_dialog, success_paths, failed_count):
        if progress_dialog:
            progress_dialog.set_progress(100, 100, "双层PDF生成完成")
        self._close_progress(progress_dialog, "双层PDF生成完成")
        self.dual_pdf_btn.setEnabled(True)
        if success_paths:
            self.current_pdf_path = success_paths[0] if self.pdf_save_path_value else success_paths[-1]
            show_success(
                self,
                "双层PDF生成完成",
                f"成功生成 {len(success_paths)} 个PDF" + (f"，失败 {failed_count} 个" if failed_count else ""),
            )
        else:
            show_error(self, "报错", "生成双层PDF失败")

    def _on_dual_pdf_failed(self, progress_dialog, message):
        self._close_progress(progress_dialog, "双层PDF生成失败")
        self.dual_pdf_btn.setEnabled(True)
        show_error(self, "报错", f"生成双层PDF失败: {message}")

    def _clear_pdf_worker_refs(self):
        self._pdf_worker = None
        self._pdf_thread = None

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.product_output.productTable_window import ProductTableWindow
            ProductTableWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user = global_cache.get("current_user")
        if user:
            self.user_label = QLabel(
                f"👤 {user.get('username','未知')} ({user.get('role','未知')})")
        else:
            self.user_label = QLabel("未登录")
            global_cache.set("current_user", {"username": "admin", "role": "管理员"})
            self.update_user_label()

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        if self._is_navigation:
            self._shutdown_background_processes()
            event.accept()
            return
        if not self._is_app_exiting:
            box = MessageBox('确认退出', '确定要退出应用程序吗？', self)
            box.yesButton.setText('退出')
            box.cancelButton.setText('取消')
            if box.exec():
                self._is_app_exiting = True
                self._shutdown_background_processes()
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
        self._shutdown_background_processes()
        QTimer.singleShot(100, self.close)

    def _shutdown_background_processes(self):
        self._shutdown_product_process()
