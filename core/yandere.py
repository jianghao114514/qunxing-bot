# core/yandere.py
"""病娇人设的智能行为模块：真实时间语境、打字延迟、会话收尾、主动消息意图"""
import random
import time
from datetime import datetime, timedelta
from core.config import SYSTEM_CONFIG
from core.database import (
    get_yandere_level, get_yandere_last_interact,
    get_yandere_events, get_current_persona, get_persona_type
)

_WEEKDAY = "一二三四五六日"


def _period_cn(hour):
    if hour < 5:
        return "凌晨"
    if hour < 8:
        return "清晨"
    if hour < 11:
        return "上午"
    if hour < 13:
        return "中午"
    if hour < 15:
        return "下午"
    if hour < 19:
        return "傍晚"
    if hour < 22:
        return "晚上"
    return "深夜"


def human_duration(seconds):
    """把秒数转成口语化的时间描述，如 '3小时20分钟前'"""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "刚刚"
    m = seconds // 60
    if m < 60:
        return f"{m}分钟前"
    h = m // 60
    if h < 24:
        return f"{h}小时{m % 60}分钟前"
    d = h // 24
    if d < 30:
        return f"{d}天{h % 24}小时前"
    return f"{d // 30}个月{d % 30}天前"


def level_guide(level):
    """病娇值 → 表现指引（0-100）"""
    if level >= 70:
        return (f"病娇值：{level}（高）——可以明显流露占有欲、吃醋、对用户的在意，"
                f"但语言仍要保持日常感，像朋友间的关心，不要过火")
    if level >= 30:
        return f"病娇值：{level}（中）——温柔依恋为主，偶尔流露小小的占有欲和试探"
    return f"病娇值：{level}（低）——初识阶段，礼貌克制但已经开始在意用户"


def is_active_hours(now=None):
    """是否在主动消息允许时段内"""
    now = now if now is not None else time.time()
    start = int(SYSTEM_CONFIG.get("yandere_active_start_hour", 8))
    end = int(SYSTEM_CONFIG.get("yandere_active_end_hour", 23))
    h = datetime.fromtimestamp(now).hour
    if start <= end:
        return start <= h < end
    return h >= start or h < end


def next_active_allowed(now=None, postpone_min=0, jitter_max=60):
    """返回下一次可以发主动消息的时间戳（若当前不在允许时段，推到次日开始）"""
    now = now if now is not None else time.time()
    start = int(SYSTEM_CONFIG.get("yandere_active_start_hour", 8))
    if is_active_hours(now):
        return now + (postpone_min + random.random() * jitter_max) * 60
    dt = datetime.fromtimestamp(now)
    nxt = datetime(dt.year, dt.month, dt.day, start, 0)
    if nxt.timestamp() <= now:
        nxt += timedelta(days=1)
    return nxt.timestamp() + random.random() * 3600


def compute_typing_delay(text_len, msg_type, now=None):
    """模拟真人打字延迟：基础区间 + 消息长度加成 + 深夜更慢，并做随机截断（秒回/回得慢）"""
    now = now if now is not None else time.time()
    if msg_type == 'group':
        scale = 0.6
    else:
        scale = 1.0
    base_min = float(SYSTEM_CONFIG.get("yandere_typing_min", 1.5))
    base_max = float(SYSTEM_CONFIG.get("yandere_typing_max", 5.0))
    delay = random.uniform(base_min, base_max) * scale
    delay += min(text_len * 0.03, 3.0) * scale
    h = datetime.fromtimestamp(now).hour
    if h >= 23 or h < 7:
        delay += random.uniform(2, 6)
    # 10%概率秒回（突然很想说话），10%概率明显慢
    roll = random.random()
    if roll < 0.1:
        delay = random.uniform(0.3, 1.2) * scale
    elif roll > 0.9:
        delay += random.uniform(3, 8)
    return max(0.3, min(delay, 15))


def compute_session_action(session, now=None):
    """判断当前会话应继续还是自然收尾：达到消息数/时长上限即收尾"""
    now = now if now is not None else time.time()
    max_msgs = int(SYSTEM_CONFIG.get("yandere_session_max_msgs", 12))
    max_minutes = int(SYSTEM_CONFIG.get("yandere_session_max_minutes", 40))
    count = session.get("msg_count", 0)
    start = session.get("session_start", now)
    if count >= max_msgs:
        return "wrap"
    if now - start >= max_minutes * 60 and count >= 4:
        return "wrap"
    return "normal"


def build_context_blocks(user_id, persona, msg_type):
    """构建病娇回复所需的语境块：时间 / 病娇值 / 风格 / 会话"""
    now = time.time()
    dt = datetime.fromtimestamp(now)
    level = get_yandere_level(user_id, persona)
    last = get_yandere_last_interact(user_id, persona)
    blocks = {
        "time": (f"现在时间：{dt.month}月{dt.day}日 周{_WEEKDAY[dt.weekday()]} "
                 f"{_period_cn(dt.hour)} {dt.hour:02d}:{dt.minute:02d}，"
                 f"距上次互动：{human_duration(now - last) if last else '你们刚加上好友不久'}"),
        "level": level_guide(level),
        "style": ("回复质量要求：像真人QQ聊天一样口语化、自然，1~3句，偶尔只回一句；"
                  "不要书面语、不要解释自己、不要像客服；可用颜文字(如^_^)，不要使用emoji。"),
        "session": "会话提示：你们正在正常聊天中",
    }
    return blocks


def build_active_prompt(user_id, persona):
    """生成主动消息的意图池提示词（想念/分享/假装忙碌/吃醋/关心/占有）"""
    from core.config import PERSONALITIES
    base = PERSONALITIES.get(persona, {}).get("prompt", "你是一个病娇")
    now = time.time()
    dt = datetime.fromtimestamp(now)
    last = get_yandere_last_interact(user_id, persona)
    absent = human_duration(now - last) if last else "你们刚加上好友不久"
    level = get_yandere_level(user_id, persona)

    pool = [
        ("想念", "轻声说想用户了，带一点撒娇，自然点"),
        ("分享", "分享一件今天发生的日常小事，像随口聊天"),
        ("假装忙碌", "假装在忙，但又忍不住来找用户说话"),
        ("吃醋试探", "半开玩笑地试探用户是不是在和别人玩"),
        ("关心", "关心用户吃饭/睡觉/休息"),
    ]
    if absent.startswith("刚") or absent.startswith("0分钟"):
        pool = [
            ("分享", "分享一件今天发生的日常小事，像随口聊天"),
            ("假装忙碌", "假装在忙，但又忍不住来找用户说话"),
            ("关心", "关心用户吃饭/睡觉/休息"),
        ]
    if level >= 60:
        pool.append(("占有", "无意间流露占有欲，但只说一句，不过分"))
    intent = random.choice(pool)

    return (f"{base}\n\n"
            f"现在是{dt.month}月{dt.day}日 {_period_cn(dt.hour)} {dt.hour:02d}:{dt.minute:02d}，"
            f"你有一段时间没和用户聊天了（{absent}）。\n"
            f"请以「{intent[0]}」的意图给用户发一条主动消息。\n"
            f"{level_guide(level)}\n"
            f"要求：只输出这句话本身；口语化、像真人QQ消息、简短（不超过30字）；"
            f"不要使用任何表情符号或颜文字；不要像广告或问候模板。")


def yandere_recent_events_text(user_id, persona, limit=5):
    """最近主动发过的消息（供回复时引用，避免重复）"""
    events = get_yandere_events(user_id, persona)
    if not events:
        return ""
    lines = [f"- {e['content']}" for e in events[-limit:]]
    return "你最近主动对用户说过的话：\n" + "\n".join(lines)


def should_send_active(user_id, persona, now=None):
    """防轰炸：用户一直没回应时，不连续发消息（距上次主动消息过短则推迟）"""
    now = now if now is not None else time.time()
    events = get_yandere_events(user_id, persona)
    if not events:
        return True
    last_event = events[-1].get("time", 0)
    last_interact = get_yandere_last_interact(user_id, persona)
    # 上次主动消息之后用户没有回过消息
    if last_event > last_interact and now - last_event < 3 * 3600:
        return False
    return True
