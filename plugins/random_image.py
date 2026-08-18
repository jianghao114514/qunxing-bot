# plugins/random_image.py
import requests
from plugins.base import BasePlugin

API = "https://api.waifu.im/images"
UA = {"User-Agent": "Mozilla/5.0"}


def build_image_caption(item, header=None):
    """从 waifu.im 的 item 拼成可读文案。
    header: 顶部标题（如「你的每日老婆」）。
    画师信息仅在已知时输出为独立的「画师：」行，避免被误认为角色名。
    """
    lines = []
    if header:
        lines.append(header)
    artists = item.get("artists") or []
    if isinstance(artists, dict):
        artists = [artists]
    if isinstance(artists, list) and artists and isinstance(artists[0], dict):
        artist = artists[0]
        name = (artist.get("name") or "").strip()
        if name:
            lines.append(f"画师：{name}")
        links = []
        for label, key in (("Pixiv", "pixiv"), ("Twitter", "twitter")):
            val = artist.get(key)
            if val:
                links.append(f"{label} {val}")
        if links:
            lines.append("主页：" + "  ".join(links))
    tags = [t.get("name") for t in item.get("tags", []) if isinstance(t, dict) and t.get("name")][:2]
    if tags:
        lines.append("标签：" + " / ".join(tags))
    source = item.get("source")
    if source:
        lines.append("来源：" + source)
    return "\n".join(lines)


def fetch_random_character(tag, header=None):
    url = f"{API}?included_tags={tag}" if tag else API
    try:
        resp = requests.get(url, timeout=10, headers=UA).json()
        item = (resp.get("items") or [None])[0]
        if not item or not (item.get("url") or item.get("imageUrl")):
            return None
        return {"image_url": item.get("url") or item.get("imageUrl"), "caption": build_image_caption(item, header)}
    except Exception:
        return None


class RandomImagePlugin(BasePlugin):
    name = "random_image"
    priority = 80

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["随机美图", "来张图"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        data = fetch_random_character(None, "随机美图")
        if data:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"{data['caption']}\n[CQ:image,file={data['image_url']}]",
                                at_user=(msg_type=='group'))
        else:
            self.bot.send_reply(msg_type, group_id, user_qq, "获取图片失败", at_user=(msg_type=='group'))
        return True


class WaifuPlugin(BasePlugin):
    name = "random_waifu"
    priority = 81

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message == "每日老婆"

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        data = fetch_random_character("waifu", "你的每日老婆")
        if data:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"{data['caption']}\n[CQ:image,file={data['image_url']}]",
                                at_user=(msg_type=='group'))
        else:
            self.bot.send_reply(msg_type, group_id, user_qq, "获取失败", at_user=(msg_type=='group'))
        return True