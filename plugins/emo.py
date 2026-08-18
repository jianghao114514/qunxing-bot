# plugins/emo.py
from plugins.base import BasePlugin
from core.ai import call_ai_with_fallback

class EmoPlugin(BasePlugin):
    name = "emo"
    priority = 70

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["emo", "每日emo"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        emo = call_ai_with_fallback("写一句深夜emo语录", system_override="忧郁诗人")
        self.bot.send_reply(msg_type, group_id, user_qq, emo or "人间不值得，但你还值得。", at_user=(msg_type=='group'))
        return True