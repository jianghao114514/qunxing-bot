import os
import json
from copy import deepcopy
from pathlib import Path
import sys


# 获取启动脚本的绝对路径（main.py）
ROOT_DIR = Path(sys.argv[0]).parent.resolve()
DATA_DIR = ROOT_DIR / "bot_data"
USERS_DIR = DATA_DIR / "users"
CONVERSATIONS_DIR = DATA_DIR / "conversations"
CONFIG_FILE = DATA_DIR / "config.json"

# 默认配置（不含任何个人密钥：真实值一律存于本机 bot_data/config.json，首次运行自动生成）
DEFAULT_CONFIG = {
    "ws_url": "",
    "bot_qq": "",
    "master_qq": "",
    "alert_group": "",
    "api_key": "",
    "base_url": "https://openrouter.ai/api/v1",
    "model_name": "microsoft/phi-3-mini-128k:free",
    "welcome_bonus": 10,
    "welcome_message": "",
    "timeout": {"chat": 20, "story": 60},
    "email": {
        "enable": False,
        "smtp_server": "",
        "smtp_port": 465,
        "sender": "",
        "password": "",
        "receiver": ""
    },
    "reconnect_delay": 5,
    "max_history": 50,
    "max_reconnect_attempts": 10,
    "reminder_days": 7,
    "web_port": 5000,
    "web_password": "",
    "web_desktop_enabled": True,
    "web_desktop_disable_gpu": False,
    "web_ui_quality": "high",
    "web_guide_auto": True,
    "web_auto_open_browser": True,
    "web_window_width": 1320,
    "web_window_height": 880,
    "friend_api_token": "",
    "app_id": "",
    "app_secret": "",
    "app_token": "",
    "napcat_watchdog_enabled": True,
    "napcat_exe": "",
    "napcat_qq": "",
    "system_name": "群星",
    "data_dir": str(DATA_DIR),
    "users_dir": str(USERS_DIR),
    "config_file": str(CONFIG_FILE)
}

DEFAULT_PERSONALITIES = {
    "default": {"prompt": "你是一个友好的AI助手，回复简洁、亲切、有趣。不使用任何emoji或颜文字。", "type": "normal"},
    "猫娘": {"prompt": "你是一只可爱的猫娘，喜欢用喵~结尾，说话软萌，喜欢撒娇。不使用emoji或颜文字。", "type": "normal"},
    "知心姐姐": {"prompt": "你是一个温柔体贴的知心姐姐，善于倾听和开导。不使用emoji或颜文字。", "type": "normal"},
    "科学助手": {"prompt": "你是一个严谨的科学助手，回复注重逻辑和事实。不使用emoji或颜文字。", "type": "normal"},
    "杦": {"prompt": "西方玄幻世界的史莱姆娘...不使用emoji或颜文字。", "type": "normal"}
}

# 全局变量（运行时填充）
CONFIG = deepcopy(DEFAULT_CONFIG)
PERSONALITIES = DEFAULT_PERSONALITIES.copy()
FEATURE_SWITCHES = {}
SYSTEM_CONFIG = {}
MEMORY_CONFIG = {
    "timeout_seconds": 300,
    "max_messages_before_summary": 10,
    "enable_auto_summary": True
}
CUSTOM_MENU_TEXTS = {}

def init_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    USERS_DIR.mkdir(exist_ok=True)
    CONVERSATIONS_DIR.mkdir(exist_ok=True)

def load_config():
    global PERSONALITIES, FEATURE_SWITCHES, SYSTEM_CONFIG, MEMORY_CONFIG, CUSTOM_MENU_TEXTS
    init_dirs()
    if not CONFIG_FILE.exists():
        default = {
            "web_password": "",
    "system_name": "群星",
    "web_theme": "light",
    "bot_display_name": "",
    "currency_name": "星尘",
            "feature_switches": {
                "signin": True, "draw": True, "tarot": True, "aichat": True,
                "weather": True, "joke": True, "kfc": True, "emo": True,
                "random_img": True, "random_waifu": True,
                "persona": True, "feedback": True, "gift": True, "query": True,
                "planet": True, "profile": True
            },
            "system_config": {
                "signin_min_reward": 10, "signin_max_reward": 100,
                "draw_cost": 100, "tarot_cost": 15,
                "ssr_prob": 0.05, "sr_prob": 0.15, "r_prob": 0.8,
                "planet_care_cost": 10, "planet_care_exp": 25, "planet_care_energy": 10,
                "planet_rename_cost": 50, "planet_collect_per_hour": 1,
                "planet_collect_max_hours": 24, "planet_max_energy": 100, "planet_max_level": 10,
                "planet_energy_decay": 4, "planet_event_enabled": True,
                "planet_event_min_interval": 3600, "planet_event_prob": 0.4,
                "planet_sulk_days": 5, "planet_sulk_penalty": 0.7,
                "planet_visit_care_exp": 5,
                "ssr_prob": 0.05, "sr_prob": 0.15, "r_prob": 0.8,
                "memory_timeout_seconds": MEMORY_CONFIG["timeout_seconds"],
                "memory_max_messages": MEMORY_CONFIG["max_messages_before_summary"],
                "memory_mode": "ai_summary",
                "yandere_active_enabled": True,
                "yandere_active_min_interval": 1800,
                "yandere_active_max_interval": 10800,
                "yandere_active_cooldown": 60,
                "yandere_typing_min": 1.5,
                "yandere_typing_max": 5.0,
                "yandere_active_start_hour": 8,
                "yandere_active_end_hour": 23,
                "yandere_active_skip_prob": 0.2,
                "yandere_session_max_msgs": 12,
                "yandere_session_max_minutes": 40
            },
            "personalities": DEFAULT_PERSONALITIES,
            "api_providers": [],
            "custom_menu_texts": {},
            "yandere_whitelist": [],
            "napcat_watchdog_enabled": False,
            "napcat_exe": "",
            "napcat_qq": "",
            "app_id": "",
            "app_secret": "",
            "app_token": ""
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 迁移 personalities 格式
    old_personalities = data.get("personalities", {})
    new_personalities = {}
    for name, val in old_personalities.items():
        if isinstance(val, str):
            new_personalities[name] = {"prompt": val, "type": "normal"}
        elif isinstance(val, dict):
            if "type" not in val:
                val["type"] = "normal"
            new_personalities[name] = val
        else:
            new_personalities[name] = {"prompt": str(val), "type": "normal"}
    # 原地更新全局字典，保证所有已导入的模块引用（插件等）实时生效
    PERSONALITIES.clear()
    PERSONALITIES.update(new_personalities)
    FEATURE_SWITCHES.clear()
    FEATURE_SWITCHES.update(data.get("feature_switches", {}))
    SYSTEM_CONFIG.clear()
    SYSTEM_CONFIG.update(data.get("system_config", {}))
    changed = False
    # 新星球键回写：旧 config.json 没有的 system_config 键用默认值补全并写盘
    planet_defaults = {
        "planet_energy_decay": 4, "planet_event_enabled": True,
        "planet_event_min_interval": 3600, "planet_event_prob": 0.4,
        "planet_sulk_days": 5, "planet_sulk_penalty": 0.7,
        "planet_visit_care_exp": 5,
    }
    missing = {k: v for k, v in planet_defaults.items() if k not in SYSTEM_CONFIG}
    if missing:
        SYSTEM_CONFIG.update(missing)
        data.setdefault("system_config", {}).update(missing)
        changed = True
    CUSTOM_MENU_TEXTS.clear()
    CUSTOM_MENU_TEXTS.update(data.get("custom_menu_texts", {}))
    CONFIG["web_password"] = data.get("web_password", "")
    CONFIG["system_name"] = data.get("system_name", "群星")
    # ===== 连接与密钥统一从 config.json 读取（缺失则用代码内默认值并回写，便于查看） =====
    conn_keys = ["ws_url", "api_key", "base_url", "model_name", "welcome_bonus",
                 "welcome_message", "timeout", "reconnect_delay", "max_history", "reminder_days",
                 "web_port", "friend_api_token", "bot_qq", "master_qq",
                 "web_desktop_enabled", "web_desktop_disable_gpu",
                 "web_ui_quality", "web_guide_auto",
                 "web_theme", "bot_display_name", "currency_name",
                 "web_window_width", "web_window_height", "web_auto_open_browser",
                 "napcat_watchdog_enabled", "napcat_exe", "napcat_qq",
                 "app_id", "app_secret", "app_token"]
    for key in conn_keys:
        if key in data:
            CONFIG[key] = data[key]
        else:
            data[key] = CONFIG.get(key)
            changed = True
    if isinstance(data.get("email"), dict):
        CONFIG["email"] = dict(data["email"])
    else:
        data["email"] = dict(CONFIG.get("email", {}))
        changed = True
    # 旧键迁移：web_desktop_low_perf → web_ui_quality
    if "web_desktop_low_perf" in data:
        old = data.pop("web_desktop_low_perf")
        data["web_ui_quality"] = "fast" if old else "high"
        CONFIG["web_ui_quality"] = data["web_ui_quality"]
        changed = True
    if changed:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    MEMORY_CONFIG["timeout_seconds"] = SYSTEM_CONFIG.get("memory_timeout_seconds", 300)
    MEMORY_CONFIG["max_messages_before_summary"] = SYSTEM_CONFIG.get("memory_max_messages", 10)
    # 确保API提供商：仅当存在默认 API Key 时才补种默认提供商（无 key 则留空，由用户自行添加）
    providers = data.get("api_providers", [])
    if not providers and CONFIG.get("api_key"):
        providers.append({
            "id": 1,
            "name": "默认Phi3",
            "api_key": CONFIG["api_key"],
            "base_url": CONFIG["base_url"],
            "model_name": "microsoft/phi-3-mini-128k:free",
            "priority": 1,
            "max_requests_per_day": 0,
            "enabled": True,
            "used_today": 0,
            "fail_count": 0,
            "last_reset_date": None,
            "is_public_welfare": True,
            "auth_type": "bearer",
            "timeout": 30,
            "provider_name": "OpenRouter",
            "admin_url": "https://openrouter.ai/activity"
        })
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def save_config():
    data = {
        "web_password": CONFIG.get("web_password", ""),
        "system_name": CONFIG.get("system_name", "群星"),
        "ws_url": CONFIG.get("ws_url", ""),
        "api_key": CONFIG.get("api_key", ""),
        "base_url": CONFIG.get("base_url", ""),
        "model_name": CONFIG.get("model_name", ""),
        "email": CONFIG.get("email", {}),
        "welcome_bonus": CONFIG.get("welcome_bonus", 10),
        "welcome_message": CONFIG.get("welcome_message", ""),
        "timeout": CONFIG.get("timeout", {}),
        "reconnect_delay": CONFIG.get("reconnect_delay", 5),
        "max_history": CONFIG.get("max_history", 50),
        "reminder_days": CONFIG.get("reminder_days", 7),
        "web_port": CONFIG.get("web_port", 5000),
        "bot_qq": CONFIG.get("bot_qq", ""),
        "master_qq": CONFIG.get("master_qq", ""),
        "web_theme": CONFIG.get("web_theme", "light"),
        "bot_display_name": CONFIG.get("bot_display_name", ""),
        "currency_name": CONFIG.get("currency_name", "星尘"),
        "web_desktop_enabled": CONFIG.get("web_desktop_enabled", True),
        "web_desktop_disable_gpu": CONFIG.get("web_desktop_disable_gpu", False),
        "web_ui_quality": CONFIG.get("web_ui_quality", "high"),
        "web_guide_auto": CONFIG.get("web_guide_auto", True),
        "web_auto_open_browser": CONFIG.get("web_auto_open_browser", True),
        "web_window_width": CONFIG.get("web_window_width", 1320),
        "web_window_height": CONFIG.get("web_window_height", 880),
        "friend_api_token": CONFIG.get("friend_api_token", ""),
        "app_id": CONFIG.get("app_id", ""),
        "app_secret": CONFIG.get("app_secret", ""),
        "app_token": CONFIG.get("app_token", ""),
        "napcat_watchdog_enabled": CONFIG.get("napcat_watchdog_enabled", True),
        "napcat_exe": CONFIG.get("napcat_exe", ""),
        "napcat_qq": CONFIG.get("napcat_qq", CONFIG.get("bot_qq", "")),
        "feature_switches": FEATURE_SWITCHES,
        "system_config": SYSTEM_CONFIG,
        "personalities": PERSONALITIES,
        "api_providers": get_all_providers(),
        "custom_menu_texts": CUSTOM_MENU_TEXTS,
        "yandere_whitelist": _get_yandere_whitelist()
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_yandere_whitelist():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("yandere_whitelist", [])

def get_all_providers():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("api_providers", [])

def currency_name():
    """星尘碎片的自定义名称（默认 星尘）"""
    return CONFIG.get("currency_name") or "星尘"

def bot_display_name():
    """机器人显示名称：优先自定义，否则用系统名"""
    return CONFIG.get("bot_display_name") or CONFIG.get("system_name") or "群星"

def save_providers(providers):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["api_providers"] = providers
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)