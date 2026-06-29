# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : about_page.py
# @Desc     : 系统管理-关于页面
# @Time     : 2025/12/16 09:50
# @Software : PyCharm

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

from src.core.cache_manager import global_cache

class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        # 创建关于卡片
        card = CardWidget()
        card.setFixedSize(600, 500)

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 120, 212, 60))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(25)

        # 应用图标
        icon_label = QLabel()
        icon_pixmap = FluentIcon.INFO.icon().pixmap(80, 80)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(icon_label)

        # 应用标题
        title_label = StrongBodyLabel("数字化加工系统")
        title_label.setFont(QFont("Microsoft YaHei", 28, QFont.Bold))
        title_label.setStyleSheet("color: #1890ff;")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        # 版本信息
        version_label = BodyLabel("版本 2.0.0")
        version_label.setFont(QFont("Microsoft YaHei", 12))
        version_label.setStyleSheet("color: #666666;")
        version_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(version_label)

        # 分隔线
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e8e8e8;")
        card_layout.addWidget(line)

        # 描述信息
        desc_text = """
        <p style='font-size: 14px; color: #333333; line-height: 1.6; text-align: center;'>
            数字化加工系统是一款专业的企业级系统管理工具，<br>
            提供完善的用户管理和角色权限管理功能。
        </p>
        """
        desc_label = QLabel(desc_text)
        desc_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(desc_label)

        # 功能特性
        features_label = StrongBodyLabel("主要特性")
        features_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        features_label.setStyleSheet("color: #333333;")
        features_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(features_label)

        features_text = """
        <ul style='color: #666666; font-size: 13px; line-height: 1.8;'>
            <li>现代化的用户界面设计</li>
            <li>完整的用户管理功能</li>
            <li>灵活的角色权限配置</li>
            <li>数据安全保护机制</li>
            <li>操作日志记录</li>
            <li>响应式布局设计</li>
        </ul>
        """
        features_content = QLabel(features_text)
        features_content.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(features_content)

        # 版权信息
        copyright_label = BodyLabel("© 2025 数字化加工系统 版权所有")
        copyright_label.setFont(QFont("Microsoft YaHei", 10))
        copyright_label.setStyleSheet("color: #999999;")
        copyright_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(copyright_label)

        layout.addWidget(card, alignment=Qt.AlignCenter)
