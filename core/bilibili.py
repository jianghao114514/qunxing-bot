# core/bilibili.py
# B 站公开接口封装：UP 主搜索、直播间状态查询。无需登录。
import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


def search_up(name, limit=5):
    """按昵称搜索 UP 主，返回 [{uid, name, room_id, sign}]；失败返回 []"""
    try:
        r = requests.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"search_type": "bili_user", "keyword": name, "page": 1},
            headers=_HEADERS, timeout=8
        )
        data = r.json()
        result = []
        for item in (data.get("data") or {}).get("result") or []:
            result.append({
                "uid": str(item.get("mid", "")),
                "name": item.get("uname", ""),
                "sign": (item.get("usign") or "")[:60],
                "fans": item.get("fans", 0)
            })
        return result[:limit]
    except Exception:
        return []


def get_live_info(uid):
    """查询 UP 主直播状态，返回 dict；失败/无数据返回 None。
    字段：uid/name/living/title/room_id/cover/url"""
    try:
        r = requests.get(
            "https://api.live.bilibili.com/live_user/v1/Master/info",
            params={"uid": uid}, headers=_HEADERS, timeout=8
        )
        data = r.json()
        d = data.get("data") or {}
        room = d.get("room") or {}
        return {
            "uid": str(uid),
            "name": d.get("info", {}).get("uname", ""),
            "living": bool(room.get("live_status") == 1),
            "title": room.get("title", ""),
            "room_id": str(room.get("roomid", "")),
            "cover": room.get("user_cover", "") or room.get("cover", ""),
            "url": "https://live.bilibili.com/{}".format(room.get("roomid", "")) if room.get("roomid") else ""
        }
    except Exception:
        return None
