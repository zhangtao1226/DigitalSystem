# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : dirTable_window.py
# @Desc      : 目录录入/校对表
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
import json
import time
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QLineEdit, QComboBox, QTableWidgetItem,
                               QFileDialog, QDialog, QAbstractItemView, QCheckBox)
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
                            LineEdit, ComboBox, FluentIcon, TableWidget, InfoBar, InfoBarPosition,
                            SpinBox)

from qframelesswindow import FramelessWindow

from src.core.settings import settings
from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.scan_service import scan_service
from src.services.task_service import task_service
from src.services.register_service import register_service
from src.services.director_service import director_service
from src.utils.NotificationTool import show_error, show_warning, show_success
from src.view.common.NavigationLabel import NavigationLabel

load_dotenv()

class DirTableWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        # self.center()
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
        task_label = NavigationLabel("目录录入/校对", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请重新登录")
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
                   "处理日期", "任务进程", "是否导入目录", "操作"]
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
        from PySide6.QtWidgets import QAbstractItemView
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setColumnWidth(0, 60)  # 档案类别
        self.table_widget.setColumnWidth(1, 120)  # 档案类别
        self.table_widget.setColumnWidth(2, 60)  # 类型
        self.table_widget.setColumnWidth(3, 120)  # 批次号
        self.table_widget.setColumnWidth(4, 120)  # 起止卷/件号
        self.table_widget.setColumnWidth(5, 120)  # 本人任务起止号
        self.table_widget.setColumnWidth(6, 100)  # 任务分发人
        self.table_widget.setColumnWidth(7, 160)  # 分发日期
        self.table_widget.setColumnWidth(8, 100)  # 处理人
        self.table_widget.setColumnWidth(9, 160)  # 处理日期
        self.table_widget.setColumnWidth(10, 160)  # 状态
        self.table_widget.setColumnWidth(11, 140)  # 是否导入目录
        self.table_widget.setColumnWidth(12, 340)  # 操作

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

        if self.current_user['role'] in ["管理员", "质检员"]:
            register = None
        else:
            register = self.current_user['username']

        self.all_data = []

        all_data = task_service.get_list(skip=skip, limit=page_size, task_name="目录录入/校对", operator=register)
        for item in all_data:
            register_info = register_service.get_by_id(item.register_id)
            item_list = [str(item.id), register_info.archive_type, register_info.category, item.batch_number,
                         f"{item.number_start}-{item.number_end}", f"{item.task_number_start}-{item.task_number_end}",
                         item.dist_officer, item.dist_date.strftime("%Y-%m-%d"), item.operator, item.operator_date.strftime("%Y-%m-%d")]
            task_status = task_service.get_task_progress_desc(item.id)
            item_list.append(task_status)

            if register_info.is_import:
                item_list.append("是")
            else:
                item_list.append("否")
            item_list.append("")

            self.all_data.append(item_list)

        self.total_rows = task_service.get_total_count(task_name='目录录入/校对', operator=register)
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

        self.current_page_data = self.all_data

        for row, data in enumerate(self.current_page_data):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)
                    # 查看详情按钮
                    task_info = task_service.get_by_id(data[0])

                    details_button = PrimaryPushButton("开始录入/校对")
                    details_button.setFixedSize(120, 32)
                    details_button.setCursor(Qt.PointingHandCursor)

                    details_button.clicked.connect(lambda checked, r=row: self.on_details_clicked(r))
                    button_layout.addWidget(details_button)

                    inputs_button = PrimaryPushButton("导入目录")
                    inputs_button.setFixedSize(90, 32)
                    inputs_button.setCursor(Qt.PointingHandCursor)
                    inputs_button.clicked.connect(lambda checked, r=row: self.on_inputs_clicked(r))
                    button_layout.addWidget(inputs_button)

                    view_button = PrimaryPushButton("查看目录")
                    view_button.setFixedSize(90, 32)
                    view_button.setCursor(Qt.PointingHandCursor)
                    view_button.clicked.connect(lambda checked, r=row: self.on_view_directory_clicked(r))
                    button_layout.addWidget(view_button)

                    if not task_info.is_ready:
                        details_button.setEnabled(False)
                        inputs_button.setEnabled(False)
                        view_button.setEnabled(False)

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

    def on_details_clicked(self, row):
        global_cache.set("current_data", self.current_page_data[row])
        self._is_navigation = True
        from src.view.dir_recognition.dir_window import DirWindow
        dir_window = DirWindow()
        dir_window.showFullScreen()
        QTimer.singleShot(100, self.close)

    def on_inputs_clicked(self, row):
        data = self.current_page_data[row]
        task_info = task_service.get_by_id(data[0])
        if task_info.is_do:
            show_warning(self, "警告", "该任务已经完成, 不可再导入目录!")
            return

        register_info = register_service.get_by_id(task_info.register_id)
        start_number, end_number = register_info.number_start, register_info.number_end

        file_path = QFileDialog.getOpenFileName()
        if not file_path[0]:
            return
        file_name, file_ext = os.path.splitext(file_path[0])
        # print(f"file_name = {file_name}; file_ext = {file_ext}; {type(file_ext)}")
        try:
            if file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path[0], dtype=str)
                inputs_header = df.columns.values.tolist()
                inputs_header.remove("序号")

                sheet_name = f"{data[1]}-{'案卷级' if '卷' == data[2] else '文件级'}"
                model_df = pd.read_excel(settings.archives_template_path, sheet_name=sheet_name)
                model_header = model_df["别名"].tolist()

                if inputs_header == model_header:
                    inputs_count = len(df['序号'].tolist())
                    # if inputs_count != ((int(end_number) - int(start_number)) + 1):
                    #     print("目录数不等")
                    #     show_error(self, "警告", "导入的目录条数与当前不等!")
                    #     return
                    # else:

                    inputs_header.insert(0, "序号")
                    director_data_list = []
                    for index, series in df.iterrows():
                        item_dict = dict()
                        item_dict["register_id"] = task_info.register_id
                        item_dict["archive_type"] = data[1]
                        item_dict["category"] = self.get_archive_level(data[2])
                        item_dict["doc_number"] = series["档号"]
                        item_dict["title"] = series.get("题名", "")
                        item_dict["source"] = "导入"
                        item_dict["director_info"] = json.dumps(dict(zip(inputs_header, list(series))), ensure_ascii=False)
                        item_dict["operator"] = self.current_user.get("username")
                        item_dict["create_date"] = datetime.now()
                        item_dict["update_date"] = datetime.now()

                        director_data_list.append(item_dict)

                    # 保存目录数
                    try:
                        if data[11] == "是":
                            director_service.delete_director_by_registerId(task_info.register_id)

                        inster_result = director_service.batch_add(director_data_list)
                        if inster_result:
                            show_success(self, "导入成功", f"{data[1]}-{data[2]}目录导入成功")
                            update_data = {
                                "is_import": True,
                            }
                            register_service.update(register_id=task_info.register_id, update_data=update_data)
                            logger.info(f"{data[1]}-{data[2]}目录导入成功")

                        self.load_all_data()
                        self.update_table_display()

                    except Exception as e:
                        logger.error(f"{data[1]}-{data[2]}目录插入到数据库失败; {str(e)}")
                        show_error(self, "导入失败", f"{data[1]}-{data[2]}目录插入到数据库失败; {str(e)}")

                else:
                    show_error(self, "错误", "导入的目录字段与模版不一致")
            else:
                show_warning(self, "警告", "文件格式不支持!")
        except Exception as e:
            logger.error(f"导入目录失败; {e}")

    def get_archive_level(self, archive_category):
        if archive_category == "卷":
            return "案卷级"
        if archive_category == "件":
            return "文件级"
        return archive_category

    def get_template_headers(self, archive_type, archive_category):
        archive_level = self.get_archive_level(archive_category)
        sheet_name = f"{archive_type}-{archive_level}"
        try:
            model_df = pd.read_excel(settings.archives_template_path, sheet_name=sheet_name, dtype=str)
        except Exception as e:
            logger.error(f"读取档案模版失败: {sheet_name}; {e}")
            show_error(self, "读取失败", f"未找到档案模版: {sheet_name}")
            return []

        if "别名" in model_df.columns:
            headers = model_df["别名"].fillna("").astype(str).str.strip().tolist()
        else:
            headers = [str(row.iloc[2]).strip() for _, row in model_df.iterrows() if len(row) > 2]

        return [header for header in headers if header and header != "序号"]

    def on_view_directory_clicked(self, row):
        data = self.current_page_data[row]
        task_info = task_service.get_by_id(data[0])
        headers = self.get_template_headers(data[1], data[2])
        if not headers:
            return

        results = director_service.get_director_by_registerId(task_info.register_id)
        if not results:
            show_warning(self, "提示", "该任务还未导入目录")
            return

        display_headers = ["全选", "序号"] + headers
        rows = []
        for index, item in enumerate(results, start=1):
            try:
                director_info = json.loads(item.director_info or "{}")
            except json.JSONDecodeError:
                director_info = {}
            row_data = [str(director_info.get("序号") or index)]
            row_data.extend(str(director_info.get(header, "")) for header in headers)
            rows.append(row_data)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"查看目录 - {data[1]}-{data[2]}")
        dialog.resize(1400, 680)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(16, 16, 16, 16)
        dialog_layout.setSpacing(12)

        title_label = QLabel(f"{data[1]}-{self.get_archive_level(data[2])} 目录列表（共 {len(rows)} 条）")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        dialog_layout.addWidget(title_label)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(12)

        select_all_checkbox = QCheckBox("全选")
        select_all_checkbox.setCursor(Qt.PointingHandCursor)
        toolbar_layout.addWidget(select_all_checkbox)

        export_button = PrimaryPushButton("导出目录")
        export_button.setFixedSize(100, 34)
        export_button.setCursor(Qt.PointingHandCursor)
        toolbar_layout.addWidget(export_button)
        toolbar_layout.addStretch(1)
        dialog_layout.addLayout(toolbar_layout)

        table = TableWidget()
        table.setColumnCount(len(display_headers))
        table.setHorizontalHeaderLabels(display_headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(TableWidget.SelectRows)
        table.setSelectionMode(TableWidget.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setBorderVisible(True)
        table.setBorderRadius(8)
        table.verticalHeader().setDefaultSectionSize(42)

        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        table.horizontalHeader().setFont(header_font)
        table.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox = QCheckBox()
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox_layout.addWidget(checkbox)
            table.setCellWidget(row_index, 0, checkbox_widget)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col_index, item)

        table.setColumnWidth(0, 70)
        table.setColumnWidth(1, 70)
        for col_index, header in enumerate(headers, start=2):
            width = 240 if header in ["题名", "备注", "责任者"] else 130
            table.setColumnWidth(col_index, width)

        def row_checkbox(row_index):
            cell_widget = table.cellWidget(row_index, 0)
            if not cell_widget:
                return None
            return cell_widget.findChild(QCheckBox)

        def on_select_all_changed(state):
            checked = state == Qt.CheckState.Checked.value
            for row_index in range(table.rowCount()):
                checkbox = row_checkbox(row_index)
                if checkbox:
                    checkbox.setChecked(checked)

        def export_directory():
            selected_rows = []
            for row_index in range(table.rowCount()):
                checkbox = row_checkbox(row_index)
                if checkbox and checkbox.isChecked():
                    selected_rows.append(row_index)

            export_rows = selected_rows if selected_rows else list(range(table.rowCount()))
            export_data = []
            export_headers = ["序号"] + headers
            for row_index in export_rows:
                export_data.append({
                    header: table.item(row_index, col_index + 1).text()
                    if table.item(row_index, col_index + 1) else ""
                    for col_index, header in enumerate(export_headers)
                })

            download_path = QFileDialog.getExistingDirectory(dialog, "选择保存路径")
            if not download_path:
                return

            try:
                file_name = f"{data[1]}-{data[2]}目录表-{int(time.time())}.xlsx"
                df = pd.DataFrame(export_data)
                df = df.fillna("")
                df.to_excel(f"{download_path}/{file_name}", index=False, header=export_headers, engine='openpyxl')
                logger.info(f"导出{data[1]}-{data[2]}目录, 路径: {download_path}/{file_name}")
                show_success(dialog, "导出成功", f"{data[1]}-{data[2]}导出成功! 保存路径：{download_path}/{file_name}")
            except Exception as e:
                logger.error(f"{data[1]}-{data[2]} 导出目录失败; {str(e)}")
                show_error(dialog, "导出失败", f"失败原因: {str(e)}")

        select_all_checkbox.stateChanged.connect(on_select_all_changed)
        export_button.clicked.connect(export_directory)

        dialog_layout.addWidget(table)
        dialog.exec()


    def update_user_label(self):
        user_info = global_cache.get("current_user")
        print(user_info)
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
