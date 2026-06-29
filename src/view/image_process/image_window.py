# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : image_window.py
# @Desc      : 图片处理窗口
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
import math
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from PySide6.QtGui import QFont, QPixmap, QImage, QTransform, QIcon, QPainter, QPen, QBrush, QCursor, QColor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView, QScrollArea, QFrame,
                               QLabel, QWidget, QLineEdit, QComboBox, QTableWidgetItem, QDialog, QSizePolicy,
                               QTreeWidget, QTreeWidgetItem, QFileSystemModel, QAbstractItemView, QStyle,
                               QGraphicsRectItem, QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
                               QSplitter, QSizePolicy, QGroupBox, QGridLayout, QProgressDialog)
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QPoint, QEasingCurve, QSize, QDir, QRect, QRectF, QEvent, QThread, Signal, Slot
from qfluentwidgets import (setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton, ScrollArea,
                            LineEdit, ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition, ElevatedCardWidget,
                            SpinBox, TextEdit, FlowLayout, CaptionLabel, CheckBox, CardWidget, TransparentToolButton)
from qframelesswindow import FramelessWindow

from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.services.scan_service import scan_service
from src.services.register_service import register_service
from src.services.operation_service import operation_service
from src.utils.DocumentBorderCleaner import DocumentBorderCleaner
from src.utils.DocumentContentDeskew import DocumentContentDeskew
from src.utils.NotificationTool import show_error, show_success, show_warning, show_info

load_dotenv(verbose=True)

IMG_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

# ──────────────────── 异步缩略图加载线程 ────────────────────

class ThumbnailLoader(QThread):
    """
    后台线程：逐张读取图片并发射 thumbnail_ready(index, QImage)。
    主线程收到信号后调用 _apply_thumbnail 填充已创建的占位卡片。
    """
    thumbnail_ready = Signal(int, object)   # (index, QImage | None)
    finished_all    = Signal(int)           # 全部完成，发射总数

    THUMB_W = 160
    THUMB_H = 200

    def __init__(self, paths: list, parent=None, start_index: int = 0, thumb_w: int = None, thumb_h: int = None):
        super().__init__(parent)
        self._paths     = paths
        self._start_index = start_index
        self._thumb_w = thumb_w or self.THUMB_W
        self._thumb_h = thumb_h or self.THUMB_H
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for idx, path in enumerate(self._paths):
            if self._cancelled:
                break
            try:
                image = QImage(path)
                if not image.isNull():
                    thumb = image.scaled(
                        self._thumb_w, self._thumb_h,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.thumbnail_ready.emit(self._start_index + idx, thumb)
                else:
                    self.thumbnail_ready.emit(self._start_index + idx, None)
            except Exception:
                self.thumbnail_ready.emit(self._start_index + idx, None)
        self.finished_all.emit(len(self._paths))


class AutoImageProcessWorker(QThread):
    progress_changed = Signal(int, int, str)
    process_finished = Signal(bool, object)

    def __init__(self, image_paths: list, operations: list, parent=None):
        super().__init__(parent)
        self._image_paths = image_paths
        self._operations = operations

    def run(self):
        total = len(self._image_paths) * len(self._operations)
        done = 0
        errors = []

        deskew_processor = None
        border_cleaner = None

        for image_path in self._image_paths:
            for operation in self._operations:
                if operation == "deskew":
                    action_name = "纠偏"
                else:
                    action_name = "去黑边"

                try:
                    self.progress_changed.emit(done, total, f"正在{action_name}: {os.path.basename(image_path)}")
                    if operation == "deskew":
                        if deskew_processor is None:
                            deskew_processor = DocumentContentDeskew()
                        deskew_processor.deskew_image(input_path=image_path, output_path=image_path)
                    elif operation == "border_clear":
                        if border_cleaner is None:
                            border_cleaner = DocumentBorderCleaner()
                        border_cleaner.clean(input_path=image_path, output_path=image_path)
                except Exception as e:
                    errors.append(f"{os.path.basename(image_path)} {action_name}失败: {e}")
                    logger.error(f"自动{action_name}失败; 图片: {image_path}; {str(e)}")
                finally:
                    done += 1
                    self.progress_changed.emit(done, total, f"已完成 {done}/{total}")

        self.process_finished.emit(len(errors) == 0, errors)


class CropOverlay(QWidget):
    def __init__(self, parent=None, mode="crop"):
        super().__init__(parent)
        self.mode = mode
        self.crop_rect = QRect()
        self.correct_line = []
        self.start_pos = None
        self.is_drawing = False
        self.is_resizing = False
        self.resize_edge = None
        self.min_size = 20
        self.setMouseTracking(True)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background-color: transparent;")

        self.handles = {}
        self.handle_size = 8

    def set_crop_rect(self, rect):
        self.crop_rect = rect
        self.update()

    def set_correct_line(self, line):
        self.correct_line = line
        self.update()

    def set_mode(self, mode):
        old_mode = self.mode
        self.mode = mode

        if old_mode != mode:
            if mode == "correct":
                self.correct_line = []
            else:
                self.crop_rect = QRect()

        self.update()

    def update_cursor(self, pos):
        if self.mode == "correct":
            self.setCursor(Qt.CrossCursor)
        elif self.crop_rect.contains(pos):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.is_drawing = True
            self.start_pos = pos
            if self.mode == "correct":
                self.correct_line = [pos]
            else:
                self.crop_rect = QRect(pos, pos)
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.is_drawing and self.start_pos:
            if self.mode == "correct":
                if len(self.correct_line) > 0:
                    self.correct_line = [self.correct_line[0], pos]
            else:
                rect = QRect(self.start_pos, pos).normalized()
                if rect.width() < self.min_size:
                    rect.setWidth(self.min_size)
                    if pos.x() < self.start_pos.x():
                        rect.moveLeft(self.start_pos.x() - self.min_size)

                if rect.height() < self.min_size:
                    rect.setHeight(self.min_size)
                    if pos.y() < self.start_pos.y():
                        rect.moveTop(self.start_pos.y() - self.min_size)
                rect = rect.intersected(QRect(0, 0, self.width(), self.height()))
                self.crop_rect = rect
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            if self.mode == "correct":
                if len(self.correct_line) == 2:
                    p1, p2 = self.correct_line[0], self.correct_line[1]
                    length = math.sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2)

                    if length >= 20:
                        parent = self.parent()
                        while parent:
                            if hasattr(parent, 'auto_process'):
                                parent.auto_correct()
                                break
                            parent = parent.parent()
                    else:
                        self.correct_line = []
                        self.update()
            else:
                if not self.crop_rect.isNull() and self.crop_rect.width() >= self.min_size and self.crop_rect.height() >= self.min_size:
                    parent = self.parent()
                    while parent:
                        if hasattr(parent, 'auto_process'):
                            if self.mode == "crop":
                                parent.auto_crop()
                            else:
                                parent.auto_black_border()
                            break
                        parent = parent.parent()

            self.start_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.mode == "correct":
            if len(self.correct_line) == 2:
                p1, p2 = self.correct_line[0], self.correct_line[1]
                painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
                painter.setPen(Qt.NoPen)
                painter.drawRect(0, 0, self.width(), self.height())
                painter.setPen(QPen(QColor(0, 150, 136, 150), 1, Qt.DashLine))
                painter.drawLine(p1.x(), p1.y(), p2.x(), p1.y())
                painter.drawLine(p2.x(), p1.y(), p2.x(), p2.y())
                painter.setPen(QPen(QColor(255, 87, 34), 3))
                painter.drawLine(p1, p2)
                painter.setBrush(QBrush(QColor(255, 87, 34)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(p1, 5, 5)
                painter.drawEllipse(p2, 5, 5)

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                if dx != 0:
                    angle = math.degrees(math.atan(dy / dx))
                else:
                    angle = 90 if dy > 0 else -90

                angle_text = f"纠偏角度: {abs(angle):.1f}°"
                font = painter.font()
                font.setPointSize(11)
                font.setBold(True)
                painter.setFont(font)

                mid_x = (p1.x() + p2.x()) // 2
                mid_y = (p1.y() + p2.y()) // 2
                text_rect = QRect(mid_x - 80, mid_y - 40, 160, 30)

                painter.setBrush(QBrush(QColor(255, 87, 34, 200)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(text_rect, 6, 6)

                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.drawText(text_rect, Qt.AlignCenter, angle_text)

                hint_text = "松开鼠标自动纠偏"
                hint_rect = QRect(mid_x - 80, mid_y - 70, 160, 25)
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                painter.drawRoundedRect(hint_rect, 4, 4)
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(hint_rect, Qt.AlignCenter, hint_text)
            else:
                if len(self.correct_line) == 1:
                    p = self.correct_line[0]
                    painter.setPen(QPen(QColor(255, 87, 34), 3))
                    painter.setBrush(QBrush(QColor(255, 87, 34)))
                    painter.drawEllipse(p, 5, 5)

                hint_text = "绘制一条水平参考线（从左到右）"
                font = painter.font()
                font.setPointSize(12)
                font.setBold(True)
                painter.setFont(font)

                text_rect = QRect(self.width() // 2 - 200, self.height() // 2 - 20, 400, 40)
                painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(text_rect, 8, 8)

                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.drawText(text_rect, Qt.AlignCenter, hint_text)
        else:
            if not self.crop_rect.isNull():
                if self.mode == "crop":
                    border_color = QColor(0, 120, 215)
                    fill_color = QColor(0, 0, 0, 80)
                    mode_text = "裁剪"
                else:
                    border_color = QColor(255, 107, 107)
                    fill_color = QColor(0, 0, 0, 40)
                    mode_text = "去黑边"

                painter.setBrush(QBrush(fill_color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(0, 0, self.width(), self.crop_rect.top())
                painter.drawRect(0, self.crop_rect.bottom(), self.width(), self.height() - self.crop_rect.bottom())
                painter.drawRect(0, self.crop_rect.top(), self.crop_rect.left(), self.crop_rect.height())
                painter.drawRect(self.crop_rect.right(), self.crop_rect.top(),
                                 self.width() - self.crop_rect.right(), self.crop_rect.height())

                pen = QPen(border_color, 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(self.crop_rect)
                corner_length = 15
                line_width = 3

                painter.setPen(QPen(QColor(255, 255, 255), line_width))
                painter.drawLine(self.crop_rect.left(), self.crop_rect.top(),
                                 self.crop_rect.left() + corner_length, self.crop_rect.top())
                painter.drawLine(self.crop_rect.left(), self.crop_rect.top(),
                                 self.crop_rect.left(), self.crop_rect.top() + corner_length)

                painter.drawLine(self.crop_rect.right(), self.crop_rect.top(),
                                 self.crop_rect.right() - corner_length, self.crop_rect.top())
                painter.drawLine(self.crop_rect.right(), self.crop_rect.top(),
                                 self.crop_rect.right(), self.crop_rect.top() + corner_length)

                painter.drawLine(self.crop_rect.left(), self.crop_rect.bottom(),
                                 self.crop_rect.left() + corner_length, self.crop_rect.bottom())
                painter.drawLine(self.crop_rect.left(), self.crop_rect.bottom(),
                                 self.crop_rect.left(), self.crop_rect.bottom() - corner_length)

                painter.drawLine(self.crop_rect.right(), self.crop_rect.bottom(),
                                 self.crop_rect.right() - corner_length, self.crop_rect.bottom())
                painter.drawLine(self.crop_rect.right(), self.crop_rect.bottom(),
                                 self.crop_rect.right(), self.crop_rect.bottom() - corner_length)


                if self.crop_rect.width() > 100 and self.crop_rect.height() > 50:
                    size_text = f"{mode_text}: {self.crop_rect.width()} × {self.crop_rect.height()}"
                    font = painter.font()
                    font.setPointSize(10)
                    font.setBold(True)
                    painter.setFont(font)

                    text_rect = QRect(self.crop_rect.center().x() - 80,
                                      self.crop_rect.center().y() - 10,
                                      160, 20)

                    painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(text_rect, 4, 4)

                    painter.setPen(QPen(QColor(255, 255, 255)))
                    painter.drawText(text_rect, Qt.AlignCenter, size_text)

    def get_crop_rect_in_image_coords(self, image_size, display_rect):
        if self.crop_rect.isNull() or display_rect.isNull():
            return QRect()

        scale_x = image_size.width() / display_rect.width()
        scale_y = image_size.height() / display_rect.height()

        crop_x = int((self.crop_rect.x() - display_rect.x()) * scale_x)
        crop_y = int((self.crop_rect.y() - display_rect.y()) * scale_y)
        crop_width = int(self.crop_rect.width() * scale_x)
        crop_height = int(self.crop_rect.height() * scale_y)

        crop_x = max(0, min(crop_x, image_size.width() - 1))
        crop_y = max(0, min(crop_y, image_size.height() - 1))
        crop_width = min(crop_width, image_size.width() - crop_x)
        crop_height = min(crop_height, image_size.height() - crop_y)

        return QRect(crop_x, crop_y, crop_width, crop_height)

    def get_correct_line_in_image_coords(self, image_size, display_rect):
        if len(self.correct_line) != 2 or display_rect.isNull():
            return []
        scale_x = image_size.width() / display_rect.width()
        scale_y = image_size.height() / display_rect.height()

        converted_line = []
        for point in self.correct_line:
            img_x = int((point.x() - display_rect.x()) * scale_x)
            img_y = int((point.y() - display_rect.y()) * scale_y)

            img_x = max(0, min(img_x, image_size.width() - 1))
            img_y = max(0, min(img_y, image_size.height() - 1))
            converted_line.append(QPoint(img_x, img_y))

        return converted_line


class FlowImageWidget(QWidget):
    def __init__(self, img_path, parent=None, thumb_w: int = 160, thumb_h: int = 200, lazy: bool = False):
        super().__init__(parent)
        self.img_path = img_path
        self.is_selected = False
        self._is_deleted = False
        self.original_pixmap = None
        self.current_pixmap = None
        self._thumbnail_pixmap = None
        self.rotation_angle = 0
        self.cached_rotations = {}
        self._thumb_w = thumb_w
        self._thumb_h = thumb_h

        self.operation_history = {
            "rotate": [], "crop": [], "black_border": [], "correct": []
        }
        self.current_operation_mode = None
        self.current_operation_type = None
        self.operation_states = {}

        self.init_ui(lazy=lazy)
        if not lazy:
            self.load_image()

    def init_ui(self, lazy: bool = False):
        card_w = self._thumb_w + 10
        card_h = self._thumb_h + 30
        self.setFixedSize(card_w, card_h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(3)

        # 图片容器（用于叠加标记角标）
        self._img_container = QWidget(self)
        self._img_container.setFixedSize(self._thumb_w, self._thumb_h)
        self._img_container.setStyleSheet("background:transparent;")

        self.img_label = QLabel(self._img_container)
        self.img_label.setFixedSize(self._thumb_w, self._thumb_h)
        self.img_label.setAlignment(Qt.AlignCenter)
        if lazy:
            self.img_label.setStyleSheet(
                "border-radius:4px; background:#e8e8e8;"
            )
            self.img_label.setText("⏳")

        # ── 标记角标（默认隐藏）──
        self._mark_badge = QLabel("⚑ 已标记", self._img_container)
        self._mark_badge.setFixedSize(66, 20)
        self._mark_badge.move(3, 3)
        self._mark_badge.setAlignment(Qt.AlignCenter)
        self._mark_badge.setStyleSheet("""
            QLabel { background:#e53935; color:white; border-radius:4px;
                font-size:10px; font-weight:bold; font-family:'Microsoft YaHei'; }
        """)
        self._mark_badge.setVisible(False)
        self._mark_badge.raise_()

        self.name_label = QLabel(os.path.basename(self.img_path))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(26)
        self.name_label.setStyleSheet(
            "color:#333; font-size:11px; padding:1px; border:none;"
        )

        outer.addWidget(self._img_container)
        outer.addWidget(self.name_label)
        self.setCursor(Qt.PointingHandCursor)

    # ── 懒加载：接收异步线程传来的缩略图 ──
    def set_pixmap(self, pixmap):
        if self._is_deleted or not self.img_label:
            return
        if isinstance(pixmap, QImage):
            pixmap = QPixmap.fromImage(pixmap)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self._thumb_w, self._thumb_h,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._thumbnail_pixmap = scaled
            self.img_label.setPixmap(scaled)
            self.img_label.setStyleSheet("border-radius:4px; background:#f5f5f5;")
        else:
            self.img_label.setText("⚠")

    def ensure_full_image_loaded(self):
        if self.current_pixmap and self.original_pixmap:
            if not self.current_pixmap.isNull() and not self.original_pixmap.isNull():
                return True
        return self.load_image()

    # ── 缩放时调整卡片尺寸 ──
    def resize_thumb(self, thumb_w: int, thumb_h: int):
        if self._is_deleted:
            return
        self._thumb_w = thumb_w
        self._thumb_h = thumb_h
        card_w = thumb_w + 10
        card_h = thumb_h + 30
        self.setFixedSize(card_w, card_h)
        self._img_container.setFixedSize(thumb_w, thumb_h)
        self.img_label.setFixedSize(thumb_w, thumb_h)

    # ── 标记角标显示/隐藏 ──
    def set_mark_state(self, mark_type: str = None):
        """mark_type=None 清除；mark_type=str 显示红色角标"""
        has_mark = mark_type is not None
        if self._mark_badge:
            if has_mark:
                short = mark_type[:5] if len(mark_type) > 5 else mark_type
                self._mark_badge.setText(f"⚑ {short}")
            self._mark_badge.setVisible(has_mark)
        color = "#e53935" if has_mark else "#333"
        self.name_label.setStyleSheet(
            f"color:{color}; font-size:11px; padding:1px; border:none; font-weight:{'bold' if has_mark else 'normal'};"
        )
        if has_mark:
            self.setStyleSheet("QWidget { background:#fff5f5; border-radius:6px; border:2px solid #e53935; }")
        else:
            self.setStyleSheet("")

    def load_image(self):
        if os.path.exists(self.img_path):
            pixmap = QPixmap(self.img_path)
            if not pixmap.isNull():
                self.original_pixmap = pixmap.copy()
                self.current_pixmap = pixmap.copy()
                self.rotation_angle = 0
                self.cached_rotations.clear()

                self.operation_history = {
                    "rotate": [],
                    "crop": [],
                    "black_border": [],
                    "correct": []
                }
                self.operation_states = {}
                self.update_display()
                return True

            logger.error(f"图片加载失败: {self.img_path}")
            return False
        else:
            self.img_label.setText("图片\n不存在")
            self.img_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    background-color: #f5f5f5;
                    padding: 5px;
                    color: #999;
                    font-size: 14px;
                }
            """)
            return False

    def update_display(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            scaled_pixmap = self.current_pixmap.scaled(
                self.img_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.img_label.setPixmap(scaled_pixmap)

    def rotate_image(self, angle):
        if not self.ensure_full_image_loaded():
            return None
        if not self.original_pixmap or self.original_pixmap.isNull():
            return None

        new_angle = (self.rotation_angle + angle) % 360

        if new_angle in self.cached_rotations:
            rotated_pixmap = self.cached_rotations[new_angle]
        else:
            transform = QTransform()
            transform.rotate(new_angle)

            rotated_pixmap = self.original_pixmap.transformed(
                transform,
                Qt.SmoothTransformation
            )
            self.cached_rotations[new_angle] = rotated_pixmap

        return rotated_pixmap

    def rotate_and_save_image(self, angle):
        if not self.ensure_full_image_loaded():
            return False
        if not self.original_pixmap or self.original_pixmap.isNull():
            return False

        original_width = self.original_pixmap.width()
        original_height = self.original_pixmap.height()

        self.save_to_history("rotate", self.current_pixmap.copy())

        new_angle = (self.rotation_angle + angle) % 360
        self.rotation_angle = new_angle

        try:
            transform = QTransform()
            transform.rotate(self.rotation_angle)

            rotated_pixmap = self.original_pixmap.transformed(
                transform,
                Qt.SmoothTransformation
            )

            if abs(angle) % 90 == 0 and abs(angle) % 180 != 0:
                rotated_width = rotated_pixmap.width()
                rotated_height = rotated_pixmap.height()
                white_background = QPixmap(rotated_width, rotated_height)
            else:
                white_background = QPixmap(original_width, original_height)

            white_background.fill(Qt.white)

            painter = QPainter(white_background)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            if abs(angle) % 90 == 0 and abs(angle) % 180 != 0:
                x_offset = 0
                y_offset = 0
            else:
                x_offset = (original_width - rotated_pixmap.width()) // 2
                y_offset = (original_height - rotated_pixmap.height()) // 2

            painter.drawPixmap(x_offset, y_offset, rotated_pixmap)
            painter.end()

            success = self.save_image(white_background)

            if success:
                self.current_pixmap = white_background
                self.operation_states["rotate"] = {
                    "angle": self.rotation_angle,
                    "pixmap": white_background.copy()
                }
                self.cached_rotations.clear()
                self.cached_rotations[self.rotation_angle] = white_background.copy()
                self.update_display()
                return True
            else:
                self.undo_from_history("rotate")
                self.rotation_angle = (self.rotation_angle - angle) % 360
                return False

        except Exception as e:
            logger.error(f"旋转图片时发生错误: {e}")
            self.undo_from_history("rotate")
            self.rotation_angle = (self.rotation_angle - angle) % 360
            return False

    def crop_and_save_image(self, crop_rect):
        if not self.ensure_full_image_loaded():
            return False
        if not self.original_pixmap or self.original_pixmap.isNull():
            return False
        if crop_rect.isNull() or crop_rect.width() <= 0 or crop_rect.height() <= 0:
            return False

        img_rect = QRect(0, 0, self.original_pixmap.width(), self.original_pixmap.height())
        if not img_rect.contains(crop_rect):
            crop_rect = crop_rect.intersected(img_rect)
            if crop_rect.isNull():
                return False

        try:
            self.save_to_history("crop", self.current_pixmap.copy())
            cropped_pixmap = self.current_pixmap.copy(crop_rect)
            success = self.save_image(cropped_pixmap)
            if success:
                self.current_pixmap = cropped_pixmap
                self.original_pixmap = cropped_pixmap.copy()
                self.rotation_angle = 0
                self.cached_rotations.clear()

                self.operation_states["crop"] = {
                    "rect": crop_rect,
                    "pixmap": cropped_pixmap.copy()
                }

                self.update_display()
                return True
            else:
                self.undo_from_history("crop")
                return False

        except Exception as e:
            logger.error(f"裁剪图片时出错: {e}")
            self.undo_from_history("crop")
            return False

    def black_border_and_save_image(self, border_rect):
        if not self.ensure_full_image_loaded():
            return False
        if not self.original_pixmap or self.original_pixmap.isNull():
            return False
        if border_rect.isNull() or border_rect.width() <= 0 or border_rect.height() <= 0:
            return False

        img_rect = QRect(0, 0, self.original_pixmap.width(), self.original_pixmap.height())
        if not img_rect.contains(border_rect):
            border_rect = border_rect.intersected(img_rect)
            if border_rect.isNull():
                return False
        try:
            self.save_to_history("black_border", self.current_pixmap.copy())
            processed_pixmap = self.current_pixmap.copy()
            painter = QPainter(processed_pixmap)
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(Qt.NoPen)
            painter.drawRect(border_rect)
            painter.end()

            success = self.save_image(processed_pixmap)
            print(f"success: {success}")
            if success:

                self.current_pixmap = processed_pixmap
                self.original_pixmap = processed_pixmap.copy()
                self.rotation_angle = 0
                self.cached_rotations.clear()

                self.operation_states["black_border"] = {
                    "rect": border_rect,
                    "pixmap": processed_pixmap.copy()
                }

                self.update_display()

                return True
            else:
                self.undo_from_history("black_border")
                return False

        except Exception as e:
            logger.error(f"去黑边操作时出错: {e}")
            self.undo_from_history("black_border")
            return False

    def correct_and_save_image(self, line_points):
        if not self.ensure_full_image_loaded():
            return False
        if not self.original_pixmap or self.original_pixmap.isNull():
            return False
        if len(line_points) != 2:
            return False

        p1, p2 = line_points[0], line_points[1]
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()

        if dx == 0 and dy == 0:
            return False

        try:
            self.save_to_history("correct", self.current_pixmap.copy())
            angle = math.degrees(math.atan2(dy, dx))
            rotation_angle = -angle
            original_width = self.current_pixmap.width()
            original_height = self.current_pixmap.height()

            transform = QTransform()
            transform.rotate(rotation_angle)
            rotated_pixmap = self.current_pixmap.transformed(
                transform,
                Qt.SmoothTransformation
            )
            white_background = QPixmap(rotated_pixmap.width(), rotated_pixmap.height())
            white_background.fill(Qt.white)
            painter = QPainter(white_background)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(0, 0, rotated_pixmap)
            painter.end()
            success = self.save_image(white_background)

            if success:
                self.current_pixmap = white_background
                self.original_pixmap = white_background.copy()
                self.rotation_angle = (self.rotation_angle + rotation_angle) % 360
                self.cached_rotations.clear()

                self.operation_states["correct"] = {
                    "angle": rotation_angle,
                    "pixmap": white_background.copy()
                }
                self.update_display()
                return True
            else:
                self.undo_from_history("correct")
                return False

        except Exception as e:
            logger.error(f"纠偏操作时出错: {e}")
            self.undo_from_history("correct")
            return False

    def save_to_history(self, operation_type, pixmap):
        if operation_type in self.operation_history:
            self.operation_history[operation_type].append(pixmap.copy())
            self.current_operation_type = operation_type
            return True
        return False

    def undo_from_history(self, operation_type):
        if operation_type in self.operation_history:
            history_stack = self.operation_history[operation_type]
            if history_stack:
                history_stack.pop()
                if history_stack:
                    restore_pixmap = history_stack[-1]
                    success = self.save_image(restore_pixmap)
                    if success:
                        self.current_pixmap = restore_pixmap.copy()
                        self.original_pixmap = restore_pixmap.copy()
                        self.update_display()
                        return True
                else:
                    return True
        return False

    def undo_last_operation(self, operation_type=None):
        if operation_type is None:
            if self.current_operation_type:
                operation_type = self.current_operation_type
            else:
                operation_type = "rotate"

        if operation_type in self.operation_history:
            history_stack = self.operation_history[operation_type]
            if len(history_stack) > 0:
                if len(history_stack) > 1:
                    restore_pixmap = history_stack[-2]
                else:
                    restore_pixmap = history_stack[-1]

                success = self.save_image(restore_pixmap)
                if success:
                    self.current_pixmap = restore_pixmap.copy()
                    self.original_pixmap = restore_pixmap.copy()

                    if len(history_stack) > 1:
                        history_stack.pop()
                    else:
                        history_stack.clear()

                    if operation_type == "rotate":
                        for angle, pixmap in self.cached_rotations.items():
                            if pixmap.cacheKey() == self.current_pixmap.cacheKey():
                                self.rotation_angle = angle
                                break
                    self.update_display()

                    if operation_type in self.operation_states:
                        del self.operation_states[operation_type]

                    return True
            else:
                logger.warning(f"没有可撤销的{operation_type}操作")
                return False
        else:
            logger.error(f"未知的操作类型: {operation_type}")
            return False

    def has_operation_history(self, operation_type=None):
        if operation_type:
            if operation_type in self.operation_history:
                return len(self.operation_history[operation_type]) > 0
            return False
        else:
            for op_type in self.operation_history:
                if len(self.operation_history[op_type]) > 0:
                    return True
            return False

    def get_last_operation_type(self):
        return self.current_operation_type

    def get_operation_history_count(self, operation_type):
        if operation_type in self.operation_history:
            return len(self.operation_history[operation_type])
        return 0

    def clear_operation_history(self):
        for op_type in self.operation_history:
            self.operation_history[op_type].clear()
        self.operation_states.clear()
        self.current_operation_type = None

    def set_operation_mode(self, mode):
        print(f"model: {mode}")
        self.current_operation_mode = mode

        if self.current_operation_mode == "crop":
            self.img_label.setStyleSheet(f"""
                QLabel {{
                    border: 3px solid #0066CC;
                    border-radius: 6px;
                    background-color: #f5f5f5;
                    padding: 5px;
                }}
            """)
        elif self.current_operation_mode == "black_border":
            self.img_label.setStyleSheet(f"""
                QLabel {{
                    border: 3px solid #FF6B6B;
                    border-radius: 6px;
                    background-color: #f5f5f5;
                    padding: 5px;
                }}
            """)
        elif self.current_operation_mode == "correct":
            self.img_label.setStyleSheet(f"""
                QLabel {{
                    border: 3px solid #FF5722;
                    border-radius: 6px;
                    background-color: #f5f5f5;
                    padding: 5px;
                }}
            """)

    def save_image(self, pixmap):
        if not pixmap or pixmap.isNull():
            return False

        temp_path = None
        try:
            file_ext = os.path.splitext(self.img_path)[1].lower()
            format_map = {
                '.jpg': ('JPEG', 95),
                '.jpeg': ('JPEG', 95),
                '.png': ('PNG', -1),
                '.bmp': ('BMP', -1),
                '.tiff': ('TIFF', -1),
                '.webp': ('WEBP', -1),
                '.gif': ('GIF', -1),
            }
            image_format, quality = format_map.get(file_ext, (None, -1))
            temp_path = f"{self.img_path}.tmp_{os.getpid()}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{file_ext}"

            if image_format:
                success = pixmap.save(temp_path, image_format, quality)
            else:
                success = pixmap.save(temp_path)

            if not success:
                logger.error(f"保存图片到临时文件失败: {temp_path}")
                return False

            os.replace(temp_path, self.img_path)
            return True
        except Exception as e:
            logger.error(f"保存图片时出错: {e}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"清理临时图片文件失败: {cleanup_error}")

    def get_current_image(self):
        return self.current_pixmap if self.current_pixmap else self.original_pixmap

    def get_original_image(self):
        return self.original_pixmap

    def get_rotation_angle(self):
        return self.rotation_angle

    def reload_image(self):
        if os.path.exists(self.img_path):
            pixmap = QPixmap(self.img_path)
            if not pixmap.isNull():
                self.original_pixmap = pixmap.copy()
                self.current_pixmap = pixmap.copy()
                self.rotation_angle = 0
                self.cached_rotations.clear()
                self.update_display()
                return True
        return False

    def mousePressEvent(self, event):
        if self._is_deleted or not self.isVisible():
            return

        try:
            self.set_selected(True)
            parent = self.parentWidget()
            while parent:
                if hasattr(parent, 'on_image_selected'):
                    parent.on_image_selected(self, self.img_path)
                    break
                parent = parent.parentWidget()
        except RuntimeError:
            pass

    def set_selected(self, selected):
        if self._is_deleted or not self.img_label:
            return

        try:
            self.is_selected = selected
            if self.current_operation_mode == "crop":
                self.img_label.setStyleSheet(f"""
                    QLabel {{
                        border: 3px solid #0066CC;
                        border-radius: 6px;
                        background-color: #f5f5f5;
                        padding: 5px;
                    }}
                """)
            elif self.current_operation_mode == "black_border":
                self.img_label.setStyleSheet(f"""
                    QLabel {{
                        border: 3px solid #FF6B6B;
                        border-radius: 6px;
                        background-color: #f5f5f5;
                        padding: 5px;
                    }}
                """)
            elif self.current_operation_mode == "correct":
                self.img_label.setStyleSheet(f"""
                    QLabel {{
                        border: 3px solid #FF5722;
                        border-radius: 6px;
                        background-color: #f5f5f5;
                        padding: 5px;
                    }}
                """)
            else:
                border_color = "#0066CC" if selected else "transparent"
                self.img_label.setStyleSheet(f"""
                    QLabel {{
                        border: 2px solid {border_color};
                        border-radius: 6px;
                        background-color: #f5f5f5;
                        padding: 5px;
                    }}
                """)
        except RuntimeError:
            self._is_deleted = True

    def cleanup(self):
        self._is_deleted = True
        self.img_label = None
        self.name_label = None
        self.original_pixmap = None
        self.current_pixmap = None
        self._thumbnail_pixmap = None
        self.cached_rotations.clear()
        for op_type in self.operation_history:
            self.operation_history[op_type].clear()
        self.operation_states.clear()

    def __del__(self):
        self.cleanup()


class ImagePreviewWidget(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_img_path = None
        self.current_pixmap = None
        self.current_operation_mode = None
        self.operation_overlay = None
        self.operation_toolbar = None
        self.original_pixmap_for_operation = None
        self.last_selected_image_widget = None
        self.init_ui()

    def init_ui(self):

        self.setBorderRadius(8)
        self.setStyleSheet("""
            CardWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
            }
        """)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(15)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)

        self.operation_hint_widget = QWidget()
        self.operation_hint_widget.setVisible(False)
        self.operation_hint_widget.setFixedHeight(40)
        operation_hint_layout = QHBoxLayout(self.operation_hint_widget)
        operation_hint_layout.setContentsMargins(0, 0, 0, 0)

        self.operation_instruction = QLabel()
        self.operation_instruction.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                line-height: 1.5;
                padding: 6px 8px;
                background-color: #f0f0f0;
                border-radius: 6px;
                border: 1px solid #e0e0e0;
            }
        """)

        operation_hint_layout.addWidget(self.operation_instruction)
        operation_hint_layout.addStretch()

        self.title_label = StrongBodyLabel("图片预览")
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
        title_layout.addWidget(self.operation_hint_widget)

        self.status_label = QLabel("未选择图片")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                color: #999;
                border-radius: 12px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        title_layout.addWidget(self.status_label)

        self.layout.addLayout(title_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #e0e0e0; height: 1px;")
        self.layout.addWidget(separator)

        self.info_toolbar = QWidget()
        self.info_toolbar.setFixedHeight(50)
        info_toolbar_layout = QHBoxLayout(self.info_toolbar)
        info_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        info_toolbar_layout.setSpacing(20)

        file_info_widget = QWidget()
        file_info_layout = QHBoxLayout(file_info_widget)
        file_info_layout.setContentsMargins(0, 0, 0, 0)
        file_info_layout.setSpacing(8)

        file_label = QLabel("📁")
        file_label.setStyleSheet("font-size: 16px; color: #666;")
        self.file_name_label = QLabel("未选择图片")
        self.file_name_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
                color: #333;
                padding: 4px 0;
            }
        """)
        self.file_name_label.setWordWrap(True)
        self.file_name_label.setMaximumWidth(300)

        file_info_layout.addWidget(file_label)
        file_info_layout.addWidget(self.file_name_label)
        info_toolbar_layout.addWidget(file_info_widget)

        size_info_widget = QWidget()
        size_info_layout = QHBoxLayout(size_info_widget)
        size_info_layout.setContentsMargins(0, 0, 0, 0)
        size_info_layout.setSpacing(8)

        size_label = QLabel("📏")
        size_label.setStyleSheet("font-size: 16px; color: #666;")
        self.image_size_label = QLabel("—")
        self.image_size_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 500;
                color: #333;
                padding: 4px 0;
            }
        """)

        size_info_layout.addWidget(size_label)
        size_info_layout.addWidget(self.image_size_label)
        info_toolbar_layout.addWidget(size_info_widget)

        info_toolbar_layout.addStretch()

        self.operation_toolbar = QWidget()
        self.operation_toolbar.setVisible(False)
        operation_toolbar_layout = QHBoxLayout(self.operation_toolbar)
        operation_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        operation_toolbar_layout.setSpacing(12)

        self.undo_operation_btn = PushButton("撤销操作")
        self.undo_operation_btn.setEnabled(False)
        self.undo_operation_btn.setFixedSize(100, 36)
        self.undo_operation_btn.setStyleSheet("""
            PushButton {
                font-size: 13px;
                font-weight: 500;
                border-radius: 6px;
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #ffcdd2;
                padding: 8px 12px;
            }
            PushButton:hover {
                background-color: #ffcdd2;
            }
            PushButton:disabled {
                background-color: #f5f5f5;
                color: #999;
                border: 1px solid #e0e0e0;
            }
        """)

        operation_toolbar_layout.addWidget(self.undo_operation_btn)
        info_toolbar_layout.addWidget(self.operation_toolbar)
        self.layout.addWidget(self.info_toolbar)
        self.preview_container = CardWidget()
        self.preview_container.setBorderRadius(8)
        self.preview_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_container.setStyleSheet("""
            CardWidget {
                background-color: #f9f9f9;
                border: 1px solid #e0e0e0;
            }
        """)

        preview_container_layout = QVBoxLayout(self.preview_container)
        preview_container_layout.setContentsMargins(0, 0, 0, 0)
        preview_container_layout.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f9f9f9;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cccccc;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #999999;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                height: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #cccccc;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #999999;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
                width: 0px;
            }
        """)

        self.image_display_container = QWidget()
        self.image_display_container.setStyleSheet("background-color: #f9f9f9;")
        self.image_display_layout = QVBoxLayout(self.image_display_container)
        self.image_display_layout.setContentsMargins(0, 0, 0, 0)
        self.image_display_layout.setSpacing(0)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f9f9f9;
            }
        """)

        default_text = "点击中间区域图片进行预览"
        self.preview_label.setText(default_text)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f9f9f9;
                font-size: 16px;
                color: #999;
                font-weight: 500;
                line-height: 1.8;
                qproperty-alignment: 'AlignCenter';
            }
        """)

        self.image_display_layout.addWidget(self.preview_label)
        self.scroll_area.setWidget(self.image_display_container)
        preview_container_layout.addWidget(self.scroll_area)

        self.layout.addWidget(self.preview_container, stretch=1)

        self.undo_operation_btn.clicked.connect(self.undo_operation)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap and not self.current_pixmap.isNull():
            self.set_preview_pixmap(self.current_pixmap)

        if self.current_operation_mode and self.operation_overlay:
            self.update_operation_overlay()

    def set_preview_image(self, img_path):
        self.current_img_path = img_path

        if not img_path or not os.path.exists(img_path):
            self.reset_preview()
            return

        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.set_preview_pixmap(pixmap)

            self.file_name_label.setText(os.path.basename(img_path))
            self.image_size_label.setText(f"{pixmap.width()} × {pixmap.height()}")
            self.status_label.setText("已选择")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    border-radius: 12px;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)

            if self.current_operation_mode:
                self.exit_operation_mode()
        else:
            self.reset_preview()

    def set_preview_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.current_pixmap = pixmap
            self.preview_label.setText("")
            scroll_area_size = self.scroll_area.viewport().size()
            if scroll_area_size.width() <= 0 or scroll_area_size.height() <= 0:
                scroll_area_size = QSize(400, 500)

            scaled_pixmap = pixmap.scaled(
                scroll_area_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setMinimumSize(scaled_pixmap.size())

            if self.current_operation_mode and self.operation_overlay:
                self.update_operation_overlay()
        else:
            self.reset_preview()

    def enter_operation_mode(self, mode):
        if not self.current_pixmap or self.current_pixmap.isNull():
            show_warning(self, "警告", "请先选择一张图片", 2000)
            return False

        if self.current_operation_mode == mode:
            operation_names = {
                "crop": "裁剪",
                "black_border": "去黑边",
                "correct": "纠偏"
            }
            operation_name = operation_names.get(mode, "操作")
            show_info(self, "提示", f"已在{operation_name}模式中，请拖动鼠标绘制操作区域", 2000)
            return True

        if self.operation_overlay:
            self.operation_overlay.deleteLater()

        self.operation_overlay = CropOverlay(self.preview_label, mode)
        self.operation_overlay.setGeometry(self.preview_label.rect())
        self.operation_overlay.raise_()
        self.operation_overlay.show()

        self.operation_toolbar.setVisible(True)
        self.operation_hint_widget.setVisible(True)

        if mode == "crop":
            self.operation_instruction.setText("拖动鼠标绘制裁剪区域，松开鼠标自动裁剪")

            self.undo_operation_btn.setText("撤销裁剪")
            self.status_label.setText("✂️ 裁剪模式")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    border-radius: 12px;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            self.undo_operation_btn.setStyleSheet("""
                PushButton {
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 6px;
                    background-color: #e3f2fd;
                    color: #1565c0;
                    border: 1px solid #bbdefb;
                    padding: 8px 12px;
                }
                PushButton:hover {
                    background-color: #bbdefb;
                }
                PushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #e0e0e0;
                }
            """)
        elif mode == "black_border":
            self.operation_instruction.setText("拖动鼠标绘制去黑边区域，松开鼠标自动填充白色")
            self.undo_operation_btn.setText("撤销去黑边")
            self.status_label.setText("⬜ 去黑边模式")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #fff3e0;
                    color: #ef6c00;
                    border-radius: 12px;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            self.undo_operation_btn.setStyleSheet("""
                PushButton {
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 6px;
                    background-color: #ffebee;
                    color: #c62828;
                    border: 1px solid #ffcdd2;
                    padding: 8px 12px;
                }
                PushButton:hover {
                    background-color: #ffcdd2;
                }
                PushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #e0e0e0;
                }
            """)
        else:
            self.operation_instruction.setText("拖动鼠标绘制水平参考线（从左到右），松开鼠标自动纠偏")
            self.undo_operation_btn.setText("撤销纠偏")
            self.status_label.setText("📐 纠偏模式")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #fce4ec;
                    color: #c2185b;
                    border-radius: 12px;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            self.undo_operation_btn.setStyleSheet("""
                PushButton {
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 6px;
                    background-color: #fff3e0;
                    color: #ef6c00;
                    border: 1px solid #ffe0b2;
                    padding: 8px 12px;
                }
                PushButton:hover {
                    background-color: #ffe0b2;
                }
                PushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #e0e0e0;
                }
            """)
        self.current_operation_mode = mode

        self.update_undo_button_state(self.last_selected_image_widget, mode)

        operation_desc = {
            "crop": "裁剪",
            "black_border": "去黑边",
            "correct": "纠偏"
        }.get(mode, "操作")

        show_info(self, f"{operation_desc}模式已激活", f"拖动鼠标绘制{operation_desc}区域，松开鼠标自动{operation_desc}", 2000)

        return True

    def auto_process(self):
        if not self.operation_overlay:
            return
        label_rect = self.preview_label.rect()

        if label_rect.isNull():
            self.exit_operation_mode()
            return
        pixmap_scaled = self.preview_label.pixmap()
        if not pixmap_scaled or pixmap_scaled.isNull():
            self.exit_operation_mode()
            return

        pixmap_width = pixmap_scaled.width()
        pixmap_height = pixmap_scaled.height()

        display_x = label_rect.x() + (label_rect.width() - pixmap_width) // 2
        display_y = label_rect.y() + (label_rect.height() - pixmap_height) // 2
        display_rect = QRect(display_x, display_y, pixmap_width, pixmap_height)

        if self.current_operation_mode == "correct":
            correct_line_display = self.operation_overlay.correct_line

            if len(correct_line_display) != 2:
                show_warning(self, "警告", "请绘制一条有效的水平参考线", 2000)
                return
            original_size = self.current_pixmap.size()
            correct_line_original = self.operation_overlay.get_correct_line_in_image_coords(
                original_size,
                display_rect
            )

            if len(correct_line_original) != 2:
                show_warning(self, "警告", "纠偏区域无效", 2000)
                return
        else:
            operation_rect_display = self.operation_overlay.crop_rect
            if operation_rect_display.isNull():
                show_warning(self, "警告", "操作区域无效", 2000)
                return
            original_size = self.current_pixmap.size()
            operation_rect_original = self.operation_overlay.get_crop_rect_in_image_coords(
                original_size,
                display_rect
            )

            if operation_rect_original.isNull():
                show_warning(self, "警告", "操作区域无效", 2000)
                return
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, 'perform_operation'):
                if self.current_operation_mode == "correct":
                    parent.perform_operation(correct_line_original, self.current_operation_mode)
                else:
                    parent.perform_operation(operation_rect_original, self.current_operation_mode)
                break
            parent = parent.parentWidget()

        if self.operation_overlay:
            if self.current_operation_mode == "correct":
                self.operation_overlay.correct_line = []
            else:
                self.operation_overlay.crop_rect = QRect()
            self.operation_overlay.update()

        self.update_undo_button_state(self.last_selected_image_widget, self.current_operation_mode)

    def auto_crop(self):
        self.auto_process()

    def auto_black_border(self):
        self.auto_process()

    def auto_correct(self):
        self.auto_process()

    def exit_operation_mode(self):
        self.current_operation_mode = None
        self.operation_toolbar.setVisible(False)
        self.operation_hint_widget.setVisible(False)
        if self.operation_overlay:
            self.operation_overlay.deleteLater()
            self.operation_overlay = None

        if self.current_pixmap and not self.current_pixmap.isNull():
            self.status_label.setText("已选择")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    border-radius: 12px;
                    padding: 6px 16px;
                    font-size: 13px;
                    font-weight: 500;
                }
            """)
            self.undo_operation_btn.setStyleSheet("""
                PushButton {
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 6px;
                    background-color: #ffebee;
                    color: #c62828;
                    border: 1px solid #ffcdd2;
                    padding: 8px 12px;
                }
                PushButton:hover {
                    background-color: #ffcdd2;
                }
                PushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #e0e0e0;
                }
            """)
        self.update_undo_button_state(self.last_selected_image_widget, None)

    def update_operation_overlay(self):
        if self.operation_overlay and self.preview_label:
            self.operation_overlay.setGeometry(self.preview_label.rect())
            self.operation_overlay.update()

    def update_undo_button_state(self, image_widget, operation_mode=None):
        if not image_widget:
            self.undo_operation_btn.setEnabled(False)
            self.undo_operation_btn.setText("撤销操作")
            self.operation_toolbar.setVisible(False)
            return
        if image_widget != self.last_selected_image_widget:
            self.last_selected_image_widget = image_widget

        has_history = False
        btn_text = "撤销操作"

        if operation_mode == "crop":
            history_count = image_widget.get_operation_history_count("crop")
            has_history = history_count > 0
            btn_text = "撤销裁剪"
        elif operation_mode == "black_border":
            history_count = image_widget.get_operation_history_count("black_border")
            has_history = history_count > 0
            btn_text = "撤销去黑边"
        elif operation_mode == "correct":
            history_count = image_widget.get_operation_history_count("correct")
            has_history = history_count > 0
            btn_text = "撤销纠偏"
        elif operation_mode is None:
            history_count = image_widget.get_operation_history_count("rotate")
            has_history = history_count > 0
            btn_text = "撤销旋转"

        self.undo_operation_btn.setText(btn_text)
        self.undo_operation_btn.setEnabled(has_history)

        if has_history or (operation_mode and self.current_operation_mode):
            self.operation_toolbar.setVisible(True)
        else:
            self.operation_toolbar.setVisible(False)

    def undo_operation(self):
        if not self.last_selected_image_widget:
            show_warning(self, "警告", "没有选中的图片", 2000)
            return
        operation_mode = self.current_operation_mode

        parent = self.parentWidget()
        while parent:
            if hasattr(parent, 'undo_operation'):
                parent.undo_operation(self.last_selected_image_widget, operation_mode)
                break
            parent = parent.parentWidget()

    def reset_preview(self):
        default_text = "点击中间区域图片进行预览"
        self.preview_label.setText(default_text)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f9f9f9;
                font-size: 16px;
                color: #999;
                font-weight: 500;
                line-height: 1.8;
                qproperty-alignment: 'AlignCenter';
            }
        """)
        self.file_name_label.setText("未选择图片")
        self.image_size_label.setText("—")
        self.status_label.setText("未选择图片")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                color: #999;
                border-radius: 12px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        self.current_pixmap = None
        self.current_img_path = None
        self.last_selected_image_widget = None
        self.operation_toolbar.setVisible(False)
        self.operation_hint_widget.setVisible(False)

        if self.current_operation_mode:
            self.exit_operation_mode()

    def clear_all_states(self):
        self.exit_operation_mode()

        self.undo_operation_btn.setEnabled(False)
        self.undo_operation_btn.setText("撤销操作")
        self.operation_toolbar.setVisible(False)
        self.operation_hint_widget.setVisible(False)
        self.last_selected_image_widget = None


class ImageDirectoryTree(CardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_selected_folder = None
        self.selected_folder_item = None

        self.setBorderRadius(8)
        self.setStyleSheet("""
            CardWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
            }
        """)
        self.main_window = parent
        self.load_mian_window_data()
        self.init_ui()

    def load_mian_window_data(self):
        print(f"scan_info_list = {self.main_window.scan_info_list}")
        self.dir_path = self.main_window.scan_info_list[-1].dir_path
        print(f"dir_path = {self.dir_path}")


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
        current_root = None
        if self.tree_widget.topLevelItemCount() > 0:
            current_root = self.tree_widget.topLevelItem(0).data(0, Qt.UserRole)
        print(f"current_root: {current_root}")
        self.load_directory_tree(current_root)

    def load_directory_tree(self, root_path=None):
        if not root_path:
            root_path = self.dir_path
            if not os.path.exists(root_path):
                root_path = f"{os.getcwd()}/upload_images"

        self.tree_widget.clear()

        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, os.path.basename(root_path))
        root_item.setData(0, Qt.UserRole, root_path)
        root_item.setIcon(0, self.get_folder_icon())

        root_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        self.load_subdirectories(root_item, root_path)

        self.tree_widget.expandItem(root_item)
        root_item.setSelected(True)
        self.selected_folder_item = root_item
        self.current_selected_folder = root_path

    def load_subdirectories(self, parent_item, path):
        try:
            dirs = []
            for item_name in os.listdir(path):
                if item_name in self.main_window.dir_name_list or item_name[:-5] in self.main_window.dir_name_list:
                    item_path = os.path.join(path, item_name)
                    if os.path.isdir(item_path):
                        dirs.append((item_name, item_path))

            dirs.sort(key=lambda x: x[0].lower())

            for item_name, item_path in dirs:
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, item_name)
                child_item.setData(0, Qt.UserRole, item_path)
                child_item.setIcon(0, self.get_folder_icon())
                child_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        except PermissionError:
            pass
        except Exception as e:
            print(f"加载目录时出错: {e}")

    def get_folder_icon(self):
        style = self.style()
        if style:
            return style.standardIcon(QStyle.SP_DirIcon)
        return QIcon()

    def on_folder_selected(self, item, column):
        if self.selected_folder_item:
            self.selected_folder_item.setSelected(False)

        self.selected_folder_item = item
        folder_path = item.data(0, Qt.UserRole)

        print(4444, folder_path)
        self.current_selected_folder = folder_path

        item.setSelected(True)

        print(55555, item.childCount())

        if item.childCount() == 0:
            self.load_subdirectories(item, folder_path)

        parent = self.parentWidget()
        while parent:
            if hasattr(parent, 'load_images_from_folder'):
                parent.load_images_from_folder(folder_path)
                break
            parent = parent.parentWidget()


class ImageGalleryWidget(CardWidget):
    # 缩略图尺寸步进
    THUMB_MIN  = 80
    THUMB_MAX  = 300
    THUMB_STEP = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.setStyleSheet("""
            CardWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
            }
        """)
        self._thumb_size = 160          # 当前缩略图宽度（正方形基准）
        self._placeholder_widgets = []  # 占位卡片列表，供 _apply_thumbnail 填充
        self.on_need_more_images = None
        self.on_zoom_changed = None
        self._zoom_refresh_timer = QTimer(self)
        self._zoom_refresh_timer.setSingleShot(True)
        self._zoom_refresh_timer.timeout.connect(self._emit_zoom_changed)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # ── 标题栏 ──
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        self.title_label = StrongBodyLabel("图片画廊")
        self.title_label.setStyleSheet("""
            QLabel { font-size:18px; font-weight:600; color:#333; padding:2px 0; }
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        self.image_count_label = QLabel("共 0 张")
        self.image_count_label.setStyleSheet("""
            QLabel { background-color:#e8f5e9; color:#2e7d32; border-radius:12px;
                padding:6px 16px; font-size:14px; font-weight:500; }
        """)
        title_layout.addWidget(self.image_count_label)

        # ── 缩放按钮 ──
        zoom_out_btn = PushButton("－")
        zoom_out_btn.setFixedSize(32, 32)
        zoom_out_btn.setToolTip("缩小（Ctrl + 鼠标滚轮向下）")
        zoom_out_btn.setCursor(Qt.PointingHandCursor)
        zoom_out_btn.setStyleSheet("""
            PushButton { font-size:18px; font-weight:bold;
                border-radius:6px; background:#f0f0f0; border:1px solid #ddd; }
            PushButton:hover { background:#e0e0e0; }
        """)
        zoom_out_btn.clicked.connect(self.zoom_out)
        title_layout.addWidget(zoom_out_btn)

        self.zoom_label = QLabel(f"{self._thumb_size}px")
        self.zoom_label.setFixedWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet(
            "font-size:12px;color:#888;font-family:'Microsoft YaHei';"
        )
        title_layout.addWidget(self.zoom_label)

        zoom_in_btn = PushButton("＋")
        zoom_in_btn.setFixedSize(32, 32)
        zoom_in_btn.setToolTip("放大（Ctrl + 鼠标滚轮向上）")
        zoom_in_btn.setCursor(Qt.PointingHandCursor)
        zoom_in_btn.setStyleSheet("""
            PushButton { font-size:18px; font-weight:bold;
                border-radius:6px; background:#f0f0f0; border:1px solid #ddd; }
            PushButton:hover { background:#e0e0e0; }
        """)
        zoom_in_btn.clicked.connect(self.zoom_in)
        title_layout.addWidget(zoom_in_btn)

        layout.addLayout(title_layout)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color:#e0e0e0; height:1px;")
        layout.addWidget(separator)

        self.scroll_container = QWidget()
        self.scroll_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.flow_layout = FlowLayout(self.scroll_container)
        self.flow_layout.setSpacing(16)
        self.flow_layout.setContentsMargins(10, 10, 10, 10)
        self.flow_layout.setHorizontalSpacing(20)
        self.flow_layout.setVerticalSpacing(20)

        self.gallery_scroll = ScrollArea()
        self.gallery_scroll.setWidget(self.scroll_container)
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("""
            QScrollArea { border:none; background-color:transparent; }
            QScrollBar:vertical { border:none; background:#f0f0f0; width:10px;
                border-radius:5px; margin:0; }
            QScrollBar::handle:vertical { background:#ccc; border-radius:5px; min-height:30px; }
            QScrollBar::handle:vertical:hover { background:#999; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)
        layout.addWidget(self.gallery_scroll, stretch=1)

        # 安装独立滚轮过滤器（不覆盖 ImageGalleryWidget 自身的 eventFilter）
        from PySide6.QtCore import QObject
        class _WheelFilter(QObject):
            def __init__(self, gallery: 'ImageGalleryWidget'):
                super().__init__(gallery)
                self._gallery = gallery
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Wheel:
                    if event.modifiers() & Qt.ControlModifier:
                        delta = event.angleDelta().y()
                        if delta > 0:
                            self._gallery.zoom_in()
                        else:
                            self._gallery.zoom_out()
                        return True
                    QTimer.singleShot(0, self._gallery.maybe_request_more_images)
                return False

        self._wheel_filter = _WheelFilter(self)
        self.gallery_scroll.viewport().installEventFilter(self._wheel_filter)
        self.gallery_scroll.verticalScrollBar().valueChanged.connect(
            lambda _: self.maybe_request_more_images()
        )

    def maybe_request_more_images(self):
        bar = self.gallery_scroll.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        if bar.value() >= bar.maximum() - 240 and callable(self.on_need_more_images):
            self.on_need_more_images()

    # ── 缩放操作 ──
    def zoom_in(self):
        if self._thumb_size < self.THUMB_MAX:
            self._thumb_size = min(self._thumb_size + self.THUMB_STEP, self.THUMB_MAX)
            self._resize_all_cards()
            self._zoom_refresh_timer.start(180)

    def zoom_out(self):
        if self._thumb_size > self.THUMB_MIN:
            self._thumb_size = max(self._thumb_size - self.THUMB_STEP, self.THUMB_MIN)
            self._resize_all_cards()
            self._zoom_refresh_timer.start(180)

    def _emit_zoom_changed(self):
        if callable(self.on_zoom_changed):
            self.on_zoom_changed(self._thumb_size, int(self._thumb_size * 1.25))

    def _resize_all_cards(self):
        """缩放时更新所有已渲染卡片的尺寸"""
        self.zoom_label.setText(f"{self._thumb_size}px")
        thumb_h = int(self._thumb_size * 1.25)
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            if not item:
                continue
            w = item.widget()
            if w and hasattr(w, 'resize_thumb'):
                w.resize_thumb(self._thumb_size, thumb_h)
        self.scroll_container.adjustSize()

    # ── 懒加载：创建占位卡片 ──
    def add_placeholder(self, img_path: str, thumb_w: int, thumb_h: int) -> 'FlowImageWidget':
        """创建骨架卡片（不加载像素），添加到流式布局，返回 widget 引用"""
        widget = FlowImageWidget(
            img_path, self.scroll_container,
            thumb_w=thumb_w, thumb_h=thumb_h, lazy=True
        )
        self.flow_layout.addWidget(widget)
        self._placeholder_widgets.append(widget)
        return widget

    @Slot(int, object)
    def apply_thumbnail(self, index: int, pixmap):
        """ThumbnailLoader.thumbnail_ready → 填充第 index 张卡片"""
        if index >= len(self._placeholder_widgets):
            return
        w = self._placeholder_widgets[index]
        if w and not w._is_deleted:
            w.set_pixmap(pixmap)

    def clear_gallery(self):
        self._placeholder_widgets.clear()
        self.safe_delete_widgets()
        self.image_count_label.setText("共 0 张")
        self.image_count_label.setStyleSheet("""
            QLabel { background-color:#f0f0f0; color:#999; border-radius:12px;
                padding:6px 16px; font-size:14px; font-weight:500; }
        """)

    def safe_delete_widgets(self):
        widgets_to_delete = []
        for i in range(self.flow_layout.count()):
            item = self.flow_layout.itemAt(i)
            if item and item.widget():
                widgets_to_delete.append(item.widget())
        for widget in widgets_to_delete:
            if widget:
                try:
                    if hasattr(widget, 'cleanup'):
                        widget.cleanup()
                    widget.hide()
                    self.flow_layout.removeWidget(widget)
                    widget.deleteLater()
                except RuntimeError:
                    pass
        self.flow_layout.update()

    def update_image_count(self, count):
        self.image_count_label.setText(f"共 {count} 张")
        color    = "#2e7d32" if count > 0 else "#999"
        bg_color = "#e8f5e9" if count > 0 else "#f0f0f0"
        self.image_count_label.setStyleSheet(f"""
            QLabel {{ background-color:{bg_color}; color:{color}; border-radius:12px;
                padding:6px 16px; font-size:14px; font-weight:500; }}
        """)


class ImageWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 图片处理")
        self.resize(1400, 850)
        self.center()

        setTheme(Theme.LIGHT)

        self.total_images = 0
        self._is_navigation = False
        self._is_app_exiting = False
        self.selected_image_widget = None
        self._thumb_loader = None
        self._zoom_thumb_loader = None
        self._all_image_paths = []
        self._path_to_img_widget = {}
        self._loaded_image_count = 0
        self._gallery_batch_size = 24
        self._gallery_loading_batch = False
        self._pending_mark_paths = []
        self._pending_mark_types = {}

        self.current_image = None
        self.current_operation_mode = None
        self.current_operation_image_widget = None
        self.current_user = global_cache.get("current_user", None)
        self.current_data = global_cache.get("current_data", None)

        print(f"current_data = {self.current_data}")
        self.task_info = task_service.get_by_id(int(self.current_data[0]))
        print(f"task_info = {self.task_info}")
        scan_where = {
            "register_id": self.task_info.register_id,
            "task_node": 2,
        }
        self.current_user_scan_info = task_service.get_data(scan_where)

        print(f"current_user_scan_info = {self.current_user_scan_info}")

        task_ids = [scan.id for scan in self.current_user_scan_info]

        print(f"<扫描查找条件>: {task_ids}")
        self.scan_info_list = scan_service.get_scan_info_taskId(task_ids)
        # TODO 整合文件夹, 如果不同路径的话, 将扫描文件夹整合到一个中
        print(f"<扫描信息>: {self.scan_info_list}")
        self.dir_name_list = []
        for scan in self.scan_info_list:
            dir_name = scan.dir_name.split("/")
            print(222, dir_name)
            if dir_name[0] not in self.dir_name_list:
                self.dir_name_list.append(dir_name[0])

        print(f"dir_name_list = {self.dir_name_list}")
        self.init_ui()

    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        self.setStyleSheet("""
            FramelessWindow {
                background-color: #f5f5f7;
            }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 30, 10, 10)
        self.setLayout(main_layout)
        top_info_container = CardWidget()
        top_info_container.setBorderRadius(8)
        top_info_container.setFixedHeight(65)
        top_info_layout = QHBoxLayout(top_info_container)
        top_info_layout.setContentsMargins(20, 10, 20, 10)
        top_info_layout.setSpacing(30)

        batch_container = QWidget()
        batch_layout = QHBoxLayout(batch_container)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        batch_layout.setSpacing(8)

        batch_label = QLabel('批次号:')
        batch_label.setStyleSheet("font-size:16px; font-weight: bold; color: #333;")
        self.number_value_label = QLabel(self.task_info.batch_number)
        self.number_value_label.setStyleSheet("""
            QLabel {
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 2px 6px;
                    background-color: white;
                    text-align: center;
                    color: #333;
                    border: none;
                }
        """)
        self.number_nuit_label = QLabel("卷")
        self.number_nuit_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #666;")

        batch_layout.addWidget(batch_label)
        batch_layout.addWidget(self.number_value_label)
        batch_layout.addWidget(self.number_nuit_label)
        batch_layout.addStretch()
        top_info_layout.addWidget(batch_container)
        task_container = QWidget()
        task_layout = QHBoxLayout(task_container)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.setSpacing(8)
        task_label = QLabel("任务号段:")
        task_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #333; min-width: 85px;")
        self.task_number_start_label = QLabel(self.task_info.task_number_start)
        self.task_number_start_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 700;
                color: #1565c0;
                padding: 4px 0;
            }
        """)
        task_number_f_label = QLabel("——")
        task_number_f_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #666;")
        self.task_number_end_label = QLabel(self.task_info.task_number_end)
        self.task_number_end_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 700;
                color: #1565c0;
                padding: 4px 0;
            }
        """)

        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_number_start_label)
        task_layout.addWidget(task_number_f_label)
        task_layout.addWidget(self.task_number_end_label)
        task_layout.addStretch()
        top_info_layout.addWidget(task_container)
        path_container = QWidget()
        path_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        path_layout = QHBoxLayout(path_container)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(10)

        path_label = QLabel("文件路径:")
        path_label.setStyleSheet("font-size: 16px; min-width: 90px;")
        self.image_path_label = QLabel("", self)
        self.image_path_label.setFont(QFont("Arial", 13))
        self.image_path_label.setStyleSheet("""
            LineEdit {
                background-color: #f8f9fa;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px 5px;
                font-size: 16px;
                font-weight: 500;
            }
        """)

        info_labels = [batch_label, task_label]
        for label in info_labels:
            label.setStyleSheet("font-size:16px; font-weight: bold;")
            label.setFixedWidth(100 if label == task_label else 70)

        value_labels = [self.number_value_label, self.number_nuit_label,
                        self.task_number_start_label, self.task_number_end_label]
        for label in value_labels:
            label.setStyleSheet("""
                QLabel {
                    border-radius: 4px;
                    font-size: 16px;
                    padding: 2px 6px;
                    background-color: white;
                    text-align: center;
                    border: none;
                }
            """)
            label.setFixedHeight(40)
            if label == self.number_value_label:
                label.setFixedWidth(120)
            elif label == self.number_nuit_label:
                label.setFixedWidth(40)
            else:
                label.setFixedWidth(60)

        path_layout.addWidget(path_label)
        path_layout.addWidget(self.image_path_label, stretch=1)

        top_info_layout.addWidget(path_container, stretch=2)
        self.update_user_label()
        self.user_label.setStyleSheet("""
            QLabel {
                background-color: #e6f3ff;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 14px;
                color: #0066cc;
                font-weight: bold;
                border: none;
            }
        """)
        self.user_label.setFixedHeight(40)
        top_info_layout.addWidget(self.user_label)
        main_layout.addWidget(top_info_container)
        btn_container = CardWidget()
        btn_container.setBorderRadius(8)
        btn_container.setFixedHeight(75)
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(20, 10, 20, 10)
        btn_layout.setSpacing(5)

        button_row = QHBoxLayout()
        button_row.setSpacing(15)
        self.forward_rotation_1 = PushButton("↻ 正转 1°")
        self.reversal_1 = PushButton("↺ 反转 1°")
        self.forward_rotation_90 = PushButton("↻ 正转 90°")
        self.reversal_90 = PushButton("↺ 反转 90°")
        self.trimming = PushButton("✂️ 裁剪")
        self.black_border = PushButton("⬜ 去黑边")
        self.correct_btn = PushButton("📐 纠偏")
        auto_container = QWidget()
        auto_layout = QHBoxLayout(auto_container)
        auto_layout.setContentsMargins(0, 0, 0, 0)
        auto_layout.setSpacing(15)
        auto_label = QLabel("自动处理:")
        auto_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #333;")
        self.correct_deviation_checkbox = CheckBox("纠偏")
        self.correct_deviation_checkbox.setStyleSheet("font-size: 15px;")
        self.blocr_border_checkbox = CheckBox("去黑边")
        self.blocr_border_checkbox.setStyleSheet("font-size: 15px;")
        self.to_do = PushButton("🚀 执行")
        self.to_do.setCursor(Qt.PointingHandCursor)
        auto_layout.addWidget(auto_label)
        auto_layout.addWidget(self.correct_deviation_checkbox)
        auto_layout.addWidget(self.blocr_border_checkbox)
        auto_layout.addWidget(self.to_do)
        self.submit_btn = PrimaryPushButton("提交")
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn = PushButton("返回")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_table)
        operation_buttons = [self.forward_rotation_1, self.reversal_1, self.forward_rotation_90,
                             self.reversal_90, self.trimming, self.black_border, self.correct_btn]
        for btn in operation_buttons:
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(96, 36)
            btn.setStyleSheet("""
                PushButton {
                    font-size: 15px;
                    font-weight: 500;
                    border-radius: 8px;
                    padding: 10px;
                }
                PushButton:hover {
                    opacity: 0.9;
                }
            """)

        self.forward_rotation_1.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #e3f2fd;
                color: #1565c0;
                border: 1px solid #bbdefb;
            }
            PushButton:hover {
                background-color: #bbdefb;
            }
        """)
        self.reversal_1.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #e3f2fd;
                color: #1565c0;
                border: 1px solid #bbdefb;
            }
            PushButton:hover {
                background-color: #bbdefb;
            }
        """)
        self.forward_rotation_90.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #f3e5f5;
                color: #7b1fa2;
                border: 1px solid #e1bee7;
            }
            PushButton:hover {
                background-color: #e1bee7;
            }
        """)
        self.reversal_90.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #f3e5f5;
                color: #7b1fa2;
                border: 1px solid #e1bee7;
            }
            PushButton:hover {
                background-color: #e1bee7;
            }
        """)
        self.trimming.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
            }
            PushButton:hover {
                background-color: #c8e6c9;
            }
        """)
        self.black_border.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #fff3e0;
                color: #ef6c00;
                border: 1px solid #ffe0b2;
            }
            PushButton:hover {
                background-color: #ffe0b2;
            }
        """)
        self.correct_btn.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background-color: #fce4ec;
                color: #c2185b;
                border: 1px solid #f8bbd9;
            }
            PushButton:hover {
                background-color: #f8bbd9;
            }
        """)
        self.to_do.setFixedSize(96, 36)
        self.to_do.setStyleSheet("""
            PushButton {
                font-size: 15px;
                font-weight: 500;
                border-radius: 8px;
                padding: 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color:  #c2185b;
                border: 1px solid #f8bbd9;
            }
            PushButton:hover {
                background-color: #e1bee7;
            }
        """)
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

        self.forward_rotation_1.clicked.connect(lambda: self.check_operation_state_and_rotate(1))
        self.reversal_1.clicked.connect(lambda: self.check_operation_state_and_rotate(-1))
        self.forward_rotation_90.clicked.connect(lambda: self.check_operation_state_and_rotate(90))
        self.reversal_90.clicked.connect(lambda: self.check_operation_state_and_rotate(-90))
        self.black_border.clicked.connect(self.enter_black_border_mode)
        self.correct_btn.clicked.connect(self.enter_correct_mode)
        self.to_do.clicked.connect(self.check_operation_state_and_execute)
        self.trimming.clicked.connect(self.enter_crop_mode)
        self.submit_btn.clicked.connect(self.check_operation_state_and_submit)

        self.mark_btn = PushButton("⚑ 标记")
        self.mark_btn.setFixedSize(96, 36)
        self.mark_btn.setToolTip("对当前图片添加质检标记")
        self.mark_btn.setStyleSheet("""
            PushButton { background-color:#e53935; color:white; border-radius:8px;
                font-size:15px; font-weight:500; border:none; }
            PushButton:hover { background-color:#c62828; }
        """)
        self.mark_btn.clicked.connect(self.sing_message_fun)
        self.mark_btn_container = QWidget()
        self.mark_btn_container.setFixedSize(108, 42)
        self.mark_btn.setParent(self.mark_btn_container)
        self.mark_btn.move(0, 6)
        self.mark_count_badge = QLabel("0", self.mark_btn_container)
        self.mark_count_badge.setAlignment(Qt.AlignCenter)
        self.mark_count_badge.setFixedSize(24, 18)
        self.mark_count_badge.move(82, 0)
        self.mark_count_badge.setStyleSheet("""
            QLabel {
                background-color:#ff1744;
                color:white;
                border-radius:9px;
                font-size:11px;
                font-weight:bold;
                padding:0 4px;
            }
        """)
        self.mark_count_badge.hide()
        self.mark_count_badge.raise_()

        button_row.addWidget(self.forward_rotation_1)
        button_row.addWidget(self.reversal_1)
        button_row.addWidget(self.forward_rotation_90)
        button_row.addWidget(self.reversal_90)
        button_row.addWidget(self.trimming)
        button_row.addWidget(self.black_border)
        button_row.addWidget(self.correct_btn)
        button_row.addSpacing(25)
        button_row.addWidget(auto_container)
        button_row.addStretch()
        if self.current_user["role"] in ["管理员", "质检员"]:
            button_row.addWidget(self.mark_btn_container)
        button_row.addWidget(self.back_btn)
        button_row.addWidget(self.submit_btn)

        btn_layout.addLayout(button_row)
        main_layout.addWidget(btn_container)

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

        self.directory_tree = ImageDirectoryTree(self)
        main_splitter.addWidget(self.directory_tree)

        self.gallery_widget = ImageGalleryWidget()
        self.gallery_widget.on_need_more_images = self.load_next_gallery_batch
        self.gallery_widget.on_zoom_changed = self.refresh_loaded_gallery_thumbnails
        main_splitter.addWidget(self.gallery_widget)

        self.preview_widget = ImagePreviewWidget()
        main_splitter.addWidget(self.preview_widget)

        main_splitter.setSizes([320, 800, 480])

        main_layout.addWidget(main_splitter, stretch=1)

        self._check_task_status()

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
                return
        else:
            self.can_do_task = f"{self.task_info.task_number_start}-{self.task_info.task_number_end}"

    def check_operation_state_and_rotate(self, angle):
        if self.current_operation_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)
            operation_name = {
                "crop": "裁剪",
                "black_border": "去黑边",
                "correct": "纠偏"
            }.get(self.current_operation_mode, "操作")

            show_info(self, f"{operation_name}状态已结束", f"已退出{operation_name}状态，开始执行旋转操作", 2000)

        self.rotate_and_save_selected_image(angle)

    def check_operation_state_and_execute(self):
        border_checkbox = self.blocr_border_checkbox.isChecked()
        correct_checkbox = self.correct_deviation_checkbox.isChecked()
        if not border_checkbox and not correct_checkbox:
            show_warning(self, "警告", "请勾选自动处理功能：纠偏或去黑边", 2000)
            return

        if self.current_image is None and self.directory_tree.current_selected_folder is None:
            show_warning(self, "警告", "请选择要处理的图片或文件夹", 2000)
            return

        images_list = []
        if self.current_image is not None:
            images_list.append(self.current_image)
        else:
            for file in sorted(os.listdir(self.directory_tree.current_selected_folder)):
                if Path(file).suffix.lower() in IMG_EXTENSIONS:
                    file_path = f"{self.directory_tree.current_selected_folder}/{file}"
                    images_list.append(file_path)

        if not images_list:
            show_warning(self, "警告", "当前选择中没有可处理的图片", 2000)
            return

        operations = []
        if correct_checkbox:
            operations.append("deskew")
        if border_checkbox:
            operations.append("border_clear")

        if self.current_operation_image_widget:
            self.exit_operation_state_before_operation("自动处理")

        self._start_auto_process(images_list, operations)

    def _start_auto_process(self, images_list: list, operations: list):
        if getattr(self, "_auto_process_worker", None) and self._auto_process_worker.isRunning():
            show_warning(self, "警告", "自动处理正在执行，请稍候", 2000)
            return

        total = len(images_list) * len(operations)
        self._auto_process_images = images_list
        self._auto_process_operations = operations
        self._auto_process_refresh_folder = (
            os.path.dirname(images_list[0])
            if self.current_image is not None
            else self.directory_tree.current_selected_folder
        )

        self._auto_process_progress = QProgressDialog("准备自动处理...", "取消", 0, total, self)
        self._auto_process_progress.setWindowTitle("自动处理进度")
        self._auto_process_progress.setWindowModality(Qt.ApplicationModal)
        self._auto_process_progress.setCancelButton(None)
        self._auto_process_progress.setMinimumDuration(0)
        self._auto_process_progress.setAutoClose(False)
        self._auto_process_progress.setAutoReset(False)
        self._auto_process_progress.setValue(0)
        self._auto_process_progress.show()

        self.to_do.setEnabled(False)
        self._auto_process_worker = AutoImageProcessWorker(images_list, operations, self)
        self._auto_process_worker.progress_changed.connect(self._on_auto_process_progress)
        self._auto_process_worker.process_finished.connect(self._on_auto_process_finished)
        self._auto_process_worker.finished.connect(self._auto_process_worker.deleteLater)
        self._auto_process_worker.start()

    @Slot(int, int, str)
    def _on_auto_process_progress(self, current: int, total: int, message: str):
        progress_dialog = getattr(self, "_auto_process_progress", None)
        if not progress_dialog:
            return

        progress_dialog.setMaximum(total)
        progress_dialog.setLabelText(message)
        progress_dialog.setValue(current)

    @Slot(bool, object)
    def _on_auto_process_finished(self, success: bool, errors: list):
        progress_dialog = getattr(self, "_auto_process_progress", None)
        if progress_dialog:
            progress_dialog.close()
            progress_dialog.deleteLater()
            self._auto_process_progress = None

        self.to_do.setEnabled(True)
        images_list = getattr(self, "_auto_process_images", [])
        operations = getattr(self, "_auto_process_operations", [])

        operation_data_list = []
        if "deskew" in operations:
            logger.info(f"图像处理-自动纠偏; 操作人: {self.current_user}")
            operation_data_list.append({
                "task_id": self.task_info.register_id,
                "task_name": "图像处理",
                "operator": self.current_user["username"],
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": f"图像处理-自动纠偏; {images_list}"
            })

        if "border_clear" in operations:
            logger.info(f"图像处理-自动去黑边; 操作人: {self.current_user}")
            operation_data_list.append({
                "task_id": self.task_info.register_id,
                "task_name": "图像处理",
                "operator": self.current_user["username"],
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": f"图像处理-自动去黑边; {images_list}"
            })

        if operation_data_list:
            operation_service.save_data(operation_data_list)

        self._refresh_after_auto_process()

        if success:
            show_success(self, "提示", "自动处理完成!", 2000)
        else:
            error_message = "\n".join(errors[:3])
            if len(errors) > 3:
                error_message += f"\n还有 {len(errors) - 3} 个错误，请查看日志"
            show_error(self, "报错", f"自动处理完成，部分图片失败:\n{error_message}", 4000)

        self._auto_process_worker = None
        self._auto_process_images = []
        self._auto_process_operations = []

    def _refresh_after_auto_process(self):
        refresh_folder = getattr(self, "_auto_process_refresh_folder", None)
        if self.directory_tree:
            self.directory_tree.refresh_tree()
            if refresh_folder:
                self.directory_tree.current_selected_folder = refresh_folder

        if refresh_folder and os.path.exists(refresh_folder):
            self.load_images_from_folder(refresh_folder)

    def auto_content_deskew(self, images_list: list):
        if len(images_list) == 0:
            show_warning(self, "警告", "自动纠偏处理时未选择图片!")
            return

        try:
            content_deskew = DocumentContentDeskew()
            for image in images_list:
                content_deskew.deskew_image(input_path=image, output_path=image)

            show_success(self, "提示", "自动批量纠偏完成!", 2000)
        except Exception as e:
            logger.error(f"自动批量纠偏失败; {str(e)}")
            show_error(self, "报错", "批量自动纠偏失败!", 2000)


    def auto_border_clear(self, images_list: list):
        if len(images_list) == 0:
            show_warning(self, "警告", "自动去黑边处理时未选择图片!")
            return

        try:
            border_cleaner = DocumentBorderCleaner()
            for image in images_list:
                border_cleaner.clean(input_path=image, output_path=image)

            show_success(self, "提示", "自动批量去黑边完成!", 2000)
        except Exception as e:
            logger.error(f"自动批量去黑边报错; {str(e)}")
            show_error(self, "报错", "批量自动去黑边失败!", 2000)

    def check_operation_state_and_submit(self):
        if self.task_info.is_do:
            show_warning(self, "警告", "该任务已提交， 不可再次提交")
            return

        if self.current_operation_image_widget:
            self.exit_operation_state_before_operation("提交")
        try:
            result = task_service.execute_task_submission(self.task_info.id, self.can_do_task.split('-')[1])
            update = {
                "complete_number": self.can_do_task,
            }
            task_service.update(self.task_info.id, update)
            if result['status'] == "success":
                operation_data = {
                    "task_id": self.task_info.id,
                    "task_name": "图像处理",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": "图像处理提交操作"
                }
                operation_service.save_data([operation_data])

                show_success(self, "提交成功", "图像处理提交成")
            else:
                show_error(self, "提交失败", "图像处理提失败")

        except Exception as e:
            show_error(self, "提交失败", f"图像处理提交失败{str(e)}")

    def exit_operation_state_before_operation(self, operation_name):
        if self.current_operation_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)
            show_info(self, "操作状态已结束", f"已退出操作状态，开始执行{operation_name}操作", 2000)

    def enter_crop_mode(self):
        if not self.selected_image_widget:
            show_warning(self, "警告", "请先选中一张图片", 2000)
            return

        if self.current_operation_image_widget and self.current_operation_image_widget != self.selected_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)

        self.current_operation_image_widget = self.selected_image_widget
        self.current_operation_mode = "crop"
        self.current_operation_image_widget.set_operation_mode("crop")

        if self.preview_widget.enter_operation_mode("crop"):
            self.preview_widget.update_undo_button_state(self.current_operation_image_widget, "crop")
            show_info(self, "裁剪模式", "已进入裁剪模式，拖动鼠标绘制裁剪区域", 2000)

    def enter_black_border_mode(self):
        if not self.selected_image_widget:
            show_warning(self, "提示", "请先选中一张图片", 2000)
            return

        if self.current_operation_image_widget and self.current_operation_image_widget != self.selected_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)

        self.current_operation_image_widget = self.selected_image_widget
        self.current_operation_mode = "black_border"
        self.current_operation_image_widget.set_operation_mode("black_border")

        if self.preview_widget.enter_operation_mode("black_border"):
            self.preview_widget.update_undo_button_state(self.current_operation_image_widget, "black_border")
            show_info(self, "去黑边模式", "已进入去黑边模式，拖动鼠标绘制要去除的黑边区域", 2000)

    def enter_correct_mode(self):
        if not self.selected_image_widget:
            show_warning(self, "提示", "请先选中一张图片", 2000)
            return

        if self.current_operation_image_widget and self.current_operation_image_widget != self.selected_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)

        self.current_operation_image_widget = self.selected_image_widget
        self.current_operation_mode = "correct"
        self.current_operation_image_widget.set_operation_mode("correct")

        if self.preview_widget.enter_operation_mode("correct"):
            self.preview_widget.update_undo_button_state(self.current_operation_image_widget, "correct")
            show_info(self, "纠偏模式", "已进入纠偏模式，拖动鼠标绘制水平参考线（从左到右）", 2000)

    def exit_operation_mode_for_image(self, image_widget):
        if image_widget:
            image_widget.set_operation_mode(None)
            self.preview_widget.exit_operation_mode()

            self.preview_widget.update_undo_button_state(image_widget, None)
            if self.current_operation_image_widget == image_widget:
                self.current_operation_image_widget = None
                self.current_operation_mode = None

    def perform_operation(self, operation_data, operation_mode):
        if not self.selected_image_widget:
            show_warning(self, "提示", "没有选中的图片", 2000)
            return

        try:
            operation_names = {
                "crop": "裁剪",
                "black_border": "去黑边",
                "correct": "纠偏"
            }
            operation_name = operation_names.get(operation_mode, "操作")

            if operation_mode == "crop":
                success = self.selected_image_widget.crop_and_save_image(operation_data)
            elif operation_mode == "black_border":
                success = self.selected_image_widget.black_border_and_save_image(operation_data)
            else:
                success = self.selected_image_widget.correct_and_save_image(operation_data)

            print(f"{operation_name} 保存失败; success = {success}")

            if success:
                self.selected_image_widget.reload_image()
                processed_pixmap = self.selected_image_widget.get_current_image()
                if processed_pixmap and not processed_pixmap.isNull():
                    self.preview_widget.set_preview_pixmap(processed_pixmap)
                    self.preview_widget.update_undo_button_state(self.selected_image_widget, operation_mode)
                    if operation_mode == "correct":
                        p1, p2 = operation_data[0], operation_data[1]
                        dx = p2.x() - p1.x()
                        dy = p2.y() - p1.y()
                        angle = math.degrees(math.atan2(dy, dx))
                        angle_text = f"{abs(angle):.1f}"
                        show_success(self, f"{operation_name}保存成功", f"图片已自动{operation_name}并保存\n"
                                    f"纠偏角度: {angle_text}°", 2000)
                    else:
                        show_success(self, f"{operation_name}保存成功", f"图片已自动{operation_name}并保存\n"
                                    f"操作尺寸: {operation_data.width()} × {operation_data.height()}", 2000)

                    operation_data = {
                        "task_id": self.task_info.register_id,
                        "task_name": "图片处理",
                        "operator": self.current_user["username"],
                        "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "operator_remark": f"图片处理-执行{operation_name}; 图片: {self.current_image}"
                    }
                    operation_service.save_data([operation_data])

                else:
                    show_warning(self, "提示", f"图片{operation_name}成功但预览更新失败", 2000)
            else:
                show_error(self, "保存失败", f"图片{operation_name}后保存失败，请检查文件权限或磁盘空间", 2000)
        except Exception as e:
            print(f"{operation_name}图片时出错: {e}")
            show_error(self, "错误", f"{operation_name}图片时发生错误: {str(e)}", 2000)

    def perform_crop(self, crop_rect):
        self.perform_operation(crop_rect, "crop")

    def undo_operation(self, image_widget, operation_mode=None):
        if not image_widget:
            show_warning(self, "提示", "没有选中的图片", 2000)
            return False

        try:
            operation_names = {
                "crop": "裁剪",
                "black_border": "去黑边",
                "correct": "纠偏",
                None: "旋转"
            }
            operation_name = operation_names.get(operation_mode, "操作")
            if image_widget.undo_last_operation(operation_mode):
                image_widget.reload_image()
                restored_pixmap = image_widget.get_current_image()
                if restored_pixmap and not restored_pixmap.isNull():
                    self.preview_widget.set_preview_pixmap(restored_pixmap)
                    self.preview_widget.update_undo_button_state(image_widget, operation_mode)
                    show_success(self, "撤销成功", f"已撤销最近一次{operation_name}操作", 2000)
                    return True
                else:
                    show_warning(self, "提示", "撤销成功但预览更新失败", 2000)
                    return False
            else:
                show_info(self, "提示", f"没有可撤销的{operation_name}操作", 2000)
                return False
        except Exception as e:
            logger.error(f"撤销操作时出错: {e}")
            show_error(self, "错误", f"撤销操作时发生错误: {str(e)}", 2000)
            return False

    def undo_crop(self, image_widget):
        self.undo_operation(image_widget, "crop")

    def rotate_and_save_selected_image(self, angle):
        if not self.selected_image_widget:
            show_warning(self, "提示", "请先选中一张图片", 2000)
            return

        try:
            if self.selected_image_widget.rotate_and_save_image(angle):
                self.selected_image_widget.reload_image()
                rotated_pixmap = self.selected_image_widget.get_current_image()

                if rotated_pixmap and not rotated_pixmap.isNull():
                    self.preview_widget.set_preview_pixmap(rotated_pixmap)
                    self.preview_widget.update_undo_button_state(self.selected_image_widget, None)

                    direction = "顺时针" if angle > 0 else "逆时针"
                    abs_angle = abs(angle)
                    show_success(self, "旋转保存成功", f"图片已{direction}旋转{abs_angle}度", 2000)
                    return True
                else:
                    show_error(self, "提示", "图片旋转成功但预览更新失败", 2000)
                    return False
            else:
                logger.error("图片旋转后保存失败，请检查文件权限或磁盘空")
                show_error(self, "保存失败", "图片旋转后保存失败，请检查文件权限或磁盘空间", 2000)
                return False
        except Exception as e:
            logger.error(f"旋转图片时出错: {e}")
            show_error(self, "错误", f"旋转图片时发生错误: {str(e)}", 2000)
            return False

    def load_images_from_folder(self, folder_path):
        if not os.path.exists(folder_path):
            show_warning(self, "警告", f"文件夹不存在: {folder_path}", 2000)
            return

        # 取消并等待上一次加载完成
        if hasattr(self, '_thumb_loader') and self._thumb_loader and self._thumb_loader.isRunning():
            self._thumb_loader.cancel()
            self._thumb_loader.quit()
            if not self._thumb_loader.wait(3000):
                logger.warning("ThumbnailLoader 未能在 3 秒内退出")
            self._thumb_loader.deleteLater()
            self._thumb_loader = None
        if self._zoom_thumb_loader and self._zoom_thumb_loader.isRunning():
            old_zoom_loader = self._zoom_thumb_loader
            old_zoom_loader.cancel()
            old_zoom_loader.quit()
            if old_zoom_loader.wait(300):
                old_zoom_loader.deleteLater()
            else:
                old_zoom_loader.finished.connect(old_zoom_loader.deleteLater)
            self._zoom_thumb_loader = None

        # 收集图片路径
        image_paths = []
        for f in sorted(os.listdir(folder_path)):
            fp = os.path.join(folder_path, f)
            if os.path.isfile(fp) and os.path.splitext(f)[1].lower() in IMG_EXTENSIONS:
                image_paths.append(fp)

        self.total_images = len(image_paths)
        self.gallery_widget.clear_gallery()
        self._all_image_paths = image_paths
        self._path_to_img_widget = {}
        self._loaded_image_count = 0
        self._gallery_loading_batch = False
        self._pending_mark_paths = []
        self._pending_mark_types = {}

        if not image_paths:
            self.image_path_label.setText(folder_path)
            self.current_image = None
            self._update_mark_count_badge()
            return

        self.gallery_widget.update_image_count(self.total_images)
        self.image_path_label.setText(image_paths[0])
        self.current_image = None
        self._restore_gallery_mark_states(folder_path)
        self.load_next_gallery_batch(show_done_message=True)

    def load_next_gallery_batch(self, show_done_message: bool = False):
        if self._gallery_loading_batch:
            return
        if self._loaded_image_count >= len(self._all_image_paths):
            return

        start = self._loaded_image_count
        end = min(start + self._gallery_batch_size, len(self._all_image_paths))
        batch_paths = self._all_image_paths[start:end]
        if not batch_paths:
            return

        tw = self.gallery_widget._thumb_size
        th = int(tw * 1.25)
        for path in batch_paths:
            w = self.gallery_widget.add_placeholder(path, tw, th)
            self._path_to_img_widget[path] = w
            mark_type = self._pending_mark_types.get(path)
            if mark_type:
                w.set_mark_state(mark_type)

        self._loaded_image_count = end
        self._gallery_loading_batch = True

        self._thumb_loader = ThumbnailLoader(
            batch_paths,
            parent=self,
            start_index=start,
            thumb_w=tw,
            thumb_h=th,
        )
        self._thumb_loader.thumbnail_ready.connect(self.gallery_widget.apply_thumbnail)
        self._thumb_loader.finished_all.connect(
            lambda _, done=end, total=len(self._all_image_paths), show=show_done_message:
                self._on_gallery_batch_loaded(done, total, show)
        )
        self._thumb_loader.start()

    def _on_gallery_batch_loaded(self, loaded_count: int, total_count: int, show_done_message: bool = False):
        self._gallery_loading_batch = False
        if show_done_message:
            show_success(
                self,
                "加载完成",
                f"已加载 {loaded_count}/{total_count} 张图片，继续下滚可加载更多",
                1500,
            )
        elif loaded_count >= total_count:
            show_success(self, "加载完成", f"已加载全部 {total_count} 张图片", 1500)

    def refresh_loaded_gallery_thumbnails(self, thumb_w: int, thumb_h: int):
        loaded_paths = self._all_image_paths[:self._loaded_image_count]
        if not loaded_paths:
            return
        if self._zoom_thumb_loader and self._zoom_thumb_loader.isRunning():
            old_loader = self._zoom_thumb_loader
            old_loader.cancel()
            old_loader.quit()
            if old_loader.wait(300):
                old_loader.deleteLater()
            else:
                old_loader.finished.connect(old_loader.deleteLater)

        self._zoom_thumb_loader = ThumbnailLoader(
            loaded_paths,
            parent=self,
            start_index=0,
            thumb_w=thumb_w,
            thumb_h=thumb_h,
        )
        self._zoom_thumb_loader.thumbnail_ready.connect(self.gallery_widget.apply_thumbnail)
        current_loader = self._zoom_thumb_loader
        self._zoom_thumb_loader.finished_all.connect(lambda _: self._clear_zoom_thumb_loader(current_loader))
        self._zoom_thumb_loader.start()

    def _clear_zoom_thumb_loader(self, loader=None):
        if loader is None:
            loader = self._zoom_thumb_loader
        if loader:
            loader.deleteLater()
        if loader is self._zoom_thumb_loader:
            self._zoom_thumb_loader = None

    def _update_mark_count_badge(self):
        count = len(self._pending_mark_paths)
        if not hasattr(self, "mark_count_badge"):
            return
        if count > 0:
            self.mark_count_badge.setText("99+" if count > 99 else str(count))
            self.mark_count_badge.show()
            self.mark_count_badge.raise_()
        else:
            self.mark_count_badge.hide()

    def on_image_selected(self, image_widget, img_path=None):
        if img_path:
            actual_img_path = img_path
            self.current_image = img_path
        elif image_widget and hasattr(image_widget, 'img_path'):
            actual_img_path = image_widget.img_path
        else:
            return
        self.end_all_states_before_switch()
        if self.selected_image_widget:
            try:
                if hasattr(self.selected_image_widget, 'set_selected'):
                    self.selected_image_widget.set_selected(False)
            except RuntimeError:
                self.selected_image_widget = None
        self.selected_image_widget = image_widget
        if image_widget:
            try:
                if hasattr(image_widget, 'set_selected'):
                    image_widget.set_selected(True)
            except RuntimeError:
                self.selected_image_widget = None
        self.preview_widget.set_preview_image(actual_img_path)
        self.preview_widget.update_undo_button_state(image_widget, None)
        self.image_path_label.setText(actual_img_path)

    def end_all_states_before_switch(self):
        if self.current_operation_image_widget:
            self.exit_operation_mode_for_image(self.current_operation_image_widget)
        self.current_operation_image_widget = None
        self.current_operation_mode = None

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请重新登录")
            time.sleep(5)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.image_process.imageProcessTable_window import ImageProcessTableWindow
            image_table_window = ImageProcessTableWindow()
            image_table_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label = QLabel(f"👤 {username} ({userrole})")
        else:
            self.user_label = QLabel("未登录")
            global_cache.set("current_user", {"username": "admin", "role": "管理员"})
            self.update_user_label()

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
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

    # ──────────────────── 质检标记功能（图像处理质检） ────────────────────

    def sing_message_fun(self):
        """质检员对当前选中图片添加图像处理质检标记"""
        if not self.current_user or self.current_user.get("role") not in ["管理员", "质检员"]:
            show_warning(self, "警告", "非管理员或质检员不可标记")
            return
        if not self.task_info or not self.task_info.is_do:
            show_warning(self, "提示", "当前任务未提交，暂不可标记！")
            return
        if not self.current_image:
            show_warning(self, "提示", "请先选中要标记的图片")
            return

        image_name = os.path.basename(self.current_image)

        # ── 查询是否已有历史标记 ──
        existing_marks = []
        try:
            from src.services.task_mark_service import task_mark_service
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
                on_mark_changed=lambda: self._refresh_gallery_mark_state(self.current_image),
            )
            if not history_dlg.exec():
                self._refresh_gallery_mark_state(self.current_image)
                return

        from src.view.common.MarkIssueDialog import MarkIssueDialog
        dlg = MarkIssueDialog(target_name=image_name, mark_stage="图像处理质检")
        if dlg.exec():
            mark_data = dlg.get_data()
            if len(mark_data.get("description", "")) < 6:
                show_warning(self, "提示", "描述标记内容不得为空！")
                return

            save_data = {
                "task_id":      self.task_info.id,
                "batch_number": self.task_info.batch_number,
                "task_node":    self.task_info.task_node,
                "mark_stage":   2,   # 图像处理质检
                "scan_file":    image_name,
                "mark_type":    mark_data.get("mark_type", "其他"),
                "level":        mark_data.get("level", "一般"),
                "description":  mark_data.get("description", ""),
                "inspector":    self.current_user.get("username", ""),
                "mark_date":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_fixed":     False,
            }
            try:
                from src.services.task_mark_service import task_mark_service
                task_mark_service.add_mark(save_data)
                self._set_gallery_mark_state(self.current_image, mark_data.get("mark_type", "已标记"))
                show_success(self, "标记成功",
                             f"已对 {image_name} 标记【{mark_data.get('mark_type', '其他')}】")
            except Exception as e:
                logger.error(f"标记保存失败: {e}")
                show_error(self, "失败", "标记保存失败，请重试")

    def _set_gallery_mark_state(self, image_path: str, mark_type: str = None):
        """显示或清除画廊中对应卡片的标记角标"""
        self._update_pending_mark_cache(image_path, mark_type)
        w = self._path_to_img_widget.get(image_path) if hasattr(self, '_path_to_img_widget') else None
        if w and not w._is_deleted:
            w.set_mark_state(mark_type)

    def _update_pending_mark_cache(self, image_path: str, mark_type: str = None):
        if not image_path:
            return
        if mark_type:
            self._pending_mark_types[image_path] = mark_type
            if image_path not in self._pending_mark_paths:
                self._pending_mark_paths.append(image_path)
                order = {path: idx for idx, path in enumerate(self._all_image_paths)}
                self._pending_mark_paths.sort(key=lambda p: order.get(p, 10 ** 9))
        else:
            self._pending_mark_types.pop(image_path, None)
            if image_path in self._pending_mark_paths:
                self._pending_mark_paths.remove(image_path)
        self._update_mark_count_badge()

    def _refresh_gallery_mark_state(self, image_path: str):
        """操作完成后查库刷新角标"""
        if not image_path or not self.task_info:
            return
        file_name = os.path.basename(image_path)
        try:
            from src.services.task_mark_service import task_mark_service
            pending = task_mark_service.get_pending_marks_by_file(
                task_id=self.task_info.id,
                scan_file=file_name,
            )
            if pending:
                self._set_gallery_mark_state(image_path, pending[0].mark_type)
            else:
                self._set_gallery_mark_state(image_path, None)
        except Exception as e:
            logger.warning(f"刷新标记状态失败: {e}")

    def _restore_gallery_mark_states(self, folder_path: str):
        """切换文件夹后回显数据库中已有的未修复标记"""
        if not self.task_info or not hasattr(self, '_path_to_img_widget'):
            return
        try:
            from src.services.task_mark_service import task_mark_service
            pending_marks = task_mark_service.get_pending_marks_by_folder(
                task_id=self.task_info.id,
                folder_path=folder_path,
            )
            if not pending_marks:
                self._update_mark_count_badge()
                return
            # 文件名 → 完整路径 反查
            name_to_path = {
                os.path.basename(p): p for p in self._all_image_paths
            }
            for mark in pending_marks:
                if not mark.scan_file:
                    continue
                full_path = name_to_path.get(mark.scan_file)
                if full_path:
                    self._set_gallery_mark_state(full_path, mark.mark_type)
            self._update_mark_count_badge()
        except Exception as e:
            logger.warning(f"回显画廊标记失败: {e}")
