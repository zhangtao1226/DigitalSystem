# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : role_manage_page.py
# @Desc     : 系统管理-角色管理
# @Time     : 2025/12/16 09:16
# @Software : PyCharm

from dataclasses import dataclass
from typing import Dict, Optional, List

from PySide6.QtGui import QFont, QColor, QPainter, QMouseEvent
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QHeaderView, QLabel, QWidget, QTableWidgetItem, QDialog,
    QAbstractItemView, QFormLayout, QScrollArea, QSizePolicy, QFrame, QGridLayout,
    QSpacerItem, QSizePolicy, QLayout
)
from PySide6.QtCore import Qt, QTimer, QSize, QRect, Signal, QPoint  # 修复：导入QPoint

from qfluentwidgets import (
    StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    LineEdit, ComboBox, FluentIcon, TableWidget,
    TextEdit, IconWidget, CardWidget, RoundMenu, Action,
    ToolTipFilter, ToolTipPosition
)

from src.services.role_service import role_service
from src.services.workflow_service import workflow_service
from src.utils.NotificationTool import show_warning, show_success, show_error

@dataclass
class Role:
    id: int
    role_name: str
    description: str
    # 新增权限字段
    permissions: List[str] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []

class PermissionTag(QWidget):
    remove_permission = Signal(str)
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.setFixedHeight(32)
        self.setMinimumWidth(80)
        self.setMaximumWidth(200)  # 限制最大宽度
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(6)

        # 标签文本
        self.label = QLabel(text)
        self.label.setStyleSheet("""
            QLabel {
                color: #262626;
                font-size: 12px;
                padding: 0 2px;
            }
        """)
        layout.addWidget(self.label)

        # 添加伸缩项，让文本居中
        layout.addStretch()

        # 删除图标
        self.close_icon = IconWidget(FluentIcon.CLOSE)
        self.close_icon.setFixedSize(14, 14)
        self.close_icon.setStyleSheet("""
            IconWidget {
                color: #8c8c8c;
            }
            IconWidget:hover {
                color: #ff4d4f;
            }
        """)
        layout.addWidget(self.close_icon)

        # 整体样式 - 标签整体带边框
        self.setStyleSheet("""
            PushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #d9d9d9;
                border-radius: 6px;
                font-size: 14px;
            }
            PushButton:hover {
                background-color: #e8e8e8;
                border-color: #bfbfbf;
            }
            PushButton:pressed {
                background-color: #d9d9d9;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # 点击任意位置都触发删除
            self.remove_permission.emit(self.text)
            self.deleteLater()
        super().mousePressEvent(event)


# 权限选择容器
class PermissionSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_permissions = []
        self.permission_buttons = {}

        self.ALL_PERMISSIONS = []
        for work in workflow_service.get_all_workflows():
            if work.status:
                self.ALL_PERMISSIONS.append(work.work_name)

        self.init_ui()

    def init_ui(self):
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # 增加间距
        layout.setContentsMargins(0, 0, 0, 0)

        # 已选权限区域
        selected_group = QWidget()
        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setSpacing(8)
        selected_layout.setContentsMargins(0, 0, 0, 0)

        # 已选权限标题
        selected_title = QLabel("已选权限：")
        selected_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #333;
                font-weight: 500;
                margin-bottom: 5px;
            }
        """)
        selected_layout.addWidget(selected_title)

        # 已选权限容器
        self.tags_container = QWidget()
        self.tags_container.setMinimumHeight(120)  # 设置最小高度
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(5)

        # 创建流式布局容器
        self.tags_flow_widget = QWidget()
        self.tags_flow_layout = FlowLayout(self.tags_flow_widget, 8, 8)
        self.tags_flow_layout.setContentsMargins(0, 0, 0, 0)

        self.tags_layout.addWidget(self.tags_flow_widget)
        self.tags_layout.addStretch()

        # 已选权限容器
        self.tags_wrapper = QWidget()
        self.tags_wrapper_layout = QVBoxLayout(self.tags_wrapper)
        self.tags_wrapper_layout.setContentsMargins(10, 10, 10, 10)
        self.tags_wrapper_layout.addWidget(self.tags_container)

        self.tags_wrapper.setStyleSheet("""
            QWidget {
                border-radius: 6px;
                background-color: white;
            }
        """)

        selected_layout.addWidget(self.tags_wrapper)

        layout.addWidget(selected_group)

        # 添加分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e8e8e8; margin: 10px 0;")
        layout.addWidget(separator)

        # 可选权限区域
        options_group = QWidget()
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(8)
        options_layout.setContentsMargins(0, 0, 0, 0)

        # 可选权限标题
        options_title = QLabel("可选权限：")
        options_title.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #333;
                font-weight: 500;
                margin-bottom: 5px;
            }
        """)
        options_layout.addWidget(options_title)

        # 权限按钮容器
        self.permissions_container = QWidget()
        self.permissions_container.setMinimumHeight(160)  # 设置最小高度
        self.permissions_layout = QVBoxLayout(self.permissions_container)
        self.permissions_layout.setContentsMargins(0, 0, 0, 0)
        self.permissions_layout.setSpacing(5)

        # 创建流式布局容器
        self.perms_flow_widget = QWidget()
        self.perms_flow_layout = FlowLayout(self.perms_flow_widget, 8, 8)
        self.perms_flow_layout.setContentsMargins(0, 0, 0, 0)

        self.permissions_layout.addWidget(self.perms_flow_widget)
        self.permissions_layout.addStretch()

        # 创建权限按钮
        self.create_permission_buttons()

        # 可选权限容器
        self.permissions_wrapper = QWidget()
        self.permissions_wrapper_layout = QVBoxLayout(self.permissions_wrapper)
        self.permissions_wrapper_layout.setContentsMargins(10, 10, 10, 10)
        self.permissions_wrapper_layout.addWidget(self.permissions_container)

        self.permissions_wrapper.setStyleSheet("""
            QWidget {
                border-radius: 6px;
                background-color: white;
            }
        """)

        options_layout.addWidget(self.permissions_wrapper)

        layout.addWidget(options_group)

        # 设置整个选择器的最小高度
        self.setMinimumHeight(350)

    def create_permission_buttons(self):
        """创建权限按钮（流式布局，多行显示）"""
        # 清空现有按钮
        self.clear_layout(self.perms_flow_layout)
        self.permission_buttons.clear()

        # 创建新按钮
        for perm in self.ALL_PERMISSIONS:
            # 跳过已选中的权限
            if perm in self.selected_permissions:
                continue

            btn = PushButton(perm)
            btn.setFixedSize(100, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                PushButton {
                    background-color: #f5f5f5;
                    color: #333;
                    border: 1px solid #d9d9d9;
                    border-radius: 6px;
                    font-size: 14px;
                }
                PushButton:hover {
                    background-color: #e8e8e8;
                    border-color: #bfbfbf;
                }
                PushButton:pressed {
                    background-color: #d9d9d9;
                }
            """)
            btn.clicked.connect(lambda checked, p=perm: self.on_permission_click(p))
            self.permission_buttons[perm] = btn

            # 添加到流式布局
            self.perms_flow_layout.addWidget(btn)

    def clear_layout(self, layout):
        """清空布局中的所有控件"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self.clear_layout(item.layout())

    def on_permission_click(self, permission: str):
        """权限按钮点击事件 - 添加到已选并从可选区域移除"""
        if permission not in self.selected_permissions:
            # 添加到已选权限
            self.selected_permissions.append(permission)

            # 创建标签并添加到已选区域
            self.add_permission_tag(permission)

            # 重新创建可选权限按钮
            self.create_permission_buttons()

    def add_permission_tag(self, permission: str):
        """添加权限标签到已选区域"""
        tag = PermissionTag(permission)
        tag.remove_permission.connect(self.on_tag_remove)

        # 添加到流式布局
        self.tags_flow_layout.addWidget(tag)

    def on_tag_remove(self, permission: str):
        """标签删除事件 - 从已选移除并添加回可选区域"""
        if permission in self.selected_permissions:
            self.selected_permissions.remove(permission)

            # 重新创建权限按钮并动态重排
            self.create_permission_buttons()

    def set_permissions(self, permissions: List[str]):
        self.selected_permissions = permissions.copy()
        self.clear_layout(self.tags_flow_layout)
        for perm in permissions:
            if perm in self.ALL_PERMISSIONS:
                self.add_permission_tag(perm)
        self.create_permission_buttons()

    def get_permissions(self) -> List[str]:
        return self.selected_permissions.copy()


class FlowLayout(QLayout):
    def __init__(self, parent=None, horizontal_spacing=-1, vertical_spacing=-1):
        super().__init__(parent)
        self.setSpacing(horizontal_spacing)
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing

        self.item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

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
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def spacing(self):
        return self.horizontal_spacing

    def do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0

        h_space = self.spacing()
        v_space = self.vertical_spacing

        if h_space == -1:
            h_space = self.style().layoutSpacing(QSizePolicy.PushButton,
                                                 QSizePolicy.PushButton, Qt.Horizontal)
        if v_space == -1:
            v_space = self.style().layoutSpacing(QSizePolicy.PushButton,
                                                 QSizePolicy.PushButton, Qt.Vertical)

        for item in self.item_list:
            wid = item.widget()
            if wid is None:
                continue

            next_x = x + item.sizeHint().width() + h_space

            if next_x - h_space > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + v_space
                next_x = x + item.sizeHint().width() + h_space
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


# 角色管理对话框
class RoleEditDialog(QDialog):
    def __init__(self, role: Optional[Role] = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.setWindowTitle("添加角色" if not role else "修改角色")
        self.resize(700, 650)
        self.setWindowModality(Qt.ApplicationModal)

        self.init_ui()

        if role:
            self.fill_role_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 20)
        title_label = QLabel(self.windowTitle())
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #1890ff;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #e8e8e8;")
        layout.addWidget(line)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(20)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入角色名称")
        self.name_edit.setMinimumWidth(300)
        form_layout.addRow("角色名称：", self.name_edit)

        self.permission_selector = PermissionSelector()
        self.permission_selector.setMinimumWidth(500)
        form_layout.addRow("权限：", self.permission_selector)

        self.desc_edit = TextEdit()
        self.desc_edit.setPlaceholderText("请输入角色描述")
        self.desc_edit.setFixedHeight(80)
        self.desc_edit.setMinimumWidth(300)
        form_layout.addRow("描述：", self.desc_edit)

        layout.addWidget(form_widget)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.setContentsMargins(0, 10, 0, 10)

        self.confirm_btn = PrimaryPushButton("确认")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setFixedWidth(100)
        self.confirm_btn.setObjectName("dialog_confirm_btn")
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
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setObjectName("dialog_cancel_btn")
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

        self.confirm_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def fill_role_data(self):
        if self.role:
            self.name_edit.setText(self.role.role_name)
            self.desc_edit.setText(self.role.description)
            if hasattr(self.role, 'permissions') and self.role.permissions:
                self.permission_selector.set_permissions(self.role.permissions)

    def get_role_data(self) -> Dict:
        return {
            "role_name": self.name_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "permissions": self.permission_selector.get_permissions()
        }


class RoleManagePage(QWidget):
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
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)
        title_icon = IconWidget(FluentIcon.CERTIFICATE)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)
        title_label = StrongBodyLabel("角色管理")
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

        self.add_btn = PrimaryPushButton("添加角色")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedSize(96, 36)

        # 刷新按钮
        self.refresh_btn = PushButton("刷新")
        self.refresh_btn.setFixedSize(96, 36)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_btn)
        layout.addWidget(btn_container)
        self.create_table_section(layout)
        self.load_all_data()
        self.update_table_display()
        self.add_btn.clicked.connect(self.add_role)
        self.refresh_btn.clicked.connect(self.refresh_role_table)

    def create_table_section(self, parent_layout):
        self.create_table(parent_layout)
        self.create_pagination_control(parent_layout)

    def create_table(self, parent_layout):
        self.table_widget = TableWidget()

        headers = ["ID", "角色名称","角色权限", "描述", "创建时间", "更新时间", "操作"]
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

        self.table_widget.setColumnWidth(0, 100)  # ID
        self.table_widget.setColumnWidth(1, 120)  # 角色名称
        self.table_widget.setColumnWidth(2, 660)  # 角色权限
        self.table_widget.setColumnWidth(3, 300)  # 描述
        self.table_widget.setColumnWidth(4, 180)  # 创建时间
        self.table_widget.setColumnWidth(5, 180)  # 更新时间
        self.table_widget.setColumnWidth(6, 240)  # 操作

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
        for role in role_service.get_all_roles():
            role_data = [
                str(role.id),
                role.name,
                ", ".join([work.work_name for work in role.workflows] if role.workflows else ""),
                role.desc,
                role.create_time.strftime("%Y-%m-%d %H:%M:%S") if role.create_time else None,
                role.update_time.strftime("%Y-%m-%d %H:%M:%S") if role.update_time else None,
                ""
            ]
            self.all_data.append(role_data)

        self.total_rows = len(self.all_data)
        self.calculate_total_pages()

    def calculate_total_pages(self):
        """计算总页数"""
        if self.current_page_size == 0:
            self.total_pages = 1
        else:
            self.total_pages = (self.total_rows + self.current_page_size - 1) // self.current_page_size

        # 更新页码信息显示
        self.page_info_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")

        # 更新按钮状态
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < self.total_pages)

    def update_table_display(self):
        """更新表格显示当前页的数据"""
        # 清空表格
        self.table_widget.setRowCount(0)

        if self.total_rows == 0:
            return

        # 计算当前页显示的数据范围
        start_index = (self.current_page - 1) * self.current_page_size
        end_index = min(start_index + self.current_page_size, self.total_rows)
        current_data = self.all_data[start_index:end_index]

        # 添加数据到表格
        for row, data in enumerate(current_data):
            self.table_widget.insertRow(row)
            for col, value in enumerate(data):
                if col == len(data) - 1:  # 操作列
                    # 创建操作按钮布局
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

                    original_row = start_index + row
                    edit_button.clicked.connect(lambda checked, r=original_row: self.edit_role(r))
                    delete_button.clicked.connect(lambda checked, r=original_row: self.delete_role(r))

                    if data[1] == "管理员" or data[1] == "质检员":
                        edit_button.setEnabled(False)
                        delete_button.setEnabled(False)

                    button_layout.addWidget(edit_button)
                    button_layout.addWidget(delete_button)
                    button_layout.addStretch()

                    self.table_widget.setCellWidget(row, col, button_widget)
                else:
                    item = QTableWidgetItem(value)
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

    def refresh_role_table(self):
        """刷新表格"""
        self.load_all_data()
        self.update_table_display()
        show_success(self, "消息提示", "角色表已刷新")

    def add_role(self):
        """添加角色"""
        dialog = RoleEditDialog(parent=self)

        if dialog.exec():
            role_data = dialog.get_role_data()
            print(role_data)

            # 验证输入
            if not role_data["role_name"]:
                show_error(self, "输入错误", "角色名称不能为空！")
                return

            # 检查角色名是否已存在
            is_exist = role_service.get_role_by_name(name=role_data["role_name"])
            if is_exist:
                show_error(self, "添加失败", f"角色 {role_data['role_name']} 已存在！")
                return

            result = role_service.create_role(
                name=role_data["role_name"],
                permissions=role_data["permissions"],
                desc=role_data["description"]
            )
            if result.id:
                self.load_all_data()
                self.update_table_display()
                show_success(self, "添加成功", f"角色 {role_data['role_name']} 添加成功！")
            else:
                show_error(self, "添加失败", "角色添加失败，请重试！")

    def edit_role(self, row):
        data = self.all_data[row]
        role_id = data[0]
        role = role_service.get_role_by_id(role_id)

        if role.name == "管理员":
            show_warning(self, "警告提示", "管理员角色不可修改或删除！")
            return

        permissions = [permission.work_name for permission in role.permissions]
        if data:
            role_obj = Role(
                id=role.id,
                role_name=role.name,
                description=role.desc,
                permissions=permissions
            )

            dialog = RoleEditDialog(role=role_obj, parent=self)
            if dialog.exec():
                role_data = dialog.get_role_data()
                if not role_data["role_name"]:
                    show_error(self, "输入错误", "角色名称不能为空！")
                    return

                exist_role = role_service.get_role_by_name(name=role_data["role_name"])
                if exist_role and exist_role.name == role_data["role_name"] and exist_role.id != int(role_id):
                    show_error(self, "修改失败", f"角色 {role_data['role_name']} 已存在！")
                    return

                update_data = {
                    "name": role_data["role_name"],
                    "desc": role_data["description"],
                    "permissions": role_data["permissions"]
                }
                print(f"update_data: {update_data}")

                if role_service.update_role(role_id, update_data):
                    self.load_all_data()
                    self.update_table_display()
                    show_success(self, "修改成功", f"角色 {role_data['role_name']} 修改成功！")
                else:
                    show_error(self, "修改失败", "角色修改失败，请重试！")

    def delete_role(self, row):
        data = self.all_data[row]
        role_id = data[0]
        role = role_service.get_role_by_id(role_id)

        if role.name == "管理员" or role.name == "质检员":
            show_warning(self, "警告提示", "管理员角色不可修改或删除！")
            return

        box = MessageBox(
            '确认删除',
            f'确定要删除角色 "{role.name}" 吗？此操作不可撤销！',
            self
        )
        box.yesButton.setText('删除')
        box.cancelButton.setText('取消')

        # 设置删除按钮样式
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

            has_users = role_service.get_role_users(role_id)
            print(f"has_users: {has_users.users}")
            if has_users.users:
                show_warning(self, "警告", f"当前角色【{role.name}】有关联用户, 暂时不可值接删除!")
                return

            if role_service.delete_role(role_id):
                self.load_all_data()
                self.update_table_display()

                show_success(self, "删除成功", f"角色 {role.name} 删除成功！")
            else:
                show_error(self, "删除失败", "角色删除失败，请重试！")