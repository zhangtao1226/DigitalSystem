# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : user_manage_page.py
# @Desc     : 系统管理-用户管理页面
# @Time     : 2025/12/16 09:14
# @Software : PyCharm

import time
from dataclasses import dataclass
from typing import List, Dict, Optional

from PySide6.QtGui import (
    QFont, QColor,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QHeaderView, QLabel, QWidget, QTableWidgetItem, QDialog,
    QAbstractItemView, QFormLayout, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import (
    StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    LineEdit, ComboBox, FluentIcon, TableWidget, CheckBox, IconWidget, CardWidget,
)

from src.core.cache_manager import global_cache
from src.services.user_service import user_service
from src.services.role_service import role_service
from src.utils.NotificationTool import show_error, show_warning, show_success

# 数据模型定义
@dataclass
class User:
    username: str
    password: str
    role: str
    is_active: bool
    create_time: str
    last_login: str = ""


# 用户管理对话框
class UserEditDialog(QDialog):
    def __init__(self, user: Optional[User] = None, roles: List[str] = [], parent=None):
        super().__init__(parent)
        self.user = user
        self.roles = roles
        self.setWindowTitle("添加用户" if not user else "修改用户")
        self.resize(500, 450)
        self.setWindowModality(Qt.ApplicationModal)

        self.init_ui()

        if user:
            self.fill_user_data()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 20)

        # 标题标签
        title_label = QLabel(self.windowTitle())
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #1890ff;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 分隔线
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e8e8e8;")
        layout.addWidget(line)

        # 表单容器
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(18)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # 用户名输入框
        self.username_edit = LineEdit()
        self.username_edit.setPlaceholderText("请输入用户名（3-20个字符）")
        form_layout.addRow("用户名：", self.username_edit)

        # 密码输入框
        self.password_edit = LineEdit()
        self.password_edit.setPlaceholderText("请输入密码（至少6位）")
        self.password_edit.setEchoMode(LineEdit.Password)
        form_layout.addRow("密码：", self.password_edit)

        # 角色选择框
        self.role_list = QListWidget()
        self.role_list.setFixedHeight(120)
        self.role_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d9d9d9;
                border-radius: 6px;
                background-color: #fff;
                padding: 4px;
            }
            QListWidget:: item {
                height: 28px;
                padding-left: 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #e6f4ff;
            }
            QListWidget::item:selected {
                background-color: transparent;
                color: #000;
            }
            """
        )
        for role_name in self.roles:
            if role_name == "管理员":
                continue
            item = QListWidgetItem(role_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.role_list.addItem(item)
        form_layout.addRow("角色", self.role_list)

        # 状态选择框
        status_layout = QHBoxLayout()
        self.status_check = CheckBox("启用账户")
        self.status_check.setChecked(True)
        status_layout.addWidget(self.status_check)
        status_layout.addStretch()
        form_layout.addRow("状态：", status_layout)

        layout.addWidget(form_widget)
        layout.addStretch()

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        self.confirm_btn = PrimaryPushButton("确认")
        self.confirm_btn.setFixedWidth(100)
        self.confirm_btn.setObjectName("dialog_confirm_btn")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1890ff;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            """
        )

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setObjectName("dialog_cancel_btn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                border: 1px solid #d9d9d9;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #bfbfbf;
            }
            QPushButton:pressed {
                background-color: #d9d9d9;
            }
            """
        )

        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # 连接信号
        self.confirm_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def fill_user_data(self):
        """填充用户数据"""
        if self.user:
            self.username_edit.setText(self.user.username)
            # self.password_edit.setText(self.user.password)
            user_role_names = {role.name for role in self.user.roles}
            for i in range(self.role_list.count()):
                item = self.role_list.item(i)
                item.setCheckState(
                    Qt.Checked if item.text() in user_role_names else Qt.Unchecked
                )
            self.status_check.setChecked(self.user.is_active)

    def get_user_data(self) -> Dict:
        """获取用户输入的数据"""
        selected_roles = []
        for i in range(self.role_list.count()):
            item = self.role_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_roles.append(item.text())

        return {
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text().strip(),
            "roles": selected_roles,
            "is_active": self.status_check.isChecked()
        }


class UserManagePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons_styled = False

        self.current_page = 1
        self.total_pages = 1
        self.page_sizes = [10, 20, 50]
        self.current_page_size = self.page_sizes[0]
        self.total_rows = 0
        self.all_data = []

        self.init_ui()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)

        title_icon = IconWidget(FluentIcon.PEOPLE)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)

        title_label = StrongBodyLabel("用户管理")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 按钮栏
        btn_container = CardWidget()
        btn_container.setFixedHeight(70)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(15)
        btn_layout.setContentsMargins(20, 15, 20, 15)

        self.add_btn = PrimaryPushButton("添加用户")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedSize(96, 36)
        self.add_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                border-radius: 8px;
                background-color: #ef5b5b;
                color: white;
                border: 1px solid #bbdefb;
                padding: 3px 6px;
                min-height: 30px;
                min-width: 60px;
            }
        """)

        self.refresh_btn = PushButton("刷新")
        self.refresh_btn.setFixedSize(96, 36)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_btn)
        layout.addWidget(btn_container)

        # 创建表格区域
        self.create_table_section(layout)
        self.load_all_data()
        self.update_table_display()

        # 连接信号
        self.add_btn.clicked.connect(self.add_user)
        self.refresh_btn.clicked.connect(self.refresh_user_table)

    def create_table_section(self, parent_layout):
        self.create_table(parent_layout)
        self.create_pagination_control(parent_layout)

    def create_table(self, parent_layout):
        self.table_widget = TableWidget()

        headers = ["ID", "用户名称", "角色", "状态", "创建时间", "最近登录时间", "操作"]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)

        # 设置表头字体大小（修改为16）
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        self.table_widget.horizontalHeader().setFont(header_font)

        # 设置表格内容字体大小（修改为10）
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
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 设置列宽
        self.table_widget.setColumnWidth(0, 100)  # ID
        self.table_widget.setColumnWidth(1, 120)  # 用户名称
        self.table_widget.setColumnWidth(2, 420)  # 角色名称
        self.table_widget.setColumnWidth(3, 100)  # 状态
        self.table_widget.setColumnWidth(4, 200)  # 创建时间
        self.table_widget.setColumnWidth(5, 200)  # 最近登录时间
        self.table_widget.setColumnWidth(6, 260)  # 操作

        # 设置行高
        self.table_widget.verticalHeader().setDefaultSectionSize(45)

        parent_layout.addWidget(self.table_widget)

    def create_pagination_control(self, parent_layout):
        """创建分页控件"""
        pagination_layout = QHBoxLayout()
        pagination_layout.setAlignment(Qt.AlignRight)

        # 每页显示行数选择
        page_size_label = QLabel("每页显示:")
        page_size_label.setStyleSheet("font-size: 12px; color: #666;")

        self.page_size_combo = ComboBox()
        self.page_size_combo.addItems([str(size) for size in self.page_sizes])
        self.page_size_combo.setCurrentText(str(self.current_page_size))
        self.page_size_combo.setFixedWidth(80)
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)

        # 页码显示
        self.page_info_label = QLabel(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")
        self.page_info_label.setStyleSheet("font-size: 12px; color: #666; margin: 0 10px;")

        # 上一页按钮
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.prev_button = PushButton("上一页")
        self.prev_button.setIcon(FluentIcon.PAGE_LEFT)
        self.prev_button.setFixedWidth(100)
        self.prev_button.clicked.connect(self.prev_page)
        self.prev_button.setEnabled(False)
        self.prev_button.setFont(font)

        # 下一页按钮
        self.next_button = PushButton("下一页")
        self.next_button.setIcon(FluentIcon.PAGE_RIGHT)
        self.next_button.setFixedWidth(100)
        self.next_button.setFont(font)
        self.next_button.clicked.connect(self.next_page)

        # 添加到布局
        pagination_layout.addWidget(page_size_label)
        pagination_layout.addWidget(self.page_size_combo)
        pagination_layout.addSpacing(20)
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_info_label)
        pagination_layout.addWidget(self.next_button)

        parent_layout.addLayout(pagination_layout)

    def load_all_data(self):
        """加载所有数据"""
        self.all_data = []
        for user in user_service.get_all_users():
            user_data = [
                str(user.id),
                user.username,
                ', '.join(role.name for role in user.roles) if user.roles else "",
                user.is_active,
                user.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else "",
                ""
            ]
            self.all_data.append(user_data)

        self.total_rows = len(self.all_data)
        self.calculate_total_pages()

    def calculate_total_pages(self):
        """计算总页数"""
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
                if col == len(data) - 1:  # 操作列
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    button_layout.setContentsMargins(5, 2, 5, 2)
                    button_layout.setSpacing(5)

                    # 修改按钮
                    edit_button = PrimaryPushButton("修改")
                    edit_button.setFixedSize(80, 32)
                    edit_button.setCursor(Qt.PointingHandCursor)

                    # 删除按钮
                    delete_button = PrimaryPushButton("删除")
                    delete_button.setFixedSize(80, 32)
                    delete_button.setCursor(Qt.PointingHandCursor)


                    if data[2] == "管理员" or data[2] == "质检员":
                        edit_button.setEnabled(False)
                        delete_button.setEnabled(False)

                    # 连接信号
                    original_row = start_index + row
                    edit_button.clicked.connect(lambda checked, r=original_row: self.edit_user(r))
                    delete_button.clicked.connect(lambda checked, r=original_row: self.delete_user(r))

                    button_layout.addWidget(edit_button)
                    button_layout.addWidget(delete_button)
                    button_layout.addStretch()

                    self.table_widget.setCellWidget(row, col, button_widget)

                elif col == 3:  # 状态列
                    is_active = data[col]
                    item = QTableWidgetItem("● 启用" if is_active else "● 禁用")
                    item.setForeground(QColor("#52c41a") if is_active else QColor("#ff4d4f"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setFont(QFont("Microsoft YaHei", 11))
                    self.table_widget.setItem(row, col, item)
                else:
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_widget.setItem(row, col, item)

    def on_page_size_changed(self, text):
        """每页显示行数改变时的处理"""
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
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.calculate_total_pages()
            self.update_table_display()

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.calculate_total_pages()
            self.update_table_display()

    def refresh_user_table(self):
        self.load_all_data()
        self.update_table_display()
        show_success(self, "更新提示", "用户表已更新！")

    def add_user(self):
        """添加用户"""
        roles = [r.name for r in role_service.get_all_roles()]
        dialog = UserEditDialog(roles=roles, parent=self)

        if dialog.exec():
            user_data = dialog.get_user_data()

            # 验证输入
            if not user_data["username"]:
                show_error(self, "输入错误", "用户名不能为空！")
                return

            if len(user_data["username"]) < 2:
                show_error(self, "输入错误", "用户名至少需要2个字符！")
                return

            if user_data["password"] and len(user_data["password"]) < 6:
                show_error(self, "输入错误", "密码至少需要6个字符！")
                return

            # 检查用户名是否已存在
            existing_user = user_service.get_user_by_username(username=user_data["username"])
            if existing_user:
                show_error(self, "添加失败", f"用户名 {user_data['username']} 已存在！")
                return

            # 创建新用户
            new_user = {
                "username": user_data["username"],
                "password": user_data["password"] or "123456",
                "roles": user_data["roles"],
                "is_active": user_data["is_active"],
                "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_login": "",
            }

            if user_service.create_user(new_user):
                self.load_all_data()
                self.update_table_display()
                show_success(self, "添加成功", f"用户 {user_data['username']} 添加成功！")
            else:
                show_error(self, "添加失败", "用户添加失败，请重试！")

    def edit_user(self, row):
        """修改用户"""
        data = self.all_data[row]
        user_id = int(data[0])
        user_name = data[1]

        if user_name == "admin":
            show_warning(self, "操作警告", "管理员不可被修改或删除!")
            return

        user = user_service.get_user_by_id(user_id)
        if user:
            roles = [r.name for r in role_service.get_all_roles()]
            dialog = UserEditDialog(user=user, roles=roles, parent=self)

            if dialog.exec():
                user_data = dialog.get_user_data()

                # 验证输入
                if not user_data["username"]:
                    show_error(self, "输入错误", "用户名不能为空！")
                    return

                if len(user_data["username"]) < 2:
                    show_error(self, "输入错误", "用户名至少需要2个字符！")
                    return

                if user_data["password"] and len(user_data["password"]) < 6:
                    show_error(self, "输入错误", "密码至少需要6个字符！")
                    return

                # 检查用户名是否已存在（排除当前用户）
                existing_user = user_service.get_user_by_username(username=user_data["username"])
                if existing_user and existing_user.id != user_id:
                    show_error(self, "修改失败", f"用户名 {user_data['username']} 已存在！")
                    return

                # 更新用户信息
                update_data = {
                    "username": user_data["username"],
                    "password": user_data["password"],
                    "roles": user_data["roles"],
                    "is_active": user_data["is_active"]
                }
                print(f"update_data: {update_data}")

                if user_service.update_user(user_id, update_data):
                    self.load_all_data()
                    self.update_table_display()
                    show_success(self, "修改成功", f"用户 {user_data['username']} 修改成功！")
                else:
                    show_error(self, "修改失败", "用户修改失败，请重试！")

    def delete_user(self, row):
        """删除用户"""
        data = self.all_data[row]
        user_id = int(data[0])
        user_name = data[1]
        user_role = data[2]

        if user_name == "admin" or user_role == "管理员":
            show_warning(self, "操作警告", "管理员不可被修改或删除!")
            return

        box = MessageBox(
            '确认删除',
            f'确定要删除用户 "【{user_name}】" 吗？此操作不可撤销！',
            self
        )
        box.yesButton.setText('删除')
        box.cancelButton.setText('取消')

        box.yesButton.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
            QPushButton:pressed {
                background-color: #d32f2f;
            }
        """)

        # 设置取消按钮样式
        box.cancelButton.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 500;
                border: 1px solid #d9d9d9;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #bfbfbf;
            }
            QPushButton:pressed {
                background-color: #d9d9d9;
            }
        """)

        if box.exec():
            if user_service.delete_user(user_id):
                self.load_all_data()
                self.update_table_display()
                show_success(self, "删除成功", f"用户 {user_name} 删除成功！")
            else:
                show_error(self, "删除失败", "用户删除失败，请重试！")