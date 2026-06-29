# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : taskAdd_window.py
# @Desc      : 任务分配窗口
# @Time      : 2025/11/22 11:31
# @Software  : PyCharm

import sys
import json
import itertools
from datetime import datetime
from collections import defaultdict
from PySide6.QtGui import QFont, QCursor

from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout,
                               QLabel, QWidget, QSizePolicy, QFrame, QLayout, QScrollArea,
                               )
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal, QTimer
from pyexpat.errors import messages

from qfluentwidgets import (setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
                            LineEdit, ComboBox, FluentIcon, InfoBar, InfoBarPosition,
                            CardWidget, ToolButton)
from qframelesswindow import FramelessWindow

from src.utils.LoggerDetector import logger
from src.core.settings import settings
from src.core.cache_manager import global_cache
from src.services.task_service import task_service
from src.services.user_service import user_service
from src.services.role_service import role_service
from src.services.workflow_service import workflow_service
from src.services.register_service import register_service
from src.services.operation_service import operation_service
from src.view.common.NavigationLabel import NavigationLabel
from src.utils.NotificationTool import show_error, show_warning, show_success, show_info

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=10):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self.item_list = []

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation.Vertical

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._calculate_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._calculate_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _calculate_layout(self, rect, test_only):
        margins = self.contentsMargins()
        left = margins.left()
        top = margins.top()
        right = margins.right()
        bottom = margins.bottom()
        available_rect = rect.adjusted(left, top, -right, -bottom)
        x = available_rect.x()
        y = available_rect.y()
        line_height = 0
        for item in self.item_list:
            if item.widget() and item.widget().isHidden():
                continue
            if item.widget():
                item_size = item.widget().size() if item.widget().size().isValid() else item.sizeHint()
            else:
                item_size = item.sizeHint()
            if not item_size.isValid():
                item_size = QSize(440, 280)
            next_x = x + item_size.width() + self.spacing()
            if next_x - self.spacing() > available_rect.right() and line_height > 0:
                x = available_rect.x()
                y += line_height + self.spacing()
                next_x = x + item_size.width() + self.spacing()
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            x = next_x
            line_height = max(line_height, item_size.height())
        total_height = y + line_height - available_rect.y() + bottom
        return total_height

class TaskWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统")
        self.resize(1400, 850)
        # self.center()
        setTheme(Theme.LIGHT)
        self._is_navigation = False
        self._is_app_exiting = False
        self.current_user = global_cache.get("current_user")

        self.current_type = global_cache.get("current_type")
        self.current_data = global_cache.get("current_data", None)
        self.register_id = None
        if self.current_type == 1:
            register_info = register_service.get_by_id(int(self.current_data[0]))
            self.register_id = register_info.id
            self.batch_number = register_info.batch_number
            tasks_list = task_service.get_list(register_id=register_info.id, batch_number=register_info.batch_number)
        else:
            self.task_info = task_service.get_by_id(task_id=int(self.current_data[0]))
            self.register_id = self.task_info.register_id
            self.batch_number = self.task_info.batch_number
            tasks_list = task_service.get_list(register_id=self.task_info.register_id,
                                               batch_number=self.task_info.batch_number,
                                               order_by=True)

        self.tasks_dict_list = {}
        for task in tasks_list:
            if task.task_name in self.tasks_dict_list.keys():
                self.tasks_dict_list[task.task_name].append(task)
            else:
                self.tasks_dict_list[task.task_name] = [task]
        self.init_ui()

    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 30, 10, 10)
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignVCenter)
        top_layout.setSpacing(5)
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
        archive_info_widget = QWidget()
        archive_info_widget.setStyleSheet("background-color: white; border-radius: 8px; padding: 10px;")
        archive_info_layout = QHBoxLayout(archive_info_widget)
        archive_info_layout.setSpacing(5)
        archive_info_layout.setContentsMargins(20, 10, 20, 10)
        archive_type_label = QLabel('档案类别:')
        archive_type_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        self.archive_type_edit = LineEdit()
        self.archive_type_edit.setText(self.current_data[1])
        self.archive_type_edit.setFixedWidth(120)
        self.archive_type_edit.setEnabled(False)
        self.archive_type_edit.setAlignment(Qt.AlignCenter)
        self.archive_type_edit.setStyleSheet("""
            LineEdit:disabled {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 14px;
            }
        """)
        self.archive_unit_edit = LineEdit()
        self.archive_unit_edit.setText(self.current_data[2])
        self.archive_unit_edit.setFixedWidth(80)
        self.archive_unit_edit.setEnabled(False)
        self.archive_unit_edit.setAlignment(Qt.AlignCenter)
        self.archive_unit_edit.setStyleSheet("""
            LineEdit:disabled {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }
        """)

        batch_name_label = QLabel("批次号:")
        batch_name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        self.batch_name_edit = LineEdit()
        self.batch_name_edit.setText(self.current_data[3])
        self.batch_name_edit.setFixedWidth(120)
        self.batch_name_edit.setEnabled(False)
        self.batch_name_edit.setAlignment(Qt.AlignCenter)
        self.batch_name_edit.setStyleSheet("""
            LineEdit:disabled {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }
        """)

        start_end_number_label = QLabel("起止卷/件号:")
        start_end_number_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        self.start_end_number_edit = LineEdit()
        self.start_end_number_edit.setText(self.current_data[4])
        self.start_end_number_edit.setFixedWidth(150)
        self.start_end_number_edit.setEnabled(False)
        self.start_end_number_edit.setAlignment(Qt.AlignCenter)
        self.start_end_number_edit.setStyleSheet("""
            LineEdit:disabled {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }
        """)

        self.save_btn = PushButton('保存')
        self.submit_btn = PrimaryPushButton('提交')

        for btn in [self.submit_btn, self.save_btn]:
            btn.setFixedSize(96, 36)
            btn.setCursor(Qt.PointingHandCursor)

        self.save_btn.setStyleSheet("""
            PushButton {
                    font-size: 14px;
                    border-radius: 8px;
                    background-color: #1590d8;
                    color: white;
                    font-weight: bold;
                    border: none;
                }
                PushButton:hover {
                    background-color: #066eac;
                }
        """)

        self.submit_btn.setStyleSheet("""
            PrimaryPushButton {
                background-color: #27ae60;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            PrimaryPushButton:hover {
                background-color: #219653;
            }
        """)

        self.save_btn.clicked.connect(self.save_taskInfo)
        self.submit_btn.clicked.connect(self.submit_taskInfo)

        archive_info_layout.addWidget(archive_type_label)
        archive_info_layout.addWidget(self.archive_type_edit)
        archive_info_layout.addWidget(self.archive_unit_edit)
        archive_info_layout.addWidget(batch_name_label)
        archive_info_layout.addWidget(self.batch_name_edit)
        archive_info_layout.addWidget(start_end_number_label)
        archive_info_layout.addWidget(self.start_end_number_edit)
        archive_info_layout.addStretch(1)

        archive_info_layout.addWidget(self.save_btn)
        archive_info_layout.addWidget(self.submit_btn)

        main_layout.addWidget(archive_info_widget)

        task_scroll_area = QScrollArea()
        task_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white; 
                border-radius: 6px;
                border: none;
            }
            /* 任务分配区滚动条整体样式 */
            QScrollArea QScrollBar:vertical {
                background-color: #f5f5f5;
                width: 8px;
                border-radius: 4px;
                margin: 0px 2px 0px 2px;
            }
            /* 滚动条滑块样式 */
            QScrollArea QScrollBar::handle:vertical {
                background-color: #dcdcdc;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollArea QScrollBar::handle:vertical:hover {
                background-color: #b3b3b3;
            }
            QScrollArea QScrollBar::handle:vertical:pressed {
                background-color: #999999;
            }
            /* 隐藏滚动条上下箭头 */
            QScrollArea QScrollBar::add-line:vertical,
            QScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }
            /* 水平滚动条隐藏（按需） */
            QScrollArea QScrollBar:horizontal {
                height: 0px;
            }
        """)
        task_scroll_area.setWidgetResizable(True)
        task_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = FlowLayout(scroll_content, spacing=15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # role_obj = role_service.get_role_by_name(name=self.current_user["role"])
        # print(f"role_obj: {role_obj}")
        all_users = user_service.get_all_users(is_active=True)
        print(f"all_users: {all_users}")
        all_permission = []
        task_user_list = []
        for user in all_users:
            if user.roles[0].name == '管理员' or user.roles[0].name == '质检员':
                continue

            for role in user.roles:
                permission = [{"id": w.id, "work_name": w.work_name, "role": role.name} for w in role.permissions]
                user_list = [{"p_name": w.work_name, 'user': user.username} for w in role.permissions]
                all_permission.append(permission)
                task_user_list.append(user_list)

        self.all_permission = sorted({item['work_name']: item for item in itertools.chain.from_iterable(all_permission)}.values(), key=lambda x: x['id'])
        print(f"all_permission: {self.all_permission}")

        temp = defaultdict(set)
        for item in itertools.chain.from_iterable(task_user_list):
            temp[item['p_name']].add(item['user'])

        self.all_permission_user = [{'p_name': k, 'user_list': list(v)} for k, v in temp.items()]

        logger.info(f"all_permission_user: {self.all_permission_user}")

        self.task_names = []
        for task in self.all_permission:
            if task['work_name'] not in ["领卷登记", "任务分发", "系统管理", "统 计"]:
                self.task_names.append(task['work_name'])

        self.task_data = {
            task: {
                'widgets': [],
                'widget_container': None,
                'scroll_widget': None
            } for task in self.task_names
        }

        logger.info(f"所有任务: {self.task_data}")

        for task_name in self.task_names:
            task_card, widget_container, scroll_widget = self.create_task_card(task_name)
            self.task_data[task_name]['widget_container'] = widget_container
            self.task_data[task_name]['scroll_widget'] = scroll_widget
            scroll_layout.addWidget(task_card)

            if self.current_type == 1:
                self.add_task_widget(task_name, target_layout=widget_container)
            else:
                for task_item in self.tasks_dict_list[task_name]:
                    self.add_task_widget(task_name, target_layout=widget_container, task_config=task_item)

        task_scroll_area.setWidget(scroll_content)
        main_layout.addWidget(task_scroll_area, stretch=1)
        self.update_user_label()

    def create_navigation_breadcrumb(self, parent_layout):
        home_label = NavigationLabel("主页", is_clickable=True)
        home_label.clicked.connect(self.go_to_home)
        parent_layout.addWidget(home_label)
        separator1 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator1)
        task_table_label = NavigationLabel("任务分配表", is_clickable=True)
        task_table_label.clicked.connect(self.back_table)
        parent_layout.addWidget(task_table_label)
        separator2 = NavigationLabel(">", is_clickable=False)
        parent_layout.addWidget(separator2)
        task_label = NavigationLabel("任务分配", is_clickable=False)
        parent_layout.addWidget(task_label)
        parent_layout.setContentsMargins(0, 0, 0, 0)

    def go_to_home(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出重新登录!")

            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(500, self.close)

        else:
            from src.view.new_main_window import MainWindow
            main_window = MainWindow()
            main_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def create_task_card(self, task_name):
        card = CardWidget()
        card.setFixedWidth(420)
        card.setMinimumHeight(280)
        card.setMaximumHeight(350)
        card.setStyleSheet("""
            CardWidget {
                background-color: white;
                border-radius: 6px;
                border: 1px solid #f0f0f0;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(20, 15, 20, 15)
        task_title = StrongBodyLabel(task_name)
        task_title.setAlignment(Qt.AlignCenter)
        task_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2d3748;")
        card_layout.addWidget(task_title)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #e8e8e8; height: 1px; margin: 5px 0;")
        card_layout.addWidget(line)
        label_layout = QHBoxLayout()
        label_layout.setSpacing(25)
        staff_label = QLabel("人员")
        staff_label.setFixedWidth(120)
        staff_label.setAlignment(Qt.AlignCenter)
        staff_label.setStyleSheet("font-size: 15px; font-weight: 500; color: #4a5568;")
        seg_label = QLabel("任务段")
        seg_label.setFixedWidth(140)
        seg_label.setAlignment(Qt.AlignCenter)
        seg_label.setStyleSheet("font-size: 15px; font-weight: 500; color: #4a5568;")
        opt_label = QLabel("操作")
        opt_label.setFixedWidth(30)
        opt_label.setAlignment(Qt.AlignCenter)
        opt_label.setStyleSheet("font-size: 15px; font-weight: 500; color: #4a5568;")
        label_layout.addWidget(staff_label)
        label_layout.addStretch(1)
        label_layout.addWidget(seg_label)
        label_layout.addStretch(1)
        label_layout.addWidget(opt_label)
        label_layout.addStretch(2)
        card_layout.addLayout(label_layout)
        task_scroll = QScrollArea()
        task_scroll.setWidgetResizable(True)
        task_scroll.setMinimumHeight(120)
        task_scroll.setMaximumHeight(180)
        task_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #f0f0f0;
                border-radius: 6px;
                background-color: #fafafa;
            }
            /* 任务卡片内部滚动条样式优化 */
            QScrollArea QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 6px;
                border-radius: 3px;
                margin: 0px 1px 0px 1px;
            }
            QScrollArea QScrollBar::handle:vertical {
                background-color: #d0d0d0;
                border-radius: 3px;
                min-height: 15px;
            }
            QScrollArea QScrollBar::handle:vertical:hover {
                background-color: #b8b8b8;
            }
            QScrollArea QScrollBar::add-line:vertical,
            QScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollArea QScrollBar:horizontal {
                height: 0px;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #fafafa;")
        widget_container = QVBoxLayout(scroll_content)
        widget_container.setSpacing(5)
        widget_container.setContentsMargins(10, 10, 10, 10)
        widget_container.setAlignment(Qt.AlignTop)

        task_scroll.setWidget(scroll_content)
        card_layout.addWidget(task_scroll)

        add_btn = PushButton("添加人员")
        add_btn.setFixedWidth(100)
        add_btn.setFixedHeight(40)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            PushButton {
                background-color: #4299e1;
                color: white;
                border-radius: 4px;
                border: none;
                font-size: 15px;
            }
            PushButton:hover {
                background-color: #3182ce;
            }
            PushButton:pressed {
                background-color: #2b6cb0;
            }
        """)
        add_btn.clicked.connect(lambda _, t=task_name: self.add_task_widget(t))
        card_layout.addWidget(add_btn, alignment=Qt.AlignRight)

        return card, widget_container, task_scroll

    def add_task_widget(self, task_name, target_layout=None, task_config=None):
        end_number = ""
        select_people_data = []
        if target_layout is None:
            target_layout = self.task_data[task_name]['widget_container']
            if not target_layout:
                return
            had_add_peoples = [widgets['staff'].currentText() for widgets in self.task_data[task_name]['widgets']]
            logger.info(f"准备添加 {len(self.task_data[task_name]['widgets']) + 1 } 人")

            end_number = self.task_data[task_name]['widgets'][-1]['seg_end'].text()
            if len(end_number) < 4:
                show_warning(self, "警告", "任务段号长度必须为 4 位, 例： 0001")
                return

            if  end_number == self.start_end_number_edit.text().strip().split("-")[1]:
                show_warning(self, "提示", f"添加其人员时，请修改第 {len(self.task_data[task_name]['widgets'])} 人的任务截止号")
                return

            print(f"end_number: {end_number}; start_number: {self.task_data[task_name]['widgets'][-1]['seg_start'].text()}")
            if int(end_number) <= int(self.task_data[task_name]['widgets'][-1]['seg_start'].text()):
                show_warning(self, "警告", "任务段截止号必须大于开始号")
                return

            if int(end_number) > int(self.start_end_number_edit.text().strip().split("-")[1]):
                show_warning(self, "警告", "任务段的截止号不可超出本批次号的截止号!")
                return

            print(f"task_name = {task_name}")
            select_people_data = [item for item in next((item['user_list'] for item in self.all_permission_user if item['p_name'] == task_name), []) if not item in had_add_peoples]

            logger.info(f"已经添加了：{had_add_peoples}; {len(select_people_data)} 人")
            if "请选择人员" in had_add_peoples:
                show_warning(self, "警告提示", "必须选择当前人员后再添加其他人员！")
                return

            if (len(self.task_data[task_name]['widgets'][-1]['seg_start'].text()) == 0 or
                    len(self.task_data[task_name]['widgets'][-1]['seg_end'].text()) == 0):
                show_warning(self, "警告提示", "必须填写正确的任务段起止号, 才可以添加其他人员！")
                return


        if len(select_people_data) == 0:
            select_people_data = next((item['user_list'] for item in self.all_permission_user if item['p_name'] == task_name), [])

        widget_layout = QHBoxLayout()
        widget_layout.setSpacing(5)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setAlignment(Qt.AlignTop)

        staff_combo = ComboBox()
        staff_combo.addItems(select_people_data)
        staff_combo.setFixedWidth(120)
        staff_combo.setStyleSheet("""
            ComboBox {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            ComboBox:hover {
                border-color: #4299e1;
            }
            ComboBox:focus {
                border-color: #4299e1;
                outline: none;
            }
        """)
        seg_start = LineEdit()
        seg_start.setPlaceholderText("起始号")
        seg_start.setFixedWidth(80)
        seg_sep = QLabel("-")
        seg_sep.setAlignment(Qt.AlignCenter)
        seg_sep.setStyleSheet("color: #666; font-size: 16px;")
        seg_end = LineEdit()
        seg_end.setPlaceholderText("截止号")
        seg_end.setFixedWidth(80)
        for item in [seg_start, seg_end]:
            item.setStyleSheet("""
            LineEdit {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            LineEdit:hover {
                border-color: #4299e1;
            }
            LineEdit:focus {
                border-color: #4299e1;
                outline: none;
            }
        """)

        delete_btn = ToolButton()
        delete_btn.setIcon(FluentIcon.DELETE)
        delete_btn.setIconSize(QSize(18, 18))
        delete_btn.setFixedSize(28, 28)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet("""
            ToolButton {
                color: #666;
                border-radius: 4px;
                background-color: transparent;
                border: none;
            }
            ToolButton:hover {
                color: #e53e3e;
                background-color: #fef2f2;
            }
            ToolButton:pressed {
                color: #c53030;
                background-color: #fee2e2;
            }
        """)
        delete_btn.setToolTip("删除该人员配置")
        seg_layout = QHBoxLayout()
        seg_layout.addWidget(seg_start)
        seg_layout.addWidget(seg_sep)
        seg_layout.addWidget(seg_end)
        seg_layout.setAlignment(Qt.AlignTop)
        widget_layout.addWidget(staff_combo)
        widget_layout.addStretch(1)
        widget_layout.addLayout(seg_layout)
        widget_layout.addStretch(1)
        widget_layout.addWidget(delete_btn)
        widget_layout.addStretch(2)
        target_layout.addLayout(widget_layout)

        widget_data = {
            "staff": staff_combo,
            "seg_start": seg_start,
            "seg_end": seg_end,
            "seg_sep": seg_sep,
            "layout": widget_layout,
            "delete_btn": delete_btn,
            "seg_layout": seg_layout
        }
        if task_config is not None:
            staff_combo.setCurrentIndex(select_people_data.index(task_config.operator))
        else:
            staff_combo.setCurrentIndex(1)

        origin_len = len(self.start_end_number_edit.text().strip().split("-")[0])

        if len(end_number) > 0:
            nex_end_number = f"{(origin_len - len(str(int(end_number) + 1))) * '0'}{str(int(end_number) + 1)}"

            if task_config is not None:
                seg_start.setText(task_config.task_number.split("-")[0])
            else:
                seg_start.setText(nex_end_number)
        else:
            if task_config is not None:
                seg_start.setText(task_config.task_number_start)
            else:
                seg_start.setText(self.start_end_number_edit.text().strip().split("-")[0])

        if task_config is not None:
            seg_end.setText(task_config.task_number_end)
        else:
            seg_end.setText(self.start_end_number_edit.text().strip().split("-")[1])

        self.task_data[task_name]['widgets'].append(widget_data)

        delete_btn.clicked.connect(
            lambda _, t=task_name, w=widget_data: self.delete_task_widget(t, w)
        )
        self.task_data[task_name]['scroll_widget'].update()

    def delete_task_widget(self, task_name, widget_data):
        widgets_list = self.task_data[task_name]['widgets']
        widget_container = self.task_data[task_name]['widget_container']
        if len(widgets_list) <= 1:
            show_warning(self, "警告", "至少保留一个人员配置")
            return
        for widget_key in ['staff', 'seg_start', 'seg_end', 'seg_sep', 'delete_btn']:
            widget = widget_data.get(widget_key)
            if widget and hasattr(widget, 'deleteLater'):
                widget.deleteLater()

        seg_layout = widget_data['seg_layout']
        while seg_layout.count():
            seg_layout.takeAt(0)
        widget_data['layout'].removeItem(seg_layout)
        seg_layout.deleteLater()

        main_layout = widget_data['layout']
        while main_layout.count():
            main_layout.takeAt(0)

        index = widget_container.indexOf(main_layout)
        if index != -1:
            widget_container.removeItem(main_layout)
            main_layout.deleteLater()

        if index < len(widgets_list) - 1:
            widgets_list[index + 1]['seg_start'].setText(widget_data['seg_start'].text())

        widget_container.update()
        widgets_list.remove(widget_data)

        self.task_data[task_name]['scroll_widget'].update()
        self.task_data[task_name]['scroll_widget'].repaint()

    def get_task_assignment_data(self):
        task_assignment = []
        base_info = {
            "archive_type": self.archive_type_edit.text().strip(),
            "archive_unit": self.archive_unit_edit.text().strip(),
            "batch_number": self.batch_name_edit.text().strip(),
            "number_start": self.start_end_number_edit.text().strip().split("-")[0],
            "number_end": self.start_end_number_edit.text().strip().split("-")[1],
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        had_add_task_name = []
        for task_name, task_info in self.task_data.items():
            for widget_data in task_info['widgets']:
                staff_name = widget_data['staff'].currentText().strip()
                seg_start = widget_data['seg_start'].text().strip()
                seg_end = widget_data['seg_end'].text().strip()
                if staff_name == "请选择人员" or not seg_start or not seg_end:
                    continue
                if task_name not in had_add_task_name:
                    had_add_task_name.append(task_name)
                assignment_item = {
                    "task_type": task_name,
                    "staff_name": staff_name,
                    "segment_start": seg_start,
                    "segment_end": seg_end,
                    **base_info
                }
                task_assignment.append(assignment_item)
        if len(had_add_task_name) < len(self.task_names):
            show_error(self, "警告提示", f"{', '.join(list(set(self.task_names) - set(had_add_task_name)))}未分配")
            return []
        return task_assignment

    def save_taskInfo(self):
        task_data = self.get_task_assignment_data()
        if not task_data:
            show_error(self, "错误", "暂未获取到任务配置信息！")
            return
        task_id = 0
        tasks_list = []
        current_task_name = ""
        for task in task_data:
            task_dict = dict()
            task_dict["register_id"] = self.register_id
            task_dict["batch_number"] = self.batch_number
            task_dict["number_start"] = task["number_start"]
            task_dict["number_end"] = task["number_end"]
            task_dict["task_name"] = task["task_type"]
            task_dict["task_number_start"] = task['segment_start']
            task_dict["task_number_end"] = task['segment_end']
            task_dict["operator"] = task["staff_name"]
            task_dict["dist_officer"] = global_cache.get("current_user").get("username")
            task_dict["dist_date"] = task["create_time"]
            task_dict["status"] = 0
            if current_task_name != task_dict["task_name"]:
                task_id += 1
                current_task_name = task_dict["task_name"]
            task_dict["task_id"] = task_id
            task_dict["task_node"] = settings.work_number[task_dict["task_name"]]
            if task_id == 1:
                task_dict["is_ready"] = True

            tasks_list.append(task_dict)

        had_task_list = task_service.get_list(register_id=self.register_id)
        if had_task_list:
            for task in had_task_list:
                task_service.delete_task(id=task.id)

        is_valid, errors = self.validate_task_number(tasks_list)
        if not is_valid:
            show_warning(self, "警告", f"{errors}", 5000)
            return

        save_result = task_service.batch_add(tasks_list)
        if save_result:
            register_service.update(register_id=self.current_data[0], update_data={"is_distribute": True})
            show_success(self, "保存成功", f"已保存 {len(task_data)} 条任务分配记录")

    def submit_taskInfo(self):
        task_data = self.get_task_assignment_data()
        if not task_data:
            return
        task_id = 0
        tasks_list = []
        current_task_name = ""
        for task in task_data:
            task_dict = dict()
            task_dict["register_id"] = self.register_id
            task_dict["batch_number"] = self.batch_number
            task_dict["number_start"] = task["number_start"]
            task_dict["number_end"] = task["number_end"]
            task_dict["task_name"] = task["task_type"]
            task_dict["task_number_start"] = task['segment_start']
            task_dict["task_number_end"] = task['segment_end']
            task_dict["operator"] = task["staff_name"]
            task_dict["dist_officer"] = global_cache.get("current_user").get("username")
            task_dict["dist_date"] = task["create_time"]
            task_dict["status"] = 1

            if current_task_name != task_dict["task_name"]:
                task_id += 1
                current_task_name = task_dict["task_name"]
            task_dict["task_id"] = task_id
            task_dict["task_node"] = settings.work_number[task_dict["task_name"]]
            if task_id == 1:
                task_dict["is_ready"] = True

            tasks_list.append(task_dict)

        exist_task = task_service.get_list(register_id=self.register_id)
        print(f"exist_task: {exist_task}")
        if exist_task and exist_task[0].status == 1:
            show_warning(self, "警告", "该批次已完成分配!")
            return
        elif exist_task and exist_task[0].status == 0:
            for task in exist_task:
                task_service.delete_task(id=task.id)
        try:
            is_valid, errors = self.validate_task_number(tasks_list)
            if not is_valid:
                show_warning(self, "警告", f"{errors}", 5000)
                return

            save_result = task_service.batch_add(tasks_list)
            if save_result:
                register_service.update(register_id=self.current_data[0], update_data={"is_distribute": True})
                show_success(self, "提交成功", f"已保存 {len(task_data)} 条任务分配记录")
                self.save_btn.setEnabled(False)
                self.submit_btn.setEnabled(False)
            operation_data = {
                "task_id": self.current_data[0],
                "task_name": "任务分配",
                "operator": self.current_user['username'],
                "operator_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator_remark": f"为用户分配工作任务; 任务ID：{[task['task_id'] for task in tasks_list]}"
            }
            try:
                operation_service.save_data([operation_data])
            except Exception as oe:
                logger.error(f"添加操作日志失败: {str(oe)}, 操作信息：{operation_data}")
        except Exception as e:
            logger.error(f"分配任务失败; {str(e)}")

    def validate_task_number(self, tasks: list[dict[str, str]]) -> tuple[bool, list[str]]:
        errors = []

        for task in tasks:
            tid = task.get("task_id")
            tname = task.get("task_name")
            start = task.get("task_number_start", "")
            end = task.get("task_number_end", "")

            if len(start) != 4:
                errors.append(f"[任务ID={tid}, 任务名称={tname}] 任务段开始号={start} 长度不为 4")

            if len(end) != 4:
                errors.append(f"[任务ID={tid}, 任务名称={tname}] 任务段结束号={end} 长度不为 4")


        groups: dict[tuple, list[dict]] = defaultdict(list)

        for task in tasks:
            key = (task["register_id"], task["batch_number"], task["task_name"])
            groups[key].append(task)

        for (register_id, batch_number, task_name), group in groups.items():
            number_start = group[0].get("number_start")
            number_end = group[0].get("number_end")
            prefix = f"[批次ID={register_id}, 批次号={batch_number}, 任务名称={task_name}]"

            if len(group) == 1:
                rec = group[0]
                if rec["task_number_start"] != number_start:
                    errors.append(f"{prefix} 单条记录 任务段开始号='{rec['task_number_start']}' "
                                  f"与 任务起始号='{number_start}' 不一致")

                if rec["task_number_end"] != number_end:
                    errors.append(f"{prefix} 单条记录 任务段结束号='{rec['task_number_end']}' "
                                  f"与 任务截止号='{number_end}' 不一致")

            else:
                if group[0]["task_number_start"] != number_start:
                    errors.append(
                        f"{prefix} 第一条 任务段开始号 = '{group[0]['task_number_start']}' 与 任务起始号='{number_start}' 不一致"
                    )

                if group[-1]["task_number_end"] != number_end:
                    errors.append(
                        f"{prefix} 最后一条 任务段结束号 = '{group[-1]['task_number_end']}' 与 任务截止号 ='{number_end}' 不一致 "
                    )

                for i in range(len(group) -1):
                    cur_end = group[i]["task_number_end"]
                    nxt_start = group[i+1]["task_number_start"]
                    if int(cur_end) + 1 != int(nxt_start):
                        errors.append(
                            f"{prefix} 第 {i + 1} 条 任务段结束号 = '{cur_end}' 与 第 {i + 2} 条 任务段开始号='{nxt_start}' 不连续"
                        )

        is_valid = len(errors) == 0
        return is_valid, errors

    def back_table(self):
        self._is_navigation = True
        if global_cache.get("current_user", None) is None:
            show_warning(self, "警告", "登录超时, 请退出重新登录!")

            from src.view.login import LoginWindow
            LoginWindow().showFullScreen()
            QTimer.singleShot(500, self.close)
        else:
            from src.view.task_window.taskTable_window import TaskTableWindow
            taskTable_window = TaskTableWindow()
            taskTable_window.showFullScreen()
            QTimer.singleShot(100, self.close)

    def update_user_label(self):
        self.current_user = global_cache.get("current_user")
        if self.current_user:
            username = self.current_user.get("username", "未知用户")
            userrole = self.current_user.get("role", "未知角色")
            self.user_label = QLabel(f"👤 {username} ({userrole})")
        else:
            show_warning(self, "警告", "登录超时, 请退出重新登录!")
            return

    def logout(self):
        global_cache.set("current_user", None)

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