# AGENTS.md

## 项目概览

本项目是“智能 OCR 档案数字化加工管理系统”，主应用为 Python 桌面端，使用 PySide6、qfluentwidgets、qframelesswindow 构建界面，并带有可选 FastAPI 服务端能力。

默认项目路径：

```text
/Volumes/Projects/projects/ERREN/DigitalSystem
```

当前主要能力包括：

- 用户登录与角色权限控制。
- 档案领卷登记、拆卷/前处理、扫描、图像处理、分件、成品转换/输出、装订、目录录入/校对、任务分发、系统管理、统计。
- SQLite 内置数据库存储，SQLAlchemy ORM 访问。
- PaddleOCR 本地 OCR 模型识别。
- TWAIN 扫描仪连接与扫描。
- 图片上传/下载 API 服务。
- 启动前 License 授权校验。
- Windows 上使用 Nuitka 目录模式打包。

## 启动入口

主入口文件：

```text
main.py
```

启动流程：

1. 识别运行目录：源码运行时为项目根目录，Nuitka exe 运行时为 exe 所在目录。
2. 切换当前工作目录到运行目录。
3. 将运行目录和 `src` 加入 `sys.path`。
4. 从运行目录加载 `.env`。
5. 创建 `QApplication`。
6. 执行 License 授权检查。
7. 如果 `SERVICER_VERSION=TRUE`，启动内置 FastAPI 服务。
8. 显示登录窗口 `src/view/login.py::LoginWindow`。
9. 登录成功后进入 `src/view/new_main_window.py::MainWindow`。

授权检查在登录窗口和 API 服务之前执行，避免未授权时进入业务界面或提前启动后台服务。

## 配置文件

根目录 `.env` 是运行期配置文件，包含数据库、服务模式、服务地址、保存目录等配置。该文件已被 `.gitignore` 忽略，不要提交真实配置或密钥。

已发现的 `.env` 变量名：

```text
SINGLE_VERSION
SERVICER_VERSION
SERVICER_SAVE_PATH
SCAN_FILE_BACK_PATH
SERVER_HOST
SERVER_PORT
LOCAL_DB_PATH
```

注意：

- 不要把 `.env` 打进单文件 exe。
- Nuitka 打包后的 `.env` 应放在 exe 同目录，便于现场修改数据库等配置。
- 多个模块会再次调用 `load_dotenv()`，但 `main.py` 已在最早期加载运行目录 `.env`。

## 目录结构

```text
main.py                       应用启动入口，包含 License 注册弹框
build_windows_exe.py          Windows Nuitka 目录模式打包脚本
BUILD_AND_LICENSE.md          授权与打包说明
requirements.txt              Python 依赖
license_core/                 License 机器码生成与授权验证
src/api/                      FastAPI 应用和路由
src/controllers/              客户端请求服务端 API 的控制器
src/core/                     配置、数据库、缓存、模板与扫描配置
src/models/                   SQLAlchemy ORM 模型
src/services/                 数据访问和业务服务层
src/utils/                    OCR、扫描、图像处理、日志、PDF、分件等工具
src/view/                     PySide6 界面
src/resources/                图片、OCR 模型、静态资源、临时目录、输出目录
tests/                        手工测试和实验脚本
download_images/              服务端图片下载到本地的目录
scan_file_back/               扫描图像备份目录
upload_images/                上传或服务端保存图片目录
```

## 核心配置与路径

核心配置在：

```text
src/core/settings.py
```

重要路径：

- `settings.image_path`：`src/resources/images`
- `settings.temp_path`：`src/resources/temp/images`
- `settings.ocr_path`：`src/resources/ocr_model`
- `settings.archives_template_path`：`src/core/档案模版.xlsx`
- `settings.scan_config_path`：`src/core/scan_config.json`
- `settings.server_save_path`：根目录 `upload_images`
- `settings.local_save_path`：根目录 `download_images`
- `settings.scan_back_path`：根目录 `scan_file_back`
- `settings.static_image_path`：`src/resources/static/images`

日志配置也在 `settings.log_info`，默认写入：

```text
src/logs/app.log
```

## 数据库

数据库连接在：

```text
src/core/db.py
```

使用：

- SQLAlchemy
- SQLite
- `SessionLocal`
- `Base = declarative_base()`

数据库环境变量：

```text
LOCAL_DB_PATH
```

`LOCAL_DB_PATH` 为空时默认使用项目根目录 `database/digitalSystem.db`。服务层通常通过 `src.core.db.SessionLocal` 直接创建会话，按 CRUD 方式操作模型。

## ORM 模型

主要模型在 `src/models/`：

- `User`：用户表 `users`，包含用户名、密码哈希、启用状态、登录时间、角色关系。
- `Role`：角色表 `roles`，包含角色名称、描述、启用状态、用户和工作流权限关系。
- `Workflow`：工作流/权限项表 `workflows`。
- `Register`：领卷登记表 `register`。
- `RegisterQuestion`：登记问题表 `register_question`。
- `Task`：任务表 `task`。
- `TaskProgress`：任务进度表 `task_progress`。
- `TaskMark`：质检/问题标记表 `task_mark`。
- `Scan`：扫描记录表 `scan`。
- `ScanImages`：扫描图片表 `scan_images`。
- `Operation`：操作记录表 `operation`。
- `DirectorModel`：目录数据表 `director`。
- `DefineTemplate`：自定义模板表 `define_template`。
- `ArchiveStamp`：归档章模板表 `archive_stamp`。
- `SubmitRecord`：提交记录表 `submit_record`。

关联表：

- `association.py`：用户与角色关联。
- `role_permission_association.py`：角色与工作流权限关联。

## 服务层

服务层在 `src/services/`，每个服务通常对应一个模型：

- `user_service.py`：用户创建、查询、登录时间、角色关联。
- `role_service.py`：角色 CRUD 和角色用户关系。
- `workflow_service.py`：工作流/权限项读取和保存。
- `register_service.py`：领卷登记 CRUD 和批量创建。
- `registerQuestion_service.py`：登记问题 CRUD。
- `task_service.py`：任务创建、查询、提交、节点流转、进度判断。
- `task_progress_service.py`：任务分段进度记录。
- `task_mark_service.py`：质检标记、修复、重开、统计。
- `scan_service.py`：扫描记录保存和查询。
- `scan_images_service.py`：扫描图片同步、查询、更新。
- `operation_service.py`：操作记录保存、统计。
- `director_service.py`：目录数据批量导入、查询、更新。
- `archive_stamp_service.py`：归档章模板管理。

## UI 结构

UI 在 `src/view/`，基于 PySide6 + qfluentwidgets + qframelesswindow。

主流程：

- `src/view/login.py::LoginWindow`：登录页。
- `src/view/new_main_window.py::MainWindow`：登录后的主导航页。

主导航页按用户角色权限展示或禁用功能卡片：

- 领卷登记：`src/view/register/registerTable_window.py`
- 拆卷/前处理：`src/view/pretreatment/pretreatmentTable_window.py`
- 扫描：`src/view/scan/scanTable_window.py`、`src/view/scan/scan_window.py`
- 图像处理：`src/view/image_process/imageProcessTable_window.py`、`src/view/image_process/image_window.py`
- 分件：`src/view/bulk_breaking/bulkTable_window.py`、`src/view/bulk_breaking/bulk_window.py`
- 成品转换/输出：`src/view/product_output/productTable_window.py`、`src/view/product_output/productOutput_window.py`
- 装订：`src/view/binding/bindingTable_window.py`
- 目录录入/校对：`src/view/dir_recognition/dirTable_window.py`、`src/view/dir_recognition/dir_window.py`
- 任务分发：`src/view/task_window/taskTable_window.py`
- 统计：`src/view/statistics/statistics_table.py`
- 系统管理：`src/view/system/system_main.py`

系统管理页包括：

- 用户管理
- 角色管理
- 档案门类管理
- 工作流配置
- 模板定义
- OCR 数据集
- 归档章模板
- 目录导入
- 标记管理
- 关于页

## API 服务

API 在 `src/api/`：

- `src/api/app.py`：创建 FastAPI 应用。
- `src/api/api_server.py`：在独立线程中启动/停止 Uvicorn 服务。
- `src/api/routers/health.py`：健康检查。
- `src/api/routers/upload.py`：图片上传、批量上传、预览/下载、删除。
- `src/api/routers/ocr.py`：OCR 路由存在，但当前在 `app.py` 中被注释，没有挂载。

API 启动条件：

```text
SERVICER_VERSION=TRUE
```

默认端口在 `main.py` 中为 `8000`。

客户端调用服务端的控制器在：

```text
src/controllers/common_controller.py
```

它依赖：

```text
SERVER_HOST
SERVER_PORT
```

## OCR、扫描与图像处理

OCR：

- `src/utils/OCRDetector.py` 使用 PaddleOCR。
- OCR 模型位于 `src/resources/ocr_model/`。
- 当前配置主要使用 `PP-OCRv5_mobile_det` 和 `PP-OCRv5_mobile_rec`。

扫描：

- `src/utils/NewScannerDetector.py` 使用 TWAIN。
- `ScanParams` 定义扫描模式、DPI、色彩模式、输出格式、保存目录、旋转、纠偏、黑边处理等。
- `src/view/scan/scan_window.py` 是扫描 UI 主窗口。

图像处理：

- `src/utils/ImageProcessor.py`
- `src/utils/DocumentBorderCleaner.py`
- `src/utils/DocumentContentDeskew.py`
- `src/utils/BlankPageDetector.py`

分件与归档章：

- `src/utils/PartsDetector.py` 支持目录分件和归档章分件。
- `src/utils/StampTableCheck.py` 负责归档章/表格检测。
- `src/view/bulk_breaking/` 为分件相关 UI。

成品输出：

- `src/utils/DualLayerPDFGenerator.py` 用于生成双层 PDF。
- `src/view/product_output/productOutput_window.py` 包含 OCR worker 和双层 PDF worker。

## License 授权

授权代码在：

```text
license_core/
```

关键文件：

- `license_core/machine.py`：生成机器码。
- `license_core/verify.py`：验证 `License.json`。
- `license_core/public_key.py`：客户端内置公钥。

授权流程：

1. `main.py` 启动时调用 `ensure_registered()`。
2. `verify_license_file()` 检查默认授权文件。
3. 授权有效则继续启动。
4. 授权缺失、过期、签名无效、版本不匹配、机器码不匹配时弹出注册窗口。
5. 注册窗口显示当前机器码，可复制机器码并导入 `License.json`。
6. 导入成功后保存授权文件，下次启动不再弹窗。

默认授权保存位置：

- Windows：`%APPDATA%\DIGITALSYSTEM-ERREN\license.json`
- 非 Windows 或无 `APPDATA`：当前运行目录下 `DIGITALSYSTEM-ERREN/license.json`

注意：

- 根目录 `DIGITALSYSTEM-ERREN/` 已被 `.gitignore` 忽略。
- 当前 Mac 环境生成的是测试机器码；正式授权应在目标 Windows 机器上生成机器码。
- `cryptography` 是签名验证依赖，打包/运行前必须安装。

## Windows 打包

打包脚本：

```text
build_windows_exe.py
```

打包方式：

- 使用 Nuitka。
- 使用 `--standalone` 目录模式。
- 不使用单文件 exe。

原因：

- `.env` 是数据库等运行期配置，必须作为外部文件保留。
- OCR 模型、静态图片、模板、扫描配置、上传/下载/备份目录都需要作为发布目录的一部分。

Windows 打包命令：

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python build_windows_exe.py
```

发布时整体复制 Nuitka 生成的 `.dist` 目录，不要只复制 exe。

发布目录至少应包含：

```text
DigitalSystem.exe
.env
src\resources\
src\core\scan_config.json
src\core\档案模版.xlsx
download_images\
scan_file_back\
upload_images\
```

当前 Mac 环境不能交叉编译 Windows exe。

## 依赖特征

依赖文件：

```text
requirements.txt
```

主要依赖类型：

- GUI：`PySide6`、`PySide6-Fluent-Widgets`、`PySideSix-Frameless-Window`
- API：`fastapi`、`uvicorn`、`python-multipart` 相关依赖
- 数据库：`SQLAlchemy`、Python 标准库 `sqlite3`
- OCR/图像：`paddleocr`、`paddlepaddle`、`opencv-contrib-python`、`Pillow`、`reportlab`、`pypdfium2`
- 数据处理：`pandas`、`openpyxl`、`numpy`
- 扫描：`pytwain`
- 授权：`cryptography`
- 打包：`nuitka`

当前本机 `python3 --version` 为 `Python 3.9.6`。代码中已有部分位置使用较新的类型注解风格，新增代码应尽量兼容 Python 3.9，避免 `str | Path`、`list[str]` 这类会在 3.9 运行时报错的注解。

## 测试与验证

`tests/` 下更多是手工测试和实验脚本，不是完整 pytest 测试套件。

已发现测试目录：

- `tests/db/`：数据库连接/模型测试。
- `tests/log/`：日志测试。
- `tests/ocr_test/`：OCR、归档章、表格检测实验脚本和图片样本。
- `tests/scanner/`：扫描仪相关实验脚本。
- `tests/upload_file/`：上传测试。

常用轻量检查：

```bash
python3 -c "import ast, pathlib; files=['main.py','build_windows_exe.py','license_core/verify.py']; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), filename=p) for p in files]; print('syntax ok')"
python3 license_core/machine.py
python3 license_core/verify.py
python3 build_windows_exe.py
```

注意：本机若未安装 `PySide6`、`cryptography`、PaddleOCR 等依赖，不能完整启动 GUI 或验证授权签名。

## 已知注意事项

- 不要提交 `.env`、本地授权文件、日志、临时图片、输出目录、Nuitka 构建产物。
- `.env` 当前被忽略，但项目根目录存在真实配置文件；阅读时只记录变量名，不暴露值。
- `src/api/routers/upload.py` 中有路径处理细节需要小心，修改前建议实测上传、下载、删除三个接口。
- `src/api/routers/ocr.py` 当前没有在 FastAPI 应用中启用；需要 OCR API 时先检查 `src/api/app.py` 的路由挂载。
- 扫描相关代码依赖 Windows/TWAIN 设备，Mac 环境通常只能做语法和静态检查。
- OCR 模型和图像资源体积较大，打包时必须确认 `src/resources` 被包含。
- `src/logs/`、`src/resources/temp/`、`src/resources/output/` 是运行产物目录。
- 现有服务层普遍直接管理数据库会话，改动时注意 commit/rollback/close。
- UI 窗口普遍使用全屏切换和 `QTimer.singleShot(100, self.close)` 关闭旧窗口，改导航时要确认窗口生命周期。

## 修改代码时的建议

- 先从 `main.py`、`src/core/settings.py`、相关 `service` 和对应 `view` 入手理解链路。
- 数据库字段变更要同步模型、服务层、UI 表格字段和可能的导入/导出逻辑。
- 新增资源文件时同步检查 Nuitka 打包脚本是否需要纳入发布目录。
- 涉及 `.env` 的改动只新增变量名和读取逻辑，不写死真实配置。
- 涉及授权逻辑时优先保持 `license_core` 独立，不让业务模块依赖授权内部实现。
- 涉及 Windows 打包、扫描仪或 OCR 模型时，最终应在 Windows 目标环境验证。
