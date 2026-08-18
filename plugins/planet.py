# plugins/planet.py
import base64
import random
import re
import time
from datetime import datetime, timedelta
from plugins.base import BasePlugin
from core.config import CONFIG, SYSTEM_CONFIG
from core.database import get_stardust, add_stardust, get_planet, update_planet, is_friend
from core.planet_image import build_planet_card, STAGE_NAMES, STAGE_ICONS

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
    "🛸 拍卖商人落在你的星球旁，出价 {price} 碎片收购「{name}」，发送「卖掉星球」即可成交！",
    "🛸 一位神秘的商人看上了「{name}」，愿意出 {price} 碎片收购！发「卖掉星球」卖掉它。",
]
SOLD_TEXTS = [
    "「{name}」被你送上了商人的飞船，{price} 碎片到账。它回望你一眼，化作一颗新的星球坠入你的怀中！",
    "交易达成！{price} 碎片到手。旧主人走了，但一颗全新的星球正等着你取名字……",
]

EVENT_NAMES = ["meteor", "whale", "merchant"]


def _roll_event(planet, uid, now):
    """满足冷却则按概率触发随机事件，返回描述行列表。不主动写盘，由调用方 update_planet。"""
    if not _cfg("planet_event_enabled", 1):
        return []
    min_interval = _cfg("planet_event_min_interval", 3600)
    if planet.get("last_event", 0) and now - planet.get("last_event", 0) < min_interval:
        return []
    if random.random() > _cfg("planet_event_prob", 0.4):
        return []
    planet["last_event"] = now
    ev = random.choice(EVENT_NAMES)
    if ev == "meteor":
        planet["collect_boost"] = 5
        return [random.choice(EVENT_METEOR_TEXTS).format(name=planet["name"])]
    if ev == "whale":
        amount = planet["level"] * random.randint(10, 40)
        add_stardust(uid, amount)
        return [random.choice(EVENT_WHALE_TEXTS).format(name=planet["name"], amount=amount)]
    # merchant
    price = max(100, int(planet["stardust_spent"] * 1.5))
    planet["merchant_offer"] = price
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
    }


def _decay_energy(planet, now):
    """按间隔自然衰减能量，返回是否进入休眠（能量 0）"""
    rate = _cfg("planet_energy_decay", 4)
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


def _status_text(planet):
    now = time.time()
    hours = max(0, (now - planet.get("last_collect", now)) / 3600)
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
    pending = int(hours * level * _cfg("planet_collect_per_hour", 1) * (0.5 if energy < 30 else 1))
    lines = [
        f"✦ 「{name}」的星球 · {STAGE_ICONS[planet['stage'] - 1]} {stage}形态 · Lv.{level}",
        f"  {exp_line} · 能量 {energy}/100（{energy_face}）",
        f"  连续照料 {planet['streak']} 天 · 累计投入 {planet['stardust_spent']} 碎片",
        f"  可收取产出约 {pending} 碎片",
    ]
    if planet.get("collect_boost", 1) > 1:
        lines.append(f"  ☄ 陨石雨加持：下次产出 ×{planet['collect_boost']}")
    if planet.get("merchant_offer"):
        lines.append(f"  🛸 商人报价 {planet['merchant_offer']} 碎片（发「卖掉星球」）")
    return "\n".join(lines)


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


class PlanetPlugin(BasePlugin):
    name = "planet"
    priority = 80

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith(("领养星球", "我的星球", "星球卡片", "拜访星球", "帮忙照料",
                                         "照料星球", "喂星球", "收取产出", "星球产出", "星球改名", "卖掉星球"))

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        uid = str(user_qq)
        planet = get_planet(uid)

        if clean_message.startswith("领养星球") or clean_message.startswith("我的星球") or clean_message.startswith("星球卡片"):
            if planet is None:
                planet = _new_planet()
                update_planet(uid, planet)
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    f"你在一片星尘中睁开了眼，一颗小小的【{planet['name']}】钻进了你的怀里！\n{_status_text(planet)}\n可用「照料星球」喂它星尘，用「收取产出」收集碎片。",
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
            if not offer:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    "现在没有商人想要你的星球，等拍卖商人出现再说吧～",
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
            new_name = clean_message[4:].strip()
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
            level = planet["level"]
            rate = level * _cfg("planet_collect_per_hour", 1)
            if hours < 1:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    random.choice(NO_COLLECT_TEXTS).format(name=name),
                                    at_user=(msg_type == 'group'))
                return True
            hours = min(hours, _cfg("planet_collect_max_hours", 24))
            amount = int(hours * rate)
            low = planet["energy"] < 30
            if low:
                amount //= 2
            boost = planet.get("collect_boost", 1)
            if boost > 1:
                amount *= boost
            sulk_days = _cfg("planet_sulk_days", 5)
            sulk = False
            if planet.get("last_care") and (now - planet["last_care"]) / 86400 > sulk_days:
                sulk = True
                amount = int(amount * _cfg("planet_sulk_penalty", 0.7))
            amount = max(1, amount)
            planet["last_collect"] = now
            planet["collect_boost"] = 1
            update_planet(uid, planet)
            new_total = add_stardust(uid, amount)
            if sulk:
                text = random.choice(SULK_TEXTS).format(name=name, amount=amount)
            else:
                text = random.choice(LOW_ENERGY_TEXTS if low else COLLECT_TEXTS).format(name=name, amount=amount)
            if boost > 1:
                text += "（含陨石雨加成 ×%d）" % boost
            self.bot.send_reply(msg_type, group_id, user_qq,
                                f"{text} 当前共有 {new_total} 碎片。", at_user=(msg_type == 'group'))
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
        msgs = []
        if t_planet["level"] < max_lv:
            t_planet["exp"] += _cfg("planet_care_exp", 25)
        t_planet["energy"] = min(max_energy, t_planet["energy"] + _cfg("planet_care_energy", 10))
        while t_planet["level"] < max_lv and t_planet["exp"] >= _exp_need(t_planet["level"]):
            t_planet["exp"] -= _exp_need(t_planet["level"])
            t_planet["level"] += 1
            new_stage = _stage_for_level(t_planet["level"])
            if new_stage != t_planet["stage"]:
                t_planet["stage"] = new_stage
                msgs.append(random.choice(STAGE_UP_TEXTS).format(name=t_planet["name"],
                                                                 stage=STAGE_NAMES[new_stage - 1]))
        update_planet(target, t_planet)

        bonus = ""
        mine = get_planet(uid)
        if mine and mine["level"] < max_lv:
            mine["exp"] += _cfg("planet_visit_care_exp", 5)
            update_planet(uid, mine)
            bonus = f"\n善意的星尘回馈了你的星球（+{_cfg('planet_visit_care_exp', 5)} 经验）"
        reply = f"你帮「{t_planet['name']}」做了星尘按摩，它舒服得亮了起来！{bonus}"
        if msgs:
            reply += "\n" + "\n".join(msgs)
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
        exp_gain_actual = exp_gain
        if planet["energy"] < 30:
            exp_gain_actual = int(exp_gain * 1.5)
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
        update_planet(uid, planet)
        if exp_gain_actual > exp_gain:
            reply = random.choice(LOW_FEED_TEXTS).format(name=planet["name"])
            reply += f"（+{gained} 经验〔虚弱激励 ×1.5〕，消耗 {need} 碎片）"
        else:
            care_text = random.choice(_texts_for_energy(planet["energy"])).format(name=planet["name"])
            reply = f"{care_text}（+{gained} 经验，消耗 {need} 碎片）"
        if msgs:
            reply += "\n" + "\n".join(msgs)
        self.bot.send_reply(msg_type, group_id, user_qq, reply, at_user=(msg_type == 'group'))
        return True
