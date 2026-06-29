# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : settings.py
# @Desc      : 
# @Time      : 2025/11/21 14:35
# @Software  : PyCharm

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


current_file_path = Path(__file__).resolve()
root_path = current_file_path.parent.parent
root_image_path = current_file_path.parent.parent.parent

class Settings(BaseSettings):

    # 档案类别
    archive_type_list:list = ['文书档案', '会计档案', '照片档案', '录像档案', '实物档案', '科技档案']

    # 档案类型
    archive_unit_list:list = ['卷', '件']

    # 图片路径
    image_path: str = f"{root_path}/resources/images"

    #临时图片路径
    temp_path:str = f"{root_path}/resources/temp/images"

    # OCR模型路径
    ocr_path:str = f"{root_path}/resources/ocr_model"

    # OCR 测试图片路径
    ocr_test_image:str = f"{root_path}/resources/images/ocr_test.png"

    # 日志文件配置信息
    log_info: dict = {
        "log_name": "app",
        "log_level": "INFO",
        "log_dir": f"{root_path}/logs",
        "log_size": 50,
        "log_retention": 7,
    }

    # 档案模型, 档案目录信息
    archives_template_path:str = f"{root_path}/core/档案模版.xlsx"

    static_image_path:str = f"{root_path}/resources/static/images/"

    # 扫描配置
    scan_config_path:str = f"{root_path}/core/scan_config.json"

    # 任务编号映射
    work_number:dict = {
        "拆卷/前处理": 1,
        "扫 描": 2,
        "图像处理": 3,
        "分 件": 4,
        "成品转换/输出": 5,
        "目录录入/校对": 6,
        "装 订": 7,
    }

    # 模板保存路径
    define_template_path:str = f"{root_path}/resources/template/"

    # 部署服务器时， 保存扫描件路径地址
    server_save_path:str = f"{root_image_path}/upload_images"

    # 服务器图片下载到本地保存路径
    local_save_path:str = f"{root_image_path}/download_images"

    # 扫描图像备份目录(根目录下 scan_file_back)
    scan_back_path:str = f"{root_image_path}/scan_file_back"

    max_file_size: int = 1024 * 1024 * 20

    # 分件选项
    parts_selects:list = ["目录", "归档章"]

    # 单文件夹存放扫描图片最大值
    folder_max_files: int = 20000

    class Config:
        case_sensitive = True


settings = Settings()