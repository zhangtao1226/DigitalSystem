# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : archive_stamp_template_page.py
# @Time     : 2026/5/11 10:29
# @Desc     : 系统管理-归档章模板自定义

import os
import json
from datetime import datetime

from PySide6.QtGui import (
    QFont, QColor, QPainter, QPen, QFontMetrics,
)
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QHeaderView,
    QTableWidgetItem, QAbstractItemView, QFrame, QDialog,
    QGridLayout, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QSize

from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox, PushButton, PrimaryPushButton,
    FluentIcon, InfoBar, InfoBarPosition, IconWidget, CardWidget, BodyLabel,
    TableWidget, LineEdit, ComboBox, SwitchButton, CaptionLabel, SpinBox,
    SubtitleLabel, TitleLabel, TransparentPushButton,
)

from src.utils.LoggerDetector import logger
from src.core.cache_manager import global_cache
from src.services.archive_stamp_service import archive_stamp_service
from src.utils.NotificationTool import show_info, show_warning, show_error, show_success

from src.view.common.Common import FIELDS_6, FIELDS_8
from src.view.common.StampPreviewWidget import StampPreviewWidget
from src.view.common.StampPreviewDialog import StampPreviewDialog

class ArchiveStampDialog(QDialog):
    saved = Signal(dict)
    FIELDS = FIELDS_6

    def __init__(self, parent=None, template_data: dict = None):
        super().__init__(parent)
        self.template_data = template_data or {}
        self.is_edit = bool(template_data)
        self._field_widgets: dict[str, tuple[LineEdit, LineEdit]] = {}
        self._editing_id = template_data.id if template_data else None

        self.setWindowTitle("修改归档章模版" if self.is_edit else "新建归档章模版")
        # self.setMinimumSize(860, 680)
        self.resize(1200, 780)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._init_ui()
        if self.template_data:
            self._load_data()

        self.current_user = None
        self._update_preview()

    # ── 构建界面 ──
    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(16, 16, 16, 16)

        # ── 左侧表单区 ──────────────────────────────────
        form_card = CardWidget()
        form_vbox = QVBoxLayout(form_card)
        form_vbox.setSpacing(14)
        form_vbox.setContentsMargins(22, 18, 22, 18)

        # 表单标题
        form_title = StrongBodyLabel("模版信息")
        form_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        form_title.setStyleSheet("color: #2c3e50;")
        form_vbox.addWidget(form_title)

        sep0 = self._make_sep()
        form_vbox.addWidget(sep0)

        # 基础信息区
        basic_grid = QGridLayout()
        basic_grid.setHorizontalSpacing(20)
        basic_grid.setVerticalSpacing(10)

        # 模版名称
        basic_grid.addWidget(BodyLabel("模版名称 *"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入模版名称，不可重复")
        self.name_edit.setFixedWidth(280)
        basic_grid.addWidget(self.name_edit, 0, 1)

        # 章体方向
        basic_grid.addWidget(BodyLabel("章格式"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        self.layout_combo = ComboBox()
        self.layout_combo.addItems(["6格章", "8格章"])
        self.layout_combo.setFixedWidth(120)
        self.layout_combo.currentIndexChanged.connect(self._update_preview)
        basic_grid.addWidget(self.layout_combo, 0, 3)

        # 显示字段名称
        basic_grid.addWidget(BodyLabel("显示字段名称"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.show_labels_sw = SwitchButton()
        self.show_labels_sw.setChecked(True)
        self.show_labels_sw.checkedChanged.connect(self._on_show_labels_changed)
        basic_grid.addWidget(self.show_labels_sw, 1, 1)

        # 字体大小
        # basic_grid.addWidget(BodyLabel("字体大小 (pt)"), 1, 2, Qt.AlignRight | Qt.AlignVCenter)
        # self.font_spin = SpinBox()
        # self.font_spin.setRange(8, 24)
        # self.font_spin.setValue(12)
        # self.font_spin.setFixedWidth(120)
        # self.font_spin.valueChanged.connect(self._update_preview)
        # basic_grid.addWidget(self.font_spin, 1, 3)

        # 边框颜色
        # basic_grid.addWidget(BodyLabel("边框颜色"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        # self.color_combo = ComboBox()
        # self.color_combo.addItems(list(self.BORDER_COLORS.keys()))
        # self.color_combo.setFixedWidth(160)
        # self.color_combo.currentIndexChanged.connect(self._update_preview)
        # basic_grid.addWidget(self.color_combo, 2, 1)

        form_vbox.addLayout(basic_grid)

        sep1 = self._make_sep()
        form_vbox.addWidget(sep1)

        # 字段配置区标题 + 说明
        field_title_row = QHBoxLayout()
        field_section = StrongBodyLabel("字段配置")
        field_section.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        field_section.setStyleSheet("color: #2c3e50;")
        field_title_row.addWidget(field_section)
        field_title_row.addStretch()
        hint_lbl = CaptionLabel("字段名称为章上印的标签文字；默认值为章的初始内容（可留空）")
        hint_lbl.setStyleSheet("color: #999; font-size: 12px;")
        field_title_row.addWidget(hint_lbl)
        form_vbox.addLayout(field_title_row)

        # 字段表头
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 2)

        def _hdr_lbl(text, stretch=0, width=None):
            l = BodyLabel(text)
            l.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
            if width:
                l.setFixedWidth(width)
            return l

        hdr.addWidget(_hdr_lbl("字段", width=72))
        hdr.addWidget(_hdr_lbl("字段名称（标签）"), 1)
        hdr.addSpacing(8)
        hdr.addWidget(_hdr_lbl("默认值"), 1)
        form_vbox.addLayout(hdr)

        sep2 = self._make_sep()
        form_vbox.addWidget(sep2)

        for key, chinese, default_lbl in self.FIELDS:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)

            row_lbl = BodyLabel(chinese)
            row_lbl.setFixedWidth(72)
            row_lbl.setStyleSheet("font-weight: 500;")
            row_layout.addWidget(row_lbl)

            label_edit = LineEdit()
            label_edit.setPlaceholderText(f"如：{default_lbl}")
            label_edit.setText(default_lbl)
            label_edit.textChanged.connect(self._update_preview)
            row_layout.addWidget(label_edit, 1)

            row_layout.addSpacing(8)

            value_edit = LineEdit()
            value_edit.setPlaceholderText("默认值（可留空）")
            value_edit.textChanged.connect(self._update_preview)
            row_layout.addWidget(value_edit, 1)

            self._field_widgets[key] = (label_edit, value_edit)
            form_vbox.addLayout(row_layout)

        form_vbox.addStretch()

        sep3 = self._make_sep()
        form_vbox.addWidget(sep3)

        # 底部按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = PushButton("取消")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = PrimaryPushButton(FluentIcon.SAVE, f'{"保存模版" if self._editing_id is None else "修改模版" }')
        self.save_btn.setFixedSize(130, 36)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)

        form_vbox.addLayout(btn_row)

        preview_card = CardWidget()
        preview_card.setFixedWidth(720)
        preview_vbox = QVBoxLayout(preview_card)
        preview_vbox.setContentsMargins(18, 16, 18, 16)
        preview_vbox.setSpacing(10)

        prev_title = StrongBodyLabel("实时预览")
        prev_title.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        prev_title.setStyleSheet("color: #2c3e50;")
        preview_vbox.addWidget(prev_title, alignment=Qt.AlignHCenter)

        sep4 = self._make_sep()
        preview_vbox.addWidget(sep4)

        self.preview_widget = StampPreviewWidget()
        self.preview_widget.setMinimumSize(720, 160)
        preview_vbox.addWidget(self.preview_widget)

        preview_vbox.addStretch()

        root.addWidget(form_card, 1)
        root.addWidget(preview_card)

    @staticmethod
    def _make_sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet("color: #ececec; margin: 2px 0;")
        return f

    def _on_show_labels_changed(self, checked: bool):
        for key, _, _ in self.FIELDS:
            lbl_edit, _ = self._field_widgets[key]
            lbl_edit.setEnabled(checked)
            lbl_edit.setStyleSheet("" if checked else "background: #f5f5f5; color: #aaa;")
        self._update_preview()

    def _load_data(self):
        d = self.template_data
        self.name_edit.setText(d.template_name)

        self.layout_combo.setCurrentIndex(
            0 if d.template_format == '6格章' else 1
        )
        self.show_labels_sw.setChecked(bool(d.show_field_labels))

        for key, value in json.loads(d.fields_json).items():
            if "_label" in key:
                lbl_e, _ = self._field_widgets[key.replace('_label', '')]
                lbl_e.setText(value)
            if "_value" in key:
                _, val_e = self._field_widgets[key.replace('_value', '')]
                val_e.setText(value)

    def _get_form_data(self) -> dict:
        data = {
            'template_name':    self.name_edit.text().strip(),
            'template_format':   self.layout_combo.currentIndex(),
            'show_field_labels': 1 if self.show_labels_sw.isChecked() else 0,
            'create_time':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'update_time':      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        if self.layout_combo.currentIndex() == 0:
            self.FIELDS = FIELDS_6
        else:
            self.FIELDS = FIELDS_8

        fields_list = dict()
        self._field_widgets.clear()

        for key, _, default_lbl in self.FIELDS:
            if key not in self._field_widgets.keys():
                label_edit = LineEdit()
                label_edit.setPlaceholderText(f"如：{default_lbl}")
                label_edit.setText(default_lbl)
                label_edit.textChanged.connect(self._update_preview)

                value_edit = LineEdit()
                value_edit.setPlaceholderText("默认值（可留空）")
                value_edit.textChanged.connect(self._update_preview)

                self._field_widgets[key] = (label_edit, value_edit)

            lbl_e, val_e = self._field_widgets[key]
            fields_list[f'{key}_label'] = lbl_e.text().strip()
            fields_list[f'{key}_value'] = val_e.text().strip()

        data['fields_json'] = json.dumps(fields_list, ensure_ascii=False, indent=4)
        print(11111, data)
        return data

    def _update_preview(self):
        self.preview_widget.set_template(self._get_form_data())

    def _save(self):
        data = self._get_form_data()

        if not data['template_name']:
            show_warning(self, "提示", "请填写模版名称")
            return

        # 重名校验
        if self._editing_id is None:
            name_is_exist = archive_stamp_service.check_name_exists(data['template_name'])
            if name_is_exist:
                show_warning(self, "提示", f'模版名称「{data["template_name"]}」已存在，请更换')
                return

        self.saved.emit(data)

        self.accept()

class ActionCellWidget(QWidget):
    editClicked    = Signal(int)
    previewClicked = Signal(int)
    deleteClicked  = Signal(int)

    def __init__(self, row_id: int, parent=None):
        super().__init__(parent)
        self.row_id = row_id

        hl = QHBoxLayout(self)
        hl.setContentsMargins(6, 3, 6, 3)
        hl.setSpacing(6)

        edit_btn = PushButton(FluentIcon.EDIT, "修改")
        edit_btn.setFixedHeight(30)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self.editClicked.emit(self.row_id))

        prev_btn = PushButton(FluentIcon.VIEW, "预览")
        prev_btn.setFixedHeight(30)
        prev_btn.setCursor(Qt.PointingHandCursor)
        prev_btn.clicked.connect(lambda: self.previewClicked.emit(self.row_id))

        del_btn = PushButton(FluentIcon.DELETE, "删除")
        del_btn.setFixedHeight(30)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda: self.deleteClicked.emit(self.row_id))

        hl.addWidget(edit_btn)
        hl.addWidget(prev_btn)
        hl.addWidget(del_btn)
        hl.addStretch()

class ArchiveStampTemplatePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        setTheme(Theme.AUTO)
        self._init_ui()
        self._load_templates()

        self.current_user = global_cache.get("current_user", None)

    # ── 构建页面 ──
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # ── 标题栏 ──────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        icon_widget = IconWidget(FluentIcon.FIT_PAGE)
        icon_widget.setFixedSize(28, 28)
        title_row.addWidget(icon_widget)

        page_title = StrongBodyLabel("归档章模版管理")
        page_title.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        page_title.setStyleSheet("color: #2c3e50;")
        title_row.addWidget(page_title)
        title_row.addStretch()

        tip_lbl = BodyLabel("提示：模版保存后可在归档操作中直接套用")
        tip_lbl.setStyleSheet("""
            color: #7f8c8d;
            font-size: 14px;
            padding: 5px 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        """)
        title_row.addWidget(tip_lbl)

        layout.addLayout(title_row)

        # ── 主卡片 ──────────────────────────────────────
        main_card = CardWidget()
        main_card.setMinimumHeight(520)
        card_vbox = QVBoxLayout(main_card)
        card_vbox.setSpacing(14)
        card_vbox.setContentsMargins(25, 20, 25, 20)

        # 操作栏
        action_bar = QHBoxLayout()

        self.create_btn = PrimaryPushButton(FluentIcon.ADD, "新建模版")
        self.create_btn.setFixedHeight(38)
        self.create_btn.setCursor(Qt.PointingHandCursor)
        self.create_btn.clicked.connect(self._open_create_dialog)
        action_bar.addWidget(self.create_btn)

        action_bar.addStretch()

        refresh_btn = PushButton(FluentIcon.SYNC, "刷新")
        refresh_btn.setFixedHeight(38)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_templates)
        action_bar.addWidget(refresh_btn)

        card_vbox.addLayout(action_bar)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #efefef;")
        card_vbox.addWidget(sep)

        # 模版列表表格
        self.table = TableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "模版名称", "章规格", "显示字段名", "创建时间", "更新时间", "创建者", "操作"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(True)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # ID
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)            # 名称
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # 章规格
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # 显示字段
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)   # 创建时间
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)   # 创建时间
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)   # 创建时间
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)               # 操作
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(7, 300)

        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e8e8e8;
                border-radius: 8px;
                gridline-color: #f2f2f2;
                font-family: "Microsoft YaHei";
                font-size: 13px;
                background-color: white;
                outline: none;
            }
            QTableWidget::item {
                padding: 4px 10px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #e8f4fd;
                color: #1a73e8;
            }
            QTableWidget::item:alternate {
                background-color: #fafafa;
            }
            QHeaderView::section {
                background-color: #f5f6fa;
                padding: 9px 10px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                font-weight: 700;
                color: #555;
                font-family: "Microsoft YaHei";
                font-size: 13px;
            }
        """)

        card_vbox.addWidget(self.table)

        # 状态栏
        self.status_lbl = CaptionLabel("共 0 条模版")
        self.status_lbl.setStyleSheet("color: #ccc; padding: 4px 0;")
        card_vbox.addWidget(self.status_lbl)

        layout.addWidget(main_card)

    # ── 加载数据 ──
    def _load_templates(self):
        templates = archive_stamp_service.get_all()
        self.table.setRowCount(0)

        for tmpl in templates:
            row = self.table.rowCount()
            self.table.insertRow(row)

            def _center_item(text: str) -> QTableWidgetItem:
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(Qt.AlignCenter)
                return it

            self.table.setItem(row, 0, _center_item(str(tmpl.id)))
            self.table.setItem(row, 1, _center_item(tmpl.template_name))
            self.table.setItem(row, 2, _center_item(
                "6格章" if tmpl.template_format == 0 else "8格章"
            ))
            self.table.setItem(row, 3, _center_item(
                "是" if tmpl.show_field_labels == 1 else "否"
            ))
            self.table.setItem(row, 4, _center_item(tmpl.create_time))
            self.table.setItem(row, 5, _center_item(tmpl.update_time))
            self.table.setItem(row, 6, _center_item(tmpl.operator))

            action = ActionCellWidget(tmpl.id)
            action.editClicked.connect(self._open_edit_dialog)
            action.previewClicked.connect(self._open_preview_dialog)
            action.deleteClicked.connect(self._delete_template)
            self.table.setCellWidget(row, 7, action)
            self.table.setRowHeight(row, 50)

        self.status_lbl.setText(f"共 {len(templates)} 条模版")

    # ── 新建 ──
    def _open_create_dialog(self):
        dlg = ArchiveStampDialog(self)
        dlg.saved.connect(self._on_template_created)
        dlg.exec()

    def _on_template_created(self, data: dict):
        data['operator'] = self.current_user['username']

        try:
            result = archive_stamp_service.create(data)
            self._load_templates()
            if result:
                show_success(self, "创建成功", f'模版「{data["template_name"]}」已创建')
                logger.info(f'模版「{data["template_name"]}」创建成功')
            else:
                show_error(self, '报错', f"创建归档章模版失败;")
                return
        except Exception as e:
            logger.error(f"创建归档章模版失败; {str(e)}")
            show_error(self, '报错', f"创建归档章模版失败;")

    # ── 编辑 ──
    def _open_edit_dialog(self, template_id: int):
        data = archive_stamp_service.get_by_id(template_id)
        if not data:
            return
        dlg = ArchiveStampDialog(self, template_data=data)
        dlg.saved.connect(lambda d: self._on_template_updated(template_id, d))
        dlg.exec()

    def _on_template_updated(self, template_id: int, data: dict):
        archive_stamp_service.update(template_id, data)
        self._load_templates()
        InfoBar.success(
            title='修改成功',
            content=f'模版「{data["template_name"]}」已更新',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self
        )

    # ── 预览 ──
    def _open_preview_dialog(self, template_id: int):
        data = archive_stamp_service.get_by_id(template_id)
        if not data:
            return
        dlg = StampPreviewDialog(data, self)
        dlg.exec()

    # ── 删除 ──
    def _delete_template(self, template_id: int):
        data = archive_stamp_service.get_by_id(template_id)
        name = data.template_name

        w = MessageBox(
            "确认删除",
            f"确定要删除模版「{name}」吗？\n\n此操作不可恢复，已使用该模版的历史记录不受影响。",
            self
        )
        w.yesButton.setText("确认删除")
        w.cancelButton.setText("取消")

        if w.exec():
            result = archive_stamp_service.delete(template_id)
            self._load_templates()
            if result:
                show_success(self, "删除成功", f'模版「{name}」已删除')
                return

if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    win = ArchiveStampTemplatePage()
    win.setWindowTitle("归档章模版管理")
    win.resize(1160, 740)
    win.show()

    sys.exit(app.exec())