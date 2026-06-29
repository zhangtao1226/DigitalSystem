# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : bulkTable_window.py
# @Desc     : 分件表
# @Time     : 2026/3/6 17:04
# @Software : PyCharm

import os
import sys
from dotenv import load_dotenv
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QTableWidgetItem, QAbstractItemView
                               )
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, MessageBox, PushButton, PrimaryPushButton,
                            ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
                            )

from qframelesswindow import FramelessWindow

from src.core.cache_manager import global_cache

from src.services.task_service import task_service
from src.services.register_service import register_service
from src.services.task_mark_service import task_mark_service

from src.view.common.NavigationLabel import NavigationLabel

from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_success, show_error, show_warning, show_info

load_dotenv(verbose=True)

class BulkTableWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)
        self.current_page = 1
        self.total_pages = 1
        self.page_sizes = [10, 20, 50]
        self.current_page_size = self.page_sizes[0]
        self.total_rows = 0
        self.all_data = []

        self._is_navigation = False
        self._is_app_exiting = False

        self.current_user = global_cache.get("current_user")

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
        main_layout.setContentsMargins(40, 40, 40, 40)
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignVCenter)
        top_layout.setSpacing(10)
        self.create_navigation_breadcrumb(top_layout)
        top_layout.addStretch(1)
        self.update_user_label()
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

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_label = NavigationLabel("分件表", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

        from src.view.new_main_window import MainWindow
        main_window = MainWindow()
        main_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def create_table_section(self, parent_layout):
        self.create_table(parent_layout)
        self.create_pagination_control(parent_layout)

    def create_table(self, parent_layout):
        self.table_widget = TableWidget()
        headers = ["ID", "档案类别", "类型", "批次号", "起止卷/件号", "本人任务起止号", "任务分发人", "分发日期", "处理人",
                   "处理日期", "任务进程", "操作"]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
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
        self.table_widget.setColumnWidth(0, 80)  #
        self.table_widget.setColumnWidth(1, 140)  # 档案类别
        self.table_widget.setColumnWidth(2, 60)  # 类型
        self.table_widget.setColumnWidth(3, 140)  # 批次号
        self.table_widget.setColumnWidth(4, 140)  # 起止卷/件号
        self.table_widget.setColumnWidth(5, 140)  # 本人任务起止号
        self.table_widget.setColumnWidth(6, 120)  # 任务分发人
        self.table_widget.setColumnWidth(7, 160)  # 分发日期
        self.table_widget.setColumnWidth(8, 120)  # 处理人
        self.table_widget.setColumnWidth(9, 160)  # 处理日期
        self.table_widget.setColumnWidth(10, 160)  # 状态
        self.table_widget.setColumnWidth(11, 140)  # 操作
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
        if self.current_user['role'] in ['管理员', '质检员']:
            register = None
        else:
            register = self.current_user['username']

        self.all_data = []

        all_data = task_service.get_list(skip=skip, limit=page_size, task_name='分 件', operator=register)
        for item in all_data:
            register_info = register_service.get_by_id(register_id=item.register_id)
            item_list = [str(item.id), register_info.archive_type, register_info.category, item.batch_number,
                         f"{item.number_start}-{item.number_end}", f"{item.task_number_start}-{item.task_number_end}",
                         item.dist_officer, item.dist_date.strftime("%Y-%m-%d"), item.operator,
                         item.operator_date.strftime("%Y-%m-%d")]
            task_status = task_service.get_task_progress_desc(item.id)
            item_list.append(task_status)
            item_list.append("")
            self.all_data.append(item_list)

        self.total_rows = task_service.get_total_count(task_name='分 件', operator=register)
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
        if self.total_rows == 0:
            return

        self.load_all_data()
        current_data = self.all_data

        for row, data in enumerate(current_data):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)

                    confirm_button = PrimaryPushButton("分件")
                    confirm_button.setFixedSize(100, 32)
                    confirm_button.setCursor(Qt.PointingHandCursor)
                    task_info = task_service.get_by_id(data[0])
                    # where = {
                    #     "register_id": task_info.register_id,
                    #     "batch_number": task_info.batch_number,
                    #     "task_node": 2,
                    # }
                    # scan_task_info = task_service.get_data(where)

                    if not task_info.is_ready:
                        confirm_button.setEnabled(False)
                    original_row = row
                    confirm_button.clicked.connect(lambda checked, r=original_row: self.on_confirm_clicked(r))
                    button_layout.addWidget(confirm_button)
                    button_layout.addStretch()
                    self.table_widget.setCellWidget(row, col, button_widget)
                else:
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

    def on_confirm_clicked(self, row):
        task_id = self.all_data[row][0]

        print(f"task_id: {task_id}")
        global_cache.set("task_id", task_id)
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

        from src.view.bulk_breaking.bulk_window import BulkWindow
        bulk_window = BulkWindow()
        bulk_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def update_user_label(self):
        user_info = global_cache.get("current_user")

        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label = QLabel(f"👤 {username} ({userrole})")
        else:
            self.user_label = QLabel("未登录")

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        if self._is_navigation:
            event.accept()
            return

        if not self._is_app_exiting:
            box = MessageBox(
                '确认退出',
                '确定要退出应用程序吗？',
                self
            )
            box.yesButton.setText('退出')
            box.cancelButton.setText('取消')

            if box.exec():
                self._is_app_exiting = True
                event.accept()
                self.logout()
                from src.view.login import LoginWindow
                self.login_window = LoginWindow()
                self.login_window.showFullScreen()
            else:
                event.ignore()
        else:
            event.accept()

    def close_without_confirm(self):
        self._is_navigation = True
        QTimer.singleShot(100, self.close)