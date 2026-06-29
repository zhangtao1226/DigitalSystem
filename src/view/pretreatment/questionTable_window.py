# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      :
# @Desc      : 问题表
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
import time
from dotenv import load_dotenv
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QLineEdit, QComboBox, QTableWidgetItem,
                               QAbstractItemView, QCheckBox)
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
                            LineEdit, ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
                            SpinBox)

from qframelesswindow import FramelessWindow

from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.services.register_service import register_service
from src.services.registerQuestion_service import register_question_service
from src.utils.NotificationTool import show_success, show_error, show_warning, show_info

load_dotenv(verbose=True)

class QuestionTableWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.resize(1400, 850)
        setTheme(Theme.LIGHT)
        self.task_name = "问题登记表"
        self.current_page = 1
        self.total_pages = 1
        self.page_sizes = [10, 20, 50]
        self.current_page_size = self.page_sizes[0]
        self.total_rows = 0
        self.all_data = []
        self.user_label = QLabel()
        self.current_user = global_cache.get("current_user")
        self.current_question_task = global_cache.get("current_question_task", {})
        self._is_navigation = False
        self._is_app_exiting = False

        self.center()
        self.init_ui()

    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 40, 20, 20)

        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignVCenter)
        top_layout.setSpacing(10)
        title_label = QLabel("问题登记表")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        top_layout.addWidget(title_label)
        top_layout.addStretch(1)

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
        top_layout.addWidget(self.user_label)
        main_layout.addLayout(top_layout)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)

        self.create_table_section(main_layout)
        self.load_all_data()
        self.update_table_display()
        self.setLayout(main_layout)

        self.update_user_label()

    def create_table_section(self, parent_layout):
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(12)

        self.select_all_checkbox = QCheckBox("全选")
        self.select_all_checkbox.setCursor(Qt.PointingHandCursor)
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        toolbar_layout.addWidget(self.select_all_checkbox)

        self.batch_processed_btn = PrimaryPushButton("全部处理")
        self.batch_processed_btn.setFixedSize(100, 34)
        self.batch_processed_btn.setCursor(Qt.PointingHandCursor)
        self.batch_processed_btn.clicked.connect(self.on_batch_processed_clicked)
        toolbar_layout.addWidget(self.batch_processed_btn)
        toolbar_layout.addStretch(1)

        parent_layout.addLayout(toolbar_layout)
        self.create_table(parent_layout)
        self.create_pagination_control(parent_layout)

    def create_table(self, parent_layout):
        self.table_widget = TableWidget()
        headers = ["全选", "问题ID", "批次号", "卷/件号", "问题描述", "记录人", "记录日期", "状态", "操作"]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        self.table_widget.horizontalHeader().sectionClicked.connect(self.on_header_clicked)

        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        self.table_widget.horizontalHeader().setFont(header_font)

        content_font = QFont()
        content_font.setPointSize(10)
        self.table_widget.setFont(content_font)

        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(TableWidget.SelectRows)
        self.table_widget.setSelectionMode(TableWidget.SingleSelection)
        self.table_widget.setBorderVisible(True)
        self.table_widget.setBorderRadius(8)

        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table_widget.setColumnWidth(0, 70)  # 全选
        self.table_widget.setColumnWidth(1, 80)  # 问题ID
        self.table_widget.setColumnWidth(2, 130)  # 批次号
        self.table_widget.setColumnWidth(3, 100)  # 卷/件号
        self.table_widget.setColumnWidth(4, 420)  # 问题描述
        self.table_widget.setColumnWidth(5, 120)  # 记录人
        self.table_widget.setColumnWidth(6, 180)  # 记录日期
        self.table_widget.setColumnWidth(7, 100)  # 状态
        self.table_widget.setColumnWidth(8, 100)  # 操作

        self.table_widget.verticalHeader().setDefaultSectionSize(45)

        parent_layout.addWidget(self.table_widget)

    def create_pagination_control(self, parent_layout):
        pagination_layout = QHBoxLayout()
        pagination_layout.setAlignment(Qt.AlignRight)
        page_size_label = QLabel("每页显示:")
        page_size_label.setStyleSheet("font-size: 12px; color: #666;")

        self.page_size_combo = ComboBox()
        self.page_size_combo.addItems([str(size) for size in self.page_sizes])
        self.page_size_combo.setCurrentText(str(self.current_page_size))
        self.page_size_combo.setFixedWidth(80)
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
        self.page_info_label = QLabel(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")
        self.page_info_label.setStyleSheet("font-size: 12px; color: #666; margin: 0 10px;")

        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.prev_button = PushButton("上一页")
        self.prev_button.setIcon(FluentIcon.PAGE_LEFT)
        self.prev_button.setFixedWidth(100)
        self.prev_button.clicked.connect(self.prev_page)
        self.prev_button.setEnabled(False)
        self.prev_button.setFont(font)

        self.next_button = PushButton("下一页")
        self.next_button.setIcon(FluentIcon.PAGE_RIGHT)
        self.next_button.setFixedWidth(100)
        self.next_button.setFont(font)
        self.next_button.clicked.connect(self.next_page)

        pagination_layout.addWidget(page_size_label)
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addSpacing(20)
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_info_label)
        pagination_layout.addWidget(self.next_button)

        parent_layout.addLayout(pagination_layout)

    def load_all_data(self):
        page_size = int(self.page_size_combo.currentText())
        page_num = int(self.current_page)
        skip = (page_num - 1) * page_size

        self.all_data = []

        condition = {
            "register_id": self.current_question_task.get("register_id"),
            "batch_number": self.current_question_task.get("batch_number"),
        }
        questions = register_question_service.get_data(condition)
        task_number_start = int(self.current_question_task.get("task_number_start", 0))
        task_number_end = int(self.current_question_task.get("task_number_end", 0))

        filtered_questions = []
        for question in questions:
            try:
                volume_number = int(question.volume_number)
            except (TypeError, ValueError):
                continue
            if task_number_start <= volume_number <= task_number_end:
                filtered_questions.append(question)

        self.total_rows = len(filtered_questions)
        page_questions = filtered_questions[skip:skip + page_size]

        for item in page_questions:
            record_time = item.recorder_time.strftime("%Y-%m-%d %H:%M:%S") if item.recorder_time else ""
            status_value = item.status or 0
            status_text = "已处理" if status_value >= 2 else "未处理"
            self.all_data.append([
                str(item.id),
                item.batch_number or "",
                item.volume_number or "",
                item.question_desc or "",
                item.recorder or "",
                record_time,
                status_text,
                status_value,
            ])
        self.calculate_total_pages()

    def calculate_total_pages(self):
        if self.current_page_size == 0:
            self.total_pages = 1
        else:
            self.total_pages = (self.total_rows + self.current_page_size - 1) // self.current_page_size
        self.page_info_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")

        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)

    def update_table_display(self):
        self.table_widget.setRowCount(0)
        if hasattr(self, "select_all_checkbox"):
            self.select_all_checkbox.blockSignals(True)
            self.select_all_checkbox.setChecked(False)
            self.select_all_checkbox.blockSignals(False)

        if self.total_rows == 0:
            return

        self.load_all_data()
        current_data = self.all_data

        for row, data in enumerate(current_data):
            self.table_widget.insertRow(row)
            for col in range(self.table_widget.columnCount()):
                if col == 0:
                    check_widget = QWidget()
                    check_layout = QHBoxLayout(check_widget)
                    check_layout.setContentsMargins(0, 0, 0, 0)
                    check_layout.setAlignment(Qt.AlignCenter)

                    checkbox = QCheckBox()
                    checkbox.setCursor(Qt.PointingHandCursor)
                    checkbox.setEnabled(data[7] < 2)
                    check_layout.addWidget(checkbox)

                    self.table_widget.setCellWidget(row, col, check_widget)
                elif col == self.table_widget.columnCount() - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)

                    details_button = PrimaryPushButton("已处理")
                    details_button.setFixedSize(80, 32)
                    details_button.setCursor(Qt.PointingHandCursor)
                    details_button.setEnabled(data[7] < 2)
                    original_row = row
                    details_button.clicked.connect(lambda checked, r=original_row: self.on_processed_clicked(r))
                    button_layout.addWidget(details_button)

                    button_layout.addStretch()

                    self.table_widget.setCellWidget(row, col, button_widget)
                else:
                    value = data[col - 1]
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_widget.setItem(row, col, item)

    def on_page_size_changed(self, text):
        try:
            new_page_size = int(text)
            if new_page_size != self.current_page_size:
                self.current_page_size = new_page_size
                self.current_page = 1
                self.calculate_total_pages()
                self.update_table_display()
        except ValueError:
            pass

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.calculate_total_pages()
            self.update_table_display()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.calculate_total_pages()
            self.update_table_display()

    def on_details_clicked(self, row):
        data = self.all_data[row]
        content = (
            f"批次号: {data[1]}\n"
            f"卷/件号: {data[2]}\n"
            f"记录人: {data[4]}\n"
            f"记录日期: {data[5]}\n\n"
            f"问题描述: {data[3]}"
        )
        MessageBox("问题详情", content, self).exec()

    def on_header_clicked(self, column):
        if column == 0:
            self.select_all_checkbox.setChecked(not self.select_all_checkbox.isChecked())

    def on_select_all_changed(self, state):
        checked = state == Qt.CheckState.Checked.value
        for row in range(self.table_widget.rowCount()):
            checkbox = self.row_checkbox(row)
            if checkbox and checkbox.isEnabled():
                checkbox.setChecked(checked)

    def row_checkbox(self, row):
        cell_widget = self.table_widget.cellWidget(row, 0)
        if not cell_widget:
            return None
        return cell_widget.findChild(QCheckBox)

    def selected_question_rows(self):
        rows = []
        for row in range(self.table_widget.rowCount()):
            checkbox = self.row_checkbox(row)
            if checkbox and checkbox.isChecked():
                rows.append(row)
        return rows

    def on_processed_clicked(self, row):
        data = self.all_data[row]
        question_id = int(data[0])

        if register_question_service.update(question_id, {"status": 2}):
            show_success(self, "提示", "问题状态已更新为已处理")
            self.load_all_data()
            self.update_table_display()
        else:
            show_error(self, "提示", "问题状态更新失败，请重试")

    def on_batch_processed_clicked(self):
        rows = self.selected_question_rows()
        if not rows:
            show_warning(self, "提示", "请先选择需要处理的问题")
            return

        success_count = 0
        for row in rows:
            data = self.all_data[row]
            if data[7] >= 2:
                continue
            if register_question_service.update(int(data[0]), {"status": 2}):
                success_count += 1

        if success_count > 0:
            show_success(self, "提示", f"已处理 {success_count} 条问题")
            self.load_all_data()
            self.update_table_display()
        else:
            show_warning(self, "提示", "选中的问题无需处理")

    def update_user_label(self):
        if self.current_user:
            username = self.current_user.get("username", "未知用户")
            userrole = self.current_user.get("role", "未知角色")
            self.user_label.setText(f"👤 {username} ({userrole})")
        else:
            self.user_label.setText("未登录")

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        event.accept()

    def close_without_confirm(self):
        self._is_navigation = True
        QTimer.singleShot(100, self.close)
