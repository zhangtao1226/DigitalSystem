# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : home_page.py
# @Desc     : 系统管理-主页面
# @Time     : 2025/12/16 09:12
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

class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        # 创建欢迎卡片
        card = CardWidget()
        card.setFixedSize(700, 450)

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 120, 212, 60))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(25)

        # # 图标
        # icon_label = QLabel()
        # icon_pixmap = FluentIcon.SETTING.icon().pixmap(64, 64)
        # icon_label.setPixmap(icon_pixmap)
        # icon_label.setAlignment(Qt.AlignCenter)
        # card_layout.addWidget(icon_label)

        # 欢迎标题
        title_label = StrongBodyLabel("欢迎使用数字化加工系统")
        title_label.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
        title_label.setStyleSheet("color: #1890ff;")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        # 系统信息
        info_label = BodyLabel(
            "本系统提供完整的用户管理、角色管理功能\n"
            "采用现代化界面设计，操作简单直观\n"
            "请从左侧导航栏选择需要管理的功能模块"
        )
        info_label.setFont(QFont("Microsoft YaHei", 13))
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #666666; line-height: 1.6;")
        card_layout.addWidget(info_label)

        # 功能卡片容器
        # features_layout = QHBoxLayout()
        # features_layout.setSpacing(20)
        # features_layout.setContentsMargins(20, 20, 20, 20)
        #
        # # 用户管理卡片
        # feature_card1 = self.create_feature_card("用户管理", "管理所有系统用户", FluentIcon.PEOPLE, "#1890ff")
        # features_layout.addWidget(feature_card1)
        #
        # # 角色管理卡片
        # feature_card2 = self.create_feature_card("角色管理", "管理系统角色权限", FluentIcon.CERTIFICATE, "#52c41a")
        # features_layout.addWidget(feature_card2)
        #
        # # 档案管理卡片
        # archival_card = self.create_feature_card("档案门类管理", "管理档案门类", FluentIcon.DOCUMENT, "#52c41a")
        # features_layout.addWidget(archival_card)
        #
        # # 工作流程配置卡片
        # workConfig_card = self.create_feature_card("工作流程配置管理", "配置工作流程", FluentIcon.TILES, "#52c41a")
        # features_layout.addWidget(workConfig_card)
        #
        # card_layout.addLayout(features_layout)

        layout.addWidget(card, alignment=Qt.AlignCenter)

    def create_feature_card(self, title: str, desc: str, icon, color: str) -> CardWidget:
        """创建功能卡片"""
        card = CardWidget()
        card.setFixedSize(200, 150)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(20, 20, 20, 20)

        # 图标
        icon_widget = IconWidget(icon)
        icon_widget.setFixedSize(40, 40)
        icon_widget.setStyleSheet(f"color: {color};")
        card_layout.addWidget(icon_widget, alignment=Qt.AlignCenter)

        # 标题
        title_label = StrongBodyLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {color};")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        # 描述
        desc_label = BodyLabel(desc)
        desc_label.setFont(QFont("Microsoft YaHei", 11))
        desc_label.setStyleSheet("color: #666666;")
        desc_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(desc_label)

        return card
