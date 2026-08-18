# plugins/profile.py
import base64
import time
from plugins.base import BasePlugin
from core.config import CONFIG
from core.profile_image import build_profile_card
from core.planet_image import STAGE_NAMES
from core.database import (
    get_stardust, get_cards_count, get_last_signin, get_current_persona,
    get_planet, get_cached_user,
)


class ProfilePlugin(BasePlugin):
    name = "profile"
    priority = 84

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["我的名片", "资料卡", "个人资料"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        uid = str(user_qq)
        data = get_cached_user(uid)
        today = time.strftime("%Y-%m-%d")
        planet = data.get("planet")
        stats = {
            "qq": uid,
            "nickname": data.get("nickname") or nickname or "星空旅人",
            "stardust": data.get("stardust", 0),
            "cards": data.get("cards", []),
            "persona": data.get("current_persona", "default"),
            "signed": data.get("last_signin") == today,
            "last_signin": data.get("last_signin"),
            "planet": {
                "name": planet.get("name", "?"),
                "level": planet.get("level", 1),
                "stage": planet.get("stage", 1),
                "stage_name": STAGE_NAMES[min(planet.get("stage", 1), len(STAGE_NAMES)) - 1],
            } if planet else None,
        }
        try:
            png = build_profile_card(stats)
            b64 = base64.b64encode(png).decode("ascii")
            self.bot.send_reply(msg_type, group_id, user_qq, f"[CQ:image,file=base64://{b64}]",
                                at_user=(msg_type == 'group'))
        except Exception as e:
            print(f"名片生成失败: {e}")
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"星空名片：星尘 {stats['stardust']} · 卡牌 {len(stats['cards'])} 张 · 人设 {stats['persona']}",
                                at_user=(msg_type == 'group'))
        return True
