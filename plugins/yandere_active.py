# plugins/yandere_active.py
import time
import os
import random
from core.config import CONFIG, SYSTEM_CONFIG, PERSONALITIES
from core.database import (
    get_current_persona, get_persona_type,
    get_yandere_next_active, set_yandere_next_active,
    get_yandere_last_interact, is_friend, add_yandere_event
)
from core.ai import call_ai_with_fallback
from core.yandere import (
    is_active_hours, next_active_allowed, build_active_prompt, should_send_active
)

def yandere_active_thread(bot):
    print(">>> 病娇主动消息线程已启动")
    _friends_checked_at = 0.0
    while True:
        time.sleep(30)
        if not SYSTEM_CONFIG.get("yandere_active_enabled", True):
            continue
        # 每 60 秒通过 websocket 刷新好友列表（不再依赖失效的 HTTP token）
        if time.time() - _friends_checked_at > 60:
            bot.refresh_friends()
            _friends_checked_at = time.time()
        min_interval = SYSTEM_CONFIG.get("yandere_active_min_interval", 1800)
        max_interval = SYSTEM_CONFIG.get("yandere_active_max_interval", 10800)
        cooldown = SYSTEM_CONFIG.get("yandere_active_cooldown", 60)
        skip_prob = float(SYSTEM_CONFIG.get("yandere_active_skip_prob", 0.2))
        now_ts = time.time()

        for fname in os.listdir(CONFIG["users_dir"]):
            if not fname.endswith(".json"):
                continue
            user_id = fname[:-5]

            persona = get_current_persona(user_id)
            if get_persona_type(persona) != "yandere":
                continue

            if not is_friend(user_id):
                set_yandere_next_active(user_id, now_ts + 3600, persona)
                continue

            next_time = get_yandere_next_active(user_id, persona)
            if next_time == 0:
                delay = random.randint(min_interval, max_interval)
                set_yandere_next_active(user_id, next_active_allowed(now_ts, postpone_min=delay // 60), persona)
                continue

            if now_ts < next_time:
                continue

            # 真人不会半夜轰炸：不在允许时段则推到次日
            if not is_active_hours(now_ts):
                set_yandere_next_active(user_id, next_active_allowed(now_ts), persona)
                continue

            # 真人也有不想发消息的时候
            if random.random() < skip_prob:
                set_yandere_next_active(user_id, next_active_allowed(now_ts, postpone_min=random.randint(30, 90)), persona)
                continue

            # 用户一直没回应时不连续轰炸
            if not should_send_active(user_id, persona, now_ts):
                set_yandere_next_active(user_id, now_ts + random.randint(60, 120) * 60, persona)
                continue

            last_interact = get_yandere_last_interact(user_id, persona)
            if now_ts - last_interact < cooldown:
                set_yandere_next_active(user_id, now_ts + 60, persona)
                continue

            gen_prompt = build_active_prompt(user_id, persona)
            msg = call_ai_with_fallback(gen_prompt, system_override=None)
            if not msg:
                msg = "你在做什么？为什么不理我？"

            try:
                bot.send_private_msg(user_id, msg)
                add_yandere_event(user_id, {"time": now_ts, "content": msg}, persona)
                next_delay = random.randint(min_interval, max_interval)
                set_yandere_next_active(user_id, next_active_allowed(now_ts, postpone_min=next_delay // 60), persona)
                print(f"向病娇用户 {user_id} 发送主动消息: {msg}")
            except Exception as e:
                print(f"向 {user_id} 发送失败: {e}")
                set_yandere_next_active(user_id, now_ts + 3600, persona)
