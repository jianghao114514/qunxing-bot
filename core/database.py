# core/database.py
import os
import json
import re
import threading
import time
from pathlib import Path
from core.config import CONFIG, USERS_DIR, CONVERSATIONS_DIR, SYSTEM_CONFIG, MEMORY_CONFIG, PERSONALITIES, DATA_DIR
from core.ai import call_ai_with_fallback

# 全局缓存
_user_cache = {}
_user_cache_lock = threading.Lock()
_user_file_locks = {}
_global_locks_lock = threading.Lock()
_temp_conversations = {}
_temp_conversations_lock = threading.Lock()

# ========== 延迟写盘队列（合并多次修改，1.5s 内统一落盘） ==========
_dirty_users = {}          # user_id -> data 对象
_dirty_convs = {}          # conv_key -> conv 对象
_dirty_lock = threading.Lock()
_flush_thread_started = False
_CONV_EXPIRE_SECONDS = 7 * 86400   # 会话文件 7 天无活动后清理

def _get_user_lock(user_id):
    with _global_locks_lock:
        if user_id not in _user_file_locks:
            _user_file_locks[user_id] = threading.Lock()
        return _user_file_locks[user_id]

def _atomic_write(path, data):
    """临时文件 + 原子替换，避免写一半崩溃导致文件损坏"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _load_user_data(user_id):
    lock = _get_user_lock(user_id)
    with lock:
        path = USERS_DIR / f"{user_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            data = {
                "user_id": str(user_id),
                "stardust": 0,
                "cards": [],
                "current_persona": "default",
                "last_signin": None,
                "nickname": "",
                "settings": {},
                "persona_memories": {}
            }
            default_mem = {
                "long_memory": {"preferences": {}, "facts": [], "recent_topics": [], "yandere_events": []},
                "yandere": {"level": 0, "next_active_time": 0, "last_interact_time": 0}
            }
            data["persona_memories"]["default"] = default_mem
            _atomic_write(path, data)
            return data

def _save_user_data(user_id, data):
    lock = _get_user_lock(user_id)
    with lock:
        _atomic_write(USERS_DIR / f"{user_id}.json", data)

def get_cached_user(user_id):
    user_id = str(user_id)
    with _user_cache_lock:
        if user_id in _user_cache:
            _user_cache[user_id]["last_access"] = time.time()
            return _user_cache[user_id]["data"]
        data = _load_user_data(user_id)
        _user_cache[user_id] = {"data": data, "last_access": time.time()}
        return data

def update_cached_user(user_id, data):
    """更新缓存并标记待写盘（不立即写文件，由后台线程合并写入）"""
    user_id = str(user_id)
    with _user_cache_lock:
        _user_cache[user_id] = {"data": data, "last_access": time.time()}
    with _dirty_lock:
        _dirty_users[user_id] = data
    _ensure_flush_thread()

def _ensure_flush_thread():
    global _flush_thread_started
    if not _flush_thread_started:
        _flush_thread_started = True
        threading.Thread(target=_flush_worker, daemon=True).start()

def _flush_worker():
    while True:
        time.sleep(1.5)
        try:
            _flush_dirty()
        except Exception as e:
            print(f"数据落盘异常: {e}")

def _flush_dirty():
    with _dirty_lock:
        users = dict(_dirty_users)
        convs = dict(_dirty_convs)
        _dirty_users.clear()
        _dirty_convs.clear()
    for uid, data in users.items():
        try:
            _save_user_data(uid, data)
        except Exception as e:
            print(f"写入用户 {uid} 失败: {e}")
            with _dirty_lock:
                _dirty_users[uid] = data
    for key, conv in convs.items():
        try:
            _save_conversation(key, conv)
        except Exception as e:
            print(f"写入会话 {key} 失败: {e}")
            with _dirty_lock:
                _dirty_convs[key] = conv

def flush_all():
    """立即落盘所有待写数据（重启/退出前调用）"""
    _flush_dirty()

def unload_inactive_users():
    while True:
        time.sleep(60)
        now = time.time()
        with _user_cache_lock:
            to_del = [uid for uid, entry in _user_cache.items() if now - entry["last_access"] > 300]
        if to_del:
            _flush_dirty()   # 先落盘再逐出缓存
            with _user_cache_lock:
                for uid in to_del:
                    _user_cache.pop(uid, None)
        with _temp_conversations_lock:
            expired = [key for key, conv in _temp_conversations.items() if now - conv.get("last_active", 0) > 3600]
        for key in expired:
            with _temp_conversations_lock:
                conv = _temp_conversations.get(key)
            if conv:
                _save_conversation(key, conv)   # 落盘（重启后仍能恢复）
        with _temp_conversations_lock:
            for key in expired:
                _temp_conversations.pop(key, None)
        # 清理 7 天无活动的会话文件
        try:
            for f in CONVERSATIONS_DIR.glob("*.json"):
                if now - f.stat().st_mtime > _CONV_EXPIRE_SECONDS:
                    f.unlink()
        except Exception:
            pass

# ========== 基础属性 ==========
NICKNAME_FILE = DATA_DIR / "nicknames.json"
_nickname_map = {}
_nickname_map_loaded = False
_nickname_lock = threading.Lock()


def _load_nickname_map():
    global _nickname_map_loaded
    if not _nickname_map_loaded:
        _nickname_map_loaded = True
        try:
            if NICKNAME_FILE.exists():
                with open(NICKNAME_FILE, "r", encoding="utf-8") as f:
                    _nickname_map.update(json.load(f))
        except Exception:
            pass


def _save_nickname_map():
    """调用方须已持有 _nickname_lock（锁不可重入，此处不再加锁）"""
    try:
        tmp = NICKNAME_FILE.with_suffix(NICKNAME_FILE.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_nickname_map, f, ensure_ascii=False)
        os.replace(tmp, NICKNAME_FILE)
    except Exception:
        pass


def record_nickname(user_id, nickname):
    """记录用户昵称（面板用户管理展示用）。只写昵称缓存；
    已有用户文件的顺手同步，不存在的用户不会因此创建文件。"""
    user_id = str(user_id)
    if not nickname:
        return
    _load_nickname_map()
    with _nickname_lock:
        if _nickname_map.get(user_id) != nickname:
            _nickname_map[user_id] = nickname
            _save_nickname_map()
    path = USERS_DIR / f"{user_id}.json"
    if path.exists():
        try:
            data = get_cached_user(user_id)
            if data.get("nickname") != nickname:
                data["nickname"] = nickname
                update_cached_user(user_id, data)
        except Exception:
            pass


def get_nickname(user_id):
    """优先读昵称缓存，其次用户文件，都没有返回空"""
    user_id = str(user_id)
    _load_nickname_map()
    with _nickname_lock:
        name = _nickname_map.get(user_id)
    if name:
        return name
    try:
        path = USERS_DIR / f"{user_id}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("nickname", "")
    except Exception:
        pass
    return ""

def delete_user(user_id):
    """删除用户全部数据：磁盘文件、缓存、会话文件"""
    user_id = str(user_id)
    if not user_id.isdigit():
        return
    with _user_cache_lock:
        _user_cache.pop(user_id, None)
    with _dirty_lock:
        _dirty_users.pop(user_id, None)
    try:
        path = USERS_DIR / f"{user_id}.json"
        if path.exists():
            path.unlink()
    except Exception:
        pass
    with _temp_conversations_lock:
        keys = [k for k in _temp_conversations if k.startswith(user_id + "_")]
        for k in keys:
            _temp_conversations.pop(k, None)
    try:
        for f in CONVERSATIONS_DIR.glob(f"{user_id}_*.json"):
            f.unlink()
    except Exception:
        pass

def get_stardust(user_id):
    return get_cached_user(user_id).get("stardust", 0)

def add_stardust(user_id, amount):
    data = get_cached_user(user_id)
    new_amt = data.get("stardust", 0) + amount
    data["stardust"] = new_amt
    update_cached_user(user_id, data)
    return new_amt

def get_cards_count(user_id):
    return len(get_cached_user(user_id).get("cards", []))

def add_card(user_id, card):
    data = get_cached_user(user_id)
    data.setdefault("cards", []).append(card)
    update_cached_user(user_id, data)

def record_signin(user_id, date_str):
    data = get_cached_user(user_id)
    data["last_signin"] = date_str
    update_cached_user(user_id, data)

def get_last_signin(user_id):
    return get_cached_user(user_id).get("last_signin")

# ========== 星球养成 ==========
def get_planet(user_id):
    return get_cached_user(user_id).get("planet")

def update_planet(user_id, planet_data):
    data = get_cached_user(user_id)
    data["planet"] = planet_data
    update_cached_user(user_id, data)

# ========== 人设管理 ==========
def get_current_persona(user_id):
    data = get_cached_user(user_id)
    return data.get("current_persona", "default")

def set_current_persona(user_id, persona_name):
    data = get_cached_user(user_id)
    old = data.get("current_persona", "default")
    if old == persona_name:
        return True
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona_name not in data["persona_memories"]:
        default_mem = {
            "long_memory": {"preferences": {}, "facts": [], "recent_topics": [], "yandere_events": []},
            "yandere": {"level": 0, "next_active_time": 0, "last_interact_time": 0}
        }
        data["persona_memories"][persona_name] = default_mem
    data["current_persona"] = persona_name
    update_cached_user(user_id, data)
    return True

def _get_persona_mem(user_id, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    mems = data.get("persona_memories", {})
    if persona not in mems:
        mems[persona] = {
            "long_memory": {"preferences": {}, "facts": [], "recent_topics": [], "yandere_events": []},
            "yandere": {"level": 0, "next_active_time": 0, "last_interact_time": 0}
        }
        update_cached_user(user_id, data)
    return mems[persona]

def get_long_memory(user_id, persona=None):
    return _get_persona_mem(user_id, persona).get("long_memory", {})

def update_long_memory(user_id, new_memory, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona not in data["persona_memories"]:
        data["persona_memories"][persona] = {}
    data["persona_memories"][persona]["long_memory"] = new_memory
    update_cached_user(user_id, data)

def get_persona_type(persona_name):
    return PERSONALITIES.get(persona_name, {}).get("type", "normal")

# ========== 病娇数值 ==========
def get_yandere_level(user_id, persona=None):
    return _get_persona_mem(user_id, persona).get("yandere", {}).get("level", 0)

def set_yandere_level(user_id, value, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona not in data["persona_memories"]:
        data["persona_memories"][persona] = {}
    if "yandere" not in data["persona_memories"][persona]:
        data["persona_memories"][persona]["yandere"] = {}
    value = max(0, min(100, value))
    data["persona_memories"][persona]["yandere"]["level"] = value
    update_cached_user(user_id, data)

def get_yandere_next_active(user_id, persona=None):
    return _get_persona_mem(user_id, persona).get("yandere", {}).get("next_active_time", 0)

def set_yandere_next_active(user_id, timestamp, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona not in data["persona_memories"]:
        data["persona_memories"][persona] = {}
    if "yandere" not in data["persona_memories"][persona]:
        data["persona_memories"][persona]["yandere"] = {}
    data["persona_memories"][persona]["yandere"]["next_active_time"] = timestamp
    update_cached_user(user_id, data)

def get_yandere_last_interact(user_id, persona=None):
    return _get_persona_mem(user_id, persona).get("yandere", {}).get("last_interact_time", 0)

def set_yandere_last_interact(user_id, timestamp, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona not in data["persona_memories"]:
        data["persona_memories"][persona] = {}
    if "yandere" not in data["persona_memories"][persona]:
        data["persona_memories"][persona]["yandere"] = {}
    data["persona_memories"][persona]["yandere"]["last_interact_time"] = timestamp
    update_cached_user(user_id, data)

def get_yandere_session(user_id, persona=None):
    return _get_persona_mem(user_id, persona).get("yandere", {}).get("session", {})

def set_yandere_session(user_id, session, persona=None):
    data = get_cached_user(user_id)
    if persona is None:
        persona = data.get("current_persona", "default")
    if "persona_memories" not in data:
        data["persona_memories"] = {}
    if persona not in data["persona_memories"]:
        data["persona_memories"][persona] = {}
    if "yandere" not in data["persona_memories"][persona]:
        data["persona_memories"][persona]["yandere"] = {}
    data["persona_memories"][persona]["yandere"]["session"] = session
    update_cached_user(user_id, data)

# ========== 临时对话（持久化到 conversations 目录，重启不丢） ==========
def get_temp_conversation_key(user_id, persona=None, group_id=None):
    """会话键：私聊 = {qq}_私聊_{persona}，群聊 = {qq}_群{group_id}_{persona}。
    不同群的聊天各自独立，避免记忆串味"""
    if persona is None:
        persona = get_current_persona(user_id)
    if group_id is not None:
        return f"{user_id}_群{group_id}_{persona}"
    return f"{user_id}_私聊_{persona}"

def _conv_filename(key):
    safe = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', key)
    return CONVERSATIONS_DIR / f"{safe}.json"

def _load_conversation(key):
    path = _conv_filename(key)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                conv = json.load(f)
            if isinstance(conv, dict) and isinstance(conv.get("messages"), list):
                conv.setdefault("message_count", len(conv["messages"]))
                conv.setdefault("last_active", 0)
                return conv
        except Exception:
            pass
    return {"messages": [], "last_active": time.time(), "message_count": 0}

def _save_conversation(key, conv):
    _atomic_write(_conv_filename(key), conv)

def get_temp_conversation(user_id, persona=None, group_id=None):
    key = get_temp_conversation_key(user_id, persona, group_id)
    with _temp_conversations_lock:
        if key not in _temp_conversations:
            _temp_conversations[key] = _load_conversation(key)
        return _temp_conversations[key]

def add_temp_message(user_id, role, content, persona=None, group_id=None):
    if persona is None:
        persona = get_current_persona(user_id)
    key = get_temp_conversation_key(user_id, persona, group_id)
    conv = get_temp_conversation(user_id, persona, group_id)
    conv["messages"].append({"role": role, "content": content, "timestamp": time.time()})
    conv["last_active"] = time.time()
    conv["message_count"] += 1
    with _dirty_lock:
        _dirty_convs[key] = conv
    _ensure_flush_thread()
    if MEMORY_CONFIG["enable_auto_summary"] and conv["message_count"] >= MEMORY_CONFIG["max_messages_before_summary"]:
        threading.Thread(target=summarize_and_clear, args=(user_id, persona, group_id), daemon=True).start()

def _extract_json(text):
    """从AI输出中提取JSON（容忍markdown代码块和多余文字）"""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.S)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                return None
        return None

def _clear_conversation(key):
    """从内存、写队列、磁盘三处删除会话"""
    with _temp_conversations_lock:
        _temp_conversations.pop(key, None)
    with _dirty_lock:
        _dirty_convs.pop(key, None)
    try:
        path = _conv_filename(key)
        if path.exists():
            path.unlink()
    except Exception:
        pass

def summarize_and_clear(user_id, persona=None, group_id=None):
    if persona is None:
        persona = get_current_persona(user_id)
    key = get_temp_conversation_key(user_id, persona, group_id)
    mode = SYSTEM_CONFIG.get("memory_mode", "ai_summary")
    with _temp_conversations_lock:
        conv = _temp_conversations.get(key)
        if not conv or not conv["messages"]:
            return
        messages = conv["messages"].copy()
    if mode == "ai_summary":
        old_mem = get_long_memory(user_id, persona)
        extra = ""
        if get_persona_type(persona) == "yandere":
            extra = "注意：请重点提取用户提到的其他人名、社交活动、可能引起吃醋的信息。"
        old_summary = (old_mem or {}).get("summary", "")
        prompt = f"""请将以下对话总结为结构化记忆，输出JSON：{{"preferences":{{}},"facts":[],"recent_topics":[],"summary":""}}。
要求：
1. facts / preferences 每条尽量标注发生时间（如「昨天」「3天前」，按消息时间戳判断）；
2. recent_topics 保留最近讨论的话题；
3. summary 用 2~4 句话浓缩这段对话的核心内容（后续将长期引用）；
4. 结合旧摘要合并，不要丢失重要长期信息（如用户姓名、重大事件）。

旧摘要：{old_summary}
旧记忆：{json.dumps(old_mem, ensure_ascii=False)}
新对话：{json.dumps(messages, ensure_ascii=False)}
{extra}"""
        summary = call_ai_with_fallback(prompt, system_override="你是一个记忆总结助手，输出纯JSON。")
        new_mem = _extract_json(summary)
        if new_mem and isinstance(new_mem, dict):
            if "yandere_events" in old_mem:
                new_mem["yandere_events"] = old_mem["yandere_events"]
            # 合并旧记忆中的偏好/事实（AI 可能遗漏）
            for k in ("preferences", "facts"):
                old_val = (old_mem or {}).get(k)
                new_val = new_mem.get(k)
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    for kk, vv in old_val.items():
                        new_val.setdefault(kk, vv)
                elif isinstance(old_val, list) and isinstance(new_val, list):
                    for item in old_val:
                        if item not in new_val:
                            new_val.append(item)
            update_long_memory(user_id, new_mem, persona)
            _clear_conversation(key)
    else:
        raw_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        new_mem = {"preferences": {}, "facts": [], "recent_topics": [], "raw_conversation": raw_text}
        update_long_memory(user_id, new_mem, persona)
        _clear_conversation(key)

# ========== 好友列表缓存 ==========
_friend_cache = {"list": [], "last_update": 0}
_FRIEND_CACHE_TTL = 60

def set_friend_cache(qq_list):
    """由 websocket 拉取的好友列表写入缓存"""
    global _friend_cache
    _friend_cache = {"list": [str(q) for q in qq_list], "last_update": time.time()}

def refresh_friend_list():
    global _friend_cache
    import requests
    now = time.time()
    if now - _friend_cache["last_update"] < _FRIEND_CACHE_TTL:
        return _friend_cache["list"]
    try:
        token = CONFIG.get("friend_api_token") or ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.get("http://127.0.0.1:3000/get_friend_list", headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            _friend_cache["list"] = [str(f["user_id"]) for f in data.get("data", [])]
            _friend_cache["last_update"] = now
    except Exception as e:
        print(f"获取好友列表失败: {e}")
    return _friend_cache["list"]

def is_friend(qq):
    friends = refresh_friend_list()
    return str(qq) in friends

# ========== 兼容别名 ==========
def get_user_stardust(user_id):
    return get_stardust(user_id)

def add_user_stardust(user_id, amount):
    return add_stardust(user_id, amount)

def get_user_cards_count(user_id):
    return get_cards_count(user_id)

def add_user_card(user_id, card):
    return add_card(user_id, card)

def get_user_long_memory(user_id, persona=None):
    return get_long_memory(user_id, persona)

def update_user_long_memory(user_id, new_memory, persona=None):
    return update_long_memory(user_id, new_memory, persona)

def get_user_persona(user_id):
    return get_current_persona(user_id)

def set_user_persona(user_id, persona_name):
    return set_current_persona(user_id, persona_name)

def get_user_last_signin(user_id):
    return get_last_signin(user_id)

def record_user_signin(user_id, date_str):
    return record_signin(user_id, date_str)

def get_yandere_events(user_id, persona=None):
    mem = _get_persona_mem(user_id, persona)
    return mem.get("long_memory", {}).get("yandere_events", [])

def add_yandere_event(user_id, event, persona=None):
    mem = _get_persona_mem(user_id, persona)
    events = mem.get("long_memory", {}).get("yandere_events", [])
    events.append(event)
    events = events[-20:]
    mem["long_memory"]["yandere_events"] = events
    update_long_memory(user_id, mem["long_memory"], persona)

def get_user_stardust_and_cards(user_id):
    return get_stardust(user_id), get_cards_count(user_id)