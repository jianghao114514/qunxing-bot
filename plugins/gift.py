# plugins/gift.py
import re
from plugins.base import BasePlugin
from core.config import CONFIG, currency_name
from core.database import get_user_stardust, add_user_stardust

USAGE = "用法：赠送 @对方 数量（例：赠送@XX 100），或 赠送 QQ号 数量"


def _parse_target_amount(raw_message, clean_message, bot_qq):
    """提取赠送对象与数量。先跳过机器人自己的 @；无 @ 时支持纯数字 QQ 号。返回 (target, amount)"""
    ats = re.findall(r'\[CQ:at,qq=(\d+)\]', raw_message)
    if not ats:
        ats = re.findall(r'@(\d+)', raw_message)
    target = None
    for qq in ats:
        if qq != str(bot_qq):
            target = qq
            break
    amount = None
    if target:
        m = re.search(r'\d+', re.sub(r'@\d+', '', clean_message))
        if m:
            amount = int(m.group())
    else:
        rest = clean_message
        for tok in rest.split():
            if tok.isdigit() and len(tok) >= 5:
                target = tok
                rest = rest.replace(tok, "", 1)
                break
        if target:
            m = re.search(r'\d+', rest)
            if m:
                amount = int(m.group())
    return target, amount


class GiftPlugin(BasePlugin):
    name = "gift"
    priority = 90

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith("赠送")

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        target, amount = _parse_target_amount(raw_message, clean_message, CONFIG["bot_qq"])
        if not target:
            self.bot.send_reply(msg_type, group_id, user_qq, USAGE, at_user=(msg_type=='group'))
            return True
        if not amount:
            self.bot.send_reply(msg_type, group_id, user_qq, "请指定数量：" + USAGE, at_user=(msg_type=='group'))
            return True
        if amount <= 0 or target == str(user_qq):
            self.bot.send_reply(msg_type, group_id, user_qq, "数量必须大于0且不能赠送给自己", at_user=(msg_type=='group'))
            return True
        if get_user_stardust(user_qq) < amount:
            self.bot.send_reply(msg_type, group_id, user_qq, f"余额不足，当前仅有 {get_user_stardust(user_qq)} {currency_name()}", at_user=(msg_type=='group'))
            return True
        add_user_stardust(user_qq, -amount)
        add_user_stardust(target, amount)
        self.bot.send_reply(msg_type, group_id, user_qq, f"赠送成功！向 [CQ:at,qq={target}] 赠送了 {amount} {currency_name()}", at_user=(msg_type=='group'))
        return True