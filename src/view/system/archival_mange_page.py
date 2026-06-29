# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : archival_mange_page.py
# @Desc     : 系统管理-档案门类管理
# @Time     : 2025/12/16 09:49
# @Software : PyCharm

import pandas as pd
from datetime import datetime
from openpyxl import load_workbook
from PySide6.QtGui import (
    QFont, QColor, QBrush,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QTreeWidgetItem,
    QAbstractItemView, QHeaderView, QTableWidgetItem, QCheckBox,
    QSplitter, QDialog, QLabel, QFrame, QApplication,
    QTableWidget, QFileDialog
)
from PySide6.QtCore import Qt
from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    FluentIcon, InfoBar, InfoBarPosition, IconWidget, CardWidget, BodyLabel,
    TreeWidget, ComboBox, LineEdit, SpinBox,
)

from src.core.settings import settings
from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_error, show_success, show_warning

def _make_checkbox_widget():
    cb = QCheckBox()
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.addWidget(cb)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(0, 0, 0, 0)
    return w, cb


def _make_edit_btn_widget(callback):
    btn = PushButton("修改")
    btn.setFixedSize(70, 32)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet("""
        PushButton {
            background-color: #1976d2; color: white;
            border-radius: 6px; font-size: 12px;
        }
        PushButton:hover { background-color: #1565c0; }
    """)
    btn.clicked.connect(callback)
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.addWidget(btn)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(0, 0, 0, 0)
    return w


class DraggableTableWidget(QTableWidget):
    TEXT_COLS = [1, 2, 3, 4, 5, 6]

    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self._drag_source_row = -1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_source_row = self.rowAt(event.pos().y())
        super().mousePressEvent(event)

    def dropEvent(self, event):
        target_row = self.rowAt(event.pos().y())
        source_row = self._drag_source_row

        if source_row == -1 or target_row == -1 or source_row == target_row:
            event.ignore()
            return

        snapshot = self._snapshot_row(source_row)
        self.removeRow(source_row)
        insert_at = target_row if target_row < source_row else target_row
        self.insertRow(insert_at)
        self.setRowHeight(insert_at, 45)
        self._restore_row(insert_at, snapshot)
        self._reindex()
        event.accept()

    def _snapshot_row(self, row: int) -> dict:
        texts = {}
        for col in self.TEXT_COLS:
            item = self.item(row, col)
            texts[col] = item.text() if item else ""

        fn_item = self.item(row, 2)
        user_data = fn_item.data(Qt.UserRole) if fn_item else None
        req_bold = texts.get(6, "") == "是"
        return {"texts": texts, "user_data": user_data, "req_bold": req_bold}

    def _restore_row(self, row: int, snapshot: dict):
        cb_widget, _ = _make_checkbox_widget()
        self.setCellWidget(row, 0, cb_widget)

        for col in self.TEXT_COLS:
            text = snapshot["texts"].get(col, "")
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            if col == 2 and snapshot["user_data"] is not None:
                item.setData(Qt.UserRole, snapshot["user_data"])
            if col == 6 and snapshot["req_bold"]:
                item.setForeground(QBrush(QColor("#e53935")))
                item.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            self.setItem(row, col, item)

        self._set_edit_btn(row, snapshot["user_data"] or {})

    def _set_edit_btn(self, row: int, field_data: dict):
        def make_cb(r, d):
            return lambda: self._fire_edit(r, d)

        w = _make_edit_btn_widget(make_cb(row, field_data))
        self.setCellWidget(row, 7, w)

    def _fire_edit(self, row: int, data: dict):
        parent = self.parent()
        while parent:
            if hasattr(parent, "open_edit_dialog"):
                parent.open_edit_dialog(row, data)
                return
            parent = parent.parent()

    def _reindex(self):
        for row in range(self.rowCount()):
            idx_item = self.item(row, 1)
            if idx_item:
                idx_item.setText(str(row + 1))

            fn_item = self.item(row, 2)
            field_data = fn_item.data(Qt.UserRole) if fn_item else {}
            self._set_edit_btn(row, field_data or {})


class FieldEditDialog(QDialog):
    def __init__(self, parent=None, field_data: dict = None):
        super().__init__(parent)
        self.field_data = field_data or {}
        self.setWindowTitle("修改字段" if field_data else "新增字段")
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = StrongBodyLabel("修改字段" if self.field_data else "新增字段")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #dfe6e9;")
        layout.addWidget(sep)

        form_layout = QHBoxLayout()
        form_layout.setSpacing(0)
        inner = QWidget()
        from PySide6.QtWidgets import QFormLayout
        form = QFormLayout(inner)
        form.setSpacing(16)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_s = "font-family:'Microsoft YaHei';font-size:13px;color:#636e72;font-weight:500;"

        def lbl(t):
            l = QLabel(t); l.setStyleSheet(lbl_s); return l

        self.field_name_edit = LineEdit()
        self.field_name_edit.setPlaceholderText("请输入字段名")
        self.field_name_edit.setText(self.field_data.get("field_name", ""))
        self.field_name_edit.setFixedWidth(180)
        form.addRow(lbl("字段名："), self.field_name_edit)

        self.alias_edit = LineEdit()
        self.alias_edit.setPlaceholderText("请输入别名")
        self.alias_edit.setText(self.field_data.get("alias", ""))
        self.alias_edit.setFixedWidth(180)
        form.addRow(lbl("别名："), self.alias_edit)

        self.type_combo = ComboBox()
        for t in ["字符串", "数字"]:
            self.type_combo.addItem(t)
        idx = self.type_combo.findText(self.field_data.get("field_type", "字符串"))
        self.type_combo.setCurrentIndex(max(idx, 0))
        form.addRow(lbl("类型："), self.type_combo)

        self.length_spin = SpinBox()
        self.length_spin.setRange(1, 9999)
        self.length_spin.setValue(int(self.field_data.get("length", 50)))
        form.addRow(lbl("长度："), self.length_spin)

        self.required_combo = ComboBox()
        self.required_combo.addItems(["否", "是"])
        self.required_combo.setCurrentText(self.field_data.get("required", "否"))
        form.addRow(lbl("是否必填："), self.required_combo)

        layout.addWidget(inner)
        layout.addSpacing(10)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("取消"); cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = PrimaryPushButton("确定"); confirm_btn.setFixedSize(100, 40)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def get_field_data(self) -> dict:
        return {
            "field_name": self.field_name_edit.text().strip(),
            "alias":      self.alias_edit.text().strip(),
            "field_type": self.type_combo.currentText(),
            "length":     self.length_spin.value(),
            "required":   self.required_combo.currentText(),
        }


class ArchiveCategoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        setTheme(Theme.AUTO)
        self._current_category = None
        self._sample_fields = {}
        self.is_add = False
        self.is_save = False
        self.is_download = False

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(15)

        title_icon = IconWidget(FluentIcon.FOLDER)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)
        title_label = StrongBodyLabel("档案类别管理")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        main_layout.addLayout(title_layout)
        main_card = CardWidget()
        main_card.setMinimumHeight(950)
        card_layout = QVBoxLayout(main_card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(30, 30, 30, 30)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("""
            QSplitter::handle { background-color: #ecf0f1; border-radius: 3px; }
            QSplitter::handle:hover { background-color: #bdc3c7; }
        """)
        left_widget = QWidget()
        ll = QVBoxLayout(left_widget); ll.setSpacing(10); ll.setContentsMargins(0, 0, 10, 0)
        left_group = QGroupBox("档案类别")
        left_group.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        left_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #dfe6e9; border-radius: 10px;
                margin-top: 12px; padding-top: 12px; background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 12px; color: #636e72; }
        """)
        lgl = QVBoxLayout(left_group)
        lgl.setContentsMargins(10, 15, 10, 10)

        self.tree_widget = TreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setMinimumWidth(220)
        self.tree_widget.setStyleSheet("""
            TreeWidget {
                border: 1px solid #e0e0e0; 
                border-radius: 8px;
                background-color: #ffffff; 
                outline: none;
                font-family: "Microsoft YaHei"; 
                font-size: 13px;
            }
            TreeWidget::item { height: 40px; padding-left: 8px; color: #333333; }
            TreeWidget::item:selected { background-color: #e3f2fd; color: #1976d2; border-left: 3px solid #2196f3;}
            TreeWidget::item:hover:!selected { background-color: #f5f5f5; }
        """)
        self.tree_widget.currentItemChanged.connect(self._on_category_changed)
        lgl.addWidget(self.tree_widget)
        ll.addWidget(left_group)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        rl = QVBoxLayout(right_widget); rl.setSpacing(12); rl.setContentsMargins(10, 0, 0, 0)
        right_group = QGroupBox("字段信息")
        right_group.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        right_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4caf50; border-radius: 10px;
                margin-top: 12px; padding-top: 12px; background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 12px; color: #4caf50; font-weight: bold; }
        """)
        rgl = QVBoxLayout(right_group); rgl.setSpacing(12); rgl.setContentsMargins(15, 20, 15, 15)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.category_name_label = BodyLabel("请选择左侧档案类别")
        self.category_name_label.setStyleSheet("font-size:14px;color:#636e72;font-family:'Microsoft YaHei';")
        toolbar.addWidget(self.category_name_label)
        toolbar.addStretch()
        self.add_field_btn = PrimaryPushButton("新增字段")
        self.add_field_btn.setFixedSize(110, 40); self.add_field_btn.setCursor(Qt.PointingHandCursor)
        self.add_field_btn.clicked.connect(self._add_field)
        toolbar.addWidget(self.add_field_btn)

        self.del_field_btn = PrimaryPushButton("删除字段")
        self.del_field_btn.setFixedSize(110, 40)
        self.del_field_btn.setCursor(Qt.PointingHandCursor)
        self.del_field_btn.setStyleSheet("""
            PushButton { 
                background-color: #f44336; 
                color: white; 
                border-radius: 8px; 
                font-weight: 500; 
            }
            PushButton:hover { background-color: #d32f2f; }
        """)
        self.del_field_btn.clicked.connect(self._delete_fields)
        toolbar.addWidget(self.del_field_btn)

        self.save_field_btn = PushButton("保存字段")
        self.save_field_btn.setFixedSize(110, 40)
        self.save_field_btn.setCursor(Qt.PointingHandCursor)
        self.save_field_btn.setStyleSheet("""
            PushButton { 
                background-color: #f44336; 
                color: white; 
                border-radius: 8px; 
                font-weight: 500; 
            }
            PushButton:hover { background-color: #d32f2f; }
        """)
        self.save_field_btn.clicked.connect(self._save_fields)
        toolbar.addWidget(self.save_field_btn)

        self.create_field_table_btn = PushButton("下载模板")
        self.create_field_table_btn.setFixedSize(110, 40)
        self.create_field_table_btn.setCursor(Qt.PointingHandCursor)
        self.create_field_table_btn.setStyleSheet("""
            PushButton { 
                background-color: #f44336; 
                color: white; 
                border-radius: 8px; 
                font-weight: 500;
            }
            PushButton:hover { background-color: #d32f2f; }
        """)
        self.create_field_table_btn.clicked.connect(self._create_table)
        toolbar.addWidget(self.create_field_table_btn)

        rgl.addLayout(toolbar)

        self.field_table = DraggableTableWidget(0, 8, self)
        self.field_table.setHorizontalHeaderLabels(["", "序号", "字段名", "别名", "类型", "长度", "是否必填", "操作"])
        self.field_table.setSortingEnabled(False)
        self.field_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.field_table.setShowGrid(True)
        self.field_table.verticalHeader().setVisible(False)
        self.field_table.setAlternatingRowColors(True)
        hdr = self.field_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed);  self.field_table.setColumnWidth(0, 43)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed);  self.field_table.setColumnWidth(1, 65)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed);  self.field_table.setColumnWidth(4, 90)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed);  self.field_table.setColumnWidth(5, 65)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed);  self.field_table.setColumnWidth(6, 90)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed);  self.field_table.setColumnWidth(7, 90)
        self.field_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #c8e6c9; border-radius: 8px;
                background-color: #ffffff; outline: none;
                font-family: "Microsoft YaHei"; font-size: 13px; gridline-color: #e8f5e9;
            }
            QTableWidget::item { padding: 6px 10px; color: #333333; height: 45px; }
            QTableWidget::item:selected { background-color: #e3f2fd; color: #1565c0; }
            QTableWidget::item:alternate { background-color: #f9fbe7; }
            QHeaderView::section {
                background-color: #f0f7f0; color: #2e7d32; font-weight: bold;
                font-size: 13px; padding: 10px 8px; border: none;
                border-bottom: 2px solid #a5d6a7; font-family: "Microsoft YaHei";
            }
        """)
        rgl.addWidget(self.field_table)

        drag_hint = BodyLabel("提示：拖拽行可调整字段顺序")
        drag_hint.setAlignment(Qt.AlignCenter)
        drag_hint.setStyleSheet("""
            color: #ff6b6b; font-size: 12px; padding: 8px;
            background-color: #fff9f7; border-radius: 8px; border: 1px solid #ffccbc;
        """)
        rgl.addWidget(drag_hint)
        rl.addWidget(right_group)
        splitter.addWidget(right_widget)
        splitter.setSizes([260, 800])
        card_layout.addWidget(splitter)
        main_layout.addWidget(main_card)

        self._load_tree()

    def _load_tree(self):
        try:
            excel_file = pd.ExcelFile(settings.archives_template_path)
            sheet_names = excel_file.sheet_names
            print(sheet_names)
        except Exception as e:
            show_error(self, "档案类型表读取失败", f"原因: {str(e)}")
            return

        categories = {}
        for item in sheet_names:
            file_type, level = item.split("-", 1)
            if file_type not in categories:
                categories[file_type] = []
            if level not in categories[file_type]:
                categories[file_type].append(level)

        self._sample_fields = {}
        for sheet_name in sheet_names:
            df = pd.read_excel(settings.archives_template_path, sheet_name=sheet_name)
            self._sample_fields[sheet_name] = []
            for index, series in df.iterrows():
                self._sample_fields[sheet_name].append(
                    {
                        "field_name": series.iloc[1],
                        "alias": series.iloc[2],
                        "field_type": series.iloc[3],
                        "length": series.iloc[4],
                        "required": "是" if series.iloc[5] == "Y" else "否"
                    }
                )

        self.tree_widget.clear()
        for parent_name, children in categories.items():
            p = QTreeWidgetItem([parent_name])
            p.setFont(0, QFont("Microsoft YaHei", 12, QFont.Bold))
            for child_name in children:
                c = QTreeWidgetItem([child_name])
                c.setFont(0, QFont("Microsoft YaHei", 12))
                p.addChild(c)


            self.tree_widget.addTopLevelItem(p)
            p.setExpanded(True)

    def _on_category_changed(self, current: QTreeWidgetItem, _previous):
        if not current:
            return
        self._current_category = ""
        if not current.parent() is None:
            self._current_father_category = current.parent().text(0)
            print(f"current: {current}; {current.parent().text(0)}")
            self.is_add = True
            self.is_save = True
            self.is_download = True
            self._current_category = f"{current.parent().text(0)}-{current.text(0)}"
        else:
            self._current_category = current.text(0)
            self.is_add = False
            self.is_save = False
            self.is_download = False

        self.category_name_label.setText(f"当前类别：{self._current_category}")

        self.category_name_label.setStyleSheet(
            "font-size:14px;color:#2e7d32;font-family:'Microsoft YaHei';font-weight:600;"
        )

        self._load_fields(self._sample_fields.get(self._current_category, []))

    def _load_fields(self, fields: list):
        self.field_table.setRowCount(0)
        for f in fields:
            self._append_row(f)

    def _append_row(self, field: dict):
        row = self.field_table.rowCount()
        self.field_table.insertRow(row)
        self.field_table.setRowHeight(row, 45)

        cb_widget, _ = _make_checkbox_widget()
        self.field_table.setCellWidget(row, 0, cb_widget)

        idx_item = QTableWidgetItem(str(row + 1))
        idx_item.setTextAlignment(Qt.AlignCenter)
        self.field_table.setItem(row, 1, idx_item)
        fn_item = QTableWidgetItem(field.get("field_name", ""))
        fn_item.setTextAlignment(Qt.AlignCenter)
        fn_item.setData(Qt.UserRole, dict(field))
        self.field_table.setItem(row, 2, fn_item)
        al_item = QTableWidgetItem(field.get("alias", ""))
        al_item.setTextAlignment(Qt.AlignCenter)
        self.field_table.setItem(row, 3, al_item)
        tp_item = QTableWidgetItem(field.get("field_type", ""))
        tp_item.setTextAlignment(Qt.AlignCenter)
        self.field_table.setItem(row, 4, tp_item)
        ln_item = QTableWidgetItem(str(field.get("length", "")))
        ln_item.setTextAlignment(Qt.AlignCenter)
        self.field_table.setItem(row, 5, ln_item)
        req_text = field.get("required", "否")
        req_item = QTableWidgetItem(req_text)
        req_item.setTextAlignment(Qt.AlignCenter)
        if req_text == "是":
            req_item.setForeground(QBrush(QColor("#e53935")))
            req_item.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.field_table.setItem(row, 6, req_item)

        self.field_table._set_edit_btn(row, dict(field))
    def open_edit_dialog(self, row: int, _field_data: dict):
        def get_text(col):
            it = self.field_table.item(row, col)
            return it.text() if it else ""

        current = {
            "field_name": get_text(2),
            "alias":      get_text(3),
            "field_type": get_text(4),
            "length":     int(get_text(5)) if get_text(5).isdigit() else 50,
            "required":   get_text(6),
        }
        dlg = FieldEditDialog(self, current)
        if dlg.exec():
            new_data = dlg.get_field_data()
            if not new_data["field_name"]:
                show_warning(self, "警告", "字段名不能为空！")
                return
            self._update_row(row, new_data)

            show_success(self, "修改成功", f"字段 '{new_data['field_name']}' 已更新")

    def _update_row(self, row: int, field: dict):
        def set_text(col, text):
            it = self.field_table.item(row, col)
            if it:
                it.setText(text)
            else:
                ni = QTableWidgetItem(text); ni.setTextAlignment(Qt.AlignCenter)
                self.field_table.setItem(row, col, ni)

        fn_item = self.field_table.item(row, 2)
        if fn_item:
            fn_item.setText(field["field_name"])
            fn_item.setData(Qt.UserRole, dict(field))

        set_text(3, field["alias"])
        set_text(4, field["field_type"])
        set_text(5, str(field["length"]))
        set_text(6, field["required"])

        req_item = self.field_table.item(row, 6)
        if req_item:
            if field["required"] == "是":
                req_item.setForeground(QBrush(QColor("#e53935")))
                req_item.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            else:
                req_item.setForeground(QBrush(QColor("#333333")))
                req_item.setFont(QFont("Microsoft YaHei", 11, QFont.Normal))

    def _add_field(self):
        if not self._current_category  or not self.is_add:
            show_warning(self, "警告", "请先在左侧选择一个档案类别!")
            return
        dlg = FieldEditDialog(self)
        if dlg.exec():
            new_data = dlg.get_field_data()
            if not new_data["field_name"]:
                show_error(self, "提示", "字段名不能为空")
                return
            self._append_row(new_data)
            show_success(self, "新增成功", f"字段 '{new_data['field_name']}' 已添加")

            self._load_tree()

    def _delete_fields(self):
        checked_rows = []
        for row in range(self.field_table.rowCount()):
            cw = self.field_table.cellWidget(row, 0)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb and cb.isChecked():
                    checked_rows.append(row)

        if not checked_rows:
            show_warning(self, "警告", "请先勾选要删除的字段！")
            return

        w = MessageBox("确认删除", f"确定要删除选中的 {len(checked_rows)} 个字段吗？\n此操作不可撤销。", self)
        w.yesButton.setText("确定"); w.cancelButton.setText("取消")

        if w.exec():
            for row in sorted(checked_rows, reverse=True):
                self.field_table.removeRow(row)
            self.field_table._reindex()
            show_success(self, "删除成功", f"已删除 {len(checked_rows)} 个字段")

            self._load_tree()

    def _save_fields(self):
        if self.is_save:
            w = MessageBox("确认保存", f"确定要保存当前字段信息表吗？\n此操作不可撤销, 保存后会更新档案模版表", self)
            w.yesButton.setText("确定")
            w.cancelButton.setText("取消")
            if w.exec():
                current_fields_info = []
                for row in range(self.field_table.rowCount()):
                    row_data_list = []
                    for col in range(1, 7):
                        row_data_list.append(self.field_table.item(row, col).text())

                    current_fields_info.append(row_data_list)

                df = pd.read_excel(settings.archives_template_path, sheet_name=f"{self._current_category}")
                current_fields_info.insert(0, df.columns.values.tolist())

                columns = current_fields_info[0]
                rows = current_fields_info[1:]
                new_df = pd.DataFrame(rows, columns=columns)

                try:
                    book = load_workbook(settings.archives_template_path)

                    with pd.ExcelWriter(
                            settings.archives_template_path,
                            engine="openpyxl",
                            mode="a",
                            if_sheet_exists="replace"
                    ) as writer:
                        new_df.to_excel(writer, sheet_name=self._current_category, index=False)

                    logger.info(f"{self._current_category}, 保存字段信息表")
                    self._load_tree()

                except FileNotFoundError:
                    print(f"错误：未找到文件 {settings.archives_template_path}，请检查文件路径是否正确！")
                except Exception as e:
                    print(f"写入失败：{str(e)}")
        else:
            show_warning(self, "警告", "未选择档案类别")
            return

    def _create_table(self):
        if self.is_download:
            headers = ['序号']
            for row in range(self.field_table.rowCount()):
                headers.append(self.field_table.item(row, 3).text())

            df = pd.DataFrame(columns=headers)
            try:
                download_path = QFileDialog.getExistingDirectory(self, "选择保存路径")
                file_name = f"{self._current_category}目录表-{datetime.now().strftime('%Y%m%d')}.xlsx"
                print(f"保存路径: {download_path}/{file_name}")
                df.to_excel(f"{download_path}/{file_name}", index=False, engine="openpyxl")
                show_success(self, "创建成功", f"导出路径为: {download_path}/{file_name}")

            except FileNotFoundError as fe:
                logger.error(f"档案目录创建失败; {str(fe)}")
                show_error(self, "错误", f"档案目录创建失败; {str(fe)}")
                return
            except Exception as e:
                logger.error(f"档案目录创建失败; {str(e)}")
                show_error(self, "错误", f"档案目录创建失败; {str(e)}")
                return
        else:
            show_warning(self, "警告", "未选择档案类别")
            return