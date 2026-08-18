# plugins/kfc.py
from plugins.base import BasePlugin
from core.ai import call_ai_with_fallback

class KFCPlugin(BasePlugin):
    name = "kfc"
    priority = 60

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["疯狂星期四", "kfc"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        kfc = call_ai_with_fallback("生成疯狂星期四幽默段子，包含V我50", system_override="段子手")
        self.bot.send_reply(msg_type, group_id, user_qq, kfc or "今天疯狂星期四，V我50？", at_user=(msg_type=='group'))
        return True