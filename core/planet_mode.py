# core/planet_mode.py
# 星球养成共享常量与小工具：避免 plugins/planet.py 与 core/planet_image.py 循环导入
import random
import time
from datetime import datetime
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


# 星球稀有度：collect 影响产出，bond 影响亲密度增长
RARITIES = {
    "普通": {"collect": 1.00, "bond": 1.00, "desc": "平凡却坚韧，一步一个脚印"},
    "精良": {"collect": 1.08, "bond": 1.08, "desc": "微光闪烁，运势不错"},
    "稀有": {"collect": 1.16, "bond": 1.14, "desc": "蕴含星尘，成长迅速"},
    "史诗": {"collect": 1.25, "bond": 1.20, "desc": "罕见星河铸就，底蕴深厚"},
    "传说": {"collect": 1.40, "bond": 1.30, "desc": "传说级的星之子，注定不凡"},
}
_RARITY_KEYS = list(RARITIES)
_RARITY_WEIGHTS = [45, 28, 18, 7, 2]


def random_rarity():
    return random.choices(_RARITY_KEYS, weights=_RARITY_WEIGHTS)[0]


def rarity_mult(planet):
    r = RARITIES.get(planet.get("rarity", "普通"))
    return float(r["collect"]) if r else 1.0


def rarity_bond_mult(planet):
    r = RARITIES.get(planet.get("rarity", "普通"))
    return float(r["bond"]) if r else 1.0


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


# ========== 成就系统 ==========
# key -> (名称, 描述, 判定字段, 阈值)
ACHIEVEMENT_DEFS = [
    ("bond_50", "心心相印", "亲密度达到 50", "bond", 50),
    ("bond_150", "知己之交", "亲密度达到 150", "bond", 150),
    ("bond_350", "执手之约", "亲密度达到 350", "bond", 350),
    ("bond_800", "命运之伴", "亲密度达到 800", "bond", 800),
    ("streak_7", "七日之约", "连续照料 7 天", "streak", 7),
    ("streak_30", "恒久之约", "连续照料 30 天", "streak", 30),
    ("stage2", "彗星之始", "进化到 彗星 形态", "stage", 2),
    ("stage3", "行星之光", "进化到 行星 形态", "stage", 3),
    ("stage4", "恒星之焰", "进化到 恒星 形态", "stage", 4),
    ("stage5", "超新星之辉", "进化到 超新星 形态", "stage", 5),
    ("max_level", "满级星球", "达到 Lv.10", "level", 10),
    ("spent_500", "星尘投入", "累计投入 500 碎片", "spent", 500),
    ("spent_2000", "挥金如土", "累计投入 2000 碎片", "spent", 2000),
]


def achievement_mult(planet):
    """每解锁 1 个成就 +1% 产出，上限 +30%"""
    count = len(planet.get("achievements", []) or [])
    return 1.0 + min(0.30, count * 0.01)


def check_achievements(planet):
    """返回本次新解锁的成就列表 [{'key','name','desc'}]（不含已解锁的）"""
    unlocked = set(planet.get("achievements", []) or [])
    news = []
    for key, name, desc, field, threshold in ACHIEVEMENT_DEFS:
        if key in unlocked:
            continue
        val = planet.get(field)
        if val is None:
            continue
        if field == "spent":
            # 累计投入在 stardust_spent 字段上，按键名 spent 映射
            val = planet.get("stardust_spent", 0)
        if val >= threshold:
            news.append({"key": key, "name": name, "desc": desc})
    return news


# ========== 每日活跃任务 ==========
DAILY_TASK_DEFS = [
    ("feed", "照料星球", "今日照料 / 喂星球 1 次"),
    ("collect", "收取产出", "今日收取产出 1 次"),
    ("visit", "好友互动", "今日拜访 / 帮忙照料好友 1 次"),
]


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def reset_daily(planet):
    """确保 daily 结构是今天的；跨天自动重置。返回 planet（原地修改）。"""
    daily = planet.get("daily")
    if not daily or daily.get("date") != today_str():
        planet["daily"] = {"date": today_str(), "progress": {}}
    return planet


def mark_daily(planet, key):
    """标记某每日任务完成；返回是否本次新完成。"""
    reset_daily(planet)
    progress = planet["daily"].setdefault("progress", {})
    if progress.get(key):
        return False
    progress[key] = True
    return True


def daily_done(planet):
    reset_daily(planet)
    progress = planet["daily"].get("progress", {})
    return all(progress.get(key) for key, _, _ in DAILY_TASK_DEFS)


def daily_count(planet):
    reset_daily(planet)
    progress = planet["daily"].get("progress", {})
    return sum(1 for key, _, _ in DAILY_TASK_DEFS if progress.get(key))


def pending_estimate(planet, now=None):
    """计算当前「可收取产出」的预估值，统一供状态文字与卡片图使用。
    规则与实际收菜一致：时长封顶、能量<30 减半、陨石雨×boost、亲密度/性格/稀有度/成就加成。
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
    amount *= rarity_mult(planet)
    amount *= achievement_mult(planet)
    return int(amount)
