# core/card.py
# 卡牌对战核心：从抽卡产出的 "{稀有度}-{名字}" 卡串自动推导 属性/定位/数值/技能。
# 目标：平衡由 稀有度曲线 + 属性循环克制 + 定位搭配 决定，无需逐张手调。
import random


# 五行相克：金→木→土→水→火→金
ELEMENTS = ["金", "木", "水", "火", "土"]
_ELEMENT_BEATS = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}

# 关键词 -> 属性（覆盖现有卡池 + 便于未来扩词库）
_ELEM_KEYWORDS = [
    (("火", "炎", "光", "焰", "创世"), "火"),
    (("水", "冰", "霜", "海", "深渊", "史莱姆"), "水"),
    (("风", "时", "旅", "灵", "影", "哥布林"), "风"),
    (("雷", "电", "龙", "星", "城"), "雷"),
    (("土", "岩", "石", "大地", "路人"), "土"),
    (("金", "铁", "剑", "机械", "钢", "锋"), "金"),
    (("森", "林", "草", "木", "精灵"), "木"),
]

# 关键词 -> 定位
_ROLE_KEYWORDS = [
    (("守护", "盾", "防", "战警", "卫士"), "防"),
    (("魔神", "剑", "刃", "拳", "战", "攻击", "精灵", "旅者"), "攻"),
    (("巫", "灵", "辅", "光", "星", "旅", "时", "歌"), "辅"),
]


def _pick_by_keywords(name, mappings, default):
    for keywords, val in mappings:
        if any(kw in name for kw in keywords):
            return val
    return default


def element_for(name):
    e = _pick_by_keywords(name, _ELEM_KEYWORDS, None)
    if e:
        return e
    return random.choice(ELEMENTS)


def role_for(name):
    r = _pick_by_keywords(name, _ROLE_KEYWORDS, None)
    if r:
        return r
    return random.choice(["攻", "防", "辅"])


# 技能池：简单、可预期。name/desc/效果类型
SKILL_POOL = [
    {"key": "atk", "name": "强攻", "desc": "攻击+15%"},
    {"key": "hp", "name": "坚韧", "desc": "血量+15%"},
    {"key": "crit", "name": "暴击", "desc": "18%概率伤害×1.8"},
    {"key": "lifesteal", "name": "吸血", "desc": "造成伤害的25%转为生命"},
    {"key": "shield", "name": "护盾", "desc": "受到伤害-25%"},
]

def _skills_for(tier):
    # 稀有度决定技能数量：R 0~1，SR 1，SSR 2
    n = {"R": random.randint(0, 1), "SR": 1, "SSR": 2}.get(tier, 1)
    return random.sample(SKILL_POOL, min(n, len(SKILL_POOL)))


# 稀有度基础值（攻击/血量）
_BASE = {"R": (25, 60), "SR": (45, 100), "SSR": (75, 155)}

def _role_adj(role):
    # 攻 / 防 / 辅 / 盾：攻击与血量权重不同
    return {
        "攻": (1.25, 0.72),
        "防": (0.72, 1.28),
        "辅": (1.00, 1.00),
        "盾": (0.55, 1.45),
    }.get(role, (1.0, 1.0))


def _skill_bonus(power, skills):
    bonus = 0
    for s in skills:
        if s["key"] == "atk":
            bonus += int(power * 0.15)
        elif s["key"] == "hp":
            bonus += int(power * 0.15)
        elif s["key"] == "crit":
            bonus += int(power * 0.12)
        elif s["key"] == "lifesteal":
            bonus += int(power * 0.10)
        elif s["key"] == "shield":
            bonus += int(power * 0.10)
    return bonus


def parse_card(card_str, seed=0):
    """把 'SSR-星尘守护者' 解析为卡牌 dict。seed 用于稳定随机（同卡同名同属性）。"""
    if not isinstance(card_str, str) or "-" not in card_str:
        return None
    tier, name = card_str.split("-", 1)
    tier = tier.strip().upper()
    if tier not in _BASE:
        tier = "R"
    name = name.strip() or "无名之卡"
    rng = random.Random(abs(hash((name, tier, seed))) % (2 ** 31))
    element = element_for(name)
    role = role_for(name)
    a0, h0 = _BASE[tier]
    aa, hh = _role_adj(role)
    attack = int(a0 * aa)
    hp = int(h0 * hh)
    skills = _skills_for(tier)
    power = attack + int(hp * 0.5) + _skill_bonus(attack + int(hp * 0.5), skills)
    return {
        "id": card_str,
        "name": name,
        "tier": tier,
        "element": element,
        "role": role,
        "attack": attack,
        "hp": hp,
        "skills": [s["name"] for s in skills],
        "power": power,
        "seed": seed,
    }


def parse_deck(cards, limit=5):
    """把玩家 cards 列表解析为卡组（最多 limit 张）。返回 [card,...]。"""
    deck = []
    for i, c in enumerate(cards or []):
        card = parse_card(c, seed=i)
        if card:
            deck.append(card)
        if len(deck) >= limit:
            break
    return deck


def cycle_bonus(a_elem, b_elem):
    """a 对 b 的属性克制系数：克制 ×1.5，被克 ×0.75，其余 ×1.0"""
    if _ELEMENT_BEATS.get(a_elem) == b_elem:
        return 1.5
    if _ELEMENT_BEATS.get(b_elem) == a_elem:
        return 0.75
    return 1.0


def would_beat(a_elem, b_elem):
    return cycle_bonus(a_elem, b_elem) > 1.0


def team_power(deck, enemy_deck=None):
    """队伍战力：卡牌自身战力；若给敌方卡组，则计入属性克制加成。"""
    total = sum(c["power"] for c in deck)
    if not enemy_deck:
        return total
    bonus = 0
    for a in deck:
        best = 1.0
        for b in enemy_deck:
            best = max(best, cycle_bonus(a["element"], b["element"]))
        bonus += int(a["power"] * (best - 1.0))
    return total + bonus


def element_name(e):
    return e
