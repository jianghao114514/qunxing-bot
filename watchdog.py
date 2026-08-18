# watchdog.py — NapCat 掉线守护：检测登录失效自动杀 QQ 并用快捷登录重启
import datetime
import json
import os
import subprocess
import sys
import time

try:
    import psutil
    import websocket
except ImportError:
    print("[守护] 缺少依赖（websocket-client / psutil），请先通过启动器运行一次")
    sys.exit(1)

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(ROOT, "bot_data", "config.json")
LOG_FILE = os.path.join(ROOT, "bot_data", "napcat_watchdog.log")

DEFAULTS = {
    "napcat_watchdog_enabled": True,
    "napcat_exe": "",
    "napcat_qq": "",
    "napcat_check_interval": 15,
    "napcat_restart_cooldown": 150,
}


def log(msg):
    line = "[{}] {}".format(datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    cfg = {k: data.get(k, v) for k, v in DEFAULTS.items()}
    cfg["ws_url"] = data.get("ws_url", "ws://127.0.0.1:3004")
    cfg["bot_qq"] = data.get("bot_qq", "")
    if not cfg["napcat_qq"]:
        cfg["napcat_qq"] = cfg["bot_qq"]
    return cfg


def find_napcat_exe(cfg):
    cands = [cfg.get("napcat_exe") or "",
             r"D:\napcat\bootmain\NapCatWinBootMain.exe",
             r"C:\napcat\bootmain\NapCatWinBootMain.exe"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    try:
        from core.napcat_finder import scan_napcat_exe
        return scan_napcat_exe()
    except Exception:
        return None


def probe_login(cfg):
    """连 NapCat WebSocket 调 get_login_info，成功返回 True，失败/无响应返回 False"""
    try:
        ws = websocket.create_connection(cfg["ws_url"], timeout=5)
        try:
            ws.send(json.dumps({"action": "get_login_info", "echo": "watchdog"}))
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    msg = ws.recv()
                except Exception:
                    break
                if not msg:
                    continue
                try:
                    r = json.loads(msg)
                except Exception:
                    continue
                if r.get("echo") != "watchdog":
                    continue
                return r.get("retcode") == 0 and int(r.get("data", {}).get("user_id") or 0) > 0
        finally:
            ws.close()
    except Exception:
        return False
    return False


def qq_processes():
    """列出 NapCat 的 QQ 进程：只认带 --enable-logging 参数（NapCat 注入标志）的
    QQ.exe 和 NapCatWinBootMain.exe，绝不误杀普通个人 QQ"""
    found = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = p.info.get("name") or ""
            if name == "NapCatWinBootMain.exe":
                found.append(p)
                continue
            if name == "QQ.exe" and "--enable-logging" in " ".join(p.cmdline()):
                found.append(p)
        except Exception:
            pass
    return found


def restart_napcat(cfg, exe):
    # 启动器已在运行说明上次重启还没结束，跳过避免重复拉起
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if p.info.get("name") == "NapCatWinBootMain.exe":
                log("NapCat 启动器已在运行，等待其登录完成...")
                return True
        except Exception:
            pass
    log("登录失效，正在重启 NapCat（杀 QQ → 快捷登录 " + str(cfg["napcat_qq"]) + "）...")
    for p in qq_processes():
        try:
            p.kill()
        except Exception:
            pass
    time.sleep(2)
    if not exe:
        log("[警告] 未找到 NapCatWinBootMain.exe，请在 config.json 设置 napcat_exe 后重试")
        return False
    try:
        # 不新建控制台窗口：日志并入当前窗口，避免反复弹窗
        subprocess.Popen([exe, str(cfg["napcat_qq"])], cwd=os.path.dirname(exe))
        log("NapCat 已重新启动，等待登录恢复（宽限期 " + str(cfg["napcat_restart_cooldown"]) + " 秒内不再重启）...")
        return True
    except Exception as e:
        log("[失败] 启动 NapCat 出错：" + str(e))
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cfg = load_cfg()
    if "--once" in sys.argv:
        ok = probe_login(cfg)
        print("登录状态: " + ("在线 OK" if ok else "离线/无响应"))
        print("QQ 进程数: " + str(len(qq_processes())))
        print("NapCat 启动器: " + str(find_napcat_exe(cfg)))
        return
    if "--restart" in sys.argv:
        restart_napcat(cfg, find_napcat_exe(cfg))
        return
    if not cfg.get("napcat_watchdog_enabled", True):
        print("[守护] 已关闭（napcat_watchdog_enabled=false），退出")
        return
    exe = find_napcat_exe(cfg)
    if not exe:
        log("[警告] 未找到 NapCatWinBootMain.exe（默认 D:\\napcat\\bootmain\\），守护运行中但无法自动重启")
    log("NapCat 守护启动，每 {} 秒检查一次（QQ {}）".format(cfg["napcat_check_interval"], cfg["napcat_qq"]))
    fails = 0
    last_restart = 0
    last_ok_log = 0
    last_wait_log = 0
    while True:
        ok = probe_login(cfg)
        now = time.time()
        if ok:
            fails = 0
            if now - last_ok_log > 300:
                log("NapCat 在线，一切正常")
                last_ok_log = now
        elif now - last_restart < cfg["napcat_restart_cooldown"]:
            # 重启后的宽限期：等待登录恢复，期间不计失败、不重复重启
            fails = 0
            if now - last_wait_log > 30:
                log("等待 NapCat 登录恢复中（宽限期内不重启）...")
                last_wait_log = now
        else:
            fails += 1
            if fails >= 3:
                fails = 0
                last_restart = now
                restart_napcat(cfg, exe)
        time.sleep(max(int(cfg["napcat_check_interval"]), 5))


if __name__ == "__main__":
    main()