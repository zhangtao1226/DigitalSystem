# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : mark_manage_page.py
# @Desc     : 质检标记管理页面
# @Time     : 2025/12/16
# @Software : PyCharm

from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QGroupBox,
    QAbstractItemView, QHeaderView, QTableWidgetItem, QCheckBox,
    QLabel, QFrame, QTableWidget, QScrollArea, QFormLayout,
    QApplication, QDialog, QPlainTextEdit, QStyleOptionButton, QStyle,
)
from PySide6.QtCore import Qt, Signal

from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, BodyLabel, MessageBox,
    PushButton, PrimaryPushButton, FluentIcon, IconWidget,
    CardWidget, ComboBox, LineEdit,
)

from src.utils.NotificationTool import show_success, show_warning
from src.services.task_mark_service import task_mark_service, MARK_STAGE


class CheckableHeader(QHeaderView):
    check_all_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._checked = False
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.viewport().update()

    def paintSection(self, painter: QPainter, rect, logical_index: int):
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()
        if logical_index == 0:
            opt = QStyleOptionButton()
            cb_size = 14
            x = rect.x() + (rect.width()  - cb_size) // 2
            y = rect.y() + (rect.height() - cb_size) // 2
            opt.rect = rect.__class__(x, y, cb_size, cb_size)
            opt.state = (
                QStyle.State_Enabled |
                (QStyle.State_On if self._checked else QStyle.State_Off)
            )
            self.style().drawControl(QStyle.CE_CheckBox, opt, painter)

    def mousePressEvent(self, event):
        if self.logicalIndexAt(event.pos()) == 0:
            self._checked = not self._checked
            self.viewport().update()
            self.check_all_changed.emit(self._checked)
        else:
            super().mousePressEvent(event)

PAGE_SIZE = 20

MARK_STAGE_MAP = {v: k for k, v in MARK_STAGE.items()}

LEVELS = ["严重", "一般", "轻微"]

LEVEL_COLOR = {
    "严重": ("#fdecea", "#c62828"),
    "一般": ("#fff8e1", "#e65100"),
    "轻微": ("#e8f5e9", "#2e7d32"),
}
STATUS_COLOR = {
    True:  ("#e8f5e9", "#2e7d32", "已修改"),
    False: ("#fff3e0", "#e65100", "待修改"),
}
STAGE_COLOR = {
    1: ("#e3f2fd", "#1565c0"),
    2: ("#f3e5f5", "#6a1b9a"),
    3: ("#e8f5e9", "#1b5e20"),
    4: ("#a1e8c4", "#047a3e")
}

COL_DEFS = [
    ("",        "fixed",   36),
    ("序号",    "fixed",   52),
    ("质检阶段","fixed",  115),
    ("标记类型","fixed",  120),
    ("严重程度","fixed",   90),
    ("标记对象","stretch", None),
    ("问题描述","stretch", None),
    ("质检员",  "fixed",   90),
    ("标记时间","fixed",  140),
    ("状态",    "fixed",   90),
    ("修改说明","stretch", None),
    ("操作",    "fixed",   90),
]
COL_HEADERS = [c[0] for c in COL_DEFS]


def _make_row_checkbox():
    cb = QCheckBox()
    w  = QWidget()
    lay = QHBoxLayout(w)
    lay.addWidget(cb)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(0, 0, 0, 0)
    return w, cb


def _make_badge(text: str, bg: str, fg: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(22)
    lbl.setStyleSheet(
        f"background:{bg};color:{fg};border-radius:4px;"
        f"font-size:12px;font-family:'Microsoft YaHei';padding:0 8px;"
    )
    return lbl


def _centered(widget: QWidget) -> QWidget:
    w   = QWidget()
    lay = QHBoxLayout(w)
    lay.addWidget(widget)
    lay.setAlignment(Qt.AlignCenter)
    lay.setContentsMargins(4, 2, 4, 2)
    return w


class MarkDetailDialog(QDialog):

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self._d = data
        self.setWindowTitle("标记详情")
        self.setMinimumWidth(520)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._init_ui()

    def _init_ui(self):
        d   = self._d
        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(30, 24, 30, 24)

        # 标题行
        title_row = QHBoxLayout(); title_row.setSpacing(10)
        ico = IconWidget(FluentIcon.TAG); ico.setFixedSize(20, 20)
        title_row.addWidget(ico)
        t = StrongBodyLabel("标记详情")
        t.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        t.setStyleSheet("color:#2c3e50;")
        title_row.addWidget(t)
        title_row.addStretch()

        is_fixed = bool(getattr(d, "is_fixed", False))
        st_bg, st_fg, st_txt = STATUS_COLOR[is_fixed]
        st_badge = _make_badge(st_txt, st_bg, st_fg)
        st_badge.setFixedWidth(72)
        title_row.addWidget(st_badge)
        lay.addLayout(title_row)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#dfe6e9;")
        lay.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner  = QWidget()
        form   = QFormLayout(inner)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 4, 0, 4)

        lbl_s  = "font-family:'Microsoft YaHei';font-size:13px;color:#636e72;font-weight:500;"
        val_s  = "font-family:'Microsoft YaHei';font-size:13px;color:#2c3e50;"
        bold_s = "font-family:'Microsoft YaHei';font-size:13px;color:#1565c0;font-weight:600;"

        def fl(txt):
            l = QLabel(f"{txt}："); l.setStyleSheet(lbl_s); return l

        def vl(txt, bold=False):
            l = QLabel(str(txt) if txt is not None else "—")
            l.setStyleSheet(bold_s if bold else val_s)
            l.setWordWrap(True)
            return l

        stage_id  = getattr(d, "mark_stage", 0)
        stage_txt = MARK_STAGE_MAP.get(stage_id, "—")
        bg, fg    = STAGE_COLOR.get(stage_id, ("#f5f5f5", "#333"))
        stage_badge = _make_badge(stage_txt, bg, fg)
        stage_badge.setFixedWidth(100)
        form.addRow(fl("质检阶段"), stage_badge)
        form.addRow(fl("标记类型"), vl(getattr(d, "mark_type", ""), bold=True))

        level    = getattr(d, "level", "一般") or "一般"
        lv_bg, lv_fg = LEVEL_COLOR.get(level, ("#f5f5f5", "#333"))
        lv_badge = _make_badge(level, lv_bg, lv_fg); lv_badge.setFixedWidth(60)
        form.addRow(fl("严重程度"), lv_badge)

        form.addRow(QFrame())   # 分隔

        if stage_id == 3:
            form.addRow(fl("字段名"),   vl(getattr(d, "field_name", "")))
            form.addRow(fl("原始值"),   vl(getattr(d, "field_value_before", "")))
            form.addRow(fl("修改后值"), vl(getattr(d, "field_value_after", ""), bold=True))
        else:
            form.addRow(fl("文件名"), vl(getattr(d, "scan_file", "")))
            page_no = getattr(d, "page_no", None)
            form.addRow(fl("页码"), vl(f"第 {page_no} 页" if page_no else None))

        form.addRow(QFrame())

        desc_box = QPlainTextEdit(getattr(d, "description", "") or "")
        desc_box.setReadOnly(True); desc_box.setFixedHeight(72)
        desc_box.setStyleSheet(
            "border:1px solid #e0e0e0;border-radius:6px;padding:6px;"
            "font-size:13px;background:#fafbfc;font-family:'Microsoft YaHei';"
        )
        form.addRow(fl("问题描述"), desc_box)
        form.addRow(fl("质检员"),   vl(getattr(d, "inspector", "")))
        form.addRow(fl("标记时间"), vl(getattr(d, "mark_date", "")))

        if is_fixed:
            form.addRow(QFrame())
            form.addRow(fl("修改时间"), vl(getattr(d, "fix_date", "")))
            remark_box = QPlainTextEdit(getattr(d, "fix_remark", "") or "")
            remark_box.setReadOnly(True); remark_box.setFixedHeight(56)
            remark_box.setStyleSheet(
                "border:1px solid #e0e0e0;border-radius:6px;padding:6px;"
                "font-size:13px;background:#f1f8e9;font-family:'Microsoft YaHei';"
            )
            form.addRow(fl("修改说明"), remark_box)

        scroll.setWidget(inner)
        lay.addWidget(scroll)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        close_btn = PrimaryPushButton("关闭")
        close_btn.setFixedSize(90, 36)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)


class MarkManagePage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        setTheme(Theme.AUTO)
        self._current_page = 1
        self._total_pages  = 1

        self._page_data: list = []
        self._header: CheckableHeader | None = None
        self._init_ui()
        self._load_page()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(18)
        root.setContentsMargins(25, 25, 25, 25)

        title_row = QHBoxLayout(); title_row.setSpacing(10)
        ico = IconWidget(FluentIcon.TAG); ico.setFixedSize(24, 24)
        title_row.addWidget(ico)
        title = StrongBodyLabel("质检标记管理")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title.setStyleSheet("color:#333333;")
        title_row.addWidget(title)
        title_row.addStretch()
        root.addLayout(title_row)

        card     = CardWidget()
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(0)
        card_lay.setContentsMargins(28, 24, 28, 24)

        card_lay.addLayout(self._build_stat_bar())
        card_lay.addSpacing(16)
        card_lay.addWidget(self._build_filter_group())
        card_lay.addSpacing(12)
        card_lay.addLayout(self._build_toolbar())
        card_lay.addSpacing(10)

        self.table = QTableWidget(0, len(COL_DEFS))
        self._apply_table_style()
        card_lay.addWidget(self.table)
        card_lay.addSpacing(8)
        card_lay.addLayout(self._build_page_bar())
        root.addWidget(card)

    def _build_stat_bar(self) -> QHBoxLayout:
        lay = QHBoxLayout(); lay.setSpacing(16)
        self._stat_widgets = {}
        for key, label, fg, bg in [
            ("total",   "全部标记", "#455a64", "#eceff1"),
            ("pending", "待修改",   "#e65100", "#fff3e0"),
            ("fixed",   "已修改",   "#2e7d32", "#e8f5e9"),
        ]:
            box = QWidget()
            box.setStyleSheet(f"background:{bg};border-radius:8px;")
            box.setFixedHeight(56)
            b = QHBoxLayout(box); b.setContentsMargins(16, 6, 16, 6)
            lbl = BodyLabel(label)
            lbl.setStyleSheet(f"font-size:12px;color:{fg};font-family:'Microsoft YaHei';")
            b.addWidget(lbl)
            num = StrongBodyLabel("0")
            num.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
            num.setStyleSheet(f"color:{fg};")
            b.addWidget(num); b.addStretch()
            lay.addWidget(box)
            self._stat_widgets[key] = num
        lay.addStretch()
        return lay

    def _update_stat_bar(self):
        total   = task_mark_service.get_total_count()
        fixed   = task_mark_service.get_total_count(is_fixed=True)
        pending = total - fixed
        self._stat_widgets["total"].setText(str(total))
        self._stat_widgets["pending"].setText(str(pending))
        self._stat_widgets["fixed"].setText(str(fixed))

    def _build_filter_group(self) -> QGroupBox:
        group = QGroupBox("筛选条件")
        group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        group.setStyleSheet("""
            QGroupBox { border:2px solid #dfe6e9; border-radius:10px;
                margin-top:10px; padding-top:8px; background:white; }
            QGroupBox::title { subcontrol-origin:margin; left:15px;
                padding:0 10px; color:#636e72; }
        """)
        lay = QHBoxLayout(group)
        lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(12)
        lbl_s = "font-family:'Microsoft YaHei';font-size:12px;color:#636e72;"

        def fl(txt):
            l = QLabel(txt + "："); l.setStyleSheet(lbl_s); return l

        lay.addWidget(fl("质检阶段"))
        self.f_stage = ComboBox()
        self.f_stage.addItems(["全部"] + list(MARK_STAGE.keys()))   # 直接用 service 常量
        self.f_stage.setFixedWidth(130)
        self.f_stage.currentIndexChanged.connect(self._on_filter_changed)
        lay.addWidget(self.f_stage)

        lay.addWidget(fl("严重程度"))
        self.f_level = ComboBox()
        self.f_level.addItems(["全部"] + LEVELS)
        self.f_level.setFixedWidth(100)
        self.f_level.currentIndexChanged.connect(self._on_filter_changed)
        lay.addWidget(self.f_level)

        lay.addWidget(fl("修改状态"))
        self.f_status = ComboBox()
        self.f_status.addItems(["全部", "待修改", "已修改"])
        self.f_status.setFixedWidth(100)
        self.f_status.currentIndexChanged.connect(self._on_filter_changed)
        lay.addWidget(self.f_status)

        lay.addWidget(fl("关键字"))
        self.f_keyword = LineEdit()
        self.f_keyword.setPlaceholderText("标记类型 / 描述 / 文件名 / 质检员")
        self.f_keyword.setFixedWidth(210)
        self.f_keyword.textChanged.connect(self._on_filter_changed)
        lay.addWidget(self.f_keyword)

        reset_btn = PushButton("重置")
        reset_btn.setFixedSize(72, 32)
        reset_btn.clicked.connect(self._reset_filter)
        lay.addWidget(reset_btn)
        lay.addStretch()
        return group

    def _build_toolbar(self) -> QHBoxLayout:
        lay = QHBoxLayout(); lay.setSpacing(10); lay.addStretch()
        del_btn = PrimaryPushButton("批量删除")
        del_btn.setFixedSize(100, 36)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            PrimaryPushButton { background-color:#f44336;color:white;
                border-radius:8px;font-size:13px; }
            PrimaryPushButton:hover { background-color:#d32f2f; }
        """)
        del_btn.clicked.connect(self._batch_delete)
        lay.addWidget(del_btn)
        return lay

    def _apply_table_style(self):
        self._header = CheckableHeader(self.table)
        self._header.check_all_changed.connect(self._on_header_check_changed)
        self.table.setHorizontalHeader(self._header)
        self.table.setHorizontalHeaderLabels(COL_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { border:1px solid #bbdefb; border-radius:8px;
                background:#fff; font-family:'Microsoft YaHei';
                font-size:13px; gridline-color:#e3f2fd; }
            QTableWidget::item { padding:4px 6px; color:#333; }
            QTableWidget::item:selected { background:#e3f2fd; color:#1565c0; }
            QTableWidget::item:alternate { background:#f8fbff; }
            QHeaderView::section { background:#e3f2fd; color:#1565c0; font-weight:bold;
                font-size:12px; padding:7px 5px; border:none;
                border-bottom:2px solid #90caf9; font-family:'Microsoft YaHei'; }
        """)
        hdr = self.table.horizontalHeader()
        for i, (_, mode, width) in enumerate(COL_DEFS):
            if mode == "fixed":
                hdr.setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, width)
            else:
                hdr.setSectionResizeMode(i, QHeaderView.Stretch)

    def _build_page_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout(); bar.setSpacing(10); bar.addStretch()
        self.prev_btn = PushButton("◀ 上一页")
        self.prev_btn.setFixedSize(90, 32)
        self.prev_btn.clicked.connect(self._prev_page)
        bar.addWidget(self.prev_btn)

        self.page_label = BodyLabel("第 1 / 1 页")
        self.page_label.setStyleSheet(
            "font-size:13px;color:#555;font-family:'Microsoft YaHei';"
        )
        bar.addWidget(self.page_label)

        self.next_btn = PushButton("下一页 ▶")
        self.next_btn.setFixedSize(90, 32)
        self.next_btn.clicked.connect(self._next_page)
        bar.addWidget(self.next_btn)

        self.total_label = BodyLabel("共 0 条")
        self.total_label.setStyleSheet(
            "font-size:12px;color:#999;font-family:'Microsoft YaHei';margin-left:10px;"
        )
        bar.addWidget(self.total_label)
        bar.addStretch()
        return bar


    def _get_filter_params(self) -> dict:
        stage_txt  = self.f_stage.currentText()
        level_txt  = self.f_level.currentText()
        status_txt = self.f_status.currentText()
        keyword    = self.f_keyword.text().strip() or None

        mark_stage = MARK_STAGE.get(stage_txt) if stage_txt != "全部" else None
        level      = level_txt  if level_txt  != "全部" else None
        is_fixed   = (
            True  if status_txt == "已修改" else
            False if status_txt == "待修改" else
            None
        )
        return dict(
            mark_stage = mark_stage,
            level      = level,
            is_fixed   = is_fixed,
            keyword    = keyword,
        )

    def _on_filter_changed(self):
        self._current_page = 1
        self._load_page()

    def _reset_filter(self):
        for w in (self.f_stage, self.f_level, self.f_status):
            w.blockSignals(True)
            w.setCurrentIndex(0)
            w.blockSignals(False)
        self.f_keyword.blockSignals(True)
        self.f_keyword.clear()
        self.f_keyword.blockSignals(False)
        self._current_page = 1
        self._load_page()


    def _load_page(self):
        params = self._get_filter_params()
        try:
            items, total = task_mark_service.get_page(
                page      = self._current_page,
                page_size = PAGE_SIZE,
                **params,
            )
        except Exception as e:
            show_warning(self, "查询失败", str(e))
            items, total = [], 0

        self._page_data    = items
        self._total_pages  = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._current_page = max(1, min(self._current_page, self._total_pages))

        # 渲染表格
        self.table.setRowCount(0)
        start = (self._current_page - 1) * PAGE_SIZE
        for row_idx, d in enumerate(items):
            self._insert_row(row_idx, start + row_idx + 1, d)

        # 分页栏
        self.page_label.setText(f"第 {self._current_page} / {self._total_pages} 页")
        self.total_label.setText(f"共 {total} 条")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

        if self._header:
            self._header.set_checked(False)

        self._update_stat_bar()

    def _insert_row(self, row: int, seq: int, d):
        self.table.insertRow(row)
        self.table.setRowHeight(row, 44)

        cb_w, _ = _make_row_checkbox()
        self.table.setCellWidget(row, 0, cb_w)

        self._ci(row, 1, str(seq))

        stage_txt = MARK_STAGE_MAP.get(d.mark_stage, "")
        bg, fg    = STAGE_COLOR.get(d.mark_stage, ("#f5f5f5", "#333"))
        self.table.setCellWidget(row, 2, _centered(_make_badge(stage_txt, bg, fg)))

        self._ci(row, 3, d.mark_type or "")

        level    = d.level or "一般"
        lv_bg, lv_fg = LEVEL_COLOR.get(level, ("#f5f5f5", "#333"))
        self.table.setCellWidget(row, 4, _centered(_make_badge(level, lv_bg, lv_fg)))

        if d.mark_stage == 3:
            obj = f"{d.field_name or ''}: {d.field_value_before or ''}"
        else:
            obj = d.scan_file or ""
            # if d.page_no:
            #     obj += f"  第{d.page_no}页"
        self._li(row, 5, obj)

        self._li(row, 6, d.description or "")
        self._ci(row, 7, d.inspector or "")

        mark_date = d.mark_date
        date_str  = (
            mark_date.strftime("%Y-%m-%d %H:%M")
            if hasattr(mark_date, "strftime") else str(mark_date or "")
        )
        self._ci(row, 8, date_str)

        is_fixed             = bool(d.is_fixed)
        st_bg, st_fg, st_txt = STATUS_COLOR[is_fixed]
        self.table.setCellWidget(row, 9, _centered(_make_badge(st_txt, st_bg, st_fg)))

        remark = ""
        if is_fixed:
            remark = d.fix_remark or ""
            if d.field_value_after:
                remark = f"→ {d.field_value_after}  {remark}"
        self._li(row, 10, remark)

        detail_btn = PushButton("详情")
        detail_btn.setFixedSize(60, 28)
        detail_btn.setCursor(Qt.PointingHandCursor)
        detail_btn.setStyleSheet("""
            PushButton { background-color:#1976d2;color:white;
                border-radius:5px;font-size:12px; }
            PushButton:hover { background-color:#1565c0; }
        """)
        detail_btn.clicked.connect(lambda _, mark_id=d.id: self._show_detail(mark_id))
        self.table.setCellWidget(row, 11, _centered(detail_btn))

    def _ci(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def _li(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.table.setItem(row, col, item)

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_page()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_page()

    def _on_header_check_changed(self, checked: bool):
        for row in range(self.table.rowCount()):
            cw = self.table.cellWidget(row, 0)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(checked)
                    cb.blockSignals(False)

    def _get_checked_mark_ids(self) -> list[int]:
        ids = []
        for row in range(self.table.rowCount()):
            cw = self.table.cellWidget(row, 0)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb and cb.isChecked() and row < len(self._page_data):
                    ids.append(self._page_data[row].id)
        return ids


    def _show_detail(self, mark_id: int):
        data = task_mark_service.get_by_id(mark_id)
        if data:
            MarkDetailDialog(self, data=data).exec()

    def _batch_delete(self):
        ids = self._get_checked_mark_ids()
        if not ids:
            show_warning(self, "提示", "请先勾选要删除的标记记录！")
            return
        w = MessageBox(
            "确认批量删除",
            f"确定要删除选中的 {len(ids)} 条记录吗？此操作不可撤销。",
            self
        )
        w.yesButton.setText("确定"); w.cancelButton.setText("取消")
        if w.exec():
            count = task_mark_service.batch_delete_marks(ids)
            self._load_page()
            show_success(self, "已删除", f"已删除 {count} 条记录")