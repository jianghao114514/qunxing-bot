# core/version.py
# 版本号以年月日命名（如 26.8.19），集中从项目根 VERSION 文件读取
import os

_VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
_CACHE = None


def app_version():
    """返回当前版本号字符串；读取失败时返回 'dev'"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_VERSION_FILE, "r", encoding="utf-8") as f:
            _CACHE = f.read().strip() or "dev"
    except Exception:
        _CACHE = "dev"
    return _CACHE
