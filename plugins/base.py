# plugins/base.py
class BasePlugin:
    name = "base"
    priority = 100
    enabled = True

    def __init__(self, bot):
        self.bot = bot

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        """返回 True 表示该插件处理此消息"""
        raise NotImplementedError

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        """处理消息，返回 True 表示已处理，False 表示未处理"""
        raise NotImplementedError