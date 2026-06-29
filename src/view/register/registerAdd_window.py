# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : registerAdd_window.py
# @Desc      : 领卷登记
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm

import os
import sys
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
from src.models.register import Register
from src.services.task_service import task_service
from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.register_service import register_service
from src.services.workflow_service import workflow_service
from src.view.common.NavigationLabel import NavigationLabel
from src.services.operation_service import operation_service
from src.services.registerQuestion_service import register_question_service
from src.utils.NotificationTool import show_error, show_success, show_warning, show_info

load_dotenv(verbose=True)


class RegisterAddWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 领卷登记")
        self.resize(1400, 850)
        # self.center()
        setTheme(Theme.LIGHT)
        self._is_navigation = False
        self._is_app_exiting = False
        self.current_user = global_cache.get("current_user")

        self.all_data = []
        self.register_id = global_cache.get("register_id", None)

        self.new_question_list = []

        if self.register_id is not None:
            self.register_info = register_service.get_by_id(register_id=self.register_id)
        else:
            self.register_info = None

        self.work_flow_status = workflow_service.get_workflow_status_by_name("任务分发")
        print(f"工作流: {self.work_flow_status}")

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
        self.user_label = QLabel(f"👤 {self.current_user['username']} ({self.current_user['role']})")
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
        left_card.setMinimumWidth(750)
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
        self.archive_type_combo = ComboBox()
        self.archive_type_combo.addItems(settings.archive_type_list)
        self.archive_type_combo.setFixedWidth(200)
        self.archive_type_combo.setFont(QFont('Microsoft YaHei', 14))
        self.archive_unit_combo = ComboBox()
        self.archive_unit_combo.addItems(settings.archive_unit_list)
        self.archive_unit_combo.setFixedWidth(100)
        self.archive_unit_combo.setFont(QFont('Microsoft YaHei', 14))
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
        self.start_number_edit.setPlaceholderText("【例: 0001】")
        separator_label = QLabel('—')
        separator_label.setFont(QFont('Microsoft YaHei', 16))
        separator_label.setStyleSheet("color: #888888;")
        self.end_number_edit = LineEdit()
        self.end_number_edit.setPlaceholderText('结束号')
        self.end_number_edit.setFixedWidth(150)
        self.end_number_edit.setFont(QFont('Microsoft YaHei', 16))
        self.end_number_edit.setPlaceholderText("【例: 0010】")
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
        right_card.setMinimumWidth(350)
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
        q_number_layout.setSpacing(15)
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
        self.update_table_display()
        self.update_page_data()

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_table_label = NavigationLabel("领卷登记任务表", is_clickable=True)
        task_table_label.clicked.connect(self.back_table)
        parent_layout.addWidget(task_table_label)
        separator2 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator2)
        task_label = NavigationLabel("领卷登记", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.new_main_window import MainWindow
            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退重新登录!")
            time.sleep(1)
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
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

        headers = ["卷/件号", "问题描述", "记录人", "记录日期", "操作"]
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
        parent_layout.addWidget(self.table_widget)

    def q_submit_fun(self):
        volume_number = self.q_number_edit.text().strip()
        start_number = self.start_number_edit.text().strip()
        end_number = self.end_number_edit.text().strip()

        if self.register_info is not None and self.register_info.status == 1:
            show_warning(self, "警告", "该登记信息已经提交, 不可在添加问题!")
            return

        if len(volume_number) !=4  or int(start_number) > int(volume_number)  or int(volume_number) > int(end_number):
            show_warning(self, "警告", f"请填写正确格式起止卷/件号【长度为 4 位; 范围: {start_number} - {end_number}】")
            return
        if not volume_number:
            show_warning(self, "警告", "请填写卷/件号")
            return
        question_desc = self.q_desc_input_edit.toPlainText()
        if not question_desc:
            show_warning(self, "警告", "请填写问题描述")
            return
        batch_number = self.batch_input.text()
        if not batch_number:
            show_warning(self, "警告", "请填写批次号")
            return
        data = {
            "batch_number": batch_number,
            "volume_number": volume_number,
            "question_desc": question_desc,
            "recorder": self.current_user["username"],
            "recorder_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        question_exist = register_question_service.get_question(register_id=self.register_id,
                                                                volume_number=volume_number,
                                                                recorder=data["recorder"])

        if question_exist:
            show_warning(self, "警告", "该卷/件号已添加, 不可重复添加!")
            return

        exist = any(item.get("volume_number") == volume_number for item in self.new_question_list)
        if exist:
            show_warning(self, "警告", "该卷/件号已添加, 不可重复添加!")
            return

        self.new_question_list.append(data)

        self.update_table_display()
        self.q_number_edit.clear()
        self.q_desc_input_edit.clear()

        logger.info(f"领卷登记-添加问题; 问题内容: {data}; 操作人: {self.current_user}")

    def update_table_display(self):
        if not hasattr(self, 'table_widget'):
            return
        self.table_widget.setRowCount(0)
        self.all_data = []
        if self.register_id is not None:
            question_data = register_question_service.get_list(register_id=self.register_id)
        else:
            question_data = []

        for item in question_data:
            row_data = [
                item.volume_number,
                item.question_desc,
                item.recorder,
                item.recorder_time.strftime("%Y-%m-%d %H:%M:%S"),
                ""
            ]
            self.all_data.append(row_data)
        for item in self.new_question_list:
            row_data = [
                item['volume_number'],
                item['question_desc'],
                item['recorder'],
                item['recorder_time'],
                ''
            ]
            self.all_data.append(row_data)
        self.total_rows = len(self.all_data)

        for row, data in enumerate(self.all_data):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == 4:
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

    def on_details_clicked(self, row):
        if 0 <= row < self.total_rows:
            data = self.all_data[row]
            volume_number = data[0]
            question_desc = data[1]
            recorder = data[2]
            record_date = data[3]
            title = "问题详情"
            content = f"卷/件号: {volume_number}\n记录日期: {record_date}\n记录人: {recorder}\n\n问题描述: {question_desc}"
            w = MessageBox(title, content, self)
            w.yesButton.setText("修改")
            w.cancelButton.setText("关闭")
            if w.exec():
                if self.register_info is not None and self.register_info.status == 1:
                    show_warning(self, "警告", "该登记信息已经提交, 不可删除该信息相关的问题！")
                    return

                exist = any(item.get("volume_number") == volume_number for item in self.new_question_list)
                if exist:
                    self.new_question_list = [item for item in self.new_question_list if item.get("volume_number") != volume_number]
                else:
                    question_info = register_question_service.get_question(register_id=self.register_id,
                                                                           volume_number=volume_number,
                                                                           recorder=recorder)
                    register_question_service.delete(question_info.id)
                    logger.info(f"领卷登记-修改登记问题; 问题内容: {question_info}; 操作人: {self.current_user}")

                self.update_table_display()
                self.question_edit(volume_number, question_desc)

    def on_delete_clicked(self, row):
        if self.register_info is not None and self.register_info.status == 1:
            show_warning(self, "警告", "该登记信息已经提交, 不可删除该信息相关的问题！")
            return

        data = self.all_data[row]
        volume_number = data[0]
        recorder = data[2]

        exists = any(item.get("volume_number") == volume_number for item in self.new_question_list)
        if exists:
            self.new_question_list = [item for item in self.new_question_list if item.get("volume_number") != volume_number]
        else:
            question_info = register_question_service.get_question(register_id=self.register_id, volume_number=volume_number, recorder=recorder)
            register_question_service.delete(question_info.id)
            logger.info(f"领卷登记-删除登记问题; 问题内容: {question_info}; 操作人: {self.current_user}")

        self.update_table_display()

    def question_edit(self, number_txt, content):
        self.q_number_edit.setText(number_txt)
        self.q_desc_input_edit.setText(content)

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is not None:
            from src.view.register.registerTable_window import RegisterTableWindow
            register_table_window = RegisterTableWindow()
            register_table_window.showFullScreen()
            QTimer.singleShot(100, self.close)
        else:
            show_warning(self, "警告", "登录超时, 请退出后重新登录!")
            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(100, self.close)

    def save_fun(self):
        if self.register_info is not None and self.register_info.status == 1:
            show_warning(self, "警告", "该登记信息已经提交, 不可更改!")
            return

        archive_type = self.archive_type_combo.currentText()
        category = self.archive_unit_combo.currentText()
        batch_number = self.batch_input.text().strip()
        if not batch_number:
            show_warning(self, "警告", "请填写批次号")
            return
        start_number = self.start_number_edit.text().strip()
        end_number = self.end_number_edit.text().strip()
        if (len(start_number) != 4) or (len(end_number) != 4) or (int(start_number) >= int(end_number)):
            show_warning(self, "警告", "请填写正确格式起止卷/件号【长度为 4 位】")
            return

        try:

            register_data = {
                "archive_type": archive_type,
                "category": category,
                "batch_number": batch_number,
                "number_start": start_number,
                "number_end": end_number,
                "register": self.current_user["username"],
                "status": 0,
                "task_node": 0,
                "is_question": bool(self.new_question_list)
            }
            if self.register_id is None:
                where = {
                    "archive_type": archive_type,
                    "category": category,
                    "batch_number": batch_number,
                    "number_start": start_number,
                    "number_end": end_number,
                }
                register_exist = register_service.get_data(where=where)
                if register_exist:
                    show_warning(self, "警告", "该登记信息已存在, 不可重复提交!")
                    return
                register = register_service.create(
                    archive_type=archive_type,
                    category=category,
                    batch_number=batch_number,
                    number_start=start_number,
                    number_end=end_number,
                    register=self.current_user['username'],
                    status=0,
                    task_node=0,
                )
                self.register_id = register.id
                if self.new_question_list:
                    for q in self.new_question_list:
                        q["register_id"] = self.register_id
                        q["number_start"] = start_number
                        q["number_end"] = end_number
                        q["status"] = 0
                    register_question_service.batch_add(self.new_question_list)
                    register_service.update(register_id=register.id, update_data={"is_question": True})
                show_success(self, "提示", "保存成功")
                logger.info(f"领卷登记保存; 领卷登记信息: {register_data}; 问题件/卷记录: {self.new_question_list}")
            else:
                register_service.update(self.register_id, update_data=register_data)

                if self.new_question_list:
                    for q in self.new_question_list:
                        q["register_id"] = self.register_id
                        q["number_start"] = start_number
                        q["number_end"] = end_number
                        q["status"] = 0
                    register_question_service.batch_add(self.new_question_list)
                    register_service.update(register_id=self.register_id, update_data={"is_question": True})
                show_success(self, "提示", "保存成功")
                logger.info(f"领卷登记保存; 领卷登记信息: {register_data}; 问题件/卷记录: {self.new_question_list}")

            operation_data = {
                "task_id": self.register_id,
                "task_name": "领卷登记",
                "operator": self.current_user["username"],
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": "领卷登记保存操作",
                "status": 0
            }
            operation_service.save_data([operation_data])

            self.new_question_list = []
        except Exception as e:
            show_error(self, "保存失败", str(e))

    def submit_btn_func(self):
        if self.register_info is not None and self.register_info.status == 1:
            show_warning(self, "警告", "该登记信息已经提交, 不可更改!")
            return

        archive_type = self.archive_type_combo.currentText()
        category = self.archive_unit_combo.currentText()
        batch_number = self.batch_input.text()
        if not batch_number:
            show_warning(self, "警告", "请填写批次号")
            return
        start_number = self.start_number_edit.text()
        end_number = self.end_number_edit.text()
        if len(start_number) != 4 or len(end_number) != 4 or (int(start_number) >= int(end_number)):
            show_warning(self, "警告", "请填写正确格式起止卷/件号【长度为 4 位】")
            return

        where = {
            "archive_type": archive_type,
            "category": category,
            "batch_number": batch_number,
            "status": 1
        }
        register_exist = register_service.get_data(where)
        if register_exist:
            had_number_start = register_exist[0].number_start
            had_number_end = register_exist[-1].number_end
            if int(had_number_end) >= int(start_number):
                show_warning(self, "警告", f"该批次的起止卷/件号已经提交了【 {had_number_start} - {had_number_end}】")
                return

        try:
            register_data = {
                "archive_type": archive_type,
                "category": category,
                "batch_number": batch_number,
                "number_start": start_number,
                "number_end": end_number,
                "register": self.current_user["username"],
                "status": 1,
                "task_node": 1,
                "is_question": bool(self.new_question_list),
            }

            if self.register_id is None:
                where = {
                    "archive_type": archive_type,
                    "category": category,
                    "batch_number": batch_number,
                    "number_start": start_number,
                    "number_end": end_number,
                }

                register_exist = register_service.get_data(where=where)
                if register_exist:
                    show_warning(self, "警告", "该登记信息已存在, 不可重复提交!")
                    return

                register = register_service.create(
                    archive_type=archive_type,
                    category=category,
                    batch_number=batch_number,
                    number_start=start_number,
                    number_end=end_number,
                    register=self.current_user['username'],
                    status=1,
                    task_node=1,
                )

                if self.new_question_list:
                    for q in self.new_question_list:
                        q["register_id"] = register.id
                        q["number_start"] = start_number
                        q["number_end"] = end_number
                        q["status"] = 1
                    register_question_service.batch_add(self.new_question_list)
                if not self.work_flow_status.status:
                    logger.info(f"准备自动分配任务")
                    auto_result = self.auto_dist_tasks(register=register)
                    if not auto_result:
                        register_service.delete(register.id)
                        return

                logger.info(f"{self.current_user['username']} 添加领卷登记, register_id = {register.id}")
                operation_data = {
                    "task_id": register.id,
                    "task_name": "领卷登记",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": "领卷登记提交操作",
                    "status": 1
                }
                operation_service.save_data([operation_data])
                show_success(self, "提示", "提交成功")
            else:
                register = register_service.update(self.register_id, update_data=register_data)
                if self.new_question_list:
                    for q in self.new_question_list:
                        q["register_id"] = self.register_id
                        q["number_start"] = start_number
                        q["number_end"] = end_number
                        q["status"] = 1
                    register_question_service.batch_add(self.new_question_list)
                if not self.work_flow_status.status:
                    logger.info(f"准备自动分配任务")
                    auto_result = self.auto_dist_tasks(register=register)
                    if not auto_result:
                        register_service.delete(register.id)
                        return


                logger.info(f"领卷登记提交; 用户: {self.current_user['username']}, 提交信息: {register_data}")
                operation_data = {
                    "task_id": self.register_id,
                    "task_name": "领卷登记",
                    "operator": self.current_user["username"],
                    "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator_remark": "领卷登记提交操作",
                    "status": 1
                }
                operation_service.save_data([operation_data])
                show_success(self, "提示", "提交成功")

        except Exception as e:
            logger.error(f"领卷登记提交失败; {str(e)}")

    def auto_dist_tasks(self, register: Register ) -> bool:
        work_flow_data = workflow_service.get_all_workflows(is_work=True)
        task_id = 0
        tasks_list = []
        current_task_name = ""
        for work in work_flow_data:
            if work.is_work == 0 or work.status is False:
                continue
            task_dict = dict()
            task_dict["register_id"] = register.id
            task_dict["batch_number"] = register.batch_number
            task_dict["number_start"] = register.number_start
            task_dict["number_end"] = register.number_end
            task_dict["task_name"] = work.work_name
            task_dict["task_number_start"] = register.number_start
            task_dict["task_number_end"] = register.number_end
            task_dict["operator"] = self.current_user["username"]
            task_dict["dist_officer"] = self.current_user["username"]
            task_dict["status"] = 1

            if current_task_name != task_dict["task_name"]:
                task_id += 1
                current_task_name = task_dict["task_name"]
            task_dict["task_id"] = task_id
            task_dict["task_node"] = settings.work_number[task_dict["task_name"]]
            if task_id == 1:
                task_dict["is_ready"] = True

            tasks_list.append(task_dict)

        try:
            result = task_service.batch_add(tasks_list)
            if result:
                logger.info(f"默认分配任务成功; {tasks_list}")
                return True
        except Exception as e:
            logger.error(f"默认分配任务时报错: {str(e)}")
            return False

    def update_page_data(self):
        if self.register_id is not None:
            register_info = register_service.get_by_id(register_id=self.register_id)
            if register_info:
                self.archive_type_combo.setCurrentText(register_info.archive_type)
                self.archive_unit_combo.setCurrentText(register_info.category)
                self.batch_input.setText(register_info.batch_number)
                self.start_number_edit.setText(register_info.number_start)
                self.end_number_edit.setText(register_info.number_end)

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