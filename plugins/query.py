# plugins/query.py
from plugins.base import BasePlugin
from core.config import currency_name
from core.database import get_user_stardust, get_user_cards_count

class QueryPlugin(BasePlugin):
    name = "query"
    priority = 25

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["背包", "查询", "碎片"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        dust = get_user_stardust(user_qq)
        cards = get_user_cards_count(user_qq)
        self.bot.send_reply(msg_type, group_id, user_qq, f"您的{currency_name()}：{dust} 个，拥有卡牌：{cards} 张。", at_user=(msg_type=='group'))
        return True