# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : NavigationLabel.py
# @Desc      : 
# @Time      : 2026/3/2 17:26
# @Software  : PyCharm

from PySide6.QtGui import QFont, QCursor
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel

class NavigationLabel(QLabel):
    clicked = Signal()
    def __init__(self, text, is_clickable=True, parent=None):
        super().__init__(text, parent)
        self.is_clickable = is_clickable
        font = QFont()
        font.setPointSize(16)
        self.setFont(font)
        if is_clickable:
            self.setStyleSheet("""
                QLabel {
                    color: #0066CC;
                    font-weight: bold;
                }
                QLabel:hover {
                    color: #0088FF;
                    text-decoration: underline;
                }
            """)
            self.setCursor(QCursor(Qt.PointingHandCursor))
        else:
            self.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-weight: normal;
                }
            """)

    def mousePressEvent(self, event):
        if self.is_clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

