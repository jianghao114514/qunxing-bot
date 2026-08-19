# core/napcat_deploy.py
# NapCat 自动化部署：检测、下载（GitHub + 镜像源切换 + 进度回调）、解压、写配置。
import io
import json
import os
import shutil
import socket
import time
import urllib.request
import zipfile

# 最新版查询接口与镜像源
_RELEASE_API = "https://api.github.com/repos/NapNeko/NapCatQQ/releases/latest"
_MIRRORS = [
    "https://ghfast.top/",      # 第一个为直连占位，实际直连由调用方先尝试
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://mirror.ghproxy.com/",
]
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


def get_latest_release():
    """查询 NapCat 最新版信息，返回 {tag, assets:[{name,url,size}]}；失败返回 None"""
    try:
        req = urllib.request.Request(_RELEASE_API, headers=_UA)
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        assets = [{"name": a["name"], "url": a["browser_download_url"], "size": a["size"]}
                  for a in d.get("assets", [])]
        return {"tag": d.get("tag_name", ""), "assets": assets}
    except Exception:
        return None


def pick_shell_asset(release):
    """挑选适合免安装部署的发行包：优先 Node 版（自带运行环境），退回 OneKey 版"""
    assets = release.get("assets", []) if release else []
    for want in ("NapCat.Shell.Windows.Node.zip", "NapCat.Shell.Windows.OneKey.zip"):
        for a in assets:
            if a["name"] == want:
                return a
    return None


def _download_url_mirrors(direct_url):
    """生成候选下载地址列表：直连 + 镜像（镜像拼接 GitHub 原始地址）"""
    raw = direct_url
    if raw.startswith("https://github.com/"):
        raw = "https://github.com/" + raw[len("https://github.com/"):]
    urls = [direct_url]
    for m in _MIRRORS:
        urls.append(m + direct_url)
    return urls


def download_with_progress(urls, dest, progress_cb=None, timeout=600):
    """依次尝试候选地址下载到 dest。progress_cb(percent, speed_mb, msg) 实时回调。
    全部失败抛异常。返回 (最终使用的URL, 下载耗时秒)"""
    last_err = None
    for url in urls:
        tmp = dest + ".part"
        try:
            req = urllib.request.Request(url, headers=_UA)
            resp = urllib.request.urlopen(req, timeout=30)
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            start = time.time()
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total and progress_cb:
                        speed = (done / 1048576) / max(time.time() - start, 0.001)
                        progress_cb(min(done / total * 100, 100), speed,
                                    "下载中 {} / {} MB".format(done // 1048576, total // 1048576))
            os.replace(tmp, dest)
            if progress_cb:
                progress_cb(100, 0, "下载完成")
            return url, time.time() - start
        except Exception as e:
            last_err = e
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    raise last_err or RuntimeError("下载失败")


def extract_zip(zip_path, target_dir, progress_cb=None):
    """解压 zip 到 target_dir。progress_cb(percent, msg)。返回解压出的根目录名（若顶层是单目录）"""
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        total = len(names)
        for i, name in enumerate(names):
            z.extract(name, target_dir)
            if progress_cb and (i % 200 == 0 or i == total - 1):
                progress_cb((i + 1) / total * 100, "解压中 {}/{} 个文件".format(i + 1, total))
    # 顶层若只有一个目录则视为包裹层
    entries = [n for n in names if "/" not in n.rstrip("/")]
    if len(entries) == 1 and not entries[0].endswith("/") and not entries[0].lower().endswith((".bat", ".exe", ".json", ".dll", ".js")):
        return entries[0]
    return ""


def locate_config_root(install_dir):
    """在新版安装目录中找到 napcat 配置根（含 config/ 子目录），找不到返回 None"""
    for base in ("napcat", ""):
        cfg = os.path.join(install_dir, base, "config")
        if os.path.isdir(cfg):
            return cfg
    return None


def _free_port(prefer):
    """找可用端口：优先 prefer，被占用则 +1 递增探测"""
    for port in range(prefer, prefer + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 3001


def write_napcat_config(install_dir, ws_port, webui_port, token, bot_qq):
    """写部署配置：webui.json（token/端口/自动登录号）+ onebot11_<qq>.json（ws 服务器）。
    返回 {config_root, ws_url, webui_url}"""
    cfg_root = locate_config_root(install_dir)
    if not cfg_root:
        raise RuntimeError("未找到 napcat 配置目录")
    os.makedirs(cfg_root, exist_ok=True)

    webui_path = os.path.join(cfg_root, "webui.json")
    webui = {"host": "::", "port": webui_port, "token": token,
             "loginRate": 10, "autoLoginAccount": str(bot_qq),
             "disableWebUI": False, "accessControlMode": "none",
             "ipWhitelist": [], "ipBlacklist": [], "enableXForwardedFor": False}
    with open(webui_path, "w", encoding="utf-8") as f:
        json.dump(webui, f, ensure_ascii=False, indent=4)

    onebot_path = os.path.join(cfg_root, "onebot11_{}.json".format(bot_qq))
    onebot = {
        "network": {
            "httpServers": [],
            "httpSseServers": [],
            "httpClients": [],
            "websocketServers": [{
                "enable": True, "name": "群星",
                "host": "127.0.0.1", "port": ws_port,
                "reportSelfMessage": True, "enableForcePushEvent": True,
                "messagePostFormat": "array", "token": token,
                "debug": False, "heartInterval": 30000
            }],
            "websocketClients": [],
            "plugins": []
        },
        "musicSignUrl": "", "enableLocalFile2Url": False, "parseMultMsg": False,
        "imageDownloadProxy": "", "timeout": {
            "baseTimeout": 10000, "uploadSpeedKBps": 256,
            "downloadSpeedKBps": 256, "maxTimeout": 1800000
        }
    }
    with open(onebot_path, "w", encoding="utf-8") as f:
        json.dump(onebot, f, ensure_ascii=False, indent=2)

    return {
        "config_root": cfg_root,
        "ws_url": "ws://127.0.0.1:{}/?token={}".format(ws_port, token),
        "webui_url": "http://127.0.0.1:{}/webui?token={}".format(webui_port, token),
        "webui_port": webui_port,
        "ws_port": ws_port,
    }


def find_bootmain(install_dir):
    """在安装目录中找 NapCatWinBootMain.exe（v4 在 napcat/ 子目录）"""
    for base in ("napcat", ""):
        p = os.path.join(install_dir, base, "NapCatWinBootMain.exe")
        if os.path.isfile(p):
            return p
    return None