# plugins/persona.py
import json
from plugins.base import BasePlugin
from core.database import get_current_persona, set_current_persona, get_persona_type
from core.config import CONFIG, PERSONALITIES
from core.ai import call_ai_with_fallback

class PersonaPlugin(BasePlugin):
    name = "persona"
    priority = 15

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith("切换人设") or clean_message == "可用人设"

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        if clean_message == "可用人设":
            personas = list(PERSONALITIES.keys())
            self.bot.send_reply(msg_type, group_id, user_qq, f"可用人设: {', '.join(personas)}", at_user=(msg_type=='group'))
            return True
        parts = clean_message.split(maxsplit=1)
        if len(parts) < 2:
            current = get_current_persona(user_qq)
            self.bot.send_reply(msg_type, group_id, user_qq, f"当前人设: {current}", at_user=(msg_type=='group'))
            return True
        name = parts[1]
        if name not in PERSONALITIES:
            self.bot.send_reply(msg_type, group_id, user_qq, f"未找到人设「{name}」", at_user=(msg_type=='group'))
            return True
        # 检查是否是病娇类型且用户不在白名单
        if get_persona_type(name) == "yandere":
            with open(CONFIG["config_file"], "r", encoding="utf-8") as f:
                conf = json.load(f)
            whitelist = conf.get("yandere_whitelist", [])
            if str(user_qq) not in whitelist and str(user_qq) != CONFIG.get("master_qq", ""):
                # 拒绝切换，调用AI生成拒绝消息
                yandere_prompt = PERSONALITIES[name]["prompt"]
                system_msg = f"{yandere_prompt}\n\n用户不在你的白名单中，请拒绝他切换人设。回复简短。"
                refuse_msg = call_ai_with_fallback("拒绝切换", system_override=system_msg)
                if not refuse_msg:
                    refuse_msg = "你没有权限使用这个人设。"
                self.bot.send_reply(msg_type, group_id, user_qq, refuse_msg, at_user=(msg_type=='group'))
                return True
        # 正常切换
        set_current_persona(user_qq, name)
        self.bot.send_reply(msg_type, group_id, user_qq, f"已将人设切换为：{name}", at_user=(msg_type=='group'))
        return True