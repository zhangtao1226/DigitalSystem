# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : StampPreviewWidget.py
# @Time     : 2026/5/13 11:17
# @Desc     : 归档章预览
import json
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QFontMetrics,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QHeaderView,
    QTableWidgetItem, QAbstractItemView, QFrame, QDialog,
    QGridLayout, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QSize

from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    FluentIcon, InfoBar, InfoBarPosition, IconWidget, CardWidget, BodyLabel,
    TableWidget, LineEdit, ComboBox, SwitchButton, CaptionLabel, SpinBox,
    SubtitleLabel, TitleLabel, TransparentPushButton,
)


class StampPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}
        self.setMinimumSize(200, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_template(self, data: dict):
        self._data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        if not self._data:
            painter.setPen(QColor("#cccccc"))
            painter.setFont(QFont("Microsoft YaHei", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无预览")
            painter.end()
            return

        d        = self._data
        show_lbl = bool(d.get('show_field_labels', 1))
        tem_format = (2, 3) if d.get('template_format', 0) == 0 else (2, 4)


        fields_name_list = [value for key, value in json.loads(d.get("fields_json", {})).items() if '_label' in key]
        fields_value_list = [value for key, value in json.loads(d.get("fields_json", {})).items() if '_value' in key]
        fields = list(zip(fields_name_list, fields_value_list))

        self._draw_horizontal(painter, fields, show_lbl, tem_format)

        painter.end()

    def _draw_horizontal(self, painter: QPainter, fields, show_lbl: bool, tem_format: tuple[int, int]):
        n_rows, n_logical_cols = tem_format
        lbl_cw  = 88 if show_lbl else 0
        val_cw  = 72
        cell_h  = 38

        logical_w = lbl_cw + val_cw
        total_w   = logical_w * n_logical_cols
        total_h   = cell_h * n_rows

        ox = (self.width()  - total_w) // 2
        oy = (self.height() - total_h) // 2

        pen = QPen(QColor("#CC0000"), 2)
        painter.setPen(pen)

        lbl_font = QFont("Microsoft YaHei", 12)
        val_font = QFont("Microsoft YaHei", 12, QFont.Bold)

        painter.drawRect(ox, oy, total_w, total_h)

        for row in range(n_rows):
            y = oy + row * cell_h
            if row > 0:
                painter.drawLine(ox, y, ox + total_w, y)

            for col in range(n_logical_cols):
                field_idx = row * n_logical_cols + col
                label, value = fields[field_idx]

                x_logical = ox + col * logical_w

                if col > 0:
                    painter.drawLine(x_logical, oy, x_logical, oy + total_h)

                if show_lbl:
                    painter.drawLine(
                        x_logical + lbl_cw, y,
                        x_logical + lbl_cw, y + cell_h
                    )
                    painter.setFont(lbl_font)
                    painter.drawText(
                        x_logical, y, lbl_cw, cell_h,
                        Qt.AlignCenter, label
                    )
                    painter.setFont(val_font)
                    painter.drawText(
                        x_logical + lbl_cw, y, val_cw, cell_h,
                        Qt.AlignCenter, value
                    )
                else:
                    painter.setFont(val_font)
                    painter.drawText(
                        x_logical, y, val_cw, cell_h,
                        Qt.AlignCenter, value
                    )