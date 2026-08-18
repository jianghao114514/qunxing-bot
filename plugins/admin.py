# plugins/admin.py
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate
from plugins.base import BasePlugin
from core.config import CONFIG
from core.ai import call_ai_with_fallback
from core.database import refresh_friend_list

def send_test_email():
    if not CONFIG["email"]["enable"]:
        return False
    try:
        msg = MIMEText("测试邮件", "plain", "utf-8")
        msg["Subject"] = "测试邮件"
        msg["From"] = CONFIG["email"]["sender"]
        msg["To"] = CONFIG["email"]["receiver"]
        server = smtplib.SMTP_SSL(CONFIG["email"]["smtp_server"], CONFIG["email"]["smtp_port"])
        server.login(CONFIG["email"]["sender"], CONFIG["email"]["password"])
        server.send_message(msg)
        server.quit()
        return True
    except:
        return False

class AdminPlugin(BasePlugin):
    name = "admin"
    priority = 5  # 高优先级

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if str(user_qq) != CONFIG["master_qq"]:
            return False
        return raw_message.startswith("/test") or raw_message.strip() == "/reload"

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        if raw_message.strip() == "/reload":
            plugins = self.bot.plugin_manager.reload_plugins()
            names = "、".join(p.name for p in plugins)
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"插件热重载完成：{len(plugins)} 个插件（{names}）。\n"
                                "注意：病娇主动消息线程保持旧版本，断线重连后生效。",
                                at_user=(msg_type=='group'))
            return True
        parts = raw_message.split()
        if len(parts) == 1:
            self.bot.send_reply(msg_type, group_id, user_qq, "AI健康检查请查看控制台", at_user=(msg_type=='group'))
            return True
        sub = parts[1].lower()
        if sub == "alert":
            self.bot.send_private_msg(CONFIG["master_qq"], "测试警告")
            self.bot.send_reply(msg_type, group_id, user_qq, "测试警告已发送", at_user=(msg_type=='group'))
        elif sub == "mail":
            if send_test_email():
                self.bot.send_reply(msg_type, group_id, user_qq, "测试邮件发送成功", at_user=(msg_type=='group'))
            else:
                self.bot.send_reply(msg_type, group_id, user_qq, "测试邮件失败", at_user=(msg_type=='group'))
        elif sub == "friend":
            refresh_friend_list()
            self.bot.send_reply(msg_type, group_id, user_qq, "好友列表已刷新", at_user=(msg_type=='group'))
        elif sub == "all":
            self.bot.send_reply(msg_type, group_id, user_qq, "开始全面测试...", at_user=(msg_type=='group'))
            # AI健康
            test_resp = call_ai_with_fallback("你好", system_override="请回复'你好'")
            self.bot.send_reply(msg_type, group_id, user_qq, f"AI对话测试：{'成功' if test_resp else '失败'}", at_user=(msg_type=='group'))
            self.bot.send_reply(msg_type, group_id, user_qq, "全面测试完成！", at_user=(msg_type=='group'))
        else:
            self.bot.send_reply(msg_type, group_id, user_qq, "未知子命令", at_user=(msg_type=='group'))
        return True