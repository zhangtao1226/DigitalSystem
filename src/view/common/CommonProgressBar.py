# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : CommonProgressBar.py
# @Desc     : 公共进度条

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton


class CommonProgressBar(QWidget):
    canceled = Signal()

    def __init__(
        self,
        title="处理中",
        message="请稍候...",
        show_cancel=False,
        parent=None,
    ):
        super().__init__(parent)
        self._total = 100
        self._current = 0
        self._init_ui(title, message, show_cancel)

    def _init_ui(self, title, message, show_cancel):
        self.setStyleSheet("""
            QWidget#progressContainer {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            QLabel#progressTitle {
                font-size: 16px;
                font-weight: bold;
                color: #333;
            }
            QLabel#progressMessage {
                font-size: 13px;
                color: #666;
            }
            QLabel#progressPercent {
                font-size: 13px;
                color: #0066cc;
                font-weight: bold;
            }
            QProgressBar {
                height: 12px;
                border: none;
                border-radius: 6px;
                background-color: #e8f3ff;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #1677ff;
            }
        """)

        self.setObjectName("progressContainer")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("progressTitle")

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("progressPercent")
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.percent_label)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("progressMessage")
        self.message_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self._total)
        self.progress_bar.setValue(self._current)
        self.progress_bar.setTextVisible(False)

        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.message_label)
        main_layout.addWidget(self.progress_bar)

        self.cancel_button = PushButton("取消")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.canceled.emit)
        self.cancel_button.setVisible(show_cancel)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def set_title(self, title):
        self.title_label.setText(title)

    def set_message(self, message):
        self.message_label.setText(message)

    def set_indeterminate(self, message=None):
        if message is not None:
            self.set_message(message)
        self.progress_bar.setRange(0, 0)
        self.percent_label.setText("处理中")

    def set_progress(self, current, total=None, message=None):
        if total is not None:
            self._total = max(1, int(total))
            self.progress_bar.setRange(0, self._total)

        self._current = max(0, min(int(current), self._total))
        self.progress_bar.setValue(self._current)

        percent = int(self._current / self._total * 100)
        self.percent_label.setText(f"{percent}%")

        if message is not None:
            self.set_message(message)

    def reset(self, message="请稍候..."):
        self._current = 0
        self._total = 100
        self.progress_bar.setRange(0, self._total)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.set_message(message)

    def finish(self, message="处理完成"):
        self.set_progress(self._total, self._total, message)


class CommonProgressDialog(QDialog):
    canceled = Signal()

    def __init__(
        self,
        title="处理中",
        message="请稍候...",
        show_cancel=False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedWidth(420)
        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        self.progress_widget = CommonProgressBar(
            title=title,
            message=message,
            show_cancel=show_cancel,
            parent=self,
        )
        self.progress_widget.canceled.connect(self._on_canceled)
        layout.addWidget(self.progress_widget)

    def _on_canceled(self):
        self.canceled.emit()
        self.close()

    def set_title(self, title):
        self.setWindowTitle(title)
        self.progress_widget.set_title(title)

    def set_message(self, message):
        self.progress_widget.set_message(message)

    def set_indeterminate(self, message=None):
        self.progress_widget.set_indeterminate(message)

    def set_progress(self, current, total=None, message=None):
        self.progress_widget.set_progress(current, total, message)

    def reset(self, message="请稍候..."):
        self.progress_widget.reset(message)

    def finish(self, message="处理完成"):
        self.progress_widget.finish(message)
