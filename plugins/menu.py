# plugins/menu.py
import time
from plugins.base import BasePlugin
from core.config import CONFIG, FEATURE_SWITCHES, CUSTOM_MENU_TEXTS
from core.menu_image import build_menu_image
from core.database import get_stardust, get_cards_count, get_last_signin, get_current_persona, get_planet

class MenuPlugin(BasePlugin):
    name = "menu"
    priority = 1   # 最高优先级，最先匹配

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["菜单", "帮助", "功能", "指令", "help", "menu"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        user_id = str(user_qq)
        show_admin = (msg_type == 'private' and str(user_qq) == str(CONFIG.get("master_qq", "")))
        today = time.strftime("%Y-%m-%d")
        user_stats = {
            "nickname": (nickname or "访客")[:12],
            "stardust": get_stardust(user_id),
            "cards": get_cards_count(user_id),
            "persona": get_current_persona(user_id)[:8],
            "signed": get_last_signin(user_id) == today,
        }
        planet = get_planet(user_id)
        if planet:
            user_stats["planet"] = (planet.get("name") or "?"), planet.get("level", 1)
        try:
            img_b64 = build_menu_image(FEATURE_SWITCHES, CUSTOM_MENU_TEXTS, show_admin, user_stats)
            reply = f"[CQ:image,file=base64://{img_b64}]"
        except Exception as e:
            print(f"菜单图片生成失败: {e}")
            reply = "菜单生成失败，请稍后再试"
        self.bot.send_reply(msg_type, group_id, user_qq, reply, at_user=(msg_type=='group'))
        return True