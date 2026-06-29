# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : mark_issue_dialog.py
# @Desc     : 质检标记弹框（公共组件）—— 用于标记扫描任务中某扫描件的错误信息
# @Time     : 2025/12/16
# @Software : PyCharm

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QDialog, QLabel,
    QFrame, QButtonGroup, QRadioButton, QPlainTextEdit
)
from PySide6.QtCore import Qt

from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, PushButton, PrimaryPushButton,
    ComboBox, LineEdit, CheckBox, FluentIcon, IconWidget
)


from src.services.task_mark_service import MARK_STAGE, MARK_TYPES

MARK_LEVELS = [("严重", "#f44336"), ("一般", "#ff9800"), ("轻微", "#4caf50")]


class MarkIssueDialog(QDialog):

    def __init__(self, parent=None, mark_stage: str = "", target_name: str = "", mark_data: dict = None):
        super().__init__(parent)
        self.mark_stage = mark_stage
        self.target_name = target_name
        self.mark_data = mark_data or {}
        self._level_group = QButtonGroup(self)

        self.mark_types = MARK_TYPES[MARK_STAGE[mark_stage]]

        self.setWindowTitle("修改标记" if self.mark_data else "标记错误信息")
        self.setMinimumWidth(720)
        self.setMinimumHeight(680)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._init_ui()
        if self.mark_data:
            self._load_data(self.mark_data)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 24, 30, 24)

        # 标题
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        title_icon = IconWidget(FluentIcon.TAG)
        title_icon.setFixedSize(22, 22)
        title_layout.addWidget(title_icon)
        title = StrongBodyLabel("修改标记" if self.mark_data else "标记错误信息")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #dfe6e9;")
        layout.addWidget(sep)

        lbl_s = "font-family:'Microsoft YaHei';font-size:13px;color:#636e72;font-weight:500;"

        # ── 标记信息 ──
        info_group = self._build_group_box("标记信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(12)
        info_layout.setContentsMargins(15, 18, 15, 15)

        # 标记对象
        target_row = QHBoxLayout()
        target_row.setSpacing(10)
        target_lbl = QLabel("标记对象：")
        target_lbl.setStyleSheet(lbl_s)
        target_lbl.setFixedWidth(80)
        target_row.addWidget(target_lbl)
        target_text = self.target_name
        self.target_label = BodyLabel(target_text or "未指定")
        self.target_label.setStyleSheet("font-size:13px;color:#1565c0;font-weight:600;font-family:'Microsoft YaHei';")
        target_row.addWidget(self.target_label)
        target_row.addStretch()
        info_layout.addLayout(target_row)

        # 标记类型
        type_row = QHBoxLayout()
        type_row.setSpacing(10)
        type_lbl = QLabel("标记类型：")
        type_lbl.setStyleSheet(lbl_s)
        type_lbl.setFixedWidth(80)
        type_row.addWidget(type_lbl)
        self.type_combo = ComboBox()
        self.type_combo.addItems(self.mark_types)
        self.type_combo.setFixedWidth(220)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        info_layout.addLayout(type_row)

        # 严重程度
        level_row = QHBoxLayout()
        level_row.setSpacing(10)
        level_lbl = QLabel("严重程度：")
        level_lbl.setStyleSheet(lbl_s)
        level_lbl.setFixedWidth(80)
        level_row.addWidget(level_lbl)
        for i, (text, color) in enumerate(MARK_LEVELS):
            rb = QRadioButton(text)
            rb.setStyleSheet(f"""
                QRadioButton {{ font-family:'Microsoft YaHei'; font-size:13px; color:{color}; }}
                QRadioButton::indicator {{ width:14px; height:14px; }}
            """)
            if i == 1:
                rb.setChecked(True)
            self._level_group.addButton(rb, i)
            level_row.addWidget(rb)
        level_row.addStretch()
        info_layout.addLayout(level_row)

        layout.addWidget(info_group)

        # ── 描述标记内容 ──
        desc_group = self._build_group_box("描述标记内容")
        desc_layout = QVBoxLayout(desc_group)
        desc_layout.setContentsMargins(15, 18, 15, 15)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("请详细描述发现的问题, 例如: 第7页图像存在严重歪斜, 文字内容无法辨认······")
        self.desc_edit.setFixedHeight(160)
        self.desc_edit.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #dfe6e9; border-radius: 6px;
                padding: 8px; font-size: 13px; color: #333;
                background: #fafbfc; font-family: 'Microsoft YaHei';
            }
            QPlainTextEdit:focus { border: 1px solid #1976d2; background: white; }
        """)
        desc_layout.addWidget(self.desc_edit)

        layout.addWidget(desc_group)

        # ── 操作内容 ──
        op_group = self._build_group_box("操作内容")
        op_layout = QVBoxLayout(op_group)
        op_layout.setSpacing(10)
        op_layout.setContentsMargins(15, 18, 15, 15)

        self.opt_edit = QPlainTextEdit()
        self.opt_edit.setPlaceholderText("请详细描述需要操作内容, 例如: 需要重新扫描······")
        self.opt_edit.setFixedHeight(100)
        self.opt_edit.setStyleSheet("""
                    QPlainTextEdit {
                        border: 1px solid #dfe6e9; border-radius: 6px;
                        padding: 8px; font-size: 13px; color: #333;
                        background: #fafbfc; font-family: 'Microsoft YaHei';
                    }
                    QPlainTextEdit:focus { border: 1px solid #1976d2; background: white; }
                """)

        op_layout.addWidget(self.opt_edit)
        layout.addWidget(op_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.setFixedSize(100, 38)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = PrimaryPushButton("提交")
        confirm_btn.setFixedSize(110, 38)
        confirm_btn.setStyleSheet("""
            PrimaryPushButton {
                background-color: #f44336; color: white;
                border-radius: 8px; font-size: 13px; font-weight: 500;
            }
            PrimaryPushButton:hover { background-color: #d32f2f; }
        """)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)


    def _build_group_box(self, title: str) -> QWidget:
        from PySide6.QtWidgets import QGroupBox
        box = QGroupBox(title)
        box.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        box.setStyleSheet("""
            QGroupBox {
                border: 2px solid #dfe6e9; border-radius: 10px;
                margin-top: 10px; padding-top: 8px; background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 10px; color: #636e72; }
        """)
        return box

    def _load_data(self, data: dict):
        print(f"data: {data}")

        if "mark_type" in data and data["mark_type"] in self.mark_types:
            self.type_combo.setCurrentText(data["mark_type"])
        if "level" in data:
            for i, (text, _color) in enumerate(MARK_LEVELS):
                if text == data["level"]:
                    self._level_group.button(i).setChecked(True)
                    break
        if "description" in data:
            self.desc_edit.setPlainText(data["description"])
        if "opt_edit" in data:
            self.opt_edit.setChecked(bool(data["opt_edit"]))

    def get_data(self) -> dict:
        level_id = self._level_group.checkedId()
        level_text = MARK_LEVELS[level_id][0] if level_id >= 0 else MARK_LEVELS[1][0]
        return {
            "target": self.target_name,
            "mark_type": self.type_combo.currentText(),
            "level": level_text,
            "description": self.desc_edit.toPlainText().strip(),
            "opt_edit": self.opt_edit.toPlainText().strip(),
        }