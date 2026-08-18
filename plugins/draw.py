# plugins/draw.py
import random
from plugins.base import BasePlugin
from core.database import get_user_stardust, add_user_stardust, add_user_card
from core.config import SYSTEM_CONFIG

def draw_card_game(user_qq):
    ssr_prob = float(SYSTEM_CONFIG.get("ssr_prob", 0.05))
    sr_prob = float(SYSTEM_CONFIG.get("sr_prob", 0.15))
    rand = random.random()
    if rand < ssr_prob:
        tier, cards, reward = "SSR", ["星尘守护者", "时空旅者", "深渊魔神", "创世之光"], 50
    elif rand < ssr_prob + sr_prob:
        tier, cards, reward = "SR", ["火焰精灵", "冰霜女巫", "机械战警", "森林之灵"], 20
    else:
        tier, cards, reward = "R", ["史莱姆", "哥布林", "路人甲", "生锈的铁剑"], 5
    card_name = random.choice(cards)
    add_user_card(user_qq, f"{tier}-{card_name}")
    return tier, card_name, reward

class DrawPlugin(BasePlugin):
    name = "draw"
    priority = 20

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message in ["抽卡", "抽一张"] or clean_message.startswith("十连")

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        cost = SYSTEM_CONFIG.get("draw_cost", 100)
        if clean_message.startswith("十连"):
            cost *= 10
            if get_user_stardust(user_qq) < cost:
                self.bot.send_reply(msg_type, group_id, user_qq, f"星尘碎片不足，十连抽需要 {cost} 碎片。", at_user=(msg_type=='group'))
                return True
            add_user_stardust(user_qq, -cost)
            results = []
            total_reward = 0
            for _ in range(10):
                tier, card, reward = draw_card_game(user_qq)
                results.append(f"{tier}-{card}")
                total_reward += reward
            add_user_stardust(user_qq, total_reward)
            reply = "十连抽结果：\n" + "\n".join(results) + f"\n额外获得 {total_reward} 星尘碎片"
        else:
            if get_user_stardust(user_qq) < cost:
                self.bot.send_reply(msg_type, group_id, user_qq, f"星尘碎片不足，抽卡需要 {cost} 碎片。", at_user=(msg_type=='group'))
                return True
            add_user_stardust(user_qq, -cost)
            tier, card, reward = draw_card_game(user_qq)
            add_user_stardust(user_qq, reward)
            reply = f"抽卡结果：{tier}-{card}\n获得 {reward} 星尘碎片"
        self.bot.send_reply(msg_type, group_id, user_qq, reply, at_user=(msg_type=='group'))
        return True