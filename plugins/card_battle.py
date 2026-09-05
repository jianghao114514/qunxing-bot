# plugins/card_battle.py
# 卡牌对战 v1：复用抽卡卡池（R/SR/SSR），自动结算，属性循环克制，胜场积分段位。
import os
import json
from plugins.base import BasePlugin
from core.config import CONFIG
from core.database import get_cached_user, update_cached_user, add_stardust, get_stardust, get_nickname
from core.card import parse_deck, team_power, ELEMENTS

RANKS = [(0, "青铜"), (100, "白银"), (300, "黄金"), (700, "铂金"), (1500, "钻石")]


def rank_for(points):
    name = "青铜"
    for threshold, r in RANKS:
        if points >= threshold:
            name = r
    return name


def _get_cards(uid):
    return get_cached_user(uid).get("cards", []) or []


def _update_battle(uid, win):
    d = get_cached_user(uid)
    cb = d.setdefault("card_battle", {"points": 0, "wins": 0, "losses": 0})
    cb["points"] += 10 if win else 3
    cb["wins" if win else "losses"] += 1
    update_cached_user(uid, d)
    return cb["points"], rank_for(cb["points"])


def _deck_text(cards, label="卡组"):
    deck = parse_deck(cards)
    if not deck:
        return "（还没有卡牌，先「抽卡」吧）"
    lines = ["【%s】" % label]
    for i, c in enumerate(deck, 1):
        sk = "/".join(c["skills"]) or "无技能"
        lines.append("%d. %s [%s] %s·%s · 攻%d/血%d · 战力%d · %s" % (
            i, c["name"], c["tier"], c["element"], c["role"], c["attack"], c["hp"], c["power"], sk))
    lines.append("总战力 %d" % sum(c["power"] for c in deck))
    return "\n".join(lines)


def _battle_text(my_cards, tar_cards):
    ma = parse_deck(my_cards)
    tb = parse_deck(tar_cards)
    if not ma:
        return None, "你还没有卡牌，先「抽卡」吧！"
    if not tb:
        return None, "对方还没有卡牌，喊 TA 去「抽卡」吧！"
    a = team_power(ma, tb)
    b = team_power(tb, ma)
    if a == b:
        return "平局", 0
    win = a > b
    return ("胜利" if win else "失败"), (1 if win else -1)


def _rank_text():
    users_dir = CONFIG.get("users_dir") or ""
    rows = []
    if users_dir and os.path.isdir(users_dir):
        for f in os.listdir(users_dir):
            if not f.endswith(".json"):
                continue
            uid = f[:-5]
            try:
                with open(os.path.join(users_dir, f), "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                cb = data.get("card_battle") or {}
                rows.append((uid, cb.get("points", 0), cb.get("wins", 0), cb.get("losses", 0)))
            except Exception:
                continue
    rows.sort(key=lambda r: r[1], reverse=True)
    top = rows[:5]
    if not top:
        return "还没有人对战过～先「抽卡」并「卡牌对战」吧！"
    lines = ["🏆 卡牌对战榜 TOP%d" % len(top)]
    for i, (uid, p, w, l) in enumerate(top, 1):
        nick = get_nickname(uid) or uid
        lines.append("%d. %s · %d 分 · %d胜/%d负 · %s" % (i, nick, p, w, l, rank_for(p)))
    return "\n".join(lines)


def _manual():
    return "\n".join([
        "🃏 卡牌对战 · 玩法手册",
        "「抽卡」获得卡牌（R/SR/SSR，抽卡还送星尘碎片）",
        "「查看卡组 / 我的卡组」查看你的前 5 张卡",
        "「卡牌对战 @好友 / 卡牌挑战 @好友」自动结算：属性克制+战力",
        "「卡牌榜单 / 卡牌排行」查看对战榜",
        "",
        "属性克制：金→木→土→水→火→金",
        "定位：攻（高攻）/ 防（高血）/ 辅（均衡）/ 盾（肉盾）",
        "段位：青铜 → 白银 → 黄金 → 铂金 → 钻石（按积分）",
        "胜负双方都有积分与星尘奖励，低星卡也能靠克制/定位发挥作用～",
    ])


def _parse_target(raw_message, clean_message, bot_qq):
    import re
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


class CardBattlePlugin(BasePlugin):
    name = "card_battle"
    priority = 70

    def match(self, msg_type, group_id, user_qq, raw_message, clean_message, is_at_bot):
        if msg_type == 'group' and not is_at_bot:
            return False
        return clean_message.startswith(("卡牌手册", "卡牌帮助", "查看卡组", "我的卡组",
                                         "卡牌对战", "卡牌挑战", "卡牌榜单", "卡牌排行"))

    def handle(self, msg_type, group_id, user_qq, nickname, raw_message, clean_message, is_at_bot):
        uid = str(user_qq)

        if clean_message.startswith(("卡牌手册", "卡牌帮助")):
            self.bot.send_reply(msg_type, group_id, user_qq, _manual(), at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("查看卡组", "我的卡组")):
            text = _deck_text(_get_cards(uid), "你的卡组")
            cb = get_cached_user(uid).get("card_battle", {})
            rk = rank_for(cb.get("points", 0))
            self.bot.send_reply(msg_type, group_id, user_qq,
                                text + "\n当前积分 %d · %s" % (cb.get("points", 0), rk),
                                at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("卡牌榜单", "卡牌排行")):
            text = _rank_text()
            self.bot.send_reply(msg_type, group_id, user_qq, text, at_user=(msg_type == 'group'))
            return True

        if clean_message.startswith(("卡牌对战", "卡牌挑战")):
            target = _parse_target(raw_message, clean_message, CONFIG["bot_qq"])
            if not target or target == uid:
                self.bot.send_reply(msg_type, group_id, user_qq,
                                    "用法：卡牌对战 @好友", at_user=(msg_type == 'group'))
                return True
            my_cards = _get_cards(uid)
            tar_cards = _get_cards(target)
            result, flag = _battle_text(my_cards, tar_cards)
            if result is None:
                self.bot.send_reply(msg_type, group_id, user_qq, flag, at_user=(msg_type == 'group'))
                return True
            my_deck = parse_deck(my_cards)
            tar_deck = parse_deck(tar_cards)
            win = flag == 1
            my_pts, my_rk = _update_battle(uid, win)
            tar_pts, tar_rk = _update_battle(target, not win)
            add_stardust(uid, 8 if win else 2)
            add_stardust(target, 2 if win else 8)
            lines = [
                "⚔ 卡牌对战结果：**%s**" % result,
                _deck_text(my_cards, "你的卡组"),
                _deck_text(tar_cards, "对方卡组"),
                "你 战力%d · %s | 对方 战力%d · %s" % (
                    team_power(my_deck, tar_deck), my_rk,
                    team_power(tar_deck, my_deck), tar_rk),
                "你 %d分/%s · 对方 %d分/%s" % (my_pts, my_rk, tar_pts, tar_rk),
            ]
            self.bot.send_reply(msg_type, group_id, user_qq, "\n".join(lines),
                                at_user=(msg_type == 'group'))
            return True

        return True
