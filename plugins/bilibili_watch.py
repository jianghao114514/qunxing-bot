# plugins/bilibili_watch.py
# B 站开播提醒：轻量轮询监控列表，检测到 UP 主开播时向提醒群发送通知。
import time
from core.config import CONFIG
from core.bilibili import get_live_info

_last_state = {}


def _state_key(uid):
    return "bili_live:" + str(uid)


def _notify(bot, info, watched_name):
    """合并发送直播间名称 + 封面 + 链接"""
    group = str(CONFIG.get("bilibili_alert_group") or "")
    lines = [
        "【开播提醒】",
        "主播：{}".format(info["name"] or watched_name),
        "直播间：{}".format(info["title"] or "（无标题）"),
        "链接：{}".format(info["url"]),
    ]
    msg = "\n".join(lines)
    if info.get("cover"):
        msg += "\n[CQ:image,url={}]".format(info["cover"])
    if group:
        try:
            bot.send_msg(group, msg)
        except Exception as e:
            print("B站开播提醒发送失败:", e)
    else:
        print("B站开播提醒：未配置提醒群（bilibili_alert_group），跳过发送")


def bilibili_watch_thread(bot):
    print(">>> B站开播监控线程已启动")
    while True:
        time.sleep(5)
        if not CONFIG.get("bilibili_enabled", False):
            continue
        interval = max(int(CONFIG.get("bilibili_check_interval", 120)), 30)
        watch = CONFIG.get("bilibili_watch", []) or []
        if not watch:
            time.sleep(interval)
            continue
        for item in watch:
            try:
                uid = str(item.get("uid", "")).strip()
                if not uid.isdigit():
                    continue
                info = get_live_info(uid)
                if info is None:
                    continue
                key = _state_key(uid)
                was_living = _last_state.get(key, False)
                if info["living"] and not was_living:
                    _notify(bot, info, item.get("name", ""))
                _last_state[key] = info["living"]
            except Exception as e:
                print("B站监控查询出错:", e)
        time.sleep(interval)
