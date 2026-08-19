# build.py — 群星启动器 exe 构建脚本（由 build_exe.bat 调用）
# 纯 Python 实现：自动装 PyInstaller、打包、复制产物，任何系统都能稳定跑
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE_NAME = "群星启动器"


def say(msg):
    print(msg)
    sys.stdout.flush()


def run(cmd):
    say(">> " + " ".join(cmd))
    r = subprocess.run(cmd)
    return r.returncode == 0


def wait_key():
    """等待按回车（无交互环境自动跳过，不报错）"""
    try:
        input("按回车退出...")
    except EOFError:
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 46)
    print("  构建群星启动器 exe")
    print("=" * 46)
    py = [sys.executable]

    say("检测到 Python: " + sys.version.split()[0])
    r = subprocess.run(py + ["-m", "pip", "show", "pyinstaller"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        say("未安装 PyInstaller，正在联网安装（仅首次需要）...")
        if not run(py + ["-m", "pip", "install", "--disable-pip-version-check", "pyinstaller"]):
            say("[失败] PyInstaller 安装失败，请检查网络后重新运行")
            wait_key()
            sys.exit(1)
        say("PyInstaller 安装完成")

    say("开始打包（约 1~2 分钟）...")
    # 程序文件内嵌进 exe：首次运行自动释放到旁边目录，实现单文件分发
    datas = []
    for f in ("main.py", "requirements.txt"):
        datas += ["--add-data", f + ";" + "."]
    for d in ("core", "plugins", "web"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            p = os.path.join(d, f)
            if os.path.isfile(os.path.join(ROOT, p)) and f.endswith((".py", ".html")):
                datas += ["--add-data", p + ";" + d]
    icon_path = os.path.join(ROOT, "web", "favicon.ico")
    icon_args = ["--icon", icon_path] if os.path.isfile(icon_path) else []
    if not run(py + ["-m", "PyInstaller", "--onefile", "--console",
                     "--name", EXE_NAME, "--noconfirm"] + icon_args + datas + ["launcher.py"]):
        say("[失败] 打包失败，请把上方错误信息截图反馈")
        wait_key()
        sys.exit(1)

    src = os.path.join(ROOT, "dist", EXE_NAME + ".exe")
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(ROOT, EXE_NAME + ".exe"))
        say("构建完成：" + os.path.join(ROOT, EXE_NAME + ".exe"))
        say("单文件版：exe 可独立运行，首次运行自动释放程序文件并生成配置。")
    else:
        say("[失败] 未找到构建产物：" + src)
        wait_key()
        sys.exit(1)
    wait_key()


if __name__ == "__main__":
    main()