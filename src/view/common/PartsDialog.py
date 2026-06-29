# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : PartsDialog.py
# @Desc     : 公共分件弹框

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import ComboBox, LineEdit, MessageBox, PushButton

from src.core.settings import settings
from src.services.archive_stamp_service import archive_stamp_service
from src.utils.NotificationTool import show_error


class PartsDialog(MessageBox):
    def __init__(
        self,
        parent=None,
        current_dir_input_path="",
        current_stamp_value="请选择模版",
    ):
        super().__init__("准备分件", "请选择分件方式，确认后开始分件。", parent)
        self.yesButton.setText("分件")
        self.yesButton.setCursor(Qt.PointingHandCursor)
        self.cancelButton.setText("取消")
        self.cancelButton.setCursor(Qt.PointingHandCursor)

        self.current_dir_input_path = current_dir_input_path or ""
        self.current_stamp_value = current_stamp_value or "请选择模版"

        self._init_ui()

    def _init_ui(self):
        self.split_type_combo = ComboBox()
        self.split_type_combo.addItems(settings.parts_selects)
        self.split_type_combo.setMinimumWidth(160)
        self.split_type_combo.setMinimumHeight(32)

        split_type_label = QLabel("分件方式:")
        split_type_label.setStyleSheet("font-size: 14px; color: #333; margin-top: 8px;")

        split_type_row = QHBoxLayout()
        split_type_row.setSpacing(10)
        split_type_row.addWidget(split_type_label)
        split_type_row.addWidget(self.split_type_combo)
        split_type_row.addStretch(1)

        split_type_widget = QWidget()
        split_type_widget.setLayout(split_type_row)
        self.textLayout.addWidget(split_type_widget)

        self.input_path_edit = LineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("请选择目录 Excel 文件")
        self.input_path_edit.setMinimumWidth(240)
        self.input_path_edit.setText(self.current_dir_input_path)

        input_button = PushButton("导入目录")
        input_button.setCursor(Qt.PointingHandCursor)
        input_button.clicked.connect(self._select_input_file)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        input_row.addWidget(QLabel("目录文件:"))
        input_row.addWidget(self.input_path_edit)
        input_row.addWidget(input_button)
        input_row.addStretch(1)

        self.input_widget = QWidget()
        self.input_widget.setLayout(input_row)
        self.textLayout.addWidget(self.input_widget)

        stamp_list = [
            item.template_name for item in archive_stamp_service.get_all()
        ]
        stamp_list.insert(0, "请选择模版")

        self.stamp_combo = ComboBox()
        self.stamp_combo.addItems(stamp_list)
        self.stamp_combo.setMinimumWidth(160)
        self.stamp_combo.setMinimumHeight(32)
        if self.current_stamp_value in stamp_list:
            self.stamp_combo.setCurrentText(self.current_stamp_value)

        stamp_row = QHBoxLayout()
        stamp_row.setSpacing(10)
        stamp_row.addWidget(QLabel("归档章模板:"))
        stamp_row.addWidget(self.stamp_combo)
        stamp_row.addStretch(1)

        self.stamp_widget = QWidget()
        self.stamp_widget.setLayout(stamp_row)
        self.textLayout.addWidget(self.stamp_widget)

        self.split_type_combo.currentTextChanged.connect(self._update_option_visible)
        self._update_option_visible(self.split_type_combo.currentText())

    def _select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入分件目录", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if not file_path:
            return

        _, file_ext = os.path.splitext(file_path)
        if file_ext.lower() not in [".xlsx", ".xls"]:
            show_error(self, "警告", f"暂不支持当前文件格式; {file_ext}")
            return

        self.input_path_edit.setText(file_path)

    def _update_option_visible(self, split_type):
        self.input_widget.setVisible(split_type == "目录")
        self.stamp_widget.setVisible(split_type == "归档章")

    def get_values(self):
        return {
            "split_type": self.split_type_combo.currentText(),
            "dir_input_path": self.input_path_edit.text().strip(),
            "stamp_value": self.stamp_combo.currentText(),
        }
