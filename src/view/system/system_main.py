# -*-coding: utf-8 -*-
# @Author    : zhangtao
# @File      : scan_system.py
# @Desc      : 系统管理主窗口
# @Time      : 2025/12/05
# @Software  : PyCharm
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget,QStackedWidget
    )
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import (
    setTheme, Theme, StrongBodyLabel, MessageBox,
    FluentIcon, NavigationInterface, ToolButton, setThemeColor, NavigationItemPosition,
)
from qframelesswindow import FramelessWindow, StandardTitleBar

from src.core.cache_manager import global_cache
from src.view.system.home_page import HomePage
from src.view.system.about_page import AboutPage
from src.view.system.role_manage_page import RoleManagePage
from src.view.system.user_manage_page import UserManagePage
from src.view.system.ocr_datasets_page import OcrDatasetsPage
from src.view.system.define_template_page import DefineTemplatePage
from src.view.system.workflow_config_page import WorkflowConfiguration
from src.view.system.archival_mange_page import ArchiveCategoryPage
from src.view.system.import_directory_page import ImportDirectoryPage
from src.view.system.mark_manage_page import MarkManagePage
from src.view.system.archive_stamp_template_page import ArchiveStampTemplatePage


# 主窗口
class SystemMainWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数字化加工系统 - 系统管理")
        # self.resize(1200, 800)
        # self.center()
        self.init_ui()

    def center(self):
        """窗口居中"""
        screen = QApplication.primaryScreen().availableGeometry()
        screen_center = screen.center()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen_center)
        self.move(window_size.topLeft())

    def init_ui(self):
        main_container = QWidget()
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.navigation_interface = NavigationInterface(self, showMenuButton=True, showReturnButton=False)
        self.navigation_interface.setExpandWidth(240)

        self.navigation_interface.setStyleSheet("""
            NavigationInterface {
                background-color: #ffffff;
                border-right: 1px solid #e8e8e8;
            }
            NavigationTreeWidget {
                background-color: transparent;
                border: none;
                font-size: 14px;
                font-family: 'Microsoft YaHei';
            }
            NavigationTreeWidget::item {
                height: 44px;
                padding-left: 20px;
                border-radius: 6px;
                margin: 2px 8px;
            }
            NavigationTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
            NavigationTreeWidget::item:selected {
                background-color: #e6f7ff;
                color: #1890ff;
            }
            NavigationTreeWidget::item:selected:hover {
                background-color: #d9f0ff;
            }
        """)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("contentWidget")
        self.content_widget.setStyleSheet("""
            QWidget#contentWidget {
                background-color: #f5f5f5;
            }
        """)

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # 顶部栏
        top_bar = self.create_top_bar()
        self.content_layout.addWidget(top_bar)

        # 创建页面堆栈
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("""
            QStackedWidget {
                background-color: #f5f5f5;
                border: none;
            }
        """)

        # 创建各个页面
        # self.home_page = HomePage()
        self.user_manage_page = UserManagePage()
        self.role_manage_page = RoleManagePage()
        self.archival_manage_page = ArchiveCategoryPage()
        self.work_config_page = WorkflowConfiguration()
        self.define_template_page = DefineTemplatePage()
        self.ocr_datasets_page = OcrDatasetsPage()
        self.archive_stamp_page = ArchiveStampTemplatePage()
        self.import_directory_page = ImportDirectoryPage()
        self.mark_manage_page = MarkManagePage()
        self.about_page = AboutPage()

        # 添加页面到堆栈
        # self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.user_manage_page)
        self.stacked_widget.addWidget(self.role_manage_page)
        self.stacked_widget.addWidget(self.archival_manage_page)
        self.stacked_widget.addWidget(self.work_config_page)
        self.stacked_widget.addWidget(self.define_template_page)
        self.stacked_widget.addWidget(self.ocr_datasets_page)
        self.stacked_widget.addWidget(self.archive_stamp_page)
        self.stacked_widget.addWidget(self.import_directory_page)
        self.stacked_widget.addWidget(self.mark_manage_page)

        self.stacked_widget.addWidget(self.about_page)
        self.content_layout.addWidget(self.stacked_widget)

        # 添加导航项
        self.add_navigation_items()

        # 设置主布局
        main_layout.addWidget(self.navigation_interface)
        main_layout.addWidget(self.content_widget, stretch=1)

        self.setLayout(main_layout)

        # 默认显示主页面
        # self.switch_page("home")

    def create_top_bar(self) -> QWidget:
        """创建顶部栏"""
        top_bar = QWidget()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-bottom: 1px solid #e8e8e8;
            }
        """)

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(25, 0, 25, 0)
        top_layout.setSpacing(20)

        # 页面标题
        self.page_title_label = StrongBodyLabel("主页面")
        self.page_title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        self.page_title_label.setStyleSheet("color: #333333;")
        top_layout.addWidget(self.page_title_label)

        top_layout.addStretch()

        # 用户信息区域
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

        # 退出按钮
        exit_btn = ToolButton(FluentIcon.POWER_BUTTON)
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.setFixedSize(40, 40)
        exit_btn.setToolTip("退出系统")
        exit_btn.setStyleSheet("""
            ToolButton {
                background-color: #d94e4ecf;
                border-radius: 8px;
            }
            ToolButton:hover {
                background-color: #fff2f0;
            }
            ToolButton:pressed {
                background-color: #ffccc7;
            }
        """)
        exit_btn.clicked.connect(self.exit_system)
        top_layout.addWidget(exit_btn)

        self.update_user_label()

        return top_bar

    def update_user_label(self):
        """更新右上角用户标签的内容"""
        user_info = global_cache.get("current_user")
        if user_info:
            username = user_info.get("username", "未知用户")
            userrole = user_info.get("role", "未知角色")
            self.user_label = QLabel(f"👤 {username} ({userrole})")
        else:
            self.user_label = QLabel("未登录")
            # 设置默认用户信息以便测试
            global_cache.set("current_user", {"username": "admin", "role": "管理员"})
            self.update_user_label()

    def add_navigation_items(self):
        """添加导航项"""
        # 主页面
        # self.navigation_interface.addItem(
        #     routeKey="home",
        #     icon=FluentIcon.HOME,
        #     text="主页面",
        #     onClick=lambda: self.switch_page("home"),
        #     position=NavigationItemPosition.TOP
        # )

        # 用户管理
        self.navigation_interface.addItem(
            routeKey="user",
            icon=FluentIcon.PEOPLE,
            text="用户管理",
            onClick=lambda: self.switch_page("user"),
            position=NavigationItemPosition.TOP
        )

        # 角色管理
        self.navigation_interface.addItem(
            routeKey="role",
            icon=FluentIcon.CERTIFICATE,
            text="角色管理",
            onClick=lambda: self.switch_page("role"),
            position=NavigationItemPosition.TOP
        )

        # 档案门类管理
        self.navigation_interface.addItem(
            routeKey="archival",
            icon=FluentIcon.FOLDER,
            text="档案门类管理",
            onClick=lambda: self.switch_page("archival"),
            position=NavigationItemPosition.TOP
        )

        # 工作流配置
        self.navigation_interface.addItem(
            routeKey="workConfig",
            icon=FluentIcon.TILES,
            text="工作流配置",
            onClick=lambda: self.switch_page("workConfig"),
            position=NavigationItemPosition.TOP
        )

        self.navigation_interface.addItem(
            routeKey="archiveStamp",
            icon=FluentIcon.FIT_PAGE,
            text="归档章模板",
            onClick=lambda: self.switch_page("archiveStamp"),
            position=NavigationItemPosition.TOP
        )

        self.navigation_interface.addItem(
            routeKey="importDirectory",
            icon=FluentIcon.FOLDER_ADD,
            text="目录导入与管理",
            onClick=lambda: self.switch_page("importDirectory"),
            position=NavigationItemPosition.TOP
        )

        self.navigation_interface.addItem(
            routeKey="markManage",
            icon=FluentIcon.TAG,
            text="标记管理",
            onClick=lambda: self.switch_page("markManage"),
            position=NavigationItemPosition.TOP
        )

        # self.navigation_interface.addItem(
        #     routeKey="defineTemplate",
        #     icon=FluentIcon.DOCUMENT,
        #     text="定义模板",
        #     onClick=lambda: self.switch_page("defineTemplate"),
        #     position=NavigationItemPosition.TOP
        # )
        #
        # self.navigation_interface.addItem(
        #     routeKey="ocr_datasets_page",
        #     icon=FluentIcon.DICTIONARY_ADD,
        #     text="OCR数据集",
        #     onClick=lambda: self.switch_page("defineTemplate"),
        #     position=NavigationItemPosition.TOP
        # )

        # 关于
        # self.navigation_interface.addItem(
        #     routeKey="about",
        #     icon=FluentIcon.INFO,
        #     text="关于系统",
        #     onClick=lambda: self.switch_page("about"),
        #     position=NavigationItemPosition.BOTTOM
        # )

    def switch_page(self, page_name: str):
        """切换页面"""
        page_titles = {
            "home": "主页面",
            "user": "用户管理",
            "role": "角色管理",
            "archival": "档案门类",
            "workConfig": "工作流配置",
            "archiveStamp": "归档章模板",
            "importDirectory": "目录导入与管理",
            "markManage": "质检标记管理",
            "defineTemplate": "定义模板",
            "about": "关于系统"
        }

        page_widgets = {
            # "home": self.home_page,
            "user": self.user_manage_page,
            "role": self.role_manage_page,
            "archival": self.archival_manage_page,
            "workConfig": self.work_config_page,
            "archiveStamp": self.archive_stamp_page,
            "importDirectory": self.import_directory_page,
            "markManage": self.mark_manage_page,
            "defineTemplate": self.define_template_page,
            # "about": self.about_page
        }

        if page_name in page_widgets:
            self.stacked_widget.setCurrentWidget(page_widgets[page_name])
            self.page_title_label.setText(page_titles[page_name])
            self.navigation_interface.setCurrentItem(page_name)

    def exit_system(self):
        """退出系统"""
        # 创建退出确认对话框
        box = MessageBox(
            '确认退出',
            '确定要退出系统管理界面吗？',
            self
        )
        box.yesButton.setText('退出')
        box.cancelButton.setText('取消')

        # 设置按钮样式
        box.yesButton.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
            QPushButton:pressed {
                background-color: #d9363e;
            }
        """)

        box.cancelButton.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333333;
                padding: 8px 20px;
                border-radius: 6px;
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
            self.open_main_window()

    def open_main_window(self):
        from src.view.new_main_window import MainWindow
        main_window = MainWindow()
        main_window.showFullScreen()
        QTimer.singleShot(100, self.close)