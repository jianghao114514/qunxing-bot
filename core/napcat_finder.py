# core/napcat_finder.py
# NapCat 安装位置自动扫描：供 web 面板与守护进程共用。
# 只做文件系统探测，不依赖任何运行时配置，纯函数。
import os


def scan_napcat_exe():
    """扫描本机 NapCatWinBootMain.exe 位置，返回第一个命中的完整路径；找不到返回 None
    优先完整运行目录（NapCat*.Shell，同目录带 QQ.exe），bootmain 占位目录（缺 QQ.exe）降级"""
    roots = []
    for drv in ("D:", "C:", "E:"):
        root = drv + "\\"
        roots += [
            os.path.join(root, "napcat"),
            os.path.join(root, "NapCat"),
            os.path.join(root, "NapCatQQ"),
            os.path.join(root, "Program Files", "napcat"),
            os.path.join(root, "Program Files", "NapCat"),
        ]
    roots += [
        os.path.expanduser("~\\napcat"),
        os.path.expanduser("~\\NapCat"),
    ]
    full_hits = []   # 完整目录：NapCatWinBootMain.exe 与 QQ.exe 同目录
    bare_hits = []   # 仅有启动器
    for r in roots:
        if not os.path.isdir(r):
            continue
        try:
            for name in os.listdir(r):
                if name.startswith("NapCat") and name.endswith("Shell"):
                    p = os.path.join(r, name, "NapCatWinBootMain.exe")
                    if os.path.isfile(p):
                        if os.path.isfile(os.path.join(r, name, "QQ.exe")):
                            full_hits.append(p)
                        else:
                            bare_hits.append(p)
        except OSError:
            pass
        bm = os.path.join(r, "bootmain", "NapCatWinBootMain.exe")
        if os.path.isfile(bm):
            if os.path.isfile(os.path.join(r, "bootmain", "QQ.exe")):
                full_hits.append(bm)
            else:
                bare_hits.append(bm)
    return (full_hits or bare_hits or [None])[0]


def find_exe(preferred=""):
    """优先用已配置路径（须为完整运行目录）；无效则自动扫描补齐"""
    if preferred and os.path.isfile(preferred):
        if os.path.isfile(os.path.join(os.path.dirname(preferred), "QQ.exe")):
            return preferred
    return scan_napcat_exe()
