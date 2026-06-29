# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : main_window.py
# @Desc      : 主窗口
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
from dotenv import load_dotenv
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QTableWidgetItem, QTabWidget)
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, MessageBox, PushButton, PrimaryPushButton,
                            ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
                            )

from qframelesswindow import FramelessWindow

from src.core.cache_manager import global_cache
from src.view.common.NavigationLabel import NavigationLabel
from src.services.task_service import task_service
from src.services.register_service import register_service
from src.services.registerQuestion_service import register_question_service
from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_info, show_error, show_warning, show_success

load_dotenv(verbose=True)


class TaskTableWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)
        self.tab1_current_page = 1
        self.tab1_total_pages = 1
        self.tab1_page_sizes = [10, 20, 50]
        self.tab1_current_page_size = self.tab1_page_sizes[0]
        self.tab1_total_rows = 0
        self.tab1_all_data = []
        self.tab2_current_page = 1
        self.tab2_total_pages = 1
        self.tab2_page_sizes = [10, 20, 50]
        self.tab2_current_page_size = self.tab2_page_sizes[0]
        self.tab2_total_rows = 0
        self.tab2_all_data = []
        self.user_label = QLabel()
        self.update_user_label()
        self._is_navigation = False
        self._is_app_exiting = False
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
        self.create_navigation_breadcrumb(top_layout)
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
        self.create_tab_widget_section(main_layout)
        self.load_all_data1()
        self.update_table1_display()
        self.load_all_data2()
        self.update_table2_display()
        self.setLayout(main_layout)
        self.update_user_label()

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_label = NavigationLabel("任务分发表", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            return

        from src.view.new_main_window import MainWindow
        main_window = MainWindow()
        main_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def create_tab_widget_section(self, parent_layout):
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                color: #666666;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                color: #0066cc;
                background-color: #e6f3ff;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:hover:!selected {
                background-color: #f5f9ff;
                border-radius: 1px solid #f5f9ff;
            }
        """)
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab1_widget = QWidget()
        self.tab1_layout = QVBoxLayout(self.tab1_widget)
        self.tab1_layout.setSpacing(15)
        self.tab1_layout.setContentsMargins(10, 10, 10, 10)
        self.create_table1(self.tab1_layout)
        self.tab1_pagination_layout = self.create_pagination_control(
            is_tab1=True,
            page_size=self.tab1_current_page_size,
            page_sizes=self.tab1_page_sizes
        )
        self.tab1_layout.addLayout(self.tab1_pagination_layout)
        self.tab_widget.addTab(self.tab1_widget, "未分配表")
        self.tab2_widget = QWidget()
        self.tab2_layout = QVBoxLayout(self.tab2_widget)
        self.tab2_layout.setSpacing(15)
        self.tab2_layout.setContentsMargins(10, 10, 10, 10)
        self.create_table2(self.tab2_layout)
        self.tab2_pagination_layout = self.create_pagination_control(
            is_tab1=False,
            page_size=self.tab2_current_page_size,
            page_sizes=self.tab2_page_sizes
        )
        self.tab2_layout.addLayout(self.tab2_pagination_layout)
        self.tab_widget.addTab(self.tab2_widget, "已分配任务表")
        parent_layout.addWidget(self.tab_widget)

    def create_table2(self, parent_layout):
        self.table_widget2 = TableWidget()
        # headers = ["任务ID", "任务名称", "批次号", "类型", "起止卷/件号", "分发人", "分发日期", "操作人", "任务段", "操作日期", "状态", "任务进程", "操作"]
        headers = ["任务ID", "任务名称", "批次号", "类型", "起止卷/件号", "分发人", "分发日期", "操作人", "任务段", "操作日期", "任务进程", "操作"]
        self.table_widget2.setColumnCount(len(headers))
        self.table_widget2.setHorizontalHeaderLabels(headers)
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        self.table_widget2.horizontalHeader().setFont(header_font)
        content_font = QFont()
        content_font.setPointSize(10)
        self.table_widget2.setFont(content_font)
        self.table_widget2.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget2.setAlternatingRowColors(True)
        self.table_widget2.setSelectionBehavior(TableWidget.SelectRows)
        self.table_widget2.setSelectionMode(TableWidget.SingleSelection)
        self.table_widget2.setBorderVisible(True)
        self.table_widget2.setBorderRadius(8)
        from PySide6.QtWidgets import QAbstractItemView
        self.table_widget2.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget2.setColumnWidth(0, 100)    # 任务ID
        self.table_widget2.setColumnWidth(1, 150)   # 任务名称
        self.table_widget2.setColumnWidth(2, 140)   # 批次号
        self.table_widget2.setColumnWidth(3, 140)    # 类型
        self.table_widget2.setColumnWidth(4, 140)   # 起止卷/件号
        self.table_widget2.setColumnWidth(5, 150)   # 分发人
        self.table_widget2.setColumnWidth(6, 260)   # 分发日期
        self.table_widget2.setColumnWidth(7, 150)   # 操作人
        self.table_widget2.setColumnWidth(8, 100)   # 任务段号
        self.table_widget2.setColumnWidth(9, 180)   # 操作日期
        # self.table_widget2.setColumnWidth(10, 140)   # 状态
        self.table_widget2.setColumnWidth(10, 180)   # 任务进程
        self.table_widget2.setColumnWidth(11, 160)  # 操作
        self.table_widget2.verticalHeader().setDefaultSectionSize(45)
        parent_layout.addWidget(self.table_widget2)

    def create_table1(self, parent_layout):
        self.table_widget1 = TableWidget()
        headers = ["登记ID", "档案类别", "类型", "批次号", "起止卷/件号", "登记日期", "登记人", "状态", "是否记录问题", "操作"]
        self.table_widget1.setColumnCount(len(headers))
        self.table_widget1.setHorizontalHeaderLabels(headers)
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        self.table_widget1.horizontalHeader().setFont(header_font)
        content_font = QFont()
        content_font.setPointSize(10)
        self.table_widget1.setFont(content_font)
        self.table_widget1.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget1.setAlternatingRowColors(True)
        self.table_widget1.setSelectionBehavior(TableWidget.SelectRows)
        self.table_widget1.setSelectionMode(TableWidget.SingleSelection)
        self.table_widget1.setBorderVisible(True)
        self.table_widget1.setBorderRadius(8)
        from PySide6.QtWidgets import QAbstractItemView
        self.table_widget1.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget1.setColumnWidth(0, 100)   # 登记ID
        self.table_widget1.setColumnWidth(1, 160)  # 档案类别
        self.table_widget1.setColumnWidth(2, 140)   # 档案类型
        self.table_widget1.setColumnWidth(3, 140)  # 批次号
        self.table_widget1.setColumnWidth(4, 140)  # 起止卷/件号
        self.table_widget1.setColumnWidth(5, 260)  # 登记日期
        self.table_widget1.setColumnWidth(6, 150)  # 登记人
        self.table_widget1.setColumnWidth(7, 180)  # 状态
        self.table_widget1.setColumnWidth(8, 120)  # 是否登记问题
        self.table_widget1.setColumnWidth(9, 140)  # 操作
        self.table_widget1.verticalHeader().setDefaultSectionSize(45)
        parent_layout.addWidget(self.table_widget1)

    def create_pagination_control(self, is_tab1, page_size, page_sizes):
        pagination_layout = QHBoxLayout()
        pagination_layout.setAlignment(Qt.AlignRight)
        page_size_label = QLabel("每页显示:")
        page_size_label.setStyleSheet("font-size: 12px; color: #666;")
        page_size_combo = ComboBox()
        page_size_combo.addItems([str(size) for size in page_sizes])
        page_size_combo.setCurrentText(str(page_size))
        page_size_combo.setFixedWidth(80)
        page_info_label = QLabel()
        if is_tab1:
            self.tab1_page_info_label = page_info_label
            self.tab1_page_size_combo = page_size_combo
            self.tab1_prev_button = PushButton("上一页")
            self.tab1_next_button = PushButton("下一页")
            page_size_combo.currentTextChanged.connect(self.on_tab1_page_size_changed)
            self.tab1_prev_button.clicked.connect(self.tab1_prev_page)
            self.tab1_next_button.clicked.connect(self.tab1_next_page)
            page_info_label.setText(f"第 {self.tab1_current_page} 页 / 共 {self.tab1_total_pages} 页")
        else:
            self.tab2_page_info_label = page_info_label
            self.tab2_page_size_combo = page_size_combo
            self.tab2_prev_button = PushButton("上一页")
            self.tab2_next_button = PushButton("下一页")
            page_size_combo.currentTextChanged.connect(self.on_tab2_page_size_changed)
            self.tab2_prev_button.clicked.connect(self.tab2_prev_page)
            self.tab2_next_button.clicked.connect(self.tab2_next_page)
            page_info_label.setText(f"第 {self.tab2_current_page} 页 / 共 {self.tab2_total_pages} 页")
        page_info_label.setStyleSheet("font-size: 12px; color: #666; margin: 0 10px;")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        prev_button = self.tab1_prev_button if is_tab1 else self.tab2_prev_button
        prev_button.setIcon(FluentIcon.PAGE_LEFT)
        prev_button.setFixedWidth(100)
        prev_button.setCursor(Qt.PointingHandCursor)
        prev_button.setEnabled(False)
        prev_button.setFont(font)
        next_button = self.tab1_next_button if is_tab1 else self.tab2_next_button
        next_button.setIcon(FluentIcon.PAGE_RIGHT)
        next_button.setFixedWidth(100)
        next_button.setFont(font)
        next_button.setCursor(Qt.PointingHandCursor)
        next_button.setEnabled(False)
        pagination_layout.addWidget(page_size_label)
        pagination_layout.addWidget(page_size_combo)
        pagination_layout.addSpacing(20)
        pagination_layout.addWidget(prev_button)
        pagination_layout.addWidget(page_info_label)
        pagination_layout.addWidget(next_button)
        return pagination_layout

    def load_all_data2(self):
        page_size = int(self.tab2_page_size_combo.currentText())
        page_num = int(self.tab2_current_page)
        skip = (page_num - 1) * page_size
        self.tab2_all_data = []
        all_data = task_service.get_list(skip=skip, limit=page_size)
        for task in all_data:
            register_info = register_service.get_by_id(task.register_id)
            item_list = [str(task.id), task.task_name, task.batch_number, register_info.category, f"{task.number_start}-{task.number_end}",
                         task.dist_officer, task.dist_date.strftime("%Y-%m-%d"), task.operator,
                         f"{task.task_number_start}-{task.task_number_end}", task.operator_date.strftime("%Y-%m-%d %H:%M:%S")]

            task_status = task_service.get_task_progress_desc(task.id)
            item_list.append(task_status)
            item_list.append("")
            self.tab2_all_data.append(item_list)
        self.tab2_total_rows = task_service.get_total_count()
        self.calculate_tab2_total_pages()

    def load_all_data1(self):
        page_size = int(self.tab1_page_size_combo.currentText())
        page_num = int(self.tab1_current_page)
        skip = (page_num - 1) * page_size
        self.tab1_all_data = []
        all_data = register_service.get_list(skip=skip, limit=page_size, is_distribute=False)
        for item in all_data:
            item_list = [str(item.id), item.archive_type, item.category, item.batch_number, f"{item.number_start}-{item.number_end}",
                        item.register_date.strftime("%Y-%m-%d %H:%M:%S"), item.register]

            item_list.append("领卷登记已保存" if item.status == 0 else "领卷登记已提交")
            has_questions = register_question_service.get_register_id(item.id)
            item_list.append("是" if has_questions else "否")

            item_list.append("")
            self.tab1_all_data.append(item_list)
        filters = {"is_distribute":False}
        self.tab1_total_rows = register_service.get_total_count(**filters)
        self.calculate_tab1_total_pages()

    def calculate_tab1_total_pages(self):
        if self.tab1_current_page_size == 0:
            self.tab1_total_pages = 1
        else:
            self.tab1_total_pages = (self.tab1_total_rows + self.tab1_current_page_size - 1) // self.tab1_current_page_size

        self.tab1_page_info_label.setText(f"第 {self.tab1_current_page} 页 / 共 {self.tab1_total_pages} 页")

        self.tab1_prev_button.setEnabled(self.tab1_current_page > 1)
        self.tab1_next_button.setEnabled(self.tab1_current_page < self.tab1_total_pages)

    def calculate_tab2_total_pages(self):
        if self.tab2_current_page_size == 0:
            self.tab2_total_pages = 1
        else:
            self.tab2_total_pages = (self.tab2_total_rows + self.tab2_current_page_size - 1) // self.tab2_current_page_size

        self.tab2_page_info_label.setText(f"第 {self.tab2_current_page} 页 / 共 {self.tab2_total_pages} 页")

        self.tab2_prev_button.setEnabled(self.tab2_current_page > 1)
        self.tab2_next_button.setEnabled(self.tab2_current_page < self.tab2_total_pages)

    def update_table2_display(self):
        self.table_widget2.setRowCount(0)

        if self.tab2_total_rows == 0:
            return

        self.load_all_data2()

        current_data = self.tab2_all_data

        for row, data in enumerate(current_data):
            self.table_widget2.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)
                    task_info = task_service.get_by_id(data[0])

                    details_button = PrimaryPushButton("修改任务")
                    details_button.setFixedSize(80, 32)
                    if task_info.status == 1:
                        details_button.setEnabled(False)
                    details_button.setCursor(Qt.PointingHandCursor)

                    original_row = row
                    details_button.clicked.connect(lambda checked, r=original_row: self.on_task_clicked(r))
                    button_layout.addWidget(details_button)

                    button_layout.addStretch()

                    self.table_widget2.setCellWidget(row, col, button_widget)
                else:
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_widget2.setItem(row, col, item)

    def update_table1_display(self):
        self.table_widget1.setRowCount(0)
        if self.tab1_total_rows == 0:
            return
        self.load_all_data1()
        current_data = self.tab1_all_data
        for row, data in enumerate(current_data):
            self.table_widget1.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)

                    details_button = PrimaryPushButton("分发任务")
                    details_button.setFixedSize(80, 32)
                    details_button.setCursor(Qt.PointingHandCursor)

                    register_info = register_service.get_by_id(data[0])

                    if register_info.task_node == 0:
                        details_button.setEnabled(False)

                    original_row = row
                    details_button.clicked.connect(lambda checked, r=original_row: self.on_start_task_clicked(r))
                    button_layout.addWidget(details_button)

                    button_layout.addStretch()

                    self.table_widget1.setCellWidget(row, col, button_widget)
                else:
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_widget1.setItem(row, col, item)

    def on_tab1_page_size_changed(self, text):
        try:
            new_page_size = int(text)
            if new_page_size != self.tab1_current_page_size:
                self.tab1_current_page_size = new_page_size
                self.tab1_current_page = 1
                self.calculate_tab1_total_pages()
                self.update_table1_display()
        except ValueError:
            pass

    def on_tab2_page_size_changed(self, text):
        try:
            new_page_size = int(text)
            if new_page_size != self.tab2_current_page_size:
                self.tab2_current_page_size = new_page_size
                self.tab2_current_page = 1
                self.calculate_tab2_total_pages()
                self.update_table2_display()
        except ValueError:
            pass

    def tab1_prev_page(self):
        if self.tab1_current_page > 1:
            self.tab1_current_page -= 1
            self.calculate_tab1_total_pages()
            self.update_table1_display()

    def tab2_prev_page(self):
        if self.tab2_current_page > 1:
            self.tab2_current_page -= 1
            self.calculate_tab2_total_pages()
            self.update_table2_display()

    def tab1_next_page(self):
        if self.tab1_current_page < self.tab1_total_pages:
            self.tab1_current_page += 1
            self.calculate_tab1_total_pages()
            self.update_table1_display()

    def tab2_next_page(self):
        if self.tab2_current_page < self.tab2_total_pages:
            self.tab2_current_page += 1
            self.calculate_tab2_total_pages()
            self.update_table2_display()

    def on_task_clicked(self, row):
        current_data = self.tab2_all_data[row]
        global_cache.set("current_data", current_data)
        global_cache.set("current_type", 2)
        self._is_navigation = True
        from src.view.task_window.taskAdd_window import TaskWindow
        task_window = TaskWindow()
        task_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def on_start_task_clicked(self, row):
        current_data = self.tab1_all_data[row]
        global_cache.set("current_data", current_data)
        global_cache.set("current_type", 1)
        self._is_navigation = True
        if global_cache.get("current_user") is None:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            return

        from src.view.task_window.taskAdd_window import TaskWindow
        task_window = TaskWindow()
        task_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def update_user_label(self):
        self.current_user = global_cache.get("current_user")
        if self.current_user:
            username = self.current_user.get("username", "未知用户")
            userrole = self.current_user.get("role", "未知角色")
            self.user_label.setText(f"👤 {username} ({userrole})")
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")

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