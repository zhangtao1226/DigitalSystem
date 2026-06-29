# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : workflow_config_page.py
# @Desc     : 系统管理-工作流配置
# @Time     : 2025/12/16 09:17
# @Software : PyCharm

from PySide6.QtGui import (
    QFont, QColor, QBrush,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QListWidgetItem
)
from PySide6.QtCore import (
    Qt, Signal,
)
from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    FluentIcon, InfoBar, InfoBarPosition,IconWidget,CardWidget, BodyLabel, ListWidget
)

from src.core.cache_manager import global_cache
from src.services.workflow_service import workflow_service
from src.utils.NotificationTool import show_success, show_error, show_warning, show_info

class WorkflowConfiguration(QWidget):
    configSaved = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        all_workflows = workflow_service.get_all_workflows()
        self.all_workflows = []
        for workflow in all_workflows:
            if workflow.work_name in ["系统管理", "统 计"]:
                continue
            self.all_workflows.append((workflow.id, workflow.work_name, workflow.status))
        self.selected_workflows = []

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)
        title_icon = IconWidget(FluentIcon.TILES)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)

        title_label = StrongBodyLabel("配置工作流步骤")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        info_label = BodyLabel("提示：领卷登记、 扫描和成品转换/输出为必选项")
        info_label.setStyleSheet("""
            color: #7f8c8d; 
            font-size: 14px; 
            padding: 5px 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        """)
        title_layout.addWidget(info_label)

        layout.addLayout(title_layout)

        main_card = CardWidget()
        main_card.setMinimumHeight(550)
        main_layout = QVBoxLayout(main_card)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(30, 30, 30, 30)

        workflow_area = QHBoxLayout()
        workflow_area.setSpacing(40)
        workflow_area.setContentsMargins(10, 20, 10, 20)

        available_group = QGroupBox("待选工作流")
        available_group.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        available_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #dfe6e9;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
                min-width: 300px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 12px 0 12px;
                color: #636e72;
            }
        """)

        available_layout = QVBoxLayout(available_group)
        available_layout.setSpacing(10)
        self.available_count_label = BodyLabel("0 个项目")
        self.available_count_label.setAlignment(Qt.AlignRight)
        self.available_count_label.setStyleSheet("""
            color: #636e72; 
            font-size: 12px; 
            font-weight: 500;
            padding: 2px 8px;
            background-color: #f1f2f6;
            border-radius: 10px;
        """)
        available_layout.addWidget(self.available_count_label)

        self.available_list = ListWidget()
        self.available_list.setSelectionMode(ListWidget.MultiSelection)
        self.available_list.setFixedSize(380, 580)
        self.available_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.available_list.itemSelectionChanged.connect(self.on_available_selection_changed)
        self.available_list.setStyleSheet("""
            ListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #ffffff;
                outline: none;
                font-family: "Microsoft YaHei";
            }
            ListWidget::item {
                height: 50px;
                border-bottom: 1px solid #f5f5f5;
                padding: 0px 15px;
                font-size: 14px;
                color: #333333;
                background-color: white;
            }
            ListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
                border-left: 4px solid #2196f3;
                border-radius: 0px;
            }
            ListWidget::item:hover:!selected {
                background-color: #f5f5f5;
            }
            ListWidget::item:last {
                border-bottom: none;
            }
            ListWidget::item:first {
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }
            ListWidget::item:last {
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
        """)
        available_layout.addWidget(self.available_list)

        workflow_area.addWidget(available_group)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(25)
        button_layout.setAlignment(Qt.AlignCenter)

        button_layout.addStretch()
        self.right_button = PushButton(FluentIcon.RIGHT_ARROW, "添加")
        self.right_button.setFixedSize(120, 45)
        self.right_button.setDisabled(True)
        self.right_button.setCursor(Qt.PointingHandCursor)
        self.right_button.clicked.connect(self.move_to_selected)
        button_layout.addWidget(self.right_button)
        self.left_button = PushButton(FluentIcon.LEFT_ARROW, "移除")
        self.left_button.setFixedSize(120, 45)
        self.left_button.setDisabled(True)
        self.left_button.setCursor(Qt.PointingHandCursor)
        self.left_button.clicked.connect(self.move_to_available)
        button_layout.addWidget(self.left_button)

        button_layout.addStretch()

        workflow_area.addLayout(button_layout)
        selected_group = QGroupBox("已选工作流")
        selected_group.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        selected_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4caf50;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
                min-width: 300px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 12px 0 12px;
                color: #4caf50;
                font-weight: bold;
            }
        """)

        selected_layout = QVBoxLayout(selected_group)
        selected_layout.setSpacing(10)

        self.selected_count_label = BodyLabel("0 个项目")
        self.selected_count_label.setAlignment(Qt.AlignRight)
        self.selected_count_label.setStyleSheet("""
            color: #4caf50; 
            font-size: 12px; 
            font-weight: 600;
            padding: 2px 8px;
            background-color: #e8f5e9;
            border-radius: 10px;
        """)
        selected_layout.addWidget(self.selected_count_label)

        self.selected_list = ListWidget()
        self.selected_list.setSelectionMode(ListWidget.MultiSelection)
        self.selected_list.setFixedSize(380, 580)
        self.selected_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.selected_list.itemSelectionChanged.connect(self.on_selected_selection_changed)
        self.selected_list.setStyleSheet("""
            ListWidget {
                border: 1px solid #c8e6c9;
                border-radius: 8px;
                background-color: #f9fbe7;
                outline: none;
                font-family: "Microsoft YaHei";
            }
            ListWidget::item {
                height: 50px;
                border-bottom: 1px solid #e8f5e9;
                padding: 0px 15px;
                font-size: 14px;
                font-weight: 500;
                background-color: white;
            }
            ListWidget::item:selected {
                background-color: #c8e6c9;
                color: #2e7d32;
                border-left: 4px solid #4caf50;
                border-radius: 0px;
            }
            ListWidget::item:hover:!selected {
                background-color: #f1f8e9;
            }
            ListWidget::item:last {
                border-bottom: none;
            }
            ListWidget::item:first {
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }
            ListWidget::item:last {
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
        """)
        selected_layout.addWidget(self.selected_list)

        workflow_area.addWidget(selected_group)

        main_layout.addLayout(workflow_area)
        order_hint = BodyLabel("提示：工作流将按照顺序执行")
        order_hint.setAlignment(Qt.AlignCenter)
        order_hint.setStyleSheet("""
            color: #ff6b6b;
            font-size: 13px;
            padding: 10px;
            background-color: #fff9f7;
            border-radius: 8px;
            border: 1px solid #ffccbc;
            margin-top: 10px;
        """)
        main_layout.addWidget(order_hint)
        button_container = QHBoxLayout()
        button_container.setSpacing(20)
        button_container.addStretch()
        self.preview_button = PushButton("预览")
        self.preview_button.setFixedSize(120, 45)
        self.preview_button.setCursor(Qt.PointingHandCursor)
        self.preview_button.clicked.connect(self.preview_configuration)
        self.preview_button.setStyleSheet("""
            PushButton {
                background-color: #795548;
                color: white;
                border-radius: 8px;
                font-weight: 500;
            }
            PushButton:hover {
                background-color: #5d4037;
            }
        """)
        button_container.addWidget(self.preview_button)

        self.save_button = PrimaryPushButton("保存配置")
        self.save_button.setFixedSize(120, 45)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self.save_configuration)
        button_container.addWidget(self.save_button)

        self.reset_button = PushButton("重置")
        self.reset_button.setFixedSize(120, 45)
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.clicked.connect(self.reset_configuration)
        self.reset_button.setStyleSheet("""
            PushButton {
                background-color: #f44336;
                color: white;
                border-radius: 8px;
                font-weight: 500;
            }
            PushButton:hover {
                background-color: #d32f2f;
            }
        """)
        button_container.addWidget(self.reset_button)

        main_layout.addLayout(button_container)
        layout.addWidget(main_card)

        self.load_available_workflows()
        self.update_button_states()
        self.update_count_labels()

    def load_available_workflows(self):
        self.available_list.clear()
        sorted_workflows = sorted(self.all_workflows, key=lambda x: x[0])

        for idx, name, is_required in sorted_workflows:
            display_text = f"{idx}. {name}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, (idx, name, is_required))

            if is_required:
                self.add_to_selected(display_text, idx, is_required)
            else:
                item.setFlags(item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.available_list.addItem(item)

        self.update_count_labels()

    def add_to_selected(self, display_text, idx, is_required=False):
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, (idx, display_text.split(". ", 1)[1], is_required))

        if ("扫 描" in item.text() or "领卷登记" in item.text() or "成品转换/输出" in item.text()):
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QBrush(QColor("#388e3c")))
            item.setToolTip("必选项（不可移除）")
            item.setBackground(QBrush(QColor("#e8f5e9")))
            item.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        else:
            item.setFont(QFont("Microsoft YaHei", 11, QFont.Normal))

        self.selected_list.addItem(item)
        self.sort_selected_list()

    def sort_selected_list(self):
        items = []
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            idx, name, is_required = item.data(Qt.UserRole)
            items.append((idx, name, is_required, item))

        items.sort(key=lambda x: x[0])

        self.selected_list.clear()
        for idx, name, is_required, original_item in items:
            display_text = f"{idx}. {name}"
            new_item = QListWidgetItem(display_text)
            new_item.setData(Qt.UserRole, (idx, name, is_required))

            if ("扫 描" in new_item.text() or "领卷登记" in new_item.text() or
                    "成品转换/输出" in new_item.text()):

                new_item.setFlags(new_item.flags() & ~Qt.ItemIsSelectable)
                new_item.setForeground(QBrush(QColor("#388e3c")))
                new_item.setToolTip("必选项（不可移除）")
                new_item.setBackground(QBrush(QColor("#e8f5e9")))
                new_item.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            else:
                new_item.setFont(QFont("Microsoft YaHei", 11, QFont.Normal))

            self.selected_list.addItem(new_item)

    def on_available_selection_changed(self):
        selected_items = self.available_list.selectedItems()
        self.right_button.setEnabled(len(selected_items) > 0)

    def on_selected_selection_changed(self):
        selected_items = self.selected_list.selectedItems()
        removable_items = [item for item in selected_items
                           if item.flags() & Qt.ItemIsSelectable]
        self.left_button.setEnabled(len(removable_items) > 0)

    def move_to_selected(self):
        selected_items = self.available_list.selectedItems()
        if not selected_items:
            return

        items_to_add = []
        for item in selected_items:
            if item.flags() & Qt.ItemIsEnabled:
                idx, name, is_required = item.data(Qt.UserRole)
                display_text = f"{idx}. {name}"
                items_to_add.append((idx, name, display_text))
                self.available_list.takeItem(self.available_list.row(item))

        for idx, name, display_text in items_to_add:
            self.add_to_selected(display_text, idx, False)

        self.update_button_states()
        self.update_count_labels()

    def move_to_available(self):
        selected_items = self.selected_list.selectedItems()
        if not selected_items:
            return

        items_to_move = []
        for item in selected_items:
            if item.flags() & Qt.ItemIsSelectable:
                idx, name, is_required = item.data(Qt.UserRole)
                display_text = f"{idx}. {name}"
                items_to_move.append((idx, name, display_text))
                for index, work in enumerate(self.all_workflows):
                    if idx == work[0]:
                        self.all_workflows.remove(work)
                        self.all_workflows.append((idx, name, False))

                self.selected_list.takeItem(self.selected_list.row(item))

        for idx, name, display_text in items_to_move:
            new_item = QListWidgetItem(display_text)
            new_item.setData(Qt.UserRole, (idx, name, False))
            new_item.setFlags(new_item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.available_list.addItem(new_item)

        self.sort_available_list()

        self.update_button_states()
        self.update_count_labels()

    def sort_available_list(self):
        items = []
        for i in range(self.available_list.count()):
            item = self.available_list.item(i)
            idx, name, is_required = item.data(Qt.UserRole)
            items.append((idx, name, item))

        items.sort(key=lambda x: x[0])

        self.available_list.clear()
        for idx, name, original_item in items:
            display_text = f"{idx}. {name}"
            new_item = QListWidgetItem(display_text)
            new_item.setData(Qt.UserRole, (idx, name, False))
            new_item.setFlags(new_item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.available_list.addItem(new_item)

    def update_button_states(self):
        self.ensure_required_workflows()

        self.available_list.clearSelection()
        self.selected_list.clearSelection()

        self.on_available_selection_changed()
        self.on_selected_selection_changed()

    def ensure_required_workflows(self):
        required_workflows = [(idx, name) for idx, name, required in self.all_workflows if required]

        selected_items = []
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            idx, name, is_required = item.data(Qt.UserRole)
            selected_items.append((idx, name))

        for idx, name in required_workflows:
            if (idx, name) not in selected_items:
                display_text = f"{idx}. {name}"
                self.add_to_selected(display_text, idx, True)

    def update_count_labels(self):
        available_count = self.available_list.count()
        selected_count = self.selected_list.count()

        self.available_count_label.setText(f"{available_count} 个项目")
        self.selected_count_label.setText(f"{selected_count} 个项目")

    def get_current_configuration(self):
        selected_workflows = []
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            idx, name, is_required = item.data(Qt.UserRole)
            selected_workflows.append({
                'index': idx,
                'name': name,
                'display': item.text(),
                'required': is_required
            })
        return selected_workflows

    def preview_configuration(self):
        selected_workflows = self.get_current_configuration()

        if len(selected_workflows) == 0:
            show_warning(self, "预览", "当前没有选择任何工作流！")
            return

        preview_text = "当前配置的工作流执行顺序：\n\n"
        for i, workflow in enumerate(selected_workflows, 1):
            status = " (必选)" if workflow['required'] else ""
            preview_text += f"{i}. {workflow['name']}{status}\n"

        preview_text += f"\n总计：{len(selected_workflows)} 个工作流"

        w = MessageBox(
            "配置预览",
            preview_text,
            self
        )

        w.yesButton.setText("确定")
        w.cancelButton.hide()

        w.widget.setMinimumWidth(400)
        w.exec()

    def save_configuration(self):
        selected_workflows = self.get_current_configuration()

        if len(selected_workflows) < 2:
            show_warning(self, "配置不完整", "至少需要选择两个工作流！")
            return

        required_names = ["扫 描", "领卷登记", "成品转换/输出"]
        missing_required = []

        for required in required_names:
            if not any(required in workflow['name'] for workflow in selected_workflows):
                missing_required.append(required)

        if missing_required:
            show_error(self, "配置错误", f"缺少必选项：{', '.join(missing_required)}")
            return

        self.selected_workflows = selected_workflows

        detail_text = "执行顺序：\n"
        for i, workflow in enumerate(selected_workflows, 1):
            detail_text += f"{i}. {workflow['name']}\n"

        w = MessageBox(
            "保存成功",
            f"工作流配置已保存！\n\n已选择 {len(selected_workflows)} 个工作流。",
            self
        )
        w.yesButton.setText("确定")
        w.cancelButton.hide()

        w.contentLabel.setText(f"工作流配置已保存！\n\n已选择 {len(selected_workflows)} 个工作流。\n\n执行顺序：")
        for i, workflow in enumerate(selected_workflows, 1):
            w.contentLabel.setText(w.contentLabel.text() + f"\n{i}. {workflow['name']}")

        w.widget.setMinimumWidth(400)

        if w.exec():
            names_only = [workflow['name'] for workflow in selected_workflows]
            self.configSaved.emit(names_only)
            workflow_service.save_workflow(names_only)

    def reset_configuration(self):
        w = MessageBox(
            "确认重置",
            "确定要重置所有配置吗？\n这将清除所有自定义选择。",
            self
        )

        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")

        if w.exec():
            self.available_list.clear()
            self.selected_list.clear()

            self.load_available_workflows()
            self.update_button_states()
            self.update_count_labels()
            show_success(self, "重置完成", "配置已重置为初始状态")