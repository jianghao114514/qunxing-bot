# plugins/feedback.py
import os
import json
from datetime import datetime
from plugins.base import BasePlugin
from core.utils import send_email
from core.config import CONFIG

class FeedbackPlugin(BasePlugin):
    name = "feedback"
    priority = 100

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith("反馈")

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        content = clean_message[2:].strip()
        if not content:
            self.bot.send_reply(msg_type, group_id, user_qq, "反馈内容不能为空", at_user=(msg_type=='group'))
            return True
        # 保存到本地文件
        fb_file = os.path.join(CONFIG["data_dir"], "feedbacks.json")
        try:
            with open(fb_file, "r", encoding="utf-8") as f:
                fb_list = json.load(f)
        except:
            fb_list = []
        fb_list.append({"user": user_qq, "time": datetime.now().isoformat(), "content": content})
        with open(fb_file, "w", encoding="utf-8") as f:
            json.dump(fb_list, f, ensure_ascii=False, indent=2)
        # 发送邮件
        send_email(f"用户反馈 from {user_qq}", f"用户{user_qq}反馈：\n{content}")
        self.bot.send_reply(msg_type, group_id, user_qq, "感谢反馈！已收到您的意见。", at_user=(msg_type=='group'))
        return True