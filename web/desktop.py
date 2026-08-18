# web/desktop.py
# 桌面端面板：用 pywebview 把现有 Flask 面板包成原生窗口。
# 只在主线程调用；窗口关闭后返回。未装 pywebview / WebView2 不可用时安全降级（调用方决定）。
import os
import threading
import time
import urllib.request


def _apply_gpu_settings():
    """弱核显/虚拟显示器上关闭 WebView2 GPU 加速，软件渲染更稳"""
    from core.config import CONFIG
    if CONFIG.get("web_desktop_disable_gpu", False):
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu"


def _wait_server_ready(port, timeout=10):
    """轮询等 Web 服务起来，避免窗口打开时还是空白页"""
    url = "http://127.0.0.1:{}/".format(port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def _ask_quit():
    """窗口关闭后弹原生对话框：是=退出机器人（先落盘数据），否=保持后台运行"""
    try:
        import ctypes
        r = ctypes.windll.user32.MessageBoxW(
            None,
            "面板窗口已关闭。\n是否同时退出机器人？\n\n选「否」则机器人保持后台运行（日志仍写入控制台）。",
            "提示", 4)  # MB_YESNO
        if r == 6:  # IDYES
            try:
                from core.database import flush_all
                flush_all()
            except Exception:
                pass
            os._exit(0)
    except Exception:
        pass


def _on_window_closed():
    threading.Thread(target=_ask_quit, daemon=True).start()


def run_desktop():
    """打开桌面管理面板（阻塞直到窗口关闭）。返回 True 表示正常显示过窗口。"""
    from core.config import CONFIG

    system_name = CONFIG.get("system_name", "群星")
    port = int(CONFIG.get("web_port", 5000))

    if not _wait_server_ready(port):
        print("Web 服务未就绪，桌面面板跳过（可用 http://127.0.0.1:{}/ ）".format(port))
        return False

    _apply_gpu_settings()
    import webview  # 延迟导入：未安装时由调用方兜底

    width = int(CONFIG.get("web_window_width", 1320))
    height = int(CONFIG.get("web_window_height", 880))

    window = webview.create_window(
        "{} 管理面板".format(system_name),
        "http://127.0.0.1:{}/".format(port),
        width=width,
        height=height,
        min_size=(1000, 680),
        text_select=True,
        confirm_close=True,
    )
    window.events.closed += _on_window_closed
    webview.start()
    return True
