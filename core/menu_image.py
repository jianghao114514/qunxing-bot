# core/menu_image.py
import base64
import hashlib
import io
import json
import random
import threading
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from core.config import CONFIG

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]

# (features开关, 菜单定制文本, 管理员标记) -> base64图片
_cache = {}
_cache_lock = threading.Lock()

_FEATURE_META = [
    ("signin", "签", "签到 - 每日签到获取星尘碎片"),
    ("draw", "抽", "抽卡 / 十连抽 - 消耗100/1000碎片抽卡（十连有额外奖励）"),
    ("tarot", "塔", "塔罗 [问题] - 消耗15碎片占卜运势"),
    ("weather", "天", "天气 城市名 - 查询实时天气"),
    ("joke", "笑", "笑话 - 随机笑话（每次不同）"),
    ("kfc", "疯", "疯狂星期四 - 生成V我50段子"),
    ("emo", "夜", "emo - 深夜emo语录"),
    ("random_img", "图", "随机美图 - 随机二次元图片"),
    ("random_waifu", "妻", "每日老婆 - 每日老婆图片"),
    ("persona", "人", "切换人设 [名称] / 可用人设 - AI人设管理"),
    ("gift", "赠", "赠送 @某人 数量 - 赠送星尘碎片"),
    ("query", "包", "背包 / 查询 / 碎片 - 查看资产"),
    ("planet", "星", "领养星球 / 照料星球 / 拜访好友 - 养一颗自己的星球"),
    ("profile", "名", "我的名片 - 查看自己的星空名片"),
    ("feedback", "信", "反馈 内容 - 提交建议"),
    ("aichat", "AI", "@机器人 任意文字 - AI聊天（支持故事模式）"),
]

_WIDTH = 1080
_MARGIN = 64
_ITEM_H = 132
_ITEM_GAP = 20


def _load_font(size, bold=False):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def _wrap_text(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _make_background(w, h, rng):
    # 整体在 1/4 分辨率下合成（渐变+光晕），再放大到最终尺寸
    sw, sh = max(w // 4, 16), max(h // 4, 16)
    stops = [(9, 13, 34), (22, 18, 58), (42, 28, 90), (26, 32, 76)]
    col = Image.new("RGB", (1, sh))
    cp = col.load()
    for y in range(sh):
        t = y / max(sh - 1, 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2)
        f = t - i
        cp[0, y] = tuple(int(stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f) for k in range(3))
    grad = col.resize((sw, sh), Image.BILINEAR)

    glow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    # 紫/青/品红三团星云
    gd.ellipse([sw * 0.60, -sh * 0.28, sw * 1.30, sh * 0.46], fill=(139, 123, 255, 66))
    gd.ellipse([-sw * 0.30, sh * 0.64, sw * 0.60, sh * 1.26], fill=(79, 195, 247, 50))
    gd.ellipse([sw * 0.36, sh * 0.28, sw * 0.88, sh * 0.80], fill=(190, 120, 255, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(grad.convert("RGBA"), glow)
    return img.resize((w, h), Image.BILINEAR).convert("RGB")


def _draw_stars(img, rng):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    colors = ["255,255,255", "185,243,255", "190,175,255", "255,220,180"]
    for _ in range(300):
        x = rng.randint(0, img.width)
        y = rng.randint(0, img.height)
        r = rng.uniform(0.4, 1.9)
        c = rng.choice(colors)
        a = rng.randint(60, 210)
        d.ellipse([x - r, y - r, x + r, y + r], fill=f"rgba({c},{a})")
    # 十字星芒
    for _ in range(9):
        x, y = rng.randint(40, img.width - 40), rng.randint(40, img.height - 40)
        s = rng.randint(5, 10)
        a = rng.randint(140, 230)
        d.line([x - s, y, x + s, y], fill=f"rgba(255,255,255,{a})", width=1)
        d.line([x, y - s, x, y + s], fill=f"rgba(255,255,255,{a})", width=1)
        r2 = s // 3
        d.ellipse([x - r2, y - r2, x + r2, y + r2], fill=f"rgba(255,255,255,{a})")
    # 柔和光星（带光晕）
    for _ in range(6):
        x, y = rng.randint(60, img.width - 60), rng.randint(60, img.height - 60)
        r = rng.uniform(2.0, 3.2)
        d.ellipse([x - r, y - r, x + r, y + r], fill="rgba(190,175,255,110)")
        d.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill="rgba(255,255,255,220)")
    img.paste(overlay, (0, 0), overlay)


def _draw_crescent(img, cx, cy, r):
    """在局部画布上绘制柔光月牙（小范围高斯模糊，避免整图模糊的性能开销）"""
    pad = int(r * 1.7)
    crop = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(crop)
    # 外层光晕
    d.ellipse([pad - r * 1.5, pad - r * 1.5, pad + r * 1.5, pad + r * 1.5], fill=(240, 232, 255, 26))
    # 满月
    d.ellipse([pad - r, pad - r, pad + r, pad + r], fill=(240, 232, 255, 240))
    # 右上偏移的镂空圆，切出月牙
    d.ellipse([pad - r * 0.5, pad - r * 0.8, pad + r * 1.05, pad + r * 0.8], fill=(0, 0, 0, 0))
    crop = crop.filter(ImageFilter.GaussianBlur(2.5))
    img.paste(crop, (cx - pad, cy - pad), crop)


def _build_image(features, custom_texts, show_admin, user_stats=None):
    rng = random.Random(20260803)
    w = _WIDTH

    system_name = CONFIG.get("system_name", "群星")
    menu_title = CONFIG.get("bot_display_name") or system_name
    cn = CONFIG.get("currency_name") or "星尘"

    item_rows = [(key, icon, (custom_texts.get(key, desc) or desc).replace("星尘碎片", cn).replace("碎片", cn))
                 for key, icon, desc in _FEATURE_META if features.get(key, True)]
    admin_rows = [("/test", "检查AI健康状态"), ("/test all", "全面测试（对话/邮件/好友列表）"),
                  ("/test mail", "测试邮件发送"), ("/test alert", "测试警告消息")]

    title_center_y = _MARGIN + 34
    items_start = title_center_y + 96 + 66
    if user_stats:
        items_start += 12 + 96 + 16   # 个人档案卡
    h = items_start + len(item_rows) * (_ITEM_H + _ITEM_GAP)
    if show_admin:
        h += 12 + 56 + len(admin_rows) * 62 + 10
    h += 68 + 130   # 分隔线/底部提示 + 下边距

    img = _make_background(w, h, rng)
    _draw_stars(img, rng)

    draw = ImageDraw.Draw(img, "RGBA")
    f_title = _load_font(58, bold=True)
    f_sub = _load_font(30)
    f_item_name = _load_font(36, bold=True)
    f_item_desc = _load_font(27)
    f_section = _load_font(34, bold=True)
    f_admin = _load_font(29)
    f_footer = _load_font(28)

    # 右上角柔光月牙
    _draw_crescent(img, w - 140, 125, 54)

    # 居中标题（anchor=mm 精确居中，不再与月亮重叠）
    y = title_center_y
    title_text = f"★ {menu_title} · 功能菜单"
    # 标题两侧流光装饰线
    tw = draw.textlength(title_text, font=f_title)
    for lx, color in ((w // 2 - tw // 2 - 30, (139, 123, 255, 120)), (w // 2 + tw // 2 + 30, (79, 195, 247, 120))):
        if lx < w // 2:
            draw.line([lx - 130, y, lx - 18, y], fill=color, width=2)
            draw.ellipse([lx - 140, y - 3, lx - 134, y + 3], fill=color)
        else:
            draw.line([lx + 18, y, lx + 130, y], fill=color, width=2)
            draw.ellipse([lx + 134, y - 3, lx + 140, y + 3], fill=color)
    for ox, oy in [(3, 3), (5, 5)]:
        draw.text((w // 2 + ox, y + oy), title_text, font=f_title, fill=(139, 123, 255, 150), anchor="mm")
    draw.text((w // 2, y), title_text, font=f_title, fill=(255, 255, 255, 255), anchor="mm")
    y += 96
    draw.text((w // 2, y), f"· {cn}收集 · 卡牌抽奖 · AI人设陪伴 ·", font=f_sub, fill=(154, 164, 199, 255), anchor="mm")
    y += 66

    # 个人档案卡
    if user_stats:
        y += 12
        card_top = y
        nickname = user_stats.get("nickname", "访客")
        draw.rounded_rectangle([_MARGIN, card_top, w - _MARGIN, card_top + 96], radius=16,
                               fill=(255, 255, 255, 10), outline=(255, 255, 255, 22), width=1)
        cx, cy = _MARGIN + 56, card_top + 48
        draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(139, 123, 255, 70),
                     outline=(139, 123, 255, 180), width=2)
        draw.text((cx, cy), "★", font=f_item_name, fill=(255, 255, 255, 235), anchor="mm")
        tx = _MARGIN + 102
        draw.text((tx, card_top + 26), f"{nickname} 的星空档案", font=f_sub,
                  fill=(255, 255, 255, 240), anchor="lm")
        draw.text((tx, card_top + 62),
                  f"{cn} {user_stats.get('stardust', 0)} · 卡牌 {user_stats.get('cards', 0)} 张",
                  font=f_item_desc, fill=(150, 164, 199, 255), anchor="lm")
        planet = user_stats.get("planet")
        if planet:
            draw.text((tx, card_top + 62),
                      f"{cn} {user_stats.get('stardust', 0)} · 卡牌 {user_stats.get('cards', 0)} 张 · 星球「{planet[0]}」Lv.{planet[1]}",
                      font=f_item_desc, fill=(150, 164, 199, 255), anchor="lm")
        right_x = w - _MARGIN - 24
        draw.text((right_x, card_top + 28), f"人设 · {user_stats.get('persona', 'default')}",
                  font=f_item_desc, fill=(139, 195, 255, 255), anchor="rm")
        signed = user_stats.get("signed", False)
        signed_text = "今日已签到" if signed else "今日未签到"
        draw.text((right_x, card_top + 62), signed_text, font=f_item_desc,
                  fill=(90, 255, 160, 255) if signed else (255, 170, 110, 255), anchor="rm")
        y = card_top + 96 + 16

    # 功能列表
    for key, icon, desc in item_rows:
        card_top = y
        draw.rounded_rectangle([_MARGIN, card_top, w - _MARGIN, card_top + _ITEM_H], radius=18,
                               fill=(255, 255, 255, 14), outline=(255, 255, 255, 26), width=1)
        # 左侧渐变条
        bar = Image.new("RGBA", (10, _ITEM_H - 24), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        for i in range(bar.height):
            t = i / max(bar.height - 1, 1)
            bd.line([0, i, bar.width, i], fill=(int(139 + (79 - 139) * t), int(123 + (195 - 123) * t), int(255 + (247 - 255) * t), 220))
        img.paste(bar, (_MARGIN + 12, card_top + 12), bar)
        # 图标（带外光环）
        cx, cy = _MARGIN + 92, card_top + _ITEM_H // 2
        draw.ellipse([cx - 48, cy - 48, cx + 48, cy + 48], fill=(139, 123, 255, 28))
        draw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(139, 123, 255, 60), outline=(139, 123, 255, 170), width=2)
        draw.text((cx, cy), icon, font=f_item_name, fill=(255, 255, 255, 255), anchor="mm")
        # 名称+描述
        tx = _MARGIN + 150
        draw.text((tx, card_top + 34), _FEATURE_NAMES.get(key, key).replace("星尘碎片", cn).replace("碎片", cn),
                  font=f_item_name, fill=(255, 255, 255, 255))
        lines = _wrap_text(draw, desc, f_item_desc, w - _MARGIN * 2 - 150)
        for i, line in enumerate(lines[:2]):
            draw.text((tx, card_top + 82 + i * 34), line, font=f_item_desc, fill=(154, 164, 199, 255))
        y = card_top + _ITEM_H + _ITEM_GAP

    # 管理员区
    if show_admin:
        y += 12
        draw.text((_MARGIN + 4, y), "[管理员测试命令]", font=f_section, fill=(255, 210, 130, 255))
        y += 56
        for cmd, desc in admin_rows:
            draw.rounded_rectangle([_MARGIN, y, w - _MARGIN, y + 50], radius=12,
                                   fill=(255, 255, 255, 10), outline=(255, 255, 255, 20), width=1)
            draw.text((_MARGIN + 24, y + 25), cmd, font=f_admin, fill=(139, 195, 255, 255), anchor="lm")
            draw.text((_MARGIN + 300, y + 25), desc, font=f_admin, fill=(154, 164, 199, 255), anchor="lm")
            y += 62
        y += 10

    # 分隔线 + 底部提示
    draw.line([_MARGIN, y, w - _MARGIN, y], fill=(255, 255, 255, 40), width=1)
    y += 34
    draw.text((w // 2, y), "✦", font=f_sub, fill=(139, 123, 255, 200), anchor="mm")
    draw.text((w // 2 - 90, y), "✦", font=f_footer, fill=(79, 195, 247, 140), anchor="mm")
    draw.text((w // 2 + 90, y), "✦", font=f_footer, fill=(79, 195, 247, 140), anchor="mm")
    y += 44
    draw.text((w // 2, y), "群聊请 @机器人 + 指令 · 私聊直接发送", font=f_footer, fill=(154, 164, 199, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_FEATURE_NAMES = {
    "signin": "每日签到", "draw": "卡牌抽卡", "tarot": "塔罗占卜", "weather": "天气预报",
    "joke": "AI笑话", "kfc": "疯狂星期四", "emo": "每日emo", "random_img": "随机美图",
    "random_waifu": "每日老婆", "persona": "AI人设", "gift": "赠送碎片", "query": "背包查询",
    "planet": "星球养成", "feedback": "问题反馈", "aichat": "AI智能聊天",
    "profile": "星空名片",
}


def build_menu_image(features, custom_texts, show_admin=False, user_stats=None):
    """生成菜单图片（带缓存），返回 base64 字符串
    user_stats: 个人档案信息 dict（nickname/stardust/cards/persona/signed）
    """
    key_data = {
        "f": {k: bool(v) for k, v in features.items() if k in [m[0] for m in _FEATURE_META]},
        "t": dict(custom_texts or {}),
        "a": show_admin,
    }
    if user_stats:
        key_data["u"] = {k: user_stats.get(k) for k in ("nickname", "stardust", "cards", "persona", "signed")}
    cache_key = hashlib.md5(json.dumps(key_data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached:
        return cached

    png = _build_image(features, custom_texts, show_admin, user_stats)
    b64 = base64.b64encode(png).decode("ascii")
    with _cache_lock:
        _cache[cache_key] = b64
        if len(_cache) > 20:
            _cache.clear()
    return b64
