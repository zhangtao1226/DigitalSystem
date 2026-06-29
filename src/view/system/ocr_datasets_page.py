# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : ocr_datasets_page.py
# @Time     : 2026/4/16 15:59
# @Desc     :

import os
import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

from PySide6.QtGui import (
    QFont, QPixmap, QImage, QPainter, QKeyEvent, QMouseEvent,
    QColor, QPalette, QBrush, QLinearGradient
)
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QHeaderView, QLabel, QWidget, QLineEdit,
    QComboBox, QTableWidgetItem, QDialog, QCheckBox, QRadioButton, QDialogButtonBox,
    QFileDialog, QScrollArea, QSizePolicy, QLayout, QTreeView, QSplitter,
    QAbstractItemView, QFileSystemModel, QMessageBox, QGraphicsDropShadowEffect,
    QFormLayout, QGroupBox, QGridLayout, QStackedWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import (
    Qt, Signal, QSize, QRect, QPoint, QModelIndex, QDir, QTimer,
    QPropertyAnimation, QEasingCurve, Slot
)
from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    LineEdit, ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
    SpinBox, TextEdit, CheckBox, IconWidget, TreeView, TeachingTip,
    TeachingTipTailPosition, InfoBarIcon, NavigationInterface, NavigationItemPosition,
    CardWidget, PillPushButton, Dialog, BodyLabel, PrimaryToolButton, ToolButton,
    TransparentToolButton, setThemeColor, NavigationWidget, NavigationPanel,
    FluentWindow, NavigationItemPosition, HyperlinkButton, SubtitleLabel, setFont, ListWidget
)
from qframelesswindow import FramelessWindow, StandardTitleBar

class OcrDatasetsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)

        title_icon = IconWidget(FluentIcon.PEOPLE)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)

        title_label = StrongBodyLabel("OCR数据集")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 按钮栏
        btn_container = CardWidget()
        btn_container.setFixedHeight(70)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(15)
        btn_layout.setContentsMargins(20, 15, 20, 15)

        self.add_btn = PrimaryPushButton("添加新模板")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedSize(96, 36)

        self.refresh_btn = PrimaryPushButton("刷新")
        self.refresh_btn.setFixedSize(96, 36)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_btn)
        layout.addWidget(btn_container)

        # 创建表格区域
        self.create_table_section(layout)
        # self.load_all_data()
        # self.update_table_display()

        # 连接信号
        # self.add_btn.clicked.connect(self.add_user)
        # self.refresh_btn.clicked.connect(self.refresh_user_table)

    def create_table_section(self, parent_layout):
        """创建表格区域"""
        # 创建表格
        # self.create_table(parent_layout)
        # 创建分页控件
        # self.create_pagination_control(parent_layout)
        pass