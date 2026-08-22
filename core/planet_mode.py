# core/planet_mode.py
# 星球养成共享常量与小工具：避免 plugins/planet.py 与 core/planet_image.py 循环导入
import time
from core.config import SYSTEM_CONFIG


def cfg(key, default):
    val = SYSTEM_CONFIG.get(key, default)
    try:
        if isinstance(default, float):
            return float(val)
        return int(val)
    except (TypeError, ValueError):
        return default


# 星球性格：mult 用于适配各项 倍率（collect/exp/event/decay/bond/sulk）
TEMPERAMENTS = {
    "活泼": {"desc": "光芒跳跃，产出 +10%",            "mult": {"collect": 1.10, "exp": 1.00, "event": 1.10, "decay": 1.00, "bond": 1.00, "sulk": 1.00}},
    "沉稳": {"desc": "默默积蓄，能量衰减 -20%",        "mult": {"collect": 1.00, "exp": 1.00, "event": 1.00, "decay": 0.80, "bond": 1.00, "sulk": 1.00}},
    "贪吃": {"desc": "爱星尘，喂养经验 +10%",          "mult": {"collect": 1.00, "exp": 1.10, "event": 1.00, "decay": 1.00, "bond": 1.00, "sulk": 1.00}},
    "黏人": {"desc": "黏着你，亲密度增长 +20%",        "mult": {"collect": 1.00, "exp": 1.00, "event": 1.00, "decay": 1.00, "bond": 1.20, "sulk": 1.00}},
    "傲娇": {"desc": "嘴硬心软，隔久不理惩罚减半",     "mult": {"collect": 1.00, "exp": 1.00, "event": 1.00, "decay": 1.00, "bond": 1.00, "sulk": 0.50}},
    "忧郁": {"desc": "心思细腻，触发事件更频繁",       "mult": {"collect": 1.00, "exp": 1.00, "event": 1.20, "decay": 1.00, "bond": 1.00, "sulk": 1.00}},
}

# 亲密度称号（按累计亲密度）
BOND_TITLES = [(0, "初识"), (50, "相伴"), (150, "知己"), (350, "挚友"), (800, "命运")]

# 亲密度对产出的加成：bond 越高产出越高，上限 +50%
def bond_mult(bond):
    bond = bond or 0
    return 1.0 + min(0.5, bond / 1600.0)


def bond_title(bond):
    bond = bond or 0
    title = BOND_TITLES[0][1]
    for threshold, name in BOND_TITLES:
        if bond >= threshold:
            title = name
    return title


def temperament_mult(planet, key):
    t = TEMPERAMENTS.get(planet.get("temperament", "活泼"))
    if not t:
        return 1.0
    return float(t["mult"].get(key, 1.0))


def pending_estimate(planet, now=None):
    """计算当前「可收取产出」的预估值，统一供状态文字与卡片图使用。
    规则与实际收菜一致：时长封顶、能量<30 减半、陨石雨×boost、亲密度加成、性格加成。
    不包含「磨蹭惩罚」（那是实际收菜时的即时折扣）。"""
    now = now if now is not None else time.time()
    level = planet.get("level", 1)
    energy = planet.get("energy", 100)
    max_hours = cfg("planet_collect_max_hours", 24)
    per_hour = cfg("planet_collect_per_hour", 1)
    hours = max(0.0, (now - planet.get("last_collect", now)) / 3600.0)
    hours = min(hours, max_hours)
    amount = hours * level * per_hour
    if energy < 30:
        amount *= 0.5
    amount *= planet.get("collect_boost", 1)
    amount *= bond_mult(planet.get("bond", 0))
    amount *= temperament_mult(planet, "collect")
    return int(amount)
