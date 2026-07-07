# DigitalSystem 授权与 Windows exe 打包说明

## 集成位置

授权检查已接入根目录 `main.py`：

1. `main()` 创建 `QApplication` 后调用 `ensure_registered()`。
2. `ensure_registered()` 调用 `verify_license_file()` 检查默认授权文件。
3. 授权有效时直接继续启动 API 服务和登录窗口。
4. 授权文件不存在、机器码不匹配、签名无效、版本不匹配或已过期时，弹出注册窗口。
5. 用户导入有效的 `License.json` 后，程序保存授权文件，下次启动不再弹窗。

授权放在登录窗口和 API 服务之前，是为了让未授权状态不能进入业务界面，也不会提前启动后台服务。

## .env 配置文件

项目根目录的 `.env` 是运行期配置文件，包含数据库等配置，不适合打包成单个 exe 内部资源。

现在 `main.py` 会在启动最早期从运行目录读取：

```text
.env
```

源码运行时读取项目根目录的 `.env`。Nuitka 打包后读取 exe 同目录的 `.env`。这样发布后可以直接修改 `.env`，不需要重新打包。

## 授权文件保存位置

Windows exe 运行后默认保存到：

```text
%APPDATA%\DIGITALSYSTEM-ERREN\license.json
```

macOS 或没有 `APPDATA` 的环境会保存到当前运行目录下：

```text
DIGITALSYSTEM-ERREN/license.json
```

使用 `%APPDATA%` 的原因是 Windows 安装目录可能没有写权限，而用户数据目录适合保存授权状态。

## 注册窗口功能

注册窗口包含：

1. 当前机器码展示。
2. 复制机器码。
3. 导入 `License.json`。
4. 导入后立即验证签名、产品名、版本、签发时间、过期时间、机器码。

验证成功后窗口关闭并进入程序。授权过期后，下次启动会再次弹出注册窗口。

## Mac 与 Windows 机器码

当前开发环境是 macOS，Windows 的 `wmic` 和 PowerShell 硬件命令不可用。因此在 Mac 上只能生成用于流程测试的机器码。

正式给客户签发授权时，应在目标 Windows 电脑上运行 exe，或运行：

```bash
python license_core/machine.py
```

然后使用 Windows 上显示的机器码生成授权文件。

如果机器码生成遇到异常，程序会返回清晰的占位值，避免注册窗口崩溃；但正式授权仍应以 Windows 目标机器生成的机器码为准。

## Nuitka 目录模式打包

本项目使用 Nuitka 的 `standalone` 目录模式，不使用单文件 exe。原因是 `.env`、OCR 资源、模板、图片、上传目录等都需要作为外部文件或目录存在。

在 Windows 上进入项目根目录后执行：

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python build_windows_exe.py
```

生成目录类似：

```text
dist_nuitka\main.dist\
```

发布时请整体复制 `.dist` 文件夹。不要只复制 `DigitalSystem.exe`。

发布目录中至少包含：

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

注意：Nuitka 也不能在 macOS 上交叉编译 Windows exe，所以当前 Mac 环境只能准备代码和打包脚本，实际 exe 需要在 Windows 上生成。
