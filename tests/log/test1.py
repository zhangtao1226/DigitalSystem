# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test1.py
# @Time     : 2026/4/15 16:53
# @Desc     : 

from src.utils.LoggerDetector import logger



if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Logger Detector")

    for i in range(10):
        logger.info(f"测试日志条目 # {i + 1} : 这是一个模拟日志消息")
        logger.debug(f"调试消息 # {i + 1}")
        logger.warning(f"警告消息 # {i + 1}")

    logger.info("=" * 50)
