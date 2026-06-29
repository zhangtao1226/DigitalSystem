# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : image_window.py
# @Desc      : 扫描列表
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm

import sys
import time

from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QTableWidgetItem,QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, MessageBox, PushButton, PrimaryPushButton,
                            ComboBox, FluentIcon, TableWidget,)
from qframelesswindow import FramelessWindow
from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.services.register_service import register_service
from src.view.common.NavigationLabel import NavigationLabel
from src.utils.NotificationTool import show_warning, show_success, show_error, show_info

class ScanTableWindow(FramelessWindow):
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
        self.current_user = global_cache.get("current_user", None)
        self.init_ui()
        self._is_navigation = False
        self._is_app_exiting = False

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
        task_label = NavigationLabel("扫描任务表", is_clickable=False)
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
        else:
            from src.view.new_main_window import MainWindow
            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def create_table_section(self, parent_layout):
        button_layout = QHBoxLayout()
        button_layout.addStretch()
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
        self.table_widget.setColumnWidth(0, 60)  # ID
        self.table_widget.setColumnWidth(1, 150)  # 档案类别
        self.table_widget.setColumnWidth(2, 60)  # 类型
        self.table_widget.setColumnWidth(3, 120)  # 批次号
        self.table_widget.setColumnWidth(4, 120)  # 起止卷/件号
        self.table_widget.setColumnWidth(5, 120)  # 本人任务起止号
        self.table_widget.setColumnWidth(6, 100)  # 任务分发人
        self.table_widget.setColumnWidth(7, 140)  # 分发日期
        self.table_widget.setColumnWidth(8, 100)  # 处理人
        self.table_widget.setColumnWidth(9, 120)  # 处理日期
        self.table_widget.setColumnWidth(10, 180)  # 状态
        self.table_widget.setColumnWidth(11, 100)  # 操作
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
        self.prev_button.setEnabled(False)  # 初始状态下一页按钮禁用
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
        all_data = task_service.get_list(skip=skip, limit=page_size, task_name="扫 描", status=1, operator=register)
        for item in all_data:
            register_info = register_service.get_by_id(item.register_id)
            item_list = [str(item.id), register_info.archive_type, register_info.category, item.batch_number,
                         f"{item.number_start}-{item.number_end}", f"{item.task_number_start}-{item.task_number_end}",
                         item.dist_officer, item.dist_date.strftime("%Y-%m-%d"), item.operator, item.operator_date.strftime("%Y-%m-%d")]

            task_status = task_service.get_task_progress_desc(item.id)
            item_list.append(task_status)
            item_list.append("")
            self.all_data.append(item_list)


        self.total_rows = task_service.get_total_count(task_name='扫 描', operator=register)
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
        start_index = (self.current_page - 1) * self.current_page_size
        end_index = min(start_index + self.current_page_size, self.total_rows)
        current_data = self.all_data[start_index:end_index]
        for row, data in enumerate(current_data):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)
                    task_info = task_service.get_by_id(data[0])
                    details_button = PrimaryPushButton("开始扫描")
                    details_button.setFixedSize(80, 32)
                    details_button.setCursor(Qt.PointingHandCursor)

                    if not task_info.is_ready :
                        details_button.setEnabled(False)
                    original_row = start_index + row
                    details_button.clicked.connect(lambda checked, r=original_row: self.start_scan_clicked(r))
                    button_layout.addWidget(details_button)
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

    def start_scan_clicked(self, row):
        data = self.all_data[row]
        global_cache.set("current_data", data)
        self._is_navigation = True
        from src.view.scan.scan_window import ScanWindow
        image_window = ScanWindow()
        image_window.showFullScreen()
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