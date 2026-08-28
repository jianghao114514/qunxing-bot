# core/group_config.py
# 群聊差异化配置：每群一份独立配置（功能开关覆盖 + 群设置），存于 bot_data/group_configs.json
import os
import json
import threading
from core.config import DATA_DIR, FEATURE_SWITCHES

GROUP_CONFIG_FILE = DATA_DIR / "group_configs.json"
_configs = None
_lock = threading.Lock()

# 插件名 -> 功能键映射；未列出的插件不参与开关过滤（始终启用）
PLUGIN_FEATURE_MAP = {
    "signin": "signin", "draw": "draw", "tarot": "tarot", "weather": "weather",
    "joke": "joke", "kfc": "kfc", "emo": "emo", "random_image": "random_img",
    "random_waifu": "random_waifu", "persona": "persona", "feedback": "feedback",
    "gift": "gift", "query": "query", "planet": "planet", "profile": "profile",
    "aichat": "aichat",
}

# 功能键 -> 中文名（与面板全局开关保持一致）
FEATURE_NAMES = {
    "signin": "签到", "draw": "抽卡", "tarot": "塔罗", "aichat": "AI聊天",
    "weather": "天气", "joke": "笑话", "kfc": "疯狂星期四", "emo": "每日emo",
    "random_img": "随机美图", "random_waifu": "每日老婆", "persona": "AI人设",
    "feedback": "问题反馈", "gift": "赠送碎片", "query": "背包查询",
    "planet": "星球养成", "profile": "星空名片", "bilibili": "B站监控",
}


def _load():
    global _configs
    if _configs is None:
        try:
            if GROUP_CONFIG_FILE.exists():
                with open(GROUP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    _configs = json.load(f)
            else:
                _configs = {}
        except Exception as e:
            print(f"加载群配置失败: {e}")
            _configs = {}
    return _configs


def _save():
    global _configs
    cfg = _load()
    try:
        GROUP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = GROUP_CONFIG_FILE.with_suffix(GROUP_CONFIG_FILE.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, GROUP_CONFIG_FILE)
    except Exception as e:
        print(f"保存群配置失败: {e}")


def get_groups():
    return list(_load().keys())


def register_group(group_id, name=None):
    """登记一个群；返回是否为新加入。name 仅在首次建档时生效。"""
    group_id = str(group_id)
    with _lock:
        cfg = _load()
        if group_id in cfg and cfg[group_id].get("name"):
            return False
        entry = cfg.get(group_id) or {}
        if name and not entry.get("name"):
            entry["name"] = str(name)
        if "features" not in entry:
            entry["features"] = {}
        if "settings" not in entry:
            entry["settings"] = {}
        is_new = group_id not in cfg
        cfg[group_id] = entry
        _save()
        return is_new


def get_group_config(group_id):
    group_id = str(group_id)
    cfg = _load().get(group_id)
    if cfg and isinstance(cfg, dict):
        return dict(cfg)
    return None


def set_group_config(group_id, config):
    group_id = str(group_id)
    with _lock:
        cfg = _load()
        default = {"features": {}, "settings": {}}
        entry = dict(default)
        entry.update(config or {})
        entry["group_id"] = group_id
        cfg[group_id] = entry
        _save()


def delete_group_config(group_id):
    group_id = str(group_id)
    with _lock:
        cfg = _load()
        if group_id in cfg:
            cfg.pop(group_id, None)
            _save()
            return True
    return False


def group_features(group_id):
    """返回该群的功能开关覆盖 dict（为空表示全部继承全局）。"""
    group_id = str(group_id)
    cfg = _load().get(group_id) or {}
    return cfg.get("features") or {}


def feature_enabled(group_id, key):
    """最终决定某功能是否启用：群覆盖 -> 全局 -> 默认 True。group_id 为 None（私聊）时只用全局。"""
    if group_id is not None:
        g = group_features(group_id)
        if key in g:
            return bool(g[key])
    return bool(FEATURE_SWITCHES.get(key, True))


def plugin_feature_key(plugin_name):
    return PLUGIN_FEATURE_MAP.get(plugin_name)


def get_setting(group_id, key, default=None):
    group_id = str(group_id)
    cfg = _load().get(group_id) or {}
    settings = cfg.get("settings") or {}
    return settings.get(key, default)


def welcome_message_for(group_id):
    val = get_setting(group_id, "welcome_message")
    return val if val not in (None, "") else None


def welcome_bonus_for(group_id):
    val = get_setting(group_id, "welcome_bonus")
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def model_name_for(group_id):
    val = get_setting(group_id, "model_name")
    return val if val not in (None, "") else None


def display_name_for(group_id):
    val = get_setting(group_id, "bot_display_name")
    return val if val not in (None, "") else None


# ========== 版本比较（供“检查更新”使用） ==========
def _parse_ver(v):
    parts = []
    for seg in str(v or "").lstrip("vV").split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return parts


def is_newer(latest, current):
    latest_parts = _parse_ver(latest)
    current_parts = _parse_ver(current)
    n = max(len(latest_parts), len(current_parts))
    latest_parts += [0] * (n - len(latest_parts))
    current_parts += [0] * (n - len(current_parts))
    return latest_parts > current_parts
