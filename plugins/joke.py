# plugins/joke.py
from plugins.base import BasePlugin
from core.ai import call_ai_with_fallback

recent_jokes = []

class JokePlugin(BasePlugin):
    name = "joke"
    priority = 50

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["笑话", "讲个笑话"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        global recent_jokes
        joke = None
        for _ in range(2):
            joke = call_ai_with_fallback("讲一个短笑话，每次内容要完全不同", system_override="幽默笑话大师，只输出笑话正文")
            if joke and (not recent_jokes or joke not in recent_jokes):
                recent_jokes.append(joke)
                if len(recent_jokes) > 5:
                    recent_jokes.pop(0)
                break
            else:
                joke = None
        self.bot.send_reply(msg_type, group_id, user_qq, joke or "暂时讲不出笑话", at_user=(msg_type=='group'))
        return True