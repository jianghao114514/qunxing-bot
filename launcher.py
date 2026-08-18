# launcher.py
# 群星启动器：自动检测 Python 环境、自动下载并安装 Python、安装依赖、启动机器人、异常自动重启
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

# 版本号：程序文件版本标记，升级后自动重新释放
VERSION = '1.1'

# 无 Python 时自动下载的候选版本（按顺序尝试）
PY_DOWNLOADS = [
    ('3.12.10', 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'),
    ('3.12.7', 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe'),
    ('3.11.9', 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'),
]


def _get_web_port():
    """从 config.json 读取面板端口（读不到按默认 5000）"""
    try:
        with open(os.path.join(ROOT, 'bot_data', 'config.json'), 'r', encoding='utf-8') as f:
            port = int(json.load(f).get('web_port', 5000))
    except Exception:
        port = 5000
    return port


def get_console_url():
    """拼出控制台地址"""
    return 'http://127.0.0.1:{}/'.format(_get_web_port())


def _browser_open_allowed():
    """是否自动开浏览器：桌面窗口占用了面板则不开；否则看用户开关（默认开）"""
    try:
        with open(os.path.join(ROOT, 'bot_data', 'config.json'), 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if cfg.get('web_desktop_enabled', True):
            return False
        return cfg.get('web_auto_open_browser', True)
    except Exception:
        return True


def _open_browser(url):
    """用系统默认浏览器打开：浏览器没开则拉起，已开着则在其新标签页打开"""
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except Exception:
        return False


def _monitor_console(browser_open):
    """机器人启动后轮询网页：就绪即显示控制台地址，开关开着则自动打开浏览器"""
    url = get_console_url()
    deadline = time.time() + 30
    ready = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            ready = True
            break
        except Exception:
            time.sleep(0.6)
    if ready:
        print('控制台已就绪：' + url)
        if browser_open:
            if _open_browser(url):
                print('已用默认浏览器打开控制台（浏览器已开着则在新标签页打开）；如未弹出，可复制上方地址手动访问')
            else:
                print('自动打开浏览器失败，请复制上方地址手动访问')
        else:
            print('未自动打开浏览器（如需自动打开，请在面板「配置修改 → 基础设置」开启开关）')

if getattr(sys, 'frozen', False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))


def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    except Exception:
        return None


def download_file(url, dest):
    """下载文件并实时打印进度条（百分比 / 已下载 / 总大小 / 速度）"""
    bar_w = 30
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        start = time.time()
        with open(dest, 'wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                pct = (done / total * 100) if total else 0
                n = int(pct / 100 * bar_w)
                bar = '#' * n + '-' * (bar_w - n)
                mb = done / 1048576
                speed = mb / max(time.time() - start, 0.001)
                sys.stdout.write(
                    '\r  下载中 [{0}] {1:5.1f}%  {2:.1f}/{3:.1f} MB  {4:.1f} MB/s'
                    .format(bar, pct, mb, total / 1048576, speed))
                sys.stdout.flush()
    sys.stdout.write('\n')
    sys.stdout.flush()


def extract_bundled():
    """单文件模式首次运行：把内嵌的程序文件释放到 exe 旁边。
    已存在且版本一致则跳过（不覆盖用户文件）；绝不触碰 bot_data。"""
    if not getattr(sys, 'frozen', False):
        return
    meipass = getattr(sys, '_MEIPASS', '')
    if not meipass:
        return
    marker = os.path.join(ROOT, '.qunxing_version')
    if os.path.exists(os.path.join(ROOT, 'main.py')):
        try:
            with open(marker, 'r', encoding='utf-8') as f:
                if f.read().strip() == VERSION:
                    return
        except Exception:
            pass
    print('首次运行：正在释放程序文件...')
    for name in ('main.py', 'requirements.txt'):
        shutil.copy2(os.path.join(meipass, name), os.path.join(ROOT, name))
    for d in ('core', 'plugins', 'web'):
        src = os.path.join(meipass, d)
        dst = os.path.join(ROOT, d)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            p = os.path.join(src, f)
            if os.path.isfile(p) and not f.endswith('.pyc'):
                shutil.copy2(p, os.path.join(dst, f))
    with open(marker, 'w', encoding='utf-8') as f:
        f.write(VERSION)
    print('程序文件已就绪')


def start_watchdog(py):
    """NapCat 掉线守护：按配置启用时，用 bot 同一 Python 启动后台守护进程"""
    try:
        with open(os.path.join(ROOT, 'bot_data', 'config.json'), 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    if not cfg.get('napcat_watchdog_enabled', True):
        return
    wd = os.path.join(ROOT, 'watchdog.py')
    if not os.path.exists(wd):
        print('未找到 watchdog.py，跳过 NapCat 守护')
        return
    print('启动 NapCat 掉线守护（自动重启被踢下线的 QQ）...')
    try:
        subprocess.Popen(py + ['watchdog.py'], cwd=ROOT)
    except Exception as e:
        print('NapCat 守护启动失败：' + str(e))


def ensure_downloaded_python():
    """无 Python 环境时：自动下载官方安装包并静默安装到项目目录（免管理员）。
    返回可用的 ['python.exe路径'] 启动命令；全部失败返回 None"""
    runtime = os.path.join(ROOT, 'python_runtime')
    os.makedirs(runtime, exist_ok=True)
    py_exe = os.path.join(runtime, 'python.exe')
    if os.path.exists(py_exe):
        r = _run([py_exe, '-c', 'pass'])
        if r is not None and r.returncode == 0:
            return [py_exe]
    for ver, url in PY_DOWNLOADS:
        print('未检测到 Python 环境，正在下载 Python ' + ver + '（约 26MB）...')
        dest = os.path.join(runtime, 'python-setup-' + ver + '.exe')
        try:
            download_file(url, dest)
        except Exception as e:
            print('Python ' + ver + ' 下载失败：' + str(e) + '，尝试其他版本...')
            continue
        print('下载完成，正在静默安装到 ' + runtime + '（约 1~2 分钟，无需管理员权限，请稍候）...')
        try:
            subprocess.run([dest, '/quiet',
                            'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0',
                            'Include_test=0', 'Include_doc=0', 'Include_pip=1',
                            'Shortcuts=0', 'TargetDir=' + runtime],
                           timeout=600)
        except Exception as e:
            print('安装失败：' + str(e) + '，尝试其他版本...')
            continue
        finally:
            try:
                os.remove(dest)
            except Exception:
                pass
        if os.path.exists(py_exe):
            ver_r = _run([py_exe, '-c', 'import platform; print(platform.python_version())'])
            print('Python 安装成功：' + (ver_r.stdout.strip() if ver_r and ver_r.returncode == 0 else ver))
            return [py_exe]
        print('Python ' + ver + ' 安装未生效，尝试其他版本...')
    return None


def find_python():
    """按优先级找可用 Python：py 启动器指定版本 → py -3 → python"""
    for ver in ['3.13', '3.12', '3.11', '3.10', '3.9']:
        r = _run(['py', '-' + ver, '-c', 'pass'])
        if r is not None and r.returncode == 0:
            return ['py', '-' + ver]
    r = _run(['py', '-3', '-c', 'pass'])
    if r is not None and r.returncode == 0:
        return ['py', '-3']
    r = _run(['python', '-c', 'pass'])
    if r is not None and r.returncode == 0:
        return ['python']
    return None


def check_deps(py):
    code = "import websocket, flask, flask_socketio, psutil, PIL, openai, requests; print('ok')"
    r = _run(py + ['-c', code])
    return r is not None and r.returncode == 0


def install_deps(py):
    req = os.path.join(ROOT, 'requirements.txt')
    if not os.path.exists(req):
        print('缺少 requirements.txt，无法安装依赖')
        return False
    print('正在自动安装依赖（首次运行需要几分钟，请稍候）...')
    r = subprocess.run(py + ['-m', 'pip', 'install', '-r', req])
    return r.returncode == 0


def main():
    try:
        os.system('chcp 65001 >nul')
    except Exception:
        pass
    print('==============================================')
    print('           群星启动器')
    print('==============================================')

    extract_bundled()

    py = find_python()
    if py is None:
        print('未检测到 Python 环境，正在自动下载并安装（首次约需几分钟，仅此一次）...')
        py = ensure_downloaded_python()
        if py is None:
            print('自动下载安装 Python 失败。')
            print('请到 https://www.python.org/downloads/ 安装 Python 3.9+（安装时勾选 Add to PATH）后重试')
            input('按回车退出...')
            sys.exit(1)

    ver = _run(py + ['-c', 'import platform; print(platform.python_version())'])
    version = ver.stdout.strip() if ver and ver.returncode == 0 else '未知'
    print('检测到 Python ' + version)

    if not check_deps(py):
        if not install_deps(py):
            print('依赖安装失败，请检查网络后重新运行启动器')
            input('按回车退出...')
            sys.exit(1)
        print('依赖安装完成')

    start_watchdog(py)

    os.chdir(ROOT)
    while True:
        print('启动机器人...（Ctrl+C 可停止）')
        print('控制台地址：' + get_console_url() + '（机器人启动完成后自动打开浏览器）')
        threading.Thread(target=_monitor_console, args=(_browser_open_allowed(),), daemon=True).start()
        r = subprocess.run(py + ['main.py'])
        if r.returncode == 0:
            print('机器人已正常退出')
            break
        try:
            again = input('机器人异常退出（代码 ' + str(r.returncode) + '）。按 r 回车重新启动，按 q 回车退出：')
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if again.strip().lower() == 'q':
            break
    sys.exit(0)


if __name__ == '__main__':
    main()
