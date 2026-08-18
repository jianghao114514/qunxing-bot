import os
import sys
import threading
# 将工作目录切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config, CONFIG
from core.ws_client import Bot


def main():
    load_config()
    # --no-ui：面板内重启/停止时由 web 服务拉起的后台进程，不弹任何窗口
    no_ui = "--no-ui" in sys.argv or os.environ.get("QUNXING_NO_UI") == "1"
    if no_ui or not CONFIG.get("web_desktop_enabled", True):
        # 纯控制台模式：和以前一样
        Bot().run()
        return
    try:
        from web.desktop import run_desktop
    except Exception as e:
        print("pywebview 不可用（{}），使用网页版面板".format(e))
        Bot().run()
        return

    bot = Bot()
    threading.Thread(target=bot.run, daemon=True).start()
    print("已启动桌面管理面板（关闭窗口时可选退出机器人）")
    try:
        run_desktop()
    except Exception as e:
        print("桌面面板异常：{}（机器人仍在运行，可用网页版 http://127.0.0.1:{}/）".format(e, CONFIG.get("web_port", 5000)))
    # 窗口已关闭：机器人继续后台运行，Ctrl+C 可退出
    print("机器人保持后台运行。控制台 Ctrl+C 可退出。")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        os._exit(0)


if __name__ == "__main__":
    main()