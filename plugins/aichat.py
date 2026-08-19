# plugins/aichat.py
import json
import time
from datetime import datetime
from plugins.base import BasePlugin
from core.database import (
    get_current_persona, get_persona_type, get_long_memory,
    get_temp_conversation, add_temp_message,
    get_yandere_session, set_yandere_session
)
from core.ai import call_with_messages
from core.config import CONFIG, PERSONALITIES
from core.yandere import (
    build_context_blocks, compute_typing_delay, compute_session_action,
    yandere_recent_events_text
)

_WEEKDAY = ["一", "二", "三", "四", "五", "六", "日"]

def _period_cn(hour):
    if 5 <= hour < 9: return "早上"
    if 9 <= hour < 12: return "上午"
    if 12 <= hour < 14: return "中午"
    if 14 <= hour < 18: return "下午"
    if 18 <= hour < 23: return "晚上"
    return "凌晨"

class AIChatPlugin(BasePlugin):
    name = "aichat"
    priority = 1000

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return True

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        user_id = str(user_qq)
        is_story = any(k in clean_message for k in ["故事", "写故事", "讲个故事", "创作故事", "编故事", "来段故事", "童话", "小说"])
        persona = get_current_persona(user_id)
        long_memory = get_long_memory(user_id, persona)
        memory_text = json.dumps(long_memory, ensure_ascii=False)
        # 群聊会话按群隔离，私聊独立
        temp_conv = get_temp_conversation(user_id, persona, group_id)
        history = [{"role": m["role"], "content": m["content"]} for m in temp_conv["messages"][-CONFIG["max_history"]:]]
        persona_prompt = PERSONALITIES.get(persona, {}).get("prompt", "你是一个友好的AI助手")

        # ============ 病娇分支：智能语境 + 会话收尾 ============
        session_block = ""
        if get_persona_type(persona) == "yandere" and not is_story:
            now = time.time()
            session = get_yandere_session(user_id, persona)
            wrapped_at = session.get("wrapped_at", 0)
            if wrapped_at and now - wrapped_at > 60:
                # 上次会话已收尾且隔了一段时间 → 开启新会话
                session = {"session_start": now, "msg_count": 1, "wrapped_at": 0}
                set_yandere_session(user_id, session, persona)
                session_block = "会话提示：上次聊天已经结束，这是新一轮聊天的开始，像老朋友重逢一样自然，可以轻轻提起『多久没聊了』"
            else:
                session["msg_count"] = session.get("msg_count", 0) + 1
                session.setdefault("session_start", now)
                if compute_session_action(session, now) == "wrap":
                    session["wrapped_at"] = now
                    set_yandere_session(user_id, session, persona)
                    session_block = ("会话提示：你们已经聊了很久（这是本次对话的最后一句），"
                                     "请自然地收尾：道晚安、说有事先忙、或约下次再聊。"
                                     "不要再抛出新话题，不要恋战，保持人设的温度。")
                else:
                    set_yandere_session(user_id, session, persona)
                    session_block = ("会话提示：你们正在聊天中，"
                                     f"这是本次会话第 {session['msg_count']} 条消息，"
                                     "节奏自然一些，不用每句都回得很满")

        # ============ 通用时间语境（所有人设） ============
        dt = datetime.now()
        time_block = (f"现在时间：{dt.month}月{dt.day}日 周{_WEEKDAY[dt.weekday()]} "
                      f"{_period_cn(dt.hour)} {dt.hour:02d}:{dt.minute:02d}")
        if msg_type == 'group':
            time_block += f"\n当前场景：QQ 群聊（群号 {group_id}）"
        else:
            time_block += "\n当前场景：QQ 私聊"

        # ============ 构建系统提示 ============
        events_text = ""
        if get_persona_type(persona) == "yandere":
            events_text = yandere_recent_events_text(user_id, persona)

        if is_story:
            system = "你是一个富有想象力的故事创作者。"
        else:
            blocks = build_context_blocks(user_id, persona, msg_type) if get_persona_type(persona) == "yandere" else None
            if blocks:
                system = f"{persona_prompt}\n\n{time_block}\n{blocks['level']}\n{blocks['style']}\n{session_block or blocks['session']}\n\n长期记忆：{memory_text}"
            else:
                style = ("回复要求：像真人聊天一样自然、口语化，不要书面语、不要像客服；"
                         "根据语境决定回复长度，闲聊时简短，提问时详细一些。")
                system = f"{persona_prompt}\n\n{time_block}\n{style}\n\n长期记忆：{memory_text}"
            if events_text:
                system += f"\n{events_text}"
            if get_persona_type(persona) == "yandere":
                if msg_type == 'group':
                    system += "\n注意：当前是群聊环境，你的回复不能过于极端、露骨或引起他人不适，需保持基本礼貌。"
                else:
                    system += ("\n注意：当前是私聊。你可以像真实的人一样：偶尔秒回、偶尔故意慢一点；"
                               "不想聊时自然结束话题，不用一直陪聊。")

        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": clean_message}]
        content = call_with_messages(messages)
        if content:
            add_temp_message(user_id, "user", clean_message, persona, group_id)
            add_temp_message(user_id, "assistant", content, persona, group_id)
            # 病娇回复模拟真人打字延迟
            if get_persona_type(persona) == "yandere" and not is_story:
                delay = compute_typing_delay(len(content), msg_type)
                if delay:
                    time.sleep(delay)
            self.bot.send_reply(msg_type, group_id, user_qq, content, at_user=(msg_type=='group'))
        else:
            self.bot.send_reply(msg_type, group_id, user_qq, "AI 服务暂时不可用，请稍后再试。", at_user=(msg_type=='group'))
        return True
