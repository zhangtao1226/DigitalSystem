# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : api_server.py
# @Time     : 2026/5/8 10:46
# @Desc     : 
import threading

import uvicorn

from src.api.app import create_app
from src.utils.LoggerDetector import logger

class APIServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None


    def start(self):
        server_app = create_app()

        config = uvicorn.Config(
            server_app,
            host=self.host,
            port=self.port,
            log_level="info",
            loop="asyncio"
        )

        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            target=self._server.run,
            name="API-Server",
            daemon=True
        )
        self._thread.start()
        logger.info(f"服务已启动: http:// {self.host}:{self.port}")

    def stop(self):
        if self._server:
            self._server.should_exit = True
            logger.info("正在关闭服务·····")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            logger.info("服务已关闭")
