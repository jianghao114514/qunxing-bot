# plugins/tarot.py
import random
from plugins.base import BasePlugin
from core.database import get_user_stardust, add_user_stardust
from core.ai import call_ai_with_fallback
from core.config import SYSTEM_CONFIG

TAROT_DECK = [
    {"name": "愚人", "meaning": "新的开始、冒险、天真"},
    {"name": "魔术师", "meaning": "创造力、技能、自信"},
    {"name": "女祭司", "meaning": "直觉、神秘、潜意识"},
    {"name": "皇后", "meaning": "丰收、母爱、自然"},
    {"name": "皇帝", "meaning": "权威、结构、控制"},
    {"name": "教皇", "meaning": "传统、信仰、指导"},
    {"name": "恋人", "meaning": "爱、和谐、选择"},
    {"name": "战车", "meaning": "胜利、意志力、决心"},
    {"name": "力量", "meaning": "勇气、耐心、控制"},
    {"name": "隐士", "meaning": "内省、孤独、指引"},
    {"name": "命运之轮", "meaning": "改变、周期、命运"},
    {"name": "正义", "meaning": "公平、真理、因果"},
    {"name": "倒吊人", "meaning": "牺牲、新视角、等待"},
    {"name": "死神", "meaning": "结束、转变、新生"},
    {"name": "节制", "meaning": "平衡、适度、耐心"},
    {"name": "恶魔", "meaning": "束缚、物质主义、诱惑"},
    {"name": "高塔", "meaning": "突变、灾难、觉醒"},
    {"name": "星星", "meaning": "希望、灵感、宁静"},
    {"name": "月亮", "meaning": "幻觉、恐惧、不安"},
    {"name": "太阳", "meaning": "快乐、成功、活力"},
    {"name": "审判", "meaning": "复活、召唤、宽恕"},
    {"name": "世界", "meaning": "完成、整合、成就"}
]
FORTUNE_LEVELS = ["大吉", "中吉", "小吉", "平", "凶"]

def draw_tarot(question):
    card = random.choice(TAROT_DECK)
    is_reversed = random.choice([True, False])
    position = "逆位" if is_reversed else "正位"
    card_name = f"{card['name']} ({position})"
    fortune = random.choice(FORTUNE_LEVELS)
    if question:
        sys_prompt = "你是一位专业的塔罗牌占卜师。请结合问题给出解读，末尾总结运势。"
        user_prompt = f"我抽到【{card_name}】，含义：{card['meaning']}。问题：'{question}'。请解读。"
        interpretation = call_ai_with_fallback(user_prompt, system_override=sys_prompt)
        if interpretation:
            return card_name, interpretation
    advice = "建议保持现状。" if is_reversed else "勇敢前进！"
    return card_name, f"【{card_name}】\n含义：{card['meaning']}\n运势：{fortune}\n💡 {advice}"

class TarotPlugin(BasePlugin):
    name = "tarot"
    priority = 30

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith("塔罗") or clean_message.startswith("占卜")

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        cost = SYSTEM_CONFIG.get("tarot_cost", 15)
        if get_user_stardust(user_qq) < cost:
            self.bot.send_reply(msg_type, group_id, user_qq, f"星尘碎片不足，塔罗需要 {cost} 碎片。", at_user=(msg_type=='group'))
            return True
        add_user_stardust(user_qq, -cost)
        question = clean_message[2:].strip() if len(clean_message) > 2 else None
        card_name, interp = draw_tarot(question)
        self.bot.send_reply(msg_type, group_id, user_qq, f"塔罗占卜结果：\n{interp}", at_user=(msg_type=='group'))
        return True