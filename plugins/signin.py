# plugins/signin.py
import random
import time
from datetime import datetime
from plugins.base import BasePlugin
from core.database import get_last_signin, record_signin, add_stardust
from core.config import SYSTEM_CONFIG

class SigninPlugin(BasePlugin):
    name = "signin"
    priority = 10

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["签到", "每日签到", "打卡"]

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        today = datetime.now().strftime("%Y-%m-%d")
        last = get_last_signin(user_qq)
        if last == today:
            self.bot.send_reply(msg_type, group_id, user_qq, "你今天已经签到过了，明天再来吧", at_user=(msg_type=='group'))
            return True
        min_r = int(SYSTEM_CONFIG.get("signin_min_reward", 10))
        max_r = int(SYSTEM_CONFIG.get("signin_max_reward", 100))
        reward = random.randint(min_r, max_r)
        new_total = add_stardust(user_qq, reward)
        record_signin(user_qq, today)
        self.bot.send_reply(msg_type, group_id, user_qq, f"签到成功！获得 {reward} 星尘碎片，当前共有 {new_total} 碎片。", at_user=(msg_type=='group'))
        return True