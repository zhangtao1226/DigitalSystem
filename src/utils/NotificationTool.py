# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : NotificationTool.py
# @Desc     : 
# @Time     : 2025/12/16 10:07
# @Software : PyCharm

from PySide6.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox


def show_success(self, title: str, content: str, duration: int = 3000):
    """显示成功提示"""
    InfoBar.success(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        position=InfoBarPosition.TOP,
        parent=self,
        duration=duration
    )


def show_error(self, title: str, content: str, duration: int = 3000):
    """显示错误提示"""
    InfoBar.error(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        position=InfoBarPosition.TOP,
        parent=self,
        duration=duration
    )


def show_warning(self, title: str, content: str, duration: int = 3000):
    """显示警告提示"""
    InfoBar.warning(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        position=InfoBarPosition.TOP,
        parent=self,
        duration=duration
    )

def show_info(self, title: str, content: str, duration: int = 3000):
    InfoBar.info(
        title=title,
        content=content,
        orient=Qt.Horizontal,
        position=InfoBarPosition.TOP,
        parent=self,
        duration=duration
    )
