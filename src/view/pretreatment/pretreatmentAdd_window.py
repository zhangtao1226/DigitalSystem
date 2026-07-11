# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : pretreatmentAdd_window.py
# @Desc      : 前处理
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm
import os
import sys
import time

from dotenv import load_dotenv
from datetime import datetime

from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QHeaderView,
                               QLabel, QWidget, QTableWidgetItem, QTableWidget)
from PySide6.QtCore import Qt, Signal, QTimer
from qfluentwidgets import (setTheme, Theme, MessageBox, PushButton, PrimaryPushButton,
                            LineEdit, ComboBox, TextEdit, CardWidget)
from qframelesswindow import FramelessWindow

from src.core.settings import settings
from src.models import RegisterQuestion
from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.services.register_service import register_service
from src.services.operation_service import operation_service
from src.services.task_progress_service import task_progress_service
from src.services.registerQuestion_service import register_question_service
from src.utils.NotificationTool import show_error, show_success, show_warning
from src.view.common.NavigationLabel import NavigationLabel

load_dotenv(verbose=True)

class PretreatmentAddWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 领卷登记")
        self.resize(1400, 850)
        self.center()
        setTheme(Theme.LIGHT)
        self._is_navigation = False
        self._is_app_exiting = False
        user_info = global_cache.get("current_user")
        if user_info and isinstance(user_info, dict):
            self.user_name = user_info
        self.all_data = []
        self.current_user = global_cache.get("current_user")
        self.current_data = global_cache.get("current_data")
        self.task_info = task_service.get_by_id(int(self.current_data[0]))
        self.register_info = register_service.get_by_id(int(self.task_info.register_id))
        self.update_id = None
        QTimer.singleShot(0, self.init_ui)

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
        self.user_label = QLabel(f"👤 {self.user_name['username']} ({self.user_name['role']})")
        self.user_label.setStyleSheet("""
            background-color: #e6f3ff;
            border-radius: 12px;
            padding: 8px 16px;
            font-size: 14px;
            color: #0066cc;
            font-weight: bold;
            border: none;
        """)
        self.user_label.setFixedHeight(40)
        top_layout.addWidget(self.user_label)
        main_layout.addLayout(top_layout)
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e0e0e0;")
        main_layout.addWidget(separator)
        main_form_layout = QHBoxLayout()
        main_form_layout.setSpacing(10)
        main_form_layout.setContentsMargins(0, 10, 0, 10)
        left_card = CardWidget()
        left_card.setMinimumWidth(650)
        left_card.setStyleSheet("border-radius: 12px; background-color: white;")
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(20)
        left_layout.setContentsMargins(20, 20, 20, 20)
        form_title = QLabel("基本信息登记")
        form_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333333; margin-bottom: 10px;")
        left_layout.addWidget(form_title)
        archive_type_layout = QHBoxLayout()
        archive_type_layout.setSpacing(15)
        archive_type_label = QLabel('档案类别:')
        archive_type_label.setFixedWidth(120)
        archive_type_label.setFont(QFont('Microsoft YaHei', 16))
        archive_type_label.setStyleSheet("color: #555555;")
        self.archive_type_combo = LineEdit()
        self.archive_type_combo.setFixedWidth(200)
        self.archive_type_combo.setFont(QFont('Microsoft YaHei', 14))
        self.archive_type_combo.setReadOnly(True)
        self.archive_unit_combo = LineEdit()
        self.archive_unit_combo.setFixedWidth(100)
        self.archive_unit_combo.setFont(QFont('Microsoft YaHei', 14))
        self.archive_unit_combo.setReadOnly(True)
        archive_type_layout.addWidget(archive_type_label)
        archive_type_layout.addWidget(self.archive_type_combo)
        archive_type_layout.addWidget(self.archive_unit_combo)
        archive_type_layout.addStretch(1)
        left_layout.addLayout(archive_type_layout)
        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(15)
        batch_label = QLabel('批次号:')
        batch_label.setFixedWidth(120)
        batch_label.setFont(QFont('Microsoft YaHei', 16))
        batch_label.setStyleSheet("color: #555555;")
        self.batch_input = LineEdit()
        self.batch_input.setPlaceholderText("请输入批次号")
        self.batch_input.setFixedWidth(315)
        self.batch_input.setFont(QFont('Microsoft YaHei', 14))
        self.batch_input.setReadOnly(True)
        batch_layout.addWidget(batch_label)
        batch_layout.addWidget(self.batch_input)
        batch_layout.addStretch(1)
        left_layout.addLayout(batch_layout)
        number_layout = QHBoxLayout()
        number_layout.setSpacing(15)
        number_label = QLabel('起止卷/件号:')
        number_label.setFixedWidth(120)
        number_label.setFont(QFont('Microsoft YaHei', 16))
        number_label.setStyleSheet("color: #555555;")
        self.start_number_edit = LineEdit()
        self.start_number_edit.setPlaceholderText('起始号')
        self.start_number_edit.setFixedWidth(150)
        self.start_number_edit.setFont(QFont('Microsoft YaHei', 14))
        separator_label = QLabel('—')
        separator_label.setFont(QFont('Microsoft YaHei', 16))
        separator_label.setStyleSheet("color: #888888;")
        self.end_number_edit = LineEdit()
        self.end_number_edit.setPlaceholderText('结束号')
        self.end_number_edit.setFixedWidth(150)
        self.end_number_edit.setFont(QFont('Microsoft YaHei', 16))
        number_layout.addWidget(number_label)
        number_layout.addWidget(self.start_number_edit)
        number_layout.addWidget(separator_label)
        number_layout.addWidget(self.end_number_edit)
        number_layout.addStretch(1)
        left_layout.addLayout(number_layout)
        table_title = QLabel("问题卷/件记录")
        table_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333333; margin-top: 10px; margin-bottom: 10px;")
        left_layout.addWidget(table_title)
        self.create_table(left_layout)
        main_form_layout.addWidget(left_card)
        right_card = CardWidget()
        right_card.setMinimumWidth(450)
        right_card.setStyleSheet("border-radius: 12px; background-color: white;")
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(25)
        right_layout.setContentsMargins(40, 30, 40, 30)
        q_title_label = QLabel('问题卷/件登记')
        q_title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #0066CC; margin-bottom: 15px;")
        q_title_layout = QHBoxLayout()
        q_title_layout.addWidget(q_title_label)
        q_title_layout.addStretch(1)
        right_layout.addLayout(q_title_layout)
        q_number_layout = QHBoxLayout()
        q_number_label = QLabel('卷/件号:')
        q_number_label.setFixedWidth(120)
        q_number_label.setFont(QFont('Microsoft YaHei', 16))
        q_number_label.setStyleSheet("color: #555555;")
        self.q_number_edit = LineEdit()
        self.q_number_edit.setPlaceholderText('请输入卷/件号【例: 0001】')
        self.q_number_edit.setFixedWidth(500)
        self.q_number_edit.setFont(QFont('Microsoft YaHei', 14))
        q_number_layout.addWidget(q_number_label)
        q_number_layout.addStretch(1)
        q_number_layout.addWidget(self.q_number_edit)
        q_number_layout.addStretch(1)
        right_layout.addLayout(q_number_layout)
        q_desc_label = QLabel('问题描述:')
        q_desc_label.setFixedWidth(120)
        q_desc_label.setFont(QFont('Microsoft YaHei', 16))
        q_desc_label.setStyleSheet("color: #555555;")
        right_layout.addWidget(q_desc_label)
        self.q_desc_input_edit = TextEdit()
        self.q_desc_input_edit.setPlaceholderText('请详细描述发现的问题，例如：页面破损、字迹模糊、缺少页码等')
        self.q_desc_input_edit.setFixedHeight(360)
        self.q_desc_input_edit.setFont(QFont('Microsoft YaHei', 12))
        self.q_desc_input_edit.setStyleSheet("""
            TextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
            TextEdit:focus {
                border-color: #0066CC;
                outline: none;
            }
        """)
        right_layout.addWidget(self.q_desc_input_edit)
        btn_layout = QHBoxLayout()
        self.q_submit_btn = PrimaryPushButton('添加问题')
        self.q_submit_btn.setFixedSize(140, 45)
        self.q_submit_btn.setFont(QFont('Microsoft YaHei', 18))
        self.q_submit_btn.setCursor(Qt.PointingHandCursor)
        self.q_submit_btn.clicked.connect(self.q_submit_fun)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.q_submit_btn)
        btn_layout.addStretch(1)
        right_layout.addLayout(btn_layout)
        main_form_layout.addWidget(right_card)
        main_layout.addLayout(main_form_layout)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.addStretch(1)
        self.save_btn = PushButton('保存')
        self.submit_btn = PrimaryPushButton('提交')
        for btn in [self.save_btn, self.submit_btn]:
            btn.setFixedSize(120, 40)
            btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_fun)
        self.submit_btn.clicked.connect(self.submit_btn_func)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.submit_btn)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        self.update_page_data()
        self.update_table_display()


    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_table_label = NavigationLabel("拆卷/前处理任务表", is_clickable=True)
        task_table_label.clicked.connect(self.back_table)
        parent_layout.addWidget(task_table_label)
        separator2 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator2)
        task_label = NavigationLabel("拆卷/前处理", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None)  is None:
            show_warning(self, "警告", "登录超时, 请关闭重新登录！")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.new_main_window import MainWindow
            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def create_table(self, parent_layout):
        self.table_widget = QTableWidget()
        self.table_widget.setFixedHeight(300)
        self.table_widget.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                background-color: white;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #f5f7fa;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                font-weight: bold;
            }
        """)
        headers = ["ID", "卷/件号", "问题描述", "记录人", "记录日期", "操作"]

        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        header_font = QFont('Microsoft YaHei', 14, QFont.Bold)
        self.table_widget.horizontalHeader().setFont(header_font)
        content_font = QFont('Microsoft YaHei', 14)
        self.table_widget.setFont(content_font)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table_widget.setColumnWidth(4, 140)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_widget.verticalHeader().setDefaultSectionSize(50)
        self.table_widget.setColumnHidden(0, True)
        parent_layout.addWidget(self.table_widget)

    def q_submit_fun(self):
        volume_number = self.q_number_edit.text().strip()
        number_start = self.start_number_edit.text().strip()
        number_end = self.end_number_edit.text().strip()
        batch_number = self.batch_input.text().strip()

        if len(volume_number) != 4 or int(number_end) < int(volume_number) or int(number_start) > int(volume_number):
            show_warning(self, "警告", f"请填写正确格式起止卷/件号【长度为 4 位, 范围: {number_start} - {number_end}】")
            return

        question_desc = self.q_desc_input_edit.toPlainText().strip()
        if not question_desc:
            show_warning(self, "警告", "请填写问题描述")
            return

        if self.update_id is not None:
            # 更新问题记录
            update = {
                "volume_number": volume_number,
                "question_desc": question_desc,
            }

            result = register_question_service.update(id=self.update_id, update_data=update)
            if result:
                operation_data = {
                    "task_id": self.task_info.id,
                    "task_name": "拆卷/前处理",
                    "operator": self.user_name["username"],
                    "task_number_start": number_start,
                    "task_number_end": number_end,
                    "status": 1,
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"更新问题记录; 问题详情: {update}"
                }
                operation_service.save_data([operation_data])

        else:
            # 添加问题记录
            where = {
                "register_id": self.task_info.register_id,
                "batch_number": batch_number,
                "volume_number": volume_number,
                "recorder": self.user_name["username"],
            }

            q_exists = register_question_service.get_data(where)
            print(f"q_exists: {q_exists}")
            if q_exists:
                show_warning(self, "警告", "该卷/件号已存在, 不可重复添加!")
                return

            data = {
                "register_id": self.task_info.register_id,
                "batch_number": batch_number,
                "volume_number": volume_number,
                "number_start": self.task_info.number_start,
                "number_end": self.task_info.number_end,
                "question_desc": question_desc,
                "recorder": self.user_name["username"],
                "recorder_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": 1
            }

            result = register_question_service.batch_add([data])
            if result:
                operation_data = {
                    "task_id": self.task_info.id,
                    "task_name": "拆卷/前处理",
                    "operator": self.user_name["username"],
                    "task_number_start": number_start,
                    "task_number_end": number_end,
                    "status": 0,
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": f"添加问题记录; 问题详情: {data}"
                }
                operation_service.save_data([operation_data])

            register_update_data = {
                "is_question": 1
            }
            register_service.update(self.register_info.id, update_data=register_update_data)

        self.update_table_display()
        self.q_number_edit.clear()
        self.q_desc_input_edit.clear()

    def update_table_display(self):
        if not hasattr(self, 'table_widget'):
            return
        self.table_widget.setRowCount(0)
        self.all_dat = []
        number_start = self.start_number_edit.text().strip()
        number_end = self.end_number_edit.text().strip()
        try:
            range_start = int(number_start)
            range_end = int(number_end)
        except ValueError:
            logger.warning(f"起止卷/件号格式错误，无法加载问题记录: {number_start} - {number_end}")
            return

        questions_list = register_question_service.get_list(register_id=self.task_info.register_id)
        for item in questions_list:
            try:
                volume_number = int(item.volume_number)
            except (TypeError, ValueError):
                logger.warning(f"问题记录卷/件号格式错误，已跳过: id={item.id}, volume_number={item.volume_number}")
                continue

            if not range_start <= volume_number <= range_end:
                continue

            row_data = [
                str(item.id),
                item.volume_number,
                item.question_desc,
                item.recorder,
                item.recorder_time.strftime("%Y-%m-%d %H:%M:%S"),
                ""
            ]
            self.all_dat.append(row_data)
        self.total_rows = len(self.all_dat)
        for row, data in enumerate(self.all_dat):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == 5:
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 5, 5, 5)
                    button_layout.setSpacing(10)
                    details_btn = PrimaryPushButton("详情")
                    details_btn.setFixedSize(60, 35)
                    details_btn.setCursor(Qt.PointingHandCursor)
                    details_btn.clicked.connect(lambda checked, r=row: self.on_details_clicked(r))
                    button_layout.addWidget(details_btn)
                    delete_btn = PushButton("删除")
                    delete_btn.setFixedSize(60, 35)
                    delete_btn.setCursor(Qt.PointingHandCursor)
                    delete_btn.clicked.connect(lambda checked, r=row: self.on_delete_clicked(r))
                    button_layout.addWidget(delete_btn)
                    button_layout.addStretch(1)
                    self.table_widget.setCellWidget(row, col, button_widget)
                else:
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table_widget.setItem(row, col, item)

    def on_details_clicked(self, r):
        data = self.all_dat[r]
        id = int(data[0])
        question_info = register_question_service.get_by_id(id)
        volume_number = question_info.volume_number
        question_desc = question_info.question_desc
        recorder = question_info.recorder
        record_date = question_info.recorder_time.strftime("%Y-%m-%d %H:%M:%S")
        title = "问题详情"
        content = f"卷/件号: {volume_number}\n记录日期: {record_date}\n记录人: {recorder}\n\n问题描述: {question_desc}"
        w = MessageBox(title, content, self)
        w.yesButton.setText("修改")
        w.cancelButton.setText("关闭")
        if w.exec():
            if self.task_info.is_do:
                show_warning(self, "警告提示", "该登记信息已经提交, 不可更改!")
                return
            self.update_table_display()
            self.question_edit(id, volume_number, question_desc)

    def on_delete_clicked(self, r):
        data = self.all_dat[r]

        if data[3] != self.user_name["username"] and self.user_name["role"] not in ['管理员', '质检员']:
            show_warning(self, "警告", "该条记录非当前用户添加, 不可被删除!")
            return

        box = MessageBox('确认删除', '确定要删除该条问题记录吗？', self)
        box.yesButton.setText('删除')
        box.cancelButton.setText('取消')

        if box.exec():
            if self.task_info.is_do:
                show_warning(self, "警告提示", "该登记信息已经提交, 不可更改!")
                return

            id = int(data[0])
            q_exists = register_question_service.get_by_id(id)

            if q_exists:
                try:
                    result = register_question_service.delete(id)
                    print(f"result = {result}")
                    if result:
                        operation_data = {
                            "task_id": self.task_info.id,
                            "task_name": "拆卷/前处理",
                            "operator": self.user_name["username"],
                            "task_number_start": number_start,
                            "task_number_end": number_end,
                            "status": 0,
                            "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "operator_remark": f"删除问题记录; 问题详情: {data}"
                        }
                        operation_service.save_data([operation_data])
                        logger.info(
                            f"删除问题记录; 操作人: {self.user_name['username']}; 角色:{self.user_name['role']};"
                            f" 删除的问题:{data}")
                    else:
                        logger.info(f"删除问题记录失败; 操作人: {self.user_name['username']}; 角色:{self.user_name['role']};"
                                    f" 删除的问题:{data}")
                except Exception as e:
                    print(f"删除失败; {e}")

        self.update_table_display()

    def question_edit(self, id, number_txt, content):
        self.update_id = id
        question = register_question_service.get_by_id(id)
        if question.recorder != self.user_name["username"]:
            show_warning(self, "提示", "该条问题记录非当前用户提交, 不可修改")
            return

        self.q_number_edit.setText(number_txt)
        self.q_desc_input_edit.setText(content)

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请关闭后重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            from src.view.pretreatment.pretreatmentTable_window import PretreatmentTableWindow
            pretreatment_table_window = PretreatmentTableWindow()
            pretreatment_table_window.showFullScreen()
            QTimer.singleShot(100, self.close)


    def save_fun(self):
        if self.task_info.is_do:
            show_warning(self, "警告提示", "该登记信息已经提交, 不可更改!")
            return

        number_start = self.start_number_edit.text().strip()
        number_end = self.end_number_edit.text().strip()


        if len(number_start) != 4 or len(number_end) != 4:
            show_warning(self, "警告", "请填写正确格式起止卷/件号【长度为 4 位】")
            return


        register_info = register_service.get_by_id(self.task_info.register_id)
        if int(number_end) > int(self.task_info.task_number_end):
            show_warning(self, "警告", f"起止卷/件号超出分配到的任务号段范围:{self.task_info.task_number_start} "
                                       f"- {self.task_info.task_number_end}")
            return
        where = {
            "task_id": self.task_info.id,
            "status": 1
        }
        task_record_list = task_progress_service.get_data(where=where)
        if len(task_record_list) == 0:
            if number_start != self.task_info.task_number_start:
                show_warning(self, "警告", f"起始卷件号必须从任务号开始, 分配到的任务号段: "
                                           f"{self.task_info.task_number_start} - {self.task_info.task_number_end}")
                return
        elif len(task_record_list) > 0:
            if int(number_start) != int(self.task_info.complete_number.split("-")[-1]) + 1:
                show_warning(self, "警告", f"保存的起始卷/件号不连续, 已经提交:{self.task_info.complete_number}")
                return

        try:
            self.batch_input.clear()
            self.start_number_edit.clear()
            self.end_number_edit.clear()

            task_operation_data = {
                "task_id": self.task_info.id,
                "sub_start": number_start,
                "sub_end": number_end,
                "status": 0,
                "operator": self.user_name["username"]
            }
            task_progress_service.add_record(data=task_operation_data)

            operation_data = {
                "task_id": self.task_info.id,
                "task_name": "拆卷/前处理",
                "operator": self.user_name["username"],
                "task_number_start": number_start,
                "task_number_end": number_end,
                "status": 0,
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": f"拆卷/前处理保存操作; 保存任务段：{number_start}-{number_end}"
            }
            operation_service.save_data([operation_data])
            show_success(self, "提示", "保存成功")

        except Exception as e:
            logger.error(f"保存失败; {str(e)}")
            show_error(self, "保存失败", str(e))

    def submit_btn_func(self):
        if self.task_info.is_do:
            show_warning(self, "警告提示", "该登记信息已经提交, 不可更改!")
            return

        start_number = self.start_number_edit.text().strip()
        end_number = self.end_number_edit.text().strip()

        if int(end_number) > int(self.task_info.task_number_end):
            show_warning(self, "警告", f"填写的起止卷/件号超出分配任务号范围: {self.task_info.task_number_start} - "
                                       f"{self.task_info.task_number_end}")
            return

        where = {
            "task_id": self.task_info.id,
            "status": 1
        }

        task_progress_list = task_progress_service.get_data(where=where)
        print(f"task_progress_list: {task_progress_list}")

        if len(task_progress_list) > 0:
            sub_end = task_progress_list[-1].sub_end
            if int(sub_end) + 1 != int(start_number):
                show_warning(self, "警告", f"提交的卷/件号不连续, { '已经完成:' + self.task_info.complete_number if self.task_info.complete_number else ''}")
                return

        task_progress_data = {
            "task_id": self.task_info.id,
            "sub_start": start_number,
            "sub_end": end_number,
            "status": 1,
            "operator": self.user_name["username"]
        }

        result = task_progress_service.add_record(data=task_progress_data)
        if result:
            update = {
                "complete_number": f"{self.task_info.task_number_start}-{end_number}",
            }
            task_service.update(task_id=self.task_info.id, update_data=update)

        try:
            result = task_service.execute_task_submission(self.task_info.id, end_number)
            if result['status'] == "success":
                operation_data = {
                    "task_id": self.task_info.id,
                    "task_name": "拆卷/前处理",
                    "task_number_start": "",
                    "task_number_end": "",
                    "operator": self.user_name["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": "拆卷/前处理提交操作"
                }
                operation_service.save_data([operation_data])
                show_success(self, "提示", "提交成功")
            else:
                logger.error(result["message"])
        except Exception as e:
            show_error(self, "提示", "提交失败")
            logger.error(f"拆卷/前处理; 提交失败: {str(e)}")


    def update_page_data(self):
        if self.register_info is not None:

            self.archive_type_combo.setText(self.register_info.archive_type)
            self.archive_unit_combo.setText(self.register_info.category)
            self.batch_input.setText(self.register_info.batch_number)

            where = {
                "task_id": self.task_info.id,
                "status": 0,
            }
            task_progress_info = task_progress_service.get_data(where)
            if len(task_progress_info) == 0:
                if self.task_info.is_do:
                    self.start_number_edit.setText(self.task_info.task_number_start)
                    self.end_number_edit.setText(self.task_info.task_number_end)
                    self.start_number_edit.setReadOnly(True)
                    self.end_number_edit.setReadOnly(True)
                else:
                    print(f"task_info: {self.task_info}")
                    if self.task_info.complete_number:
                        had_number_end = self.task_info.complete_number.split("-")[1]
                        self.start_number_edit.setText(
                            f"{(4 - len(str(int(had_number_end) + 1))) * '0'}{str(int(had_number_end) + 1)}")
                        self.end_number_edit.setText(self.task_info.task_number_end)
                    else:
                        self.start_number_edit.setText(self.task_info.task_number_start)
                        self.end_number_edit.setText(self.task_info.task_number_end)
            else:
                number_start = task_progress_info[-1].sub_start
                number_end = task_progress_info[-1].sub_end
                self.start_number_edit.setText(number_start)
                self.end_number_edit.setText(number_end)

                task_progress_service.delete_record(task_progress_info[-1].id)

    def logout(self):
        global_cache.delete("current_user")
        QTimer.singleShot(100, self.close)

    def closeEvent(self, event):
        if self._is_navigation:
            event.accept()
            return
        if not self._is_app_exiting:
            box = MessageBox('确认退出', '确定要退出应用程序吗？', self)
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
