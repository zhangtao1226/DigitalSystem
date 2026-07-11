# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : statistics_table.py
# @Desc      : 统计
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm

from datetime import datetime, timedelta

from dotenv import load_dotenv
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QTableWidgetItem, QDateEdit,
                               )
from PySide6.QtCore import Qt, QTimer, QDate
from qfluentwidgets import (setTheme, Theme, MessageBox, PushButton, PrimaryPushButton,
                            ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
                            )

from qframelesswindow import FramelessWindow

from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.utils.NotificationTool import show_warning
from src.view.common.NavigationLabel import NavigationLabel

load_dotenv(verbose=True)

class StatisticsTableWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("")
        # self.resize(1400, 850)
        #
        # self.center()
        setTheme(Theme.LIGHT)

        self.current_page = 1
        self.total_pages = 1
        self.page_sizes = [10, 20, 50]
        self.current_page_size = self.page_sizes[0]  # 默认每页10行
        self.total_rows = 0
        self.all_data = []  # 存储所有数据
        self._is_navigation = False  # 是否为页面跳转
        self._is_app_exiting = False  # 是否为应用退出

        self.current_user = global_cache.get("current_user")
        self.period_options = ["日", "周", "月", "日期段"]
        self.current_start_date = None
        self.current_end_date = None
        self.current_range_label = ""
        self.initial_filter_context = global_cache.get("statistics_filter_context", {}) or {}
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
        self.create_filter_section(main_layout)
        self.create_table_section(main_layout)
        self.update_table_display()  # 更新表格显示

        self.setLayout(main_layout)
        self.update_user_label()

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_label = NavigationLabel("统计表", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def create_filter_section(self, parent_layout):
        filter_layout = QHBoxLayout()
        filter_layout.setAlignment(Qt.AlignVCenter)
        filter_layout.setSpacing(12)

        label_style = "font-size: 13px; color: #555;"

        period_label = QLabel("统计周期:")
        period_label.setStyleSheet(label_style)
        filter_layout.addWidget(period_label)

        self.period_combo = ComboBox()
        self.period_combo.addItems(self.period_options)
        self.period_combo.setCurrentText("日")
        self.period_combo.setFixedWidth(120)
        self.period_combo.currentTextChanged.connect(self.on_period_changed)
        filter_layout.addWidget(self.period_combo)

        self.start_date_label = QLabel("日期:")
        self.start_date_label.setStyleSheet(label_style)
        filter_layout.addWidget(self.start_date_label)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setFixedWidth(140)
        self.start_date_edit.dateChanged.connect(self.on_start_date_changed)
        filter_layout.addWidget(self.start_date_edit)

        self.end_date_label = QLabel("结束日期:")
        self.end_date_label.setStyleSheet(label_style)
        filter_layout.addWidget(self.end_date_label)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setFixedWidth(140)
        filter_layout.addWidget(self.end_date_edit)

        self.search_button = PrimaryPushButton("查询")
        self.search_button.setFixedWidth(90)
        self.search_button.clicked.connect(self.on_filter_clicked)
        filter_layout.addWidget(self.search_button)

        self.reset_button = PushButton("重置")
        self.reset_button.setFixedWidth(90)
        self.reset_button.clicked.connect(self.on_reset_filter_clicked)
        filter_layout.addWidget(self.reset_button)

        filter_layout.addStretch(1)
        parent_layout.addLayout(filter_layout)

        self.stat_summary_label = QLabel()
        self.stat_summary_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                padding: 0 2px;
            }
        """)
        parent_layout.addWidget(self.stat_summary_label)
        self._apply_initial_filter_context()
        self.on_period_changed(self.period_combo.currentText())

    def _qdate_to_datetime(self, qdate):
        return datetime(qdate.year(), qdate.month(), qdate.day())

    def _date_to_qdate(self, date_value):
        return QDate(date_value.year, date_value.month, date_value.day)

    def _set_end_date(self, date_value):
        self.end_date_edit.blockSignals(True)
        self.end_date_edit.setDate(self._date_to_qdate(date_value))
        self.end_date_edit.blockSignals(False)

    def _apply_initial_filter_context(self):
        if not isinstance(self.initial_filter_context, dict):
            return

        period = self.initial_filter_context.get("period")
        start_date = self.initial_filter_context.get("start_date")
        end_date = self.initial_filter_context.get("end_date")

        if period in self.period_options:
            self.period_combo.setCurrentText(period)
        if isinstance(start_date, datetime):
            self.start_date_edit.setDate(self._date_to_qdate(start_date))
        if period == "日期段" and isinstance(end_date, datetime):
            self.end_date_edit.setDate(self._date_to_qdate(end_date - timedelta(days=1)))

    def _get_selected_range(self):
        period = self.period_combo.currentText()
        start_date = self._qdate_to_datetime(self.start_date_edit.date())
        end_date = self._qdate_to_datetime(self.end_date_edit.date())

        if period == "日":
            range_start = start_date
            range_end = range_start + timedelta(days=1)
            range_label = range_start.strftime("%Y-%m-%d")
        elif period == "周":
            range_start = start_date - timedelta(days=start_date.weekday())
            range_end = range_start + timedelta(days=7)
            range_label = f"{range_start.strftime('%Y-%m-%d')} 至 {(range_end - timedelta(days=1)).strftime('%Y-%m-%d')}"
        elif period == "月":
            range_start = start_date.replace(day=1)
            if range_start.month == 12:
                range_end = range_start.replace(year=range_start.year + 1, month=1)
            else:
                range_end = range_start.replace(month=range_start.month + 1)
            range_label = range_start.strftime("%Y-%m")
        else:
            if end_date < start_date:
                show_warning(self, "日期范围错误", "结束日期不能早于开始日期")
                return None, None, ""
            range_start = start_date
            range_end = end_date + timedelta(days=1)
            range_label = f"{range_start.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"

        return range_start, range_end, range_label

    def _sync_period_date_display(self):
        period = self.period_combo.currentText()
        start_date = self._qdate_to_datetime(self.start_date_edit.date())

        if period == "日期段":
            self.start_date_label.setText("开始日期:")
            self.end_date_label.setVisible(True)
            self.end_date_edit.setVisible(True)
            self.end_date_edit.setEnabled(True)
            return

        self.start_date_label.setText("日期:" if period == "日" else "参考日期:")
        self.end_date_label.setVisible(True)
        self.end_date_edit.setVisible(True)
        self.end_date_edit.setEnabled(False)

        if period == "日":
            display_end = start_date
        elif period == "周":
            display_end = start_date - timedelta(days=start_date.weekday()) + timedelta(days=6)
        else:
            month_start = start_date.replace(day=1)
            if month_start.month == 12:
                next_month = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month = month_start.replace(month=month_start.month + 1)
            display_end = next_month - timedelta(days=1)

        self._set_end_date(display_end)

    def on_period_changed(self, text):
        self._sync_period_date_display()

    def on_start_date_changed(self, date):
        self._sync_period_date_display()

    def on_filter_clicked(self):
        self.current_page = 1
        self.update_table_display()

    def on_reset_filter_clicked(self):
        today = QDate.currentDate()
        global_cache.delete("statistics_filter_context")
        self.period_combo.setCurrentText("日")
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)
        self.current_page = 1
        self.update_table_display()

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请重新登录!")
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.new_main_window import MainWindow
            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def create_table_section(self, parent_layout):
        self.create_table(parent_layout)
        self.create_pagination_control(parent_layout)

    def create_table(self, parent_layout):
        self.table_widget = TableWidget()

        headers = [
            "ID", "用户名", "批次号", "批次起止卷/件号", "本人分配卷/件号",
            "任务状态", "已完成任务段", "涉及流程", "卷/件数", "最后完成时间"
        ]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        self.table_widget.horizontalHeader().setFont(header_font)

        content_font = QFont()
        content_font.setPointSize(10)
        self.table_widget.setFont(content_font)

        # 设置表格属性
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(TableWidget.SelectRows)
        self.table_widget.setSelectionMode(TableWidget.SingleSelection)
        self.table_widget.setBorderVisible(True)
        self.table_widget.setBorderRadius(8)

        from PySide6.QtWidgets import QAbstractItemView
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 设置列宽
        self.table_widget.setColumnWidth(0, 60)  # ID
        self.table_widget.setColumnWidth(1, 130)  # 用户名
        self.table_widget.setColumnWidth(2, 160)  # 批次号
        self.table_widget.setColumnWidth(3, 180)  # 批次起止卷/件号
        self.table_widget.setColumnWidth(4, 180)  # 本人分配卷/件号
        self.table_widget.setColumnWidth(5, 110)  # 任务状态
        self.table_widget.setColumnWidth(6, 180)  # 已完成任务段
        self.table_widget.setColumnWidth(7, 180)  # 涉及流程
        self.table_widget.setColumnWidth(8, 90)  # 卷/件数
        self.table_widget.setColumnWidth(9, 180)  # 最后完成时间

        # 设置行高
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
        start_date, end_date, range_label = self._get_selected_range()
        if start_date is None:
            self.total_rows = 0
            self.calculate_total_pages()
            self.stat_summary_label.setText("请选择正确的日期范围")
            return

        self.current_start_date = start_date
        self.current_end_date = end_date
        self.current_range_label = range_label
        global_cache.set("statistics_filter_context", {
            "period": self.period_combo.currentText(),
            "range_label": range_label,
            "start_date": start_date,
            "end_date": end_date,
        })

        operator = None
        if self.current_user and self.current_user.get("role") != "管理员":
            operator = self.current_user.get("username")

        self.total_rows = task_service.get_completed_statistics_count(
            operator=operator,
            start_date=start_date,
            end_date=end_date,
        )
        all_data = task_service.get_completed_statistics(
            skip=skip,
            limit=page_size,
            operator=operator,
            start_date=start_date,
            end_date=end_date,
        )
        summary = task_service.get_completed_statistics_summary(
            operator=operator,
            start_date=start_date,
            end_date=end_date,
        )

        for index, item in enumerate(all_data, start=skip + 1):
            self.all_data.append({
                "index": index,
                "operator": item.get("operator") or "未知用户",
                "batch_count": item.get("batch_count") or 0,
                "task_count": item.get("task_count") or 0,
                "workflow_count": item.get("workflow_count") or 0,
                "batch_numbers": item.get("batch_numbers") or "",
                "batch_ranges": item.get("batch_ranges") or "",
                "assigned_segments": item.get("assigned_segments") or "",
                "task_statuses": item.get("task_statuses") or "",
                "completed_segments": item.get("completed_segments") or "",
                "workflow_names": item.get("workflow_names") or "",
                "volume_count": item.get("volume_count") or 0,
                "first_done_at": item.get("first_done_at"),
                "last_done_at": item.get("last_done_at"),
            })

        self.calculate_total_pages()
        self.stat_summary_label.setText(
            f"统计范围：{self.period_combo.currentText()}（{range_label}）  "
            f"用户数：{summary['operator_count']}  "
            f"完成批次：{summary['batch_count']}  "
            f"完成任务段：{summary['task_count']}  "
            f"涉及流程：{summary['workflow_count']}  "
            f"卷/件数：{summary['volume_count']}"
        )

    def calculate_total_pages(self):

        if self.current_page_size == 0:
            self.total_pages = 1
        else:
            self.total_pages = max(1, (self.total_rows + self.current_page_size - 1) // self.current_page_size)

        self.page_info_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")

        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)

    def update_table_display(self):
        self.table_widget.setRowCount(0)

        self.load_all_data()

        if self.total_rows == 0:
            return

        current_data = self.all_data

        for row, data in enumerate(current_data):
            self.table_widget.insertRow(row)
            row_values = [
                str(data["index"]),
                data["operator"],
                data["batch_numbers"],
                data["batch_ranges"],
                data["assigned_segments"],
                data["task_statuses"],
                data["completed_segments"],
                data["workflow_names"],
                str(data["volume_count"]),
                data["last_done_at"].strftime("%Y-%m-%d %H:%M:%S") if data["last_done_at"] else "",
            ]
            for col, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_widget.setItem(row, col, item)

    def on_page_size_changed(self, text):
        try:
            new_page_size = int(text)
            if new_page_size != self.current_page_size:
                self.current_page_size = new_page_size
                self.current_page = 1  # 重置到第一页
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
