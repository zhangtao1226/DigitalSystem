# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : import_directory_page.py
# @Desc     : 目录导入与管理页面
# @Time     : 2025/12/16
# @Software : PyCharm

import json
from datetime import datetime

import pandas as pd

from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGroupBox, QTreeWidgetItem,
    QAbstractItemView, QHeaderView, QTableWidgetItem, QCheckBox,
    QSplitter, QDialog, QLabel, QFrame, QTableWidget, QFileDialog,
    QLineEdit, QApplication
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from paddle.base.libpaddle.eager.ops.legacy import row_conv, pir_run_program

from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    FluentIcon, IconWidget, CardWidget, BodyLabel,
    TreeWidget, ComboBox, LineEdit, SpinBox,
)
from unicodedata import category

from src.core.settings import settings
from src.core.cache_manager import global_cache

from src.utils.LoggerDetector import logger
from src.utils.NotificationTool import show_error, show_success, show_warning

from src.services.director_service import director_service


# ─────────────────────────── 档案类别字段定义 ────────────────────────────
# 每个 sheet 的别名列表（不含序号），用于表头显示
CATEGORY_HEADERS = {
    "文书档案-案卷级": ["档号", "保管期限", "题名", "责任者", "起始时间", "终止时间", "页数"],
    "文书档案-文件级": ["档号", "题名", "保管期限", "文号", "责任者", "日期", "页数", "密级", "主题词", "控制符", "备注"],
    "照片档案-案卷级": ["档号", "保管期限", "题名", "起始时间", "终止时间", "页数", "密级", "摄影者", "备注"],
    "照片档案-文件级": ["档号", "保管期限", "题名", "摄影者", "参见号", "密级", "备注", "页数", "摄影时间"],
    "会计档案-案卷级": ["档号", "保管期限", "类别", "题名", "起止时间", "卷内张数", "备注", "立卷部门", "归档时间", "立卷人"],
    "会计档案-文件级": ["档号", "责任者", "文号", "题名", "日期", "页数", "保管期限", "备注", "密级"],
    "科技档案-案卷级": ["档号", "保管期限", "题名", "起止时间", "页数", "密级", "备注", "立卷单位", "立卷人", "立卷日期", "检查人", "检查日期"],
    "科技档案-文件级": ["档号", "保管期限", "题名", "责任者", "日期", "页数", "密级", "主题词", "备注"],
}

# 字段名（英文列名），与别名一一对应，供导入/导出 Excel 时使用
CATEGORY_FIELDS = {
    "文书档案-案卷级": ["dh", "bgqx", "tm", "zrz", "qssj", "zzsj", "ys"],
    "文书档案-文件级": ["dh", "tm", "bgqx", "wh", "zrz", "cwrq", "ys", "mj", "ztc", "kzf", "bz"],
    "照片档案-案卷级": ["dh", "bgqx", "tm", "qssj", "zzsj", "ys", "mj", "syz", "bz"],
    "照片档案-文件级": ["dh", "bgqx", "tm", "syz", "cjh", "mj", "bz", "ys", "sysj"],
    "会计档案-案卷级": ["dh", "bgqx", "lb", "tm", "qzsj", "jnzs", "bz", "ljbm", "gdsj", "ljr"],
    "会计档案-文件级": ["dh", "zrz", "wh", "tm", "cwrq", "ys", "bgqx", "bz", "mj"],
    "科技档案-案卷级": ["dh", "bgqx", "tm", "qzsj", "ys", "mj", "bz", "ljdw", "ljr", "ljrq", "jcr", "jcrq"],
    "科技档案-文件级": ["dh", "bgqx", "tm", "zrz", "cwrq", "ys", "mj", "ztc", "bz"],
}

PAGE_SIZE = 20  # 每页行数


# ─────────────────────────── 辅助函数 ────────────────────────────

def _make_checkbox_widget():
    cb = QCheckBox()
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.addWidget(cb)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(0, 0, 0, 0)
    return w, cb


def _make_action_btn_widget(edit_cb, del_cb):
    """每行操作列：修改 + 删除两个按钮"""
    edit_btn = PushButton("修改")
    edit_btn.setFixedSize(60, 28)
    edit_btn.setCursor(Qt.PointingHandCursor)
    edit_btn.setStyleSheet("""
        PushButton {
            background-color: #1976d2; color: white;
            border-radius: 5px; font-size: 12px;
        }
        PushButton:hover { background-color: #1565c0; }
    """)
    edit_btn.clicked.connect(edit_cb)

    del_btn = PushButton("删除")
    del_btn.setFixedSize(60, 28)
    del_btn.setCursor(Qt.PointingHandCursor)
    del_btn.setStyleSheet("""
        PushButton {
            background-color: #f44336; color: white;
            border-radius: 5px; font-size: 12px;
        }
        PushButton:hover { background-color: #d32f2f; }
    """)
    del_btn.clicked.connect(del_cb)

    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(4, 2, 4, 2)
    lay.setSpacing(6)
    lay.addWidget(edit_btn)
    lay.addWidget(del_btn)
    lay.setAlignment(Qt.AlignCenter)
    return w


# ─────────────────────────── 行编辑对话框 ────────────────────────────

class RowEditDialog(QDialog):
    """根据当前档案类别动态生成表单字段的编辑对话框"""

    def __init__(self, parent=None, headers: list = None, row_data: dict = None):
        super().__init__(parent)
        self.headers = headers or []
        self.row_data = row_data or {}
        self.setWindowTitle("修改记录" if row_data else "新增记录")
        self.setMinimumWidth(500)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._editors = {}
        self._init_ui()

    def _init_ui(self):
        from PySide6.QtWidgets import QScrollArea, QFormLayout
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 24, 30, 24)

        title = StrongBodyLabel("修改记录" if self.row_data else "新增记录")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #dfe6e9;")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_s = "font-family:'Microsoft YaHei';font-size:13px;color:#636e72;font-weight:500;"

        for header in self.headers:
            lbl = QLabel(f"{header}：")
            lbl.setStyleSheet(lbl_s)
            edit = LineEdit()
            edit.setPlaceholderText(f"请输入{header}")
            edit.setText(str(self.row_data.get(header, "")))
            edit.setFixedWidth(240)
            form.addRow(lbl, edit)
            self._editors[header] = edit

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.setFixedSize(100, 38)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = PrimaryPushButton("确定")
        confirm_btn.setFixedSize(100, 38)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        return {h: self._editors[h].text().strip() for h in self.headers}


# ─────────────────────────── 主页面 ────────────────────────────

class ImportDirectoryPage(QWidget):
    """目录导入与管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        setTheme(Theme.AUTO)
        self._current_category: str = ""
        self._current_headers: list = []   # 当前类别的别名列表
        self._all_data: list = []          # 全量数据（list of dict）
        self._filtered_data: list = []     # 筛选后数据
        self._current_page: int = 1
        self._total_pages: int = 1
        self._filter_values: dict = {}     # 列头筛选值 {header: text}
        self._import_df = None
        self._add_exit_list = []

        self._filters:dict = {}

        self._import_data_question = []

        self.current_user = global_cache.get("current_user")
        self._init_ui()

    # ──────────────────── UI 构建 ────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # 标题
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        title_icon = IconWidget(FluentIcon.FOLDER_ADD)
        title_icon.setFixedSize(24, 24)
        title_layout.addWidget(title_icon)
        title_label = StrongBodyLabel("目录导入与管理")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setStyleSheet("color: #333333;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 主卡片
        main_card = CardWidget()
        main_card.setMinimumHeight(950)
        card_layout = QVBoxLayout(main_card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(30, 30, 30, 30)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("""
            QSplitter::handle { background-color: #ecf0f1; border-radius: 3px; }
            QSplitter::handle:hover { background-color: #bdc3c7; }
        """)

        # ── 左侧：档案类别树 ──
        left_widget = QWidget()
        ll = QVBoxLayout(left_widget)
        ll.setSpacing(10)
        ll.setContentsMargins(0, 0, 10, 0)

        left_group = QGroupBox("档案类别")
        left_group.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
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
        self.tree_widget.setMinimumWidth(200)
        self.tree_widget.setStyleSheet("""
            TreeWidget {
                border: 1px solid #e0e0e0; border-radius: 8px;
                background-color: #ffffff; outline: none;
                font-family: "Microsoft YaHei"; font-size: 13px;
            }
            TreeWidget::item { height: 40px; padding-left: 8px; color: #333333; }
            TreeWidget::item:selected { background-color: #e3f2fd; color: #1976d2; border-left: 3px solid #2196f3; }
            TreeWidget::item:hover:!selected { background-color: #f5f5f5; }
        """)
        self.tree_widget.currentItemChanged.connect(self._on_category_changed)
        lgl.addWidget(self.tree_widget)
        ll.addWidget(left_group)
        splitter.addWidget(left_widget)

        # ── 右侧：目录表 ──
        right_widget = QWidget()
        rl = QVBoxLayout(right_widget)
        rl.setSpacing(12)
        rl.setContentsMargins(10, 0, 0, 0)

        right_group = QGroupBox("目录信息")
        right_group.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        right_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #1976d2; border-radius: 10px;
                margin-top: 12px; padding-top: 12px; background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 12px; color: #1976d2; font-weight: bold; }
        """)
        rgl = QVBoxLayout(right_group)
        rgl.setSpacing(12)
        rgl.setContentsMargins(15, 20, 15, 15)

        # 当前类别标签
        self.category_label = BodyLabel("请选择左侧档案类别")
        self.category_label.setStyleSheet("font-size:14px;color:#636e72;font-family:'Microsoft YaHei';")
        rgl.addWidget(self.category_label)

        # 工具栏
        toolbar = self._build_toolbar()
        rgl.addLayout(toolbar)

        # 筛选栏（动态生成，放在表格上方）
        self.filter_widget = QWidget()
        self.filter_layout = QHBoxLayout(self.filter_widget)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_layout.setSpacing(6)
        rgl.addWidget(self.filter_widget)

        # 表格
        self.table = QTableWidget(0, 0, self)
        self._apply_table_style()
        rgl.addWidget(self.table)

        # 分页控件
        page_bar = self._build_page_bar()
        rgl.addLayout(page_bar)

        rl.addWidget(right_group)
        splitter.addWidget(right_widget)
        splitter.setSizes([230, 900])
        card_layout.addWidget(splitter)
        main_layout.addWidget(main_card)

        self._load_tree()

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addStretch()

        btn_defs = [
            ("导入目录", "#388e3c", "#2e7d32", self._import_data),
            ("导出目录", "#1976d2", "#1565c0", self._export_data),
            ("添加记录", "#7b1fa2", "#6a1b9a", self._add_record),
            ("批量删除", "#f44336", "#d32f2f", self._batch_delete),
            ("下载导入问题表", "#3be3d7", "#13cec0", self._download_question),
        ]
        self._toolbar_btns = []
        for text, bg, hover, cb in btn_defs:
            btn = PrimaryPushButton(text)
            btn.setFixedSize(100, 38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                PrimaryPushButton {{
                    background-color: {bg}; color: white;
                    border-radius: 8px; font-size: 13px; font-weight: 500;
                }}
                PrimaryPushButton:hover {{ background-color: {hover}; }}
            """)
            btn.clicked.connect(cb)
            toolbar.addWidget(btn)
            self._toolbar_btns.append(btn)

        return toolbar

    def _build_page_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addStretch()

        self.prev_btn = PushButton("◀ 上一页")
        self.prev_btn.setFixedSize(90, 32)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.clicked.connect(self._prev_page)
        bar.addWidget(self.prev_btn)

        self.page_label = BodyLabel("第 1 / 1 页")
        self.page_label.setStyleSheet("font-size:13px;color:#555;font-family:'Microsoft YaHei';")
        bar.addWidget(self.page_label)

        self.next_btn = PushButton("下一页 ▶")
        self.next_btn.setFixedSize(90, 32)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.clicked.connect(self._next_page)
        bar.addWidget(self.next_btn)

        self.total_label = BodyLabel("共 0 条")
        self.total_label.setStyleSheet("font-size:12px;color:#999;font-family:'Microsoft YaHei';margin-left:10px;")
        bar.addWidget(self.total_label)
        bar.addStretch()

        return bar

    def _apply_table_style(self):
        self.table.setSortingEnabled(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bbdefb; border-radius: 8px;
                background-color: #ffffff; outline: none;
                font-family: "Microsoft YaHei"; font-size: 13px;
                gridline-color: #e3f2fd;
            }
            QTableWidget::item { padding: 5px 8px; color: #333333; height: 40px; }
            QTableWidget::item:selected { background-color: #e3f2fd; color: #1565c0; }
            QTableWidget::item:alternate { background-color: #f8fbff; }
            QHeaderView::section {
                background-color: #e3f2fd; color: #1565c0; font-weight: bold;
                font-size: 13px; padding: 8px 6px; border: none;
                border-bottom: 2px solid #90caf9; font-family: "Microsoft YaHei";
            }
        """)

    # ──────────────────── 加载树形类别 ────────────────────

    def _load_tree(self):
        categories = {}
        for key in CATEGORY_HEADERS:
            parts = key.split("-", 1)
            if len(parts) == 2:
                parent, child = parts
                categories.setdefault(parent, []).append(child)

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

    # ──────────────────── 类别切换 ────────────────────

    def _on_category_changed(self, current: QTreeWidgetItem, _previous):
        if not current or current.parent() is None:
            return
        category = f"{current.parent().text(0)}-{current.text(0)}"
        if category == self._current_category:
            return
        self._current_category = category
        self._current_headers = CATEGORY_HEADERS.get(category, [])
        self._filter_values = {}
        self._all_data = []
        self._filtered_data = []
        self._current_page = 1

        self.category_label.setText(f"当前类别：{category}")
        self.category_label.setStyleSheet(
            "font-size:14px;color:#1565c0;font-family:'Microsoft YaHei';font-weight:600;"
        )
        self._rebuild_columns()
        self._rebuild_filter_bar()
        self._refresh_table()

    # ──────────────────── 列头与筛选栏重建 ────────────────────

    def _rebuild_columns(self):
        """根据当前类别重新设置表格列：复选框 + 序号 + 数据列 + 操作"""
        headers = self._current_headers
        col_count = 2 + len(headers) + 1  # checkbox, 序号, 数据列..., 操作
        self.table.setColumnCount(col_count)

        labels = [""] + ["序号"] + headers + ["操作"]
        self.table.setHorizontalHeaderLabels(labels)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 55)

        for c in range(2, 2 + len(headers)):
            hdr.setSectionResizeMode(c, QHeaderView.Stretch)
        op_col = 2 + len(headers)
        hdr.setSectionResizeMode(op_col, QHeaderView.Fixed)
        self.table.setColumnWidth(op_col, 155)

        # 设置页数宽度
        if "页数" in headers:
            page_col = 2 + headers.index("页数")
            hdr.setSectionResizeMode(page_col, QHeaderView.Fixed)
            self.table.setColumnWidth(page_col, 55)

        if "档号" in headers:
            ar_col = 2 + headers.index("档号")
            hdr.setSectionResizeMode(ar_col, QHeaderView.Fixed)
            self.table.setColumnWidth(ar_col, 215)

        if "卷内张数" in headers:
            page_col = 2 + headers.index("卷内张数")
            hdr.setSectionResizeMode(page_col, QHeaderView.Fixed)
            self.table.setColumnWidth(page_col, 55)

        if "保管期限" in headers:
            date_col = 2 + headers.index("保管期限")
            hdr.setSectionResizeMode(date_col, QHeaderView.Fixed)
            self.table.setColumnWidth(date_col, 65)

        if "起始时间" in headers or "终止时间" in headers:
            date_col = 2 + headers.index("起始时间")
            hdr.setSectionResizeMode(date_col, QHeaderView.Fixed)
            self.table.setColumnWidth(date_col, 125)
        if  "终止时间" in headers:
            date_col = 2 + headers.index("终止时间")
            hdr.setSectionResizeMode(date_col, QHeaderView.Fixed)
            self.table.setColumnWidth(date_col, 125)

        if "题名" in headers:
            title_col = 2 + headers.index("题名")
            hdr.setSectionResizeMode(title_col, QHeaderView.Fixed)
            self.table.setColumnWidth(title_col, 325)


    def _rebuild_filter_bar(self):
        """在表格上方重建筛选输入框，与列头对应"""
        # 清空旧筛选控件
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._filter_edits = {}

        # 复选框占位
        spacer_cb = QWidget()
        spacer_cb.setFixedWidth(40)
        self.filter_layout.addWidget(spacer_cb)

        # 序号占位
        spacer_idx = QWidget()
        spacer_idx.setFixedWidth(55)
        self.filter_layout.addWidget(spacer_idx)

        # 筛选框
        for header in ["档号", "题名"]:
            edit = QLineEdit()
            edit.setPlaceholderText(f"筛选{header}")
            edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #90caf9; border-radius: 5px;
                    padding: 4px 8px; font-size: 12px; color: #333;
                    background: #f8fbff; font-family: 'Microsoft YaHei';
                }
                QLineEdit:focus { border: 1px solid #1976d2; background: white; }
            """)
            edit.textChanged.connect(lambda text, h=header: self._on_filter_changed(h, text))
            self.filter_layout.addWidget(edit, 1)
            self._filter_edits[header] = edit

        # 操作列占位
        spacer_op = QWidget()
        spacer_op.setFixedWidth(135)
        self.filter_layout.addWidget(spacer_op)

    # ──────────────────── 筛选逻辑 ────────────────────

    def _on_filter_changed(self, header: str, text: str):
        self._filter_values[header] = text.strip()
        self._apply_filter()

    def _apply_filter(self):
        self._filters = {h: v for h, v in self._filter_values.items() if v}
        self._refresh_table()

    # ──────────────────── 表格刷新（分页） ────────────────────

    def _refresh_table(self):
        archive_type = self._current_category.split('-')[0]
        category = self._current_category.split('-')[1]
        title = self._filters.get("题名", None)
        doc_number = self._filters.get("档号", None)
        total = director_service.get_total(archive_type=archive_type, category=category,
                                           title=title, doc_number=doc_number)

        self._total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._current_page = max(1, min(self._current_page, self._total_pages))

        start = (self._current_page - 1) * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)

        page_data = director_service.get_list(skip=start, limit= end, archive_type=archive_type, category=category,
                                              title=title, doc_number=doc_number)

        self._all_data = page_data
        self.table.setRowCount(0)
        for idx, row_dict in enumerate(page_data):
            global_idx = start + idx
            self._insert_row(idx, global_idx + 1, row_dict)

        self.page_label.setText(f"第 {self._current_page} / {self._total_pages} 页")
        self.total_label.setText(f"共 {total} 条")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    def _insert_row(self, table_row: int, display_idx: int, row_dict: dict):
        self.table.insertRow(table_row)
        self.table.setRowHeight(table_row, 42)

        # 复选框
        cb_w, _ = _make_checkbox_widget()
        self.table.setCellWidget(table_row, 0, cb_w)

        # 序号
        idx_item = QTableWidgetItem(str(display_idx))
        idx_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(table_row, 1, idx_item)

        # 数据列
        for col_offset, header in enumerate(self._current_headers):
            val = json.loads(row_dict.director_info).get(header, "")
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(table_row, 2 + col_offset, item)

        # 操作列
        op_col = 2 + len(self._current_headers)
        data_idx = row_dict.id

        def make_edit_cb(d_idx):
            return lambda: self._edit_record(d_idx)

        def make_del_cb(d_idx):
            return lambda: self._delete_single(d_idx)

        op_w = _make_action_btn_widget(make_edit_cb(data_idx), make_del_cb(data_idx))
        self.table.setCellWidget(table_row, op_col, op_w)

    # ──────────────────── 分页按钮 ────────────────────

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._refresh_table()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._refresh_table()

    # ──────────────────── 导入 ────────────────────

    def _import_data(self):
        if not self._current_category:
            show_warning(self, "警告", "请先选择左侧档案类别！")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "导入目录 Excel", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if not path:
            return

        try:
            df = pd.read_excel(path, dtype=str)
            df.fillna("", inplace=True)
            self._import_df = df
            headers = self._current_headers
            fields = CATEGORY_HEADERS.get(self._current_category, [])

            # 校验字段（档案门类、类别）
            verify_result = self.verify_field(fields, df.columns.to_list())

            if not verify_result['status']:
                show_error(self, "导入失败", f"原因: {verify_result['message']}")
                return

            # 尝试按别名列或字段名列匹配
            imported = []
            for _, series in df.iterrows():
                row_dict = {}
                archival_number = ""
                for i, h in enumerate(headers):
                    # 先尝试别名，再尝试字段名
                    if h in df.columns:
                        row_dict[h] = str(series.get(h, ""))
                    elif i < len(fields) and fields[i] in df.columns:
                        row_dict[h] = str(series.get(fields[i], ""))
                    else:
                        # 按列位置匹配
                        if i < len(df.columns):
                            row_dict[h] = str(series.iloc[i])
                        else:
                            row_dict[h] = ""

                    if h == "档号":
                        archival_number  = series.iloc[i + 1]

                data_dict = {
                    "register_id": 0,
                    "archive_type": self._current_category.split('-')[0],
                    "category": self._current_category.split('-')[1],
                    "doc_number": archival_number,
                    "title": row_dict["题名"],
                    "director_info": json.dumps(row_dict, ensure_ascii=False),
                    "source": "导入",
                    "create_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "operator": self.current_user['username'],
                }

                imported.append(data_dict)
            add_result = director_service.batch_add(imported)
            self._add_exit_list = add_result['exit_list']

            self._refresh_table()
            self._apply_filter()
            show_success(self, "导入成功", f"成功导入 {len(imported) - len(add_result['exit_list'])} 条记录")
        except Exception as e:
            show_error(self, "导入失败", str(e))

    def verify_field(self, default_field, expected_field):
        if len(default_field) != len(expected_field) - 1:
            return {"status": False, "message": "字段数不一致!"}

        if "序号" in expected_field:
            expected_field.remove("序号")
        if sorted(default_field) != sorted(expected_field):
            return {'status': False, "message": "字段名不一致！"}

        return {"status": True, "message": ""}

    # ──────────────────── 导出 ────────────────────

    def _export_data(self):
        if not self._current_category:
            show_warning(self, "警告", "请先选择左侧档案类别！")
            return

        archive_type = self._current_category.split('-')[0]
        category = self._current_category.split('-')[1]
        title = self._filters.get("题名", None)
        doc_number = self._filters.get("档号", None)
        data_total = director_service.get_total(archive_type=archive_type, category=category, doc_number=doc_number, title=title)

        if data_total == 0:
            show_warning(self, "警告", "当前没有可导出的数据！")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出目录",
            f"{self._current_category}目录表-{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        data = director_service.get_list(archive_type=archive_type, category=category, title=title, doc_number=doc_number)
        try:
            rows = []
            for row_dict in data:
                rows.append(json.loads(row_dict.director_info))
            df = pd.DataFrame(rows, columns=self._current_headers)
            df.index = range(1, len(df) + 1)
            df.index.name = "序号"
            df.to_excel(path, engine="openpyxl")
            show_success(self, "导出成功", f"已导出到：{path}")
        except Exception as e:
            show_error(self, "导出失败", str(e))

    # ──────────────────── 新增记录 ────────────────────

    def _add_record(self):
        if not self._current_category:
            show_warning(self, "警告", "请先选择左侧档案类别！")
            return
        dlg = RowEditDialog(self, headers=self._current_headers)
        if dlg.exec():
            data = dlg.get_data()
            data_dict = {
                "register_id": 0,
                "archive_type": self._current_category.split('-')[0],
                "category": self._current_category.split('-')[1],
                "doc_number": data['档号'],
                "title": data['题名'],
                "director_info": json.dumps(data, ensure_ascii=False),
                "source": "添加",
                "create_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "update_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operator": self.current_user['username'],
            }
            result = director_service.batch_add([data_dict])
            print(111, result)

            self._refresh_table()
            self._apply_filter()
            show_success(self, "新增成功", "目录已添加")

    # ──────────────────── 单行编辑 ────────────────────

    def _edit_record(self, data_idx: int):
        current = json.loads(director_service.get_director_by_id(data_idx).director_info)
        dlg = RowEditDialog(self, headers=self._current_headers, row_data=current)
        if dlg.exec():
            new_data = dlg.get_data()
            update = {
                "director_info": json.dumps(new_data, ensure_ascii=False),
            }
            director_service.update_director(data_idx, update)
            self._refresh_table()
            self._apply_filter()
            show_success(self, "修改成功", "记录已更新")

    # ──────────────────── 单行删除 ────────────────────

    def _delete_single(self, data_idx: int):

        w = MessageBox("确认删除", "确定要删除该条记录吗？此操作不可撤销。", self)
        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")
        if w.exec():
            director_service.delete_director_by_id(data_idx)
            self._refresh_table()
            self._apply_filter()
            show_success(self, "删除成功", "记录已删除")

    # ──────────────────── 批量删除 ────────────────────

    def _batch_delete(self):
        if not self._current_category:
            show_warning(self, "警告", "请先选择左侧档案类别！")
            return

        start = (self._current_page - 1) * PAGE_SIZE
        page_data = self._all_data[start:start+PAGE_SIZE]

        checked_indices = []
        for row in range(self.table.rowCount()):
            cw = self.table.cellWidget(row, 0)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb and cb.isChecked() and row < len(self._all_data):
                    real_row = page_data[row]
                    idx = self._all_data.index(real_row) if real_row in self._all_data else -1
                    if idx >= 0:
                        checked_indices.append(idx)

        if not checked_indices:
            show_warning(self, "警告", "请先勾选要删除的记录！")
            return

        w = MessageBox("确认删除", f"确定要删除选中的 {len(checked_indices)} 条记录吗？\n此操作不可撤销。", self)
        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")
        if w.exec():
            for idx in sorted(set(checked_indices), reverse=True):
                id = self._all_data[idx].id
                director_service.delete_director_by_id(id=id)
            self._apply_filter()
            show_success(self, "删除成功", f"已删除 {len(checked_indices)} 条记录")


    def _download_question(self):
        """
        下载导入失败或问题表
        """

        if len(self._add_exit_list) == 0:
            show_warning(self, "提示", "暂无问题可下载")
            return

        d_df = self._import_df[self._import_df["档号"].isin(self._add_exit_list)]

        path, _ = QFileDialog.getSaveFileName(
            self, "导出目录",
            f"{self._current_category}目录表(重复导入或已存在档号)-{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        try:
            d_df.to_excel(path, engine="openpyxl", index=False)
            show_success(self, "导出成功", f"已导出到：{path}")
        except Exception as e:
            show_error(self, "导出失败", str(e))