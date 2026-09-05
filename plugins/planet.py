# plugins/planet.py
import base64
import random
import re
import time
from datetime import datetime, timedelta
from plugins.base import BasePlugin
from core.config import CONFIG, SYSTEM_CONFIG
from core.database import get_stardust, add_stardust, get_planet, update_planet, is_friend, get_nickname, list_planets
from core.planet_image import build_planet_card, STAGE_NAMES, STAGE_ICONS
from core.planet_mode import (TEMPERAMENTS, BOND_TITLES, bond_title, bond_mult,
                              temperament_mult, pending_estimate,
                              random_rarity, rarity_mult, rarity_bond_mult,
                              check_achievements, reset_daily, mark_daily, daily_count,
                              daily_done, DAILY_TASK_DEFS, ACHIEVEMENT_DEFS, today_str, RARITIES)

STAGE_UNLOCKS = [1, 3, 5, 8, 10]   # 各形态对应解锁等级

NAME_A = ["小", "阿", "星", "蓝", "璃", "幽", "绯", "皓", "灵", "幻"]
NAME_B = ["蓝", "辰", "光", "耀", "羽", "澜", "烬", "霜", "萤", "绯"]

CARE_TEXTS_HIGH = [
    "「{name}」吸饱了星尘，开心地转了三个圈～",
    "「{name}」的温度悄悄升高，像是在对你撒娇。",
    "「{name}」发出了咕噜咕噜的声音，听，是满足的星鸣。",
    "「{name}」周围飘起细碎的光点，仿佛在说谢谢你。",
    "「{name}」轻轻蹭了蹭你的手指，能量满满！",
]
CARE_TEXTS_MID = [
    "「{name}」慢慢吸收着星尘，打了个小小的饱嗝。",
    "「{name}」的光泽柔和了几分，看起来精神多了。",
    "「{name}」表面泛起一圈涟漪，像是笑了。",
    "「{name}」安静地吸收着，偶尔闪两下回应你。",
]
CARE_TEXTS_LOW = [
    "「{name}」疲惫地蜷成一团，好想被好好照顾……",
    "「{name}」的光晕有点暗淡，需要你的陪伴。",
    "「{name}」小声呜咽着，喂星尘的样子惹人怜爱。",
]
LEVEL_UP_TEXTS = [
    "「{name}」发出一阵明亮的光芒，升级了！现在 Lv.{level}",
    "「{name}」欢呼着爆发出一圈光晕，Lv.{level}！",
]
STAGE_UP_TEXTS = [
    "「{name}」的光芒越来越亮，蜕变成了【{stage}】！",
    "轰的一声，星尘汇聚——「{name}」进化成了【{stage}】！",
]
COLLECT_TEXTS = [
    "「{name}」抖了抖身子，掉出了 {amount} 星尘碎片！",
    "「{name}」把沉淀的星尘轻轻推到你手心：{amount} 碎片。",
    "「{name}」打了个哈欠，你收获了 {amount} 星尘碎片。",
]
NO_COLLECT_TEXTS = [
    "「{name}」还没攒够，过会儿再来收取吧～",
    "「{name}」眨了眨眼：再等等嘛，还没长出来呢。",
]
LOW_ENERGY_TEXTS = [
    "「{name}」的能量太低，只勉强结出了 {amount} 碎片……",
    "「{name}」有气无力地交给你 {amount} 碎片，记得多陪陪它。",
]
SULK_TEXTS = [
    "「{name}」哼了一声别过头去：这么久不理人家，产出先打七折！",
    "「{name}」闷闷不乐地盘着星尘：{amount} 碎片，下次记得常回来看我。",
]
LOW_FEED_TEXTS = [
    "「{name}」虚弱地靠在你手心里，你的照料让它格外感动！",
    "「{name}」泪汪汪地吸收着星尘，虚弱之下的照料效果翻倍！",
]
EVENT_METEOR_TEXTS = [
    "☄ 流星雨划过夜空！「{name}」沐浴在星雨中，下次产出翻 5 倍！",
    "☄ 一场陨石雨落在「{name}」周围，珍贵的星尘遍地都是，下次产出 ×5！",
]
EVENT_WHALE_TEXTS = [
    "🐋 一头星鲸游过你头顶，喷出的星尘落了你一身：+{amount} 碎片！",
    "🐋 路过的星鲸好奇地围着「{name}」绕了一圈，留下大把星尘：+{amount}！",
]
EVENT_MERCHANT_TEXTS = [
    "🛸 拍卖商人落在你的星球旁，出价 {price} 碎片收购「{name}」，发送「卖掉星球」即可成交（6 小时内有效）！",
    "🛸 一位神秘的商人看上了「{name}」，愿意出 {price} 碎片收购！发「卖掉星球」卖掉它（限时 6 小时）。",
]
EVENT_AURORA_TEXTS = [
    "🌌 一抹极光掠过天际！「{name}」被温柔的光芒笼罩，能量大幅回升，亲密度上升！",
    "🌌 星之子发来祝福——极光涤荡了「{name}」的疲惫，能量+40，亲密度+15！",
]
EVENT_GEYSER_TEXTS = [
    "⛲ 一座星尘喷泉在「{name}」脚下喷涌而出！星尘四溅，你收获颇丰：+{amount} 碎片！",
    "⛲ 大地深处涌出澄澈的星尘之泉，「{name}」沐浴其中，你捡到了 {amount} 碎片！",
]
SOLD_TEXTS = [
    "「{name}」被你送上了商人的飞船，{price} 碎片到账。它回望你一眼，化作一颗新的星球坠入你的怀中！",
    "交易达成！{price} 碎片到手。旧主人走了，但一颗全新的星球正等着你取名字……",
]
EXPIRED_TEXTS = [
    "🕐 那位商人已经离开星海，报价也随风消散了～下次遇到要抓准时机呀。",
    "「{name}」歪着脑袋告诉你：商人早就走了，报价过期啦。",
]

EVENT_NAMES = ["meteor", "whale", "merchant", "aurora", "geyser"]


def _roll_event(planet, uid, now):
    """满足冷却则按概率触发随机事件，返回描述行列表。不主动写盘，由调用方 update_planet。"""
    if not _cfg("planet_event_enabled", 1):
        return []
    min_interval = _cfg("planet_event_min_interval", 3600)
    if planet.get("last_event", 0) and now - planet.get("last_event", 0) < min_interval:
        return []
    prob = _cfg("planet_event_prob", 0.4) * temperament_mult(planet, "event")
    prob = min(1.0, max(0.0, prob))
    if random.random() > prob:
        return []
    planet["last_event"] = now
    ev = random.choice(EVENT_NAMES)
    if ev == "meteor":
        planet["collect_boost"] = 5
        return [random.choice(EVENT_METEOR_TEXTS).format(name=planet["name"])]
    if ev == "whale":
        amount = planet["level"] * random.randint(10, 40)
        add_stardust(uid, amount)
        planet["bond"] = planet.get("bond", 0) + _cfg("planet_bond_per_whale", 12)
        return [random.choice(EVENT_WHALE_TEXTS).format(name=planet["name"], amount=amount)]
    if ev == "aurora":
        max_energy = _cfg("planet_max_energy", 100)
        planet["energy"] = min(max_energy, planet.get("energy", 0) + 40)
        planet["bond"] = planet.get("bond", 0) + _cfg("planet_bond_per_aurora", 15)
        return [random.choice(EVENT_AURORA_TEXTS).format(name=planet["name"])]
    if ev == "geyser":
        amount = planet["level"] * random.randint(20, 60)
        add_stardust(uid, amount)
        planet["bond"] = planet.get("bond", 0) + _cfg("planet_bond_per_geyser", 18)
        return [random.choice(EVENT_GEYSER_TEXTS).format(name=planet["name"], amount=amount)]
    # merchant
    price = max(100, int(planet["stardust_spent"] * 1.5))
    planet["merchant_offer"] = price
    planet["merchant_expire"] = now + _cfg("planet_merchant_expire_hours", 6) * 3600
    return [random.choice(EVENT_MERCHANT_TEXTS).format(name=planet["name"], price=price)]


def _cfg(key, default):
    val = SYSTEM_CONFIG.get(key, default)
    try:
        if isinstance(default, float):
            return float(val)
        return int(val)
    except (TypeError, ValueError):
        return default


def _new_planet():
    now = time.time()
    return {
        "name": random.choice(NAME_A) + random.choice(NAME_B),
        "stage": 1, "level": 1, "exp": 0, "energy": 100,
        "last_care": 0, "last_collect": now, "streak": 0, "stardust_spent": 0,
        "last_energy_time": now, "last_event": 0, "collect_boost": 1, "merchant_offer": 0,
        "merchant_expire": 0, "bond": 0, "temperament": random.choice(list(TEMPERAMENTS)),
        "rarity": random_rarity(), "achievements": [],
        "daily": {"date": today_str(), "progress": {}},
    }


def _decay_energy(planet, now):
    """按间隔自然衰减能量，返回是否进入休眠（能量 0）"""
    rate = _cfg("planet_energy_decay", 4) * temperament_mult(planet, "decay")
    last = planet.get("last_energy_time") or now
    hours = max(0.0, (now - last) / 3600)
    if hours <= 0:
        return planet["energy"] <= 0
    planet["energy"] = max(0, planet["energy"] - int(hours * rate))
    planet["last_energy_time"] = now
    return planet["energy"] <= 0


def _exp_need(level):
    return level * 100


def _stage_for_level(level):
    stage = 1
    for i, lv in enumerate(STAGE_UNLOCKS):
        if level >= lv:
            stage = i + 1
    return stage


def _texts_for_energy(energy):
    if energy >= 60:
        return CARE_TEXTS_HIGH
    if energy >= 30:
        return CARE_TEXTS_MID
    return CARE_TEXTS_LOW


def _apply_daily(planet, uid, key):
    """标记每日任务完成；若为新完成则给奖励并返回提示文字，否则返回空串。"""
    if not mark_daily(planet, key):
        return ""
    bonus = _cfg("planet_daily_bonus", 10)
    bond = _cfg("planet_daily_bond", 5)
    add_stardust(uid, bonus)
    planet["bond"] = planet.get("bond", 0) + bond
    task_name = next((n for k, n, _ in DAILY_TASK_DEFS if k == key), key)
    return f" 每日任务「{task_name}」完成：+{bonus} 碎片, 亲密度+{bond}！"


def _achievement_text(planet):
    ach = planet.get("achievements", []) or []
    total = len(ACHIEVEMENT_DEFS)
    lines = ["🏅 星球成就（%d/%d）" % (len(ach), total)]
    for key, name, desc, field, thresh in ACHIEVEMENT_DEFS:
        done = "✅" if key in ach else "⬜"
        val = planet.get("stardust_spent", 0) if field == "spent" else planet.get(field, 0)
        lines.append("%s %s · %s（%s/%s）" % (done, name, desc, val, thresh))
    return "\n".join(lines)


def _daily_text(planet):
    reset_daily(planet)
    progress = planet["daily"].get("progress", {})
    lines = ["📅 今日星球任务"]
    for key, name, desc in DAILY_TASK_DEFS:
        done = progress.get(key)
        lines.append(("%s %s · %s" % ("✅" if done else "⬜", name, desc)))
    lines.append("全部完成会额外奖励星尘与亲密度～")
    return "\n".join(lines)


def _status_text(planet):
    now = time.time()
    max_lv = _cfg("planet_max_level", 10)
    name = planet["name"]
    stage = STAGE_NAMES[planet["stage"] - 1] if planet["stage"] <= len(STAGE_NAMES) else STAGE_NAMES[-1]
    level = planet["level"]
    exp_need = _exp_need(level) if level < max_lv else 0
    exp_line = f"经验 {planet['exp']}/{exp_need}" if level < max_lv else "已满级！"
    energy = planet["energy"]
    if energy <= 0:
        energy_face = "休眠中（快喂星尘唤醒）"
    elif energy < 30:
        energy_face = "奄奄一息"
    elif energy < 60:
        energy_face = "有点疲惫"
    else:
        energy_face = "元气满满"
    pending = pending_estimate(planet, now)
    rarity = planet.get("rarity", "普通")
    lines = [
        f"✦ 「{name}」的星球 · {STAGE_ICONS[planet['stage'] - 1]} {stage}形态 · Lv.{level}",
        f"  稀有度 {rarity}（{RARITIES.get(rarity, {}).get('desc', '')}）",
        f"  {exp_line} · 能量 {energy}/{_cfg('planet_max_energy', 100)}（{energy_face}）",
        f"  性格 {planet.get('temperament', '活泼')}（{TEMPERAMENTS.get(planet.get('temperament', '活泼'), {}).get('desc', '')}）",
        f"  亲密度 {planet.get('bond', 0)} · {bond_title(planet.get('bond', 0))} · 成就 {len(planet.get('achievements', []) or [])} 个",
        f"  连续照料 {planet['streak']} 天 · 累计投入 {planet['stardust_spent']} 碎片 · 今日任务 {daily_count(planet)}/{len(DAILY_TASK_DEFS)}",
        f"  可收取产出约 {pending} 碎片",
    ]
    if planet.get("collect_boost", 1) > 1:
        lines.append(f"  ☄ 陨石雨加持：下次产出 ×{planet['collect_boost']}")
    if planet.get("merchant_offer") and now < planet.get("merchant_expire", 0):
        lines.append(f"  🛸 商人报价 {planet['merchant_offer']} 碎片（发「卖掉星球」，限时）")
    return "\n".join(lines)


def _manual_text():
    lines = [
        "🌟 星球养成 · 玩法手册",
        "「领养星球」：获得一颗专属星球，随机固有「性格 + 稀有度」，影响产出与成长",
        "「我的星球 / 星球卡片」：查看状态，并可能触发随机事件",
        "「照料星球 [次数] / 喂星球」：消耗星尘碎片换经验与能量，能量<30 时经验×1.5",
        "「收取产出 / 星球产出」：按时间累积星尘，可收取（稀有度/亲密度/成就加成）",
        "「星球改名 名字」：花碎片给星球改名",
        "「拜访星球 @好友 / 帮忙照料 @好友」：好友互动，双方都有奖励",
        "「卖掉星球」：商人出现时出售（限时），赚钱后领养一颗新的（稀有度重新随机）",
        "「星球成就 / 星球图鉴」：查看已解锁成就与进度",
        "「星球任务 / 每日任务」：查看今日活跃任务",
        "「星球排行榜」：看看谁的星球被你养得最亲密",
        "「星球手册」：再次查看本说明",
        "",
        "✨ 稀有度：普通 < 精良 < 稀有 < 史诗 < 传说（产出/亲密度越高）",
        "✨ 成就：达成条件自动解锁，每个成就 +1% 产出（上限 +30%）",
        "✨ 亲密度：喂养/收取/帮忙照料/事件都会积累，越高产出越高，并解锁称号：",
        "   " + " / ".join(f"{n}({v})" for v, n in BOND_TITLES),
        "",
        "🎭 星球性格：",
    ]
    for name, info in TEMPERAMENTS.items():
        lines.append(f"   · {name}：{info['desc']}")
    lines.append("")
    lines.append("💡 小提示：多喂、多聊天、每天做做任务，稀有星球会越来越多哦～")
    return "\n".join(lines)


def _rank(msg_type, group_id, user_qq):
    try:
        planets = list_planets()
    except Exception as e:
        print(f"星球排行榜失败: {e}")
        return None
    ranked = [p for p in planets if p[1] and p[1].get("bond", 0) > 0]
    ranked.sort(key=lambda p: (p[1].get("bond", 0), p[1].get("level", 1)), reverse=True)
    top = ranked[:8]
    if not top:
        return None
    lines = ["🏆 星球亲密榜 TOP%d" % len(top)]
    for i, (uid, p) in enumerate(top, 1):
        stage = STAGE_NAMES[p["stage"] - 1] if p["stage"] <= len(STAGE_NAMES) else STAGE_NAMES[-1]
        nick = get_nickname(uid) or uid
        rarity = p.get("rarity", "普通")
        lines.append(f"{i}. 「{p.get('name','?')}」· {nick} · {rarity} · Lv.{p.get('level',1)} {stage} · "
                     f"亲密 {p.get('bond',0)} · {bond_title(p.get('bond',0))}")
    return "\n".join(lines)


def _clean_name(raw):
    """清理玩家输入的名字：去掉 CQ 码、控制字符与首尾空白"""
    raw = re.sub(r'\[CQ:[^\]]*\]', '', raw)
    raw = re.sub(r'[\x00-\x1f\x7f]', '', raw)
    return raw.strip()


def _parse_target(raw_message, clean_message, bot_qq):
    """提取 @ 目标或纯数字 QQ 号（跳过机器人自己），返回 str 或 None"""
    ats = re.findall(r'\[CQ:at,qq=(\d+)\]', raw_message)
    if not ats:
        ats = re.findall(r'@(\d+)', raw_message)
    for qq in ats:
        if qq != str(bot_qq):
            return qq
    for tok in clean_message.split():
        if tok.isdigit() and len(tok) >= 5 and tok != str(bot_qq):
            return tok
    return None


def _unlock_achievements(planet):
    """发现新成就即写入 achievements，并返回提示列表。"""
    if not isinstance(planet.get("achievements"), list):
        planet["achievements"] = []
    news = check_achievements(planet)
    msgs = []
    for a in news:
        planet["achievements"].append(a["key"])
        msgs.append(f"🏅 解锁成就【{a['name']}】！{a['desc']}")
    return msgs


class PlanetPlugin(BasePlugin):
    name = "planet"
    priority = 80

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith(("领养星球", "我的星球", "星球卡片", "拜访星球", "帮忙照料",
                                         "照料星球", "喂星球", "收取产出", "星球产出", "星球改名", "卖掉星球",
                                         "星球手册", "星球帮助", "星球玩法", "星球榜单", "星球排行榜",
                                         "星球成就", "星球图鉴", "星球任务", "每日任务"))

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        uid = str(user_qq)
        planet = get_planet(uid)

        if clean_message.startswith(("星球手册", "星球帮助", "星球玩法")):
            self.bot.send_reply(msg_type, group_id, user_qq, _manual_text(),
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("星球榜单", "星球排行榜")):
            text = _rank(msg_type, group_id, user_qq)
            if not text:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    "还没有星球上榜～快去「领养星球」吧！",
                                    at_user=(msg_type == 'group'))
            else:
                self.bot.send_reply(msg_type, group_id, user_qq, text,
                                    at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("星球成就", "星球图鉴")):
            if planet is None:
                self.bot.send_reply(msg_type, group_id, user_qq, "你还没有星球，先发送「领养星球」吧",
                                    at_user=(msg_type == 'group'))
                return True
            reset_daily(planet)
            update_planet(uid, planet)
            self.bot.send_reply(msg_type, group_id, user_qq, _achievement_text(planet),
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("星球任务", "每日任务")):
            if planet is None:
                self.bot.send_reply(msg_type, group_id, user_qq, "你还没有星球，先发送「领养星球」吧",
                                    at_user=(msg_type == 'group'))
                return True
            reset_daily(planet)
            update_planet(uid, planet)
            self.bot.send_reply(msg_type, group_id, user_qq, _daily_text(planet),
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith("领养星球") or clean_message.startswith("我的星球") or clean_message.startswith("星球卡片"):
            if planet is None:
                planet = _new_planet()
                update_planet(uid, planet)
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    f"你在一片星尘中睁开了眼，一颗小小的【{planet['name']}】钻进了你的怀里！\n"
                                    f"性格：{planet['temperament']}（{TEMPERAMENTS.get(planet['temperament'])['desc']}）\n"
                                    f"稀有度：{planet['rarity']}（{RARITIES.get(planet['rarity'], {}).get('desc', '')}）\n"
                                    f"{_status_text(planet)}\n可用「照料星球」喂它星尘，用「收取产出」收集碎片。「星球手册」看全部玩法。",
                                    at_user=(msg_type == 'group'))
                self._send_card(msg_type, group_id, user_qq, planet)
            else:
                now = time.time()
                _decay_energy(planet, now)
                events = _roll_event(planet, uid, now)
                update_planet(uid, planet)
                if events:
                    self.bot.send_reply(msg_type, group_id, user_qq, "\n".join(events),
                                        at_user=(msg_type == 'group'))
                self._send_card(msg_type, group_id, user_qq, planet)
            return True

        if clean_message.startswith("拜访星球") or clean_message.startswith("帮忙照料"):
            return self._interact(msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot)

        if planet is None:
            self.bot.send_reply(msg_type, group_id, user_qq, "你还没有星球，先发送「领养星球」吧",
                                at_user=(msg_type == 'group'))
            return True

        now = time.time()
        _decay_energy(planet, now)

        if clean_message.startswith("卖掉星球"):
            offer = planet.get("merchant_offer", 0)
            expire = planet.get("merchant_expire", 0)
            if not offer or now >= expire:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    random.choice(EXPIRED_TEXTS).format(name=planet["name"]),
                                    at_user=(msg_type == 'group'))
                return True
            old_name = planet["name"]
            add_stardust(uid, offer)
            planet = _new_planet()
            update_planet(uid, planet)
            self.bot.send_reply(msg_type, group_id, user_qq,
                                random.choice(SOLD_TEXTS).format(name=old_name, price=offer),
                                at_user=(msg_type == 'group'))
            return True

        name = planet["name"]
        if clean_message.startswith("星球改名"):
            new_name = _clean_name(clean_message[4:])
            if not new_name or len(new_name) > 6:
                self.bot.send_reply(msg_type, group_id, user_qq, "名字要 1-6 个字哦，用法：星球改名 名字",
                                    at_user=(msg_type == 'group'))
                return True
            cost = _cfg("planet_rename_cost", 50)
            if get_stardust(uid) < cost:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    f"改名需要 {cost} 碎片，你目前只有 {get_stardust(uid)} 碎片",
                                    at_user=(msg_type == 'group'))
                return True
            add_stardust(uid, -cost)
            old = name
            planet["name"] = new_name
            planet["stardust_spent"] += cost
            update_planet(uid, planet)
            self.bot.send_reply(msg_type, group_id, user_qq, f"「{old}」正式更名为「{new_name}」！",
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith("收取产出") or clean_message.startswith("星球产出"):
            hours = (now - planet.get("last_collect", now)) / 3600
            if hours < 1:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    random.choice(NO_COLLECT_TEXTS).format(name=name),
                                    at_user=(msg_type == 'group'))
                return True
            amount = pending_estimate(planet, now)
            sulk_days = _cfg("planet_sulk_days", 5)
            sulk = False
            if planet.get("last_care") and (now - planet["last_care"]) / 86400 > sulk_days:
                sulk = True
                sulk_factor = 1.0 - (1.0 - _cfg("planet_sulk_penalty", 0.7)) * temperament_mult(planet, "sulk")
                amount = int(amount * sulk_factor)
            amount = max(1, amount)
            boost = planet.get("collect_boost", 1)
            bond_gained = _cfg("planet_bond_per_collect", 1)
            planet["bond"] = planet.get("bond", 0) + bond_gained
            planet["last_collect"] = now
            planet["collect_boost"] = 1
            daily_extra = _apply_daily(planet, uid, "collect")
            ach_msgs = _unlock_achievements(planet)
            update_planet(uid, planet)
            new_total = add_stardust(uid, amount)
            low = planet["energy"] < 30
            if sulk:
                text = random.choice(SULK_TEXTS).format(name=name, amount=amount)
            else:
                text = random.choice(LOW_ENERGY_TEXTS if low else COLLECT_TEXTS).format(name=name, amount=amount)
            if boost > 1:
                text += "（含陨石雨加成 ×%d）" % boost
            text += f" 亲密度 +{bond_gained}。当前共有 {new_total} 碎片。{daily_extra}"
            if ach_msgs:
                text += "\n" + "\n".join(ach_msgs)
            self.bot.send_reply(msg_type, group_id, user_qq, text, at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith("照料星球") or clean_message.startswith("喂星球"):
            rest = clean_message[3:].strip() if clean_message.startswith("照料星球") else clean_message[3:].strip()
            count = 1
            for tok in rest.split():
                if tok.isdigit():
                    count = min(max(int(tok), 1), 10)
                    break
            return self._feed(uid, planet, count, msg_type, group_id, user_qq)

        return True

    def _send_card(self, msg_type, group_id, user_qq, planet):
        try:
            png = build_planet_card(planet)
            b64 = base64.b64encode(png).decode("ascii")
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"[CQ:image,file=base64://{b64}]", at_user=(msg_type == 'group'))
        except Exception as e:
            print(f"星球卡片生成失败: {e}")
            self.bot.send_reply(msg_type, group_id, user_qq, _status_text(planet),
                                at_user=(msg_type == 'group'))

    def _interact(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        """拜访好友星球 / 帮忙照料好友星球"""
        uid = str(user_qq)
        target = _parse_target(raw_message, clean_message, CONFIG["bot_qq"])
        if not target or target == uid:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                "用法：拜访星球 @好友 / 帮忙照料 @好友",
                                at_user=(msg_type == 'group'))
            return True
        if not is_friend(target):
            self.bot.send_reply(msg_type, group_id, user_qq,
                                "只能拜访好友的星球哦～（对方需要是你的 QQ 好友）",
                                at_user=(msg_type == 'group'))
            return True
        t_planet = get_planet(target)
        if not t_planet:
            self.bot.send_reply(msg_type, group_id, user_qq, "TA 还没有领养星球，喊 TA 来领养一颗吧",
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith("拜访星球"):
            now = time.time()
            _decay_energy(t_planet, now)
            update_planet(target, t_planet)
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"你乘着星光来到 TA 的星球旁边：\n{_status_text(t_planet)}",
                                at_user=(msg_type == 'group'))
            self._send_card(msg_type, group_id, user_qq, t_planet)
            return True

        # 帮忙照料
        today = datetime.now().strftime("%Y-%m-%d")
        visitors = t_planet.setdefault("visitors", {})
        if visitors.get(uid) == today:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"今天已经帮「{t_planet['name']}」照料过啦，明天再来吧～",
                                at_user=(msg_type == 'group'))
            return True
        cost = _cfg("planet_care_cost", 10)
        if get_stardust(uid) < cost:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"帮忙照料需要 {cost} 碎片，你目前只有 {get_stardust(uid)} 碎片",
                                at_user=(msg_type == 'group'))
            return True
        max_lv = _cfg("planet_max_level", 10)
        max_energy = _cfg("planet_max_energy", 100)
        if t_planet["level"] >= max_lv and t_planet["energy"] >= max_energy:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"「{t_planet['name']}」已满级且能量满满，不需要帮忙啦",
                                at_user=(msg_type == 'group'))
            return True

        add_stardust(uid, -cost)
        visitors[uid] = today
        t_planet["stardust_spent"] += cost
        t_bond = int(_cfg("planet_bond_per_visit", 5) * temperament_mult(t_planet, "bond") * rarity_bond_mult(t_planet))
        t_planet["bond"] = t_planet.get("bond", 0) + t_bond
        msgs = []
        if t_planet["level"] < max_lv:
            exp_gain = int(_cfg("planet_care_exp", 25) * temperament_mult(t_planet, "exp"))
            t_planet["exp"] += exp_gain
        t_planet["energy"] = min(max_energy, t_planet["energy"] + _cfg("planet_care_energy", 10))
        while t_planet["level"] < max_lv and t_planet["exp"] >= _exp_need(t_planet["level"]):
            t_planet["exp"] -= _exp_need(t_planet["level"])
            t_planet["level"] += 1
            new_stage = _stage_for_level(t_planet["level"])
            if new_stage != t_planet["stage"]:
                t_planet["stage"] = new_stage
                msgs.append(random.choice(STAGE_UP_TEXTS).format(name=t_planet["name"],
                                                                 stage=STAGE_NAMES[new_stage - 1]))
        t_ach = _unlock_achievements(t_planet)
        update_planet(target, t_planet)

        bonus = ""
        mine = get_planet(uid)
        if mine and mine["level"] < max_lv:
            mine["exp"] += _cfg("planet_visit_care_exp", 5)
            mine["bond"] = mine.get("bond", 0) + int(_cfg("planet_bond_per_visit_self", 2) * temperament_mult(mine, "bond") * rarity_bond_mult(mine))
            mine_daily = _apply_daily(mine, uid, "visit")
            mine_ach = _unlock_achievements(mine)
            update_planet(uid, mine)
            bonus = f"\n善意的星尘回馈了你的星球(+{_cfg('planet_visit_care_exp', 5)} 经验, 亲密度+{_cfg('planet_bond_per_visit_self', 2)}){mine_daily}"
            if mine_ach:
                bonus += "\n" + "\n".join(mine_ach)
        reply = f"你帮「{t_planet['name']}」做了星尘按摩，它舒服得亮了起来！(对方亲密度 +{t_bond}){bonus}"
        if msgs:
            reply += "\n" + "\n".join(msgs)
        if t_ach:
            reply += "\n" + "\n".join(t_ach)
        self.bot.send_reply(msg_type, group_id, user_qq, reply, at_user=(msg_type == 'group'))
        return True

    def _feed(self, uid, planet, count, msg_type, group_id, user_qq):
        cost = _cfg("planet_care_cost", 10)
        exp_gain = _cfg("planet_care_exp", 25)
        energy_gain = _cfg("planet_care_energy", 10)
        max_lv = _cfg("planet_max_level", 10)
        have = get_stardust(uid)
        need = cost * count
        if have < need:
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"喂养 {count} 次需要 {need} 碎片，你只有 {have} 碎片",
                                at_user=(msg_type == 'group'))
            return True
        if planet["level"] >= max_lv and planet["energy"] >= _cfg("planet_max_energy", 100):
            self.bot.send_reply(msg_type, group_id, user_qq,
                                "「%s」已满级且能量满满，暂时吃不下了～" % planet["name"],
                                at_user=(msg_type == 'group'))
            return True

        today = datetime.now().strftime("%Y-%m-%d")
        last_care_day = datetime.fromtimestamp(planet.get("last_care", 0)).strftime("%Y-%m-%d") if planet.get("last_care") else None
        if last_care_day != today:
            yesterday = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
            planet["streak"] = planet["streak"] + 1 if last_care_day == yesterday else 1
            planet["last_care"] = time.time()

        add_stardust(uid, -need)
        planet["stardust_spent"] += need
        gained = 0
        exp_mult = temperament_mult(planet, "exp")
        exp_gain_actual = int(exp_gain * exp_mult)
        low_feed = planet["energy"] < 30
        if low_feed:
            exp_gain_actual = int(exp_gain_actual * 1.5)
        bond_add = int(_cfg("planet_bond_per_feed", 2) * count * temperament_mult(planet, "bond") * rarity_bond_mult(planet))
        planet["bond"] = planet.get("bond", 0) + bond_add
        for _ in range(count):
            if planet["level"] < max_lv:
                planet["exp"] += exp_gain_actual
                gained += exp_gain_actual
            if planet["energy"] < 100:
                planet["energy"] = min(100, planet["energy"] + energy_gain)

        msgs = []
        while planet["level"] < max_lv and planet["exp"] >= _exp_need(planet["level"]):
            planet["exp"] -= _exp_need(planet["level"])
            planet["level"] += 1
            new_stage = _stage_for_level(planet["level"])
            msgs.append(random.choice(LEVEL_UP_TEXTS).format(name=planet["name"], level=planet["level"]))
            if new_stage != planet["stage"]:
                planet["stage"] = new_stage
                msgs.append(random.choice(STAGE_UP_TEXTS).format(name=planet["name"],
                                                                 stage=STAGE_NAMES[new_stage - 1]))
        daily_extra = _apply_daily(planet, uid, "feed")
        ach_msgs = _unlock_achievements(planet)
        update_planet(uid, planet)
        if low_feed:
            reply = random.choice(LOW_FEED_TEXTS).format(name=planet["name"])
            reply += f"（+{gained} 经验〔虚弱激励 ×1.5〕，消耗 {need} 碎片，亲密度 +{bond_add}）{daily_extra}"
        else:
            care_text = random.choice(_texts_for_energy(planet["energy"])).format(name=planet["name"])
            reply = f"{care_text}（+{gained} 经验，消耗 {need} 碎片，亲密度 +{bond_add}）{daily_extra}"
        if msgs:
            reply += "\n" + "\n".join(msgs)
        if ach_msgs:
            reply += "\n" + "\n".join(ach_msgs)
        self.bot.send_reply(msg_type, group_id, user_qq, reply, at_user=(msg_type == 'group'))
        return True
