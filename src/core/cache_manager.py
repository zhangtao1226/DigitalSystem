# -*-coding  : utf-8 -*-
# @Author    : zhangtao
# @File      : cache_manager.py
# @Desc      : 
# @Time      : 2025/11/22 10:11
# @Software  : PyCharm

from cachetools import TTLCache
from typing import Any, Optional


class CacheManager:
    _instance = None
    _cache = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._cache = TTLCache(maxsize=1000, ttl=3600)
        return cls._instance

    def set(self, key: str, value: Any):
        self._cache[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        self._cache.clear()

global_cache = CacheManager()
