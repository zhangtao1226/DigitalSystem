# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : StampPreviewDialog.py
# @Time     : 2026/5/13 11:19
# @Desc     : 

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

from src.view.common.StampPreviewWidget import StampPreviewWidget

class StampPreviewDialog(QDialog):
    def __init__(self, template_data: dict, parent=None):
        super().__init__(parent)
        name = template_data.template_name
        self.setWindowTitle(f"归档章预览 — {name}")
        self.setFixedSize(780, 400)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(24, 20, 24, 20)
        vbox.setSpacing(16)

        title = StrongBodyLabel(name)
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        vbox.addWidget(title, alignment=Qt.AlignHCenter)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ececec;")
        vbox.addWidget(sep)

        pw = StampPreviewWidget()
        pw.setMinimumSize(320, 140)
        pw.set_template(self.to_dict(template_data))
        vbox.addWidget(pw)

        vbox.addStretch()

        close_btn = PrimaryPushButton("关闭")
        close_btn.setFixedSize(120, 36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        vbox.addWidget(close_btn, alignment=Qt.AlignHCenter)

    def to_dict(self, data):
        return {
            "template_name": data.template_name,
            "template_format": data.template_format,
            "show_field_labels": bool(data.show_field_labels),
            "fields_json": data.fields_json
        }
