# -*-coding : utf-8 -*-
# @Author   : zhangtao
# @FileName : MarkHistoryDialog.py
# @Desc     : 历史标记查看 & 修改状态弹框
#             - 展示扫描件已有全部标记
#             - 每条标记可「标记已修改」或「撤销已修改」
#             - 底部「继续新增标记」→ accept()；「关闭」→ reject()
# @Time     : 2026/6/16

from datetime import datetime
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QFrame, QScrollArea, QPlainTextEdit,
)

from qfluentwidgets import (
    StrongBodyLabel, BodyLabel,
    PushButton, PrimaryPushButton,
    FluentIcon, IconWidget, MessageBox,
)

# ──────────── 颜色常量 ────────────

LEVEL_COLOR = {
    "严重": ("#fdecea", "#c62828", "#e53935"),
    "一般": ("#fff8e1", "#e65100", "#fb8c00"),
    "轻微": ("#e8f5e9", "#2e7d32", "#43a047"),
}
STATUS_BG   = { True: "#e8f5e9", False: "#fff3e0" }
STATUS_FG   = { True: "#2e7d32", False: "#e65100" }
STATUS_TEXT = { True: "已修改",  False: "待修改"  }


def _badge(text, bg, fg, w=None):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(22)
    if w:
        lbl.setFixedWidth(w)
    lbl.setStyleSheet(
        f"background:{bg};color:{fg};border-radius:4px;"
        f"font-size:11px;font-weight:bold;font-family:'Microsoft YaHei';padding:0 6px;"
    )
    return lbl


def _hsep():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#eee;margin:0;"); return f


# ──────────── 单条标记卡片（含操作按钮）────────────

class _MarkCard(QWidget):
    """
    单条标记卡片。
    fix_clicked(mark_id)   → 点击「标记已修改」
    reopen_clicked(mark_id)→ 点击「撤销已修改」
    """
    fix_clicked    = Signal(int)
    reopen_clicked = Signal(int)

    def __init__(self, mark, index: int, readonly: bool = False, parent=None):
        super().__init__(parent)
        self._mark    = mark
        self._readonly = readonly
        self.setObjectName("markCard")
        bg, _, fg = LEVEL_COLOR.get(mark.level, ("#f5f5f5", "#333", "#333"))
        self.setStyleSheet(f"""
            QWidget#markCard {{
                background:{bg}; border-radius:8px;
                border:1px solid {fg}40;
            }}
        """)
        self._build_ui(index, bg, fg)

    def _build_ui(self, index: int, bg: str, fg: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        row1 = QHBoxLayout(); row1.setSpacing(8)
        idx_lbl = QLabel(f"#{index}")
        idx_lbl.setStyleSheet("font-size:12px;color:#999;font-family:'Microsoft YaHei';")
        row1.addWidget(idx_lbl)

        type_lbl = StrongBodyLabel(self._mark.mark_type or "—")
        type_lbl.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        type_lbl.setStyleSheet(f"color:{fg};")
        row1.addWidget(type_lbl)
        row1.addStretch()

        lv_bg, lv_fg, _ = LEVEL_COLOR.get(self._mark.level, ("#f5f5f5","#333","#333"))
        row1.addWidget(_badge(self._mark.level or "一般", lv_bg, lv_fg, 52))

        is_fixed = bool(self._mark.is_fixed)
        self._status_badge = _badge(
            STATUS_TEXT[is_fixed], STATUS_BG[is_fixed], STATUS_FG[is_fixed], 62
        )
        row1.addWidget(self._status_badge)
        lay.addLayout(row1)

        # ── 行2：问题描述 ──
        desc = self._mark.description or ""
        desc_lbl = BodyLabel(desc or "（无描述）")
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            "font-size:13px;color:#444;font-family:'Microsoft YaHei';"
        )
        lay.addWidget(desc_lbl)

        # ── 行3：元信息 ──
        meta_s = "font-size:11px;color:#888;font-family:'Microsoft YaHei';"
        row3 = QHBoxLayout(); row3.setSpacing(16)
        row3.addWidget(self._ml(f"质检员：{self._mark.inspector or '—'}", meta_s))
        row3.addWidget(self._ml(f"标记时间：{self._mark.mark_date or '—'}", meta_s))
        row3.addStretch()
        lay.addLayout(row3)

        # ── 已修改信息区 ──
        if is_fixed:
            lay.addWidget(_hsep())
            self._build_fix_info(lay, meta_s)

        # ── 操作按钮（非只读时显示）──
        if not self._readonly:
            lay.addWidget(_hsep())
            self._build_action_row(lay, is_fixed)

    def _build_fix_info(self, parent_lay, meta_s):
        fix_row = QHBoxLayout(); fix_row.setSpacing(16)
        fix_row.addWidget(self._ml(f"修改时间：{self._mark.fix_date or '—'}", meta_s))
        remark = self._mark.fix_remark or "—"
        fix_row.addWidget(
            self._ml(
                f"修改说明：{remark[:40]}{'…' if len(remark) > 40 else ''}",
                meta_s
            )
        )
        fix_row.addStretch()
        parent_lay.addLayout(fix_row)

    def _build_action_row(self, parent_lay, is_fixed: bool):
        row = QHBoxLayout(); row.setSpacing(8); row.addStretch()

        if not is_fixed:
            # 输入修改说明
            self._remark_input = QPlainTextEdit()
            self._remark_input.setPlaceholderText("填写修改说明（可选）……")
            self._remark_input.setFixedHeight(52)
            self._remark_input.setStyleSheet("""
                QPlainTextEdit {
                    border:1px solid #ddd; border-radius:5px; padding:4px;
                    font-size:12px; font-family:'Microsoft YaHei'; background:#fafafa;
                }
                QPlainTextEdit:focus { border:1px solid #1976d2; }
            """)
            parent_lay.addWidget(self._remark_input)

            fix_btn = PrimaryPushButton("✔ 标记已修改")
            fix_btn.setFixedSize(110, 30)
            fix_btn.setCursor(Qt.PointingHandCursor)
            fix_btn.setStyleSheet("""
                PrimaryPushButton { background:#388e3c; color:white;
                    border-radius:6px; font-size:12px; }
                PrimaryPushButton:hover { background:#2e7d32; }
            """)
            fix_btn.clicked.connect(self._on_fix_clicked)
            row.addWidget(fix_btn)
        else:
            reopen_btn = PushButton("↩ 撤销已修改")
            reopen_btn.setFixedSize(110, 30)
            reopen_btn.setCursor(Qt.PointingHandCursor)
            reopen_btn.setStyleSheet("""
                PushButton { background:#f57c00; color:white;
                    border-radius:6px; font-size:12px; }
                PushButton:hover { background:#e65100; }
            """)
            reopen_btn.clicked.connect(lambda: self.reopen_clicked.emit(self._mark.id))
            row.addWidget(reopen_btn)

        parent_lay.addLayout(row)

    def _on_fix_clicked(self):
        remark = ""
        if hasattr(self, "_remark_input"):
            remark = self._remark_input.toPlainText().strip()
        self.fix_clicked.emit(self._mark.id)
        # 暂存 remark 供外部读取
        self._pending_remark = remark

    @staticmethod
    def _ml(text, style):
        l = QLabel(text); l.setStyleSheet(style); return l


# ──────────── 主弹框 ────────────

class MarkHistoryDialog(QDialog):
    """
    历史标记查看 & 修改状态弹框。

    参数：
        image_name    — 扫描件文件名（展示用）
        marks         — TaskMark 对象列表
        task_info     — 当前任务对象（可选）
        current_user  — 当前用户 dict（可选）
        on_mark_changed — 标记状态变化后的回调，用于刷新外部 UI（可选）

    返回值：
        exec() == Accepted → 用户点「继续新增标记」
        exec() == Rejected → 用户点「关闭」
    """

    def __init__(
        self,
        parent=None,
        image_name:      str              = "",
        marks:           List             = None,
        task_info        = None,
        current_user:    dict             = None,
        on_mark_changed: Optional[Callable] = None,
    ):
        super().__init__(parent)
        self._image_name      = image_name
        self._marks           = list(marks or [])
        self._task_info       = task_info
        self._current_user    = current_user or {}
        self._on_mark_changed = on_mark_changed
        self._cards: dict[int, _MarkCard] = {}   # mark_id → card widget

        # 质检员才可操作
        role = self._current_user.get("role", "")
        self._can_edit = (role in ["管理员", "质检员"])

        self.setWindowTitle("标记管理")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._init_ui()

    # ──────────── UI 构建 ────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_scroll())
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background:#1565c0;")
        header.setFixedHeight(64)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0); lay.setSpacing(10)

        ico = IconWidget(FluentIcon.TAG); ico.setFixedSize(20, 20)
        lay.addWidget(ico)

        title = StrongBodyLabel(f"标记管理  —  {self._image_name}")
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        title.setStyleSheet("color:white;background:transparent;")
        lay.addWidget(title)
        lay.addStretch()

        total   = len(self._marks)
        pending = sum(1 for m in self._marks if not m.is_fixed)
        self._count_lbl = QLabel(f"共 {total} 条  |  待修改 {pending} 条")
        self._count_lbl.setStyleSheet(
            "font-size:12px;color:#bbdefb;font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._count_lbl)
        return header

    def _build_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:#f5f7fa;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background:#f5f7fa;")
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(20, 16, 20, 16)
        self._inner_lay.setSpacing(12)

        self._render_cards()
        self._inner_lay.addStretch()
        scroll.setWidget(self._inner)
        return scroll

    def _render_cards(self):
        """清空并重新渲染所有卡片"""
        # 清空已有卡片
        while self._inner_lay.count() > 0:
            item = self._inner_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        if not self._marks:
            empty = BodyLabel("暂无标记记录")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#bbb;font-size:14px;")
            self._inner_lay.addWidget(empty)
            return

        for i, mark in enumerate(self._marks, start=1):
            card = _MarkCard(mark, i, readonly=not self._can_edit)
            card.fix_clicked.connect(self._on_fix_clicked)
            card.reopen_clicked.connect(self._on_reopen_clicked)
            self._inner_lay.addWidget(card)
            self._cards[mark.id] = card

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background:white;border-top:1px solid #e0e0e0;")
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(20, 0, 20, 0); lay.setSpacing(12)
        lay.addStretch()

        close_btn = PushButton("关闭")
        close_btn.setFixedSize(90, 36)
        close_btn.clicked.connect(self.reject)
        lay.addWidget(close_btn)

        if self._can_edit and self._task_info:
            add_btn = PrimaryPushButton("继续新增标记")
            add_btn.setFixedSize(130, 36)
            add_btn.setStyleSheet("""
                PrimaryPushButton { background:#e53935; color:white;
                    border-radius:8px; font-size:13px; }
                PrimaryPushButton:hover { background:#c62828; }
            """)
            add_btn.clicked.connect(self.accept)
            lay.addWidget(add_btn)

        return footer

    # ──────────── 操作处理 ────────────

    def _on_fix_clicked(self, mark_id: int):
        """点击「标记已修改」"""
        card = self._cards.get(mark_id)
        remark = ""
        if card and hasattr(card, "_pending_remark"):
            remark = card._pending_remark

        try:
            from src.services.task_mark_service import task_mark_service
            task_mark_service.mark_fixed(mark_id, {
                "fix_remark": remark or f"质检员手动确认（{self._current_user.get('username','')}）",
                "fix_date":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            # 刷新本地数据并重渲染
            self._reload_marks()
            if self._on_mark_changed:
                self._on_mark_changed()
        except Exception as e:
            from qfluentwidgets import MessageBox as MB
            MB("操作失败", f"标记已修改失败：{e}", self).exec()

    def _on_reopen_clicked(self, mark_id: int):
        """点击「撤销已修改」"""
        w = MessageBox("确认撤销", "确定要撤销该条标记的「已修改」状态吗？", self)
        w.yesButton.setText("确认撤销"); w.cancelButton.setText("取消")
        if not w.exec():
            return
        try:
            from src.services.task_mark_service import task_mark_service
            task_mark_service.reopen_mark(mark_id, reason="质检员手动撤销")
            self._reload_marks()
            if self._on_mark_changed:
                self._on_mark_changed()
        except Exception as e:
            from qfluentwidgets import MessageBox as MB
            MB("操作失败", f"撤销失败：{e}", self).exec()

    def _reload_marks(self):
        """重新从数据库加载标记并刷新卡片列表和标题统计"""
        if not self._task_info:
            return
        try:
            from src.service.task_mark_service import task_mark_service
            self._marks = task_mark_service.get_mark_info({
                "task_id":   self._task_info.id,
                "scan_file": self._image_name,
            })
        except Exception:
            pass
        self._render_cards()
        self._inner_lay.addStretch()

        # 更新标题统计
        total   = len(self._marks)
        pending = sum(1 for m in self._marks if not m.is_fixed)
        self._count_lbl.setText(f"共 {total} 条  |  待修改 {pending} 条")
