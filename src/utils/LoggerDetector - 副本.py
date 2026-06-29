# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : LoggerDetector.py
# @Desc      : 
# @Time      : 2025/8/15 16:42
# @Software  : PyCharm

import os
import re
import glob
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from logging.handlers import TimedRotatingFileHandler

from src.core.settings import settings


class LoggerDetector(TimedRotatingFileHandler):
    def __init__(self, filename, when='D', interval=1, backupCount=7, maxBytes=10, encoding=None, delay=False, utc=False):
        TimedRotatingFileHandler.__init__(
            self, filename, when=when, interval=interval,
            backupCount=backupCount, encoding=encoding,
            delay=delay, utc=utc
        )
        self.maxBytes = maxBytes   * 1024 * 1024
        self.current_file_size = os.path.getsize(self.baseFilename) if os.path.exists(self.baseFilename) else 0

    def shouldRollover(self, record):
        if self.current_file_size + len(record.getMessage().encode(self.encoding)) > self.maxBytes:
            return 1

        return TimedRotatingFileHandler.shouldRollover(self, record)

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        current_time = datetime.now()
        time_based_name = self.baseFilename + "." + current_time.strftime(self.suffix)
        pattern = f"{time_based_name}.*"
        existing_files = glob.glob(pattern)
        max_index = 0

        for fname in existing_files:
            match = re.search(rf"{re.escape(time_based_name)}\.(\d+)", fname)
            if match:
                index = int(match.group(1))
                if index > max_index:
                    max_index = index

        new_name = f"{time_based_name}.{max_index + 1}"
        os.rename(self.baseFilename, new_name)
        self._clean_old_logs()
        if not self.delay:
            self.stream = self._open()

        self.current_file_size = 0

    def emit(self, record):
        TimedRotatingFileHandler.emit(self, record)
        if self.stream and hasattr(self.stream, 'tell'):
            self.current_file_size = self.stream.tell()

    def _clean_old_logs(self):
        cutoff_time = time.time() - (7 * 86400)
        log_dir = os.path.dirname(self.baseFilename)
        log_files = glob.glob(os.path.join(log_dir, f"{os.path.basename(self.baseFilename)}.*"))
        for log_file in log_files:
            try:
                file_time = os.path.getmtime(log_file)
                if file_time < cutoff_time:
                    os.remove(log_file)
                    print(f"Deleted old log: {log_file}")
            except Exception as e:
                print(f"Error deleting {log_file}: {str(e)}")

def setup_logger(log_dir="logs", log_name="app", max_log_size=10, retention_days=7):
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{log_name}.log")
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = LoggerDetector(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        maxBytes=max_log_size,
        encoding="utf-8"
    )
    handler.setFormatter(formatter)
    handler.suffix = "%Y-%m-%d"  # 日志后缀格式
    logger.addHandler(handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

logger = setup_logger(
    log_dir=settings.log_info["log_dir"],
    log_name=settings.log_info["log_name"],
    retention_days=settings.log_info["log_retention"],
    max_log_size=settings.log_info["log_size"])
