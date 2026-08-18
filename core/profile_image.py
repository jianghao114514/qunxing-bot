# core/profile_image.py
import io
import random
from core.menu_image import _load_font, _make_background, _draw_stars
from core.config import CONFIG, currency_name

_W = 860
_H = 1080


def _bar(draw, x, y, w, h, ratio, color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(255, 255, 255, 26))
    ratio = max(0.0, min(1.0, ratio))
    if ratio > 0:
        draw.rounded_rectangle([x, y, x + w * ratio, y + h], radius=h // 2, fill=color + (255,))


def build_profile_card(stats):
    """生成用户星空名片图，返回 PNG 字节。
    stats: {qq, nickname, stardust, cards:[], persona, signed, last_signin, planet:{name,level,stage}}
    """
    rng = random.Random(abs(hash(str(stats.get("qq", "?")))) % (2 ** 31))
    w, h = _W, _H
    img = _make_background(w, h, rng)
    _draw_stars(img, rng)

    draw = ImageDraw.Draw(img, "RGBA")
    f_title = _load_font(52, bold=True)
    f_stat = _load_font(32)
    f_small = _load_font(27)
    f_footer = _load_font(27)
    f_big = _load_font(56, bold=True)

    nickname = (stats.get("nickname") or "星空旅人")[:12]
    qq = str(stats.get("qq", ""))
    persona = stats.get("persona", "default")
    stardust = stats.get("stardust", 0)
    cards = stats.get("cards", [])
    signed = stats.get("signed", False)
    last_signin = stats.get("last_signin") or "未签到"
    planet = stats.get("planet") or {}

    # 标题
    y = 92
    title = f"★ {nickname} 的星空名片"
    for ox, oy in [(3, 3), (5, 5)]:
        draw.text((w // 2 + ox, y + oy), title, font=f_title, fill=(139, 123, 255, 150), anchor="mm")
    draw.text((w // 2, y), title, font=f_title, fill=(255, 255, 255, 255), anchor="mm")
    ul_y = y + 48
    for i in range(140):
        t = i / 139
        c = (int(139 + (79 - 139) * t), int(123 + (195 - 123) * t), int(255 + (247 - 255) * t))
        draw.line([w // 2 - 70 + i, ul_y, w // 2 - 70 + i + 1, ul_y], fill=c + (170,), width=2)

    # 头像（昵称首字）
    cx, cy, r = w // 2, 330, 96
    draw.ellipse([cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16], fill=(139, 123, 255, 40))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(139, 123, 255, 90), outline=(139, 123, 255, 200), width=3)
    draw.ellipse([cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8], outline=(79, 195, 247, 120), width=2)
    draw.text((cx, cy), nickname[0], font=f_big, fill=(255, 255, 255, 250), anchor="mm")

    # 基本信息条
    y = cy + r + 60
    bx, bw, bh = 86, w - 172, 22
    # QQ / 人设 / 签到
    info = [
        ("QQ", qq, (154, 164, 199)),
        ("人设", persona, (139, 195, 255)),
        ("签到", "今日已签到" if signed else "今日未签到",
         (90, 255, 160) if signed else (255, 170, 110)),
    ]
    seg = bw // 3
    for i, (label, value, color) in enumerate(info):
        sx = bx + seg * i
        draw.text((sx + seg // 2, y), label, font=f_small, fill=(154, 164, 199, 255), anchor="mm")
        draw.text((sx + seg // 2, y + 40), str(value), font=f_stat, fill=color + (255,), anchor="mm")
    y += 96

    # 星尘大数字
    draw.rounded_rectangle([bx, y, bx + bw, y + 92], radius=16,
                           fill=(255, 255, 255, 10), outline=(255, 255, 255, 22), width=1)
    draw.text((bx + 30, y + 46), currency_name(), font=f_small, fill=(154, 164, 199, 255), anchor="lm")
    draw.text((bx + bw - 30, y + 46), f"{stardust} ✦", font=f_big, fill=(90, 255, 160, 255), anchor="rm")
    y += 92 + 20

    # 卡牌
    tier_count = {"SSR": 0, "SR": 0, "R": 0}
    for c in cards:
        t = str(c).split("-")[0].strip().upper()
        if t in tier_count:
            tier_count[t] += 1
    draw.rounded_rectangle([bx, y, bx + bw, y + 92], radius=16,
                           fill=(255, 255, 255, 10), outline=(255, 255, 255, 22), width=1)
    draw.text((bx + 30, y + 24), f"卡牌收藏（{len(cards)} 张）", font=f_small, fill=(154, 164, 199, 255), anchor="lm")
    colors = {"SSR": (255, 90, 90), "SR": (255, 170, 110), "R": (170, 175, 190)}
    tx = bx + 30
    for t in ("SSR", "SR", "R"):
        draw.text((tx, y + 62), f"{t} ×{tier_count[t]}", font=f_stat, fill=colors[t] + (255,), anchor="lm")
        tx += draw.textlength(f"{t} ×{tier_count[t]}", font=f_stat) + 44
    y += 92 + 20

    # 星球
    if planet:
        draw.rounded_rectangle([bx, y, bx + bw, y + 92], radius=16,
                               fill=(255, 255, 255, 10), outline=(255, 255, 255, 22), width=1)
        draw.text((bx + 30, y + 24), "星球", font=f_small, fill=(154, 164, 199, 255), anchor="lm")
        draw.text((bx + 30, y + 62),
                  f"「{planet.get('name', '?')}」 Lv.{planet.get('level', 1)} · {planet.get('stage_name', '星云')}形态",
                  font=f_stat, fill=(190, 175, 255, 255), anchor="lm")
        y += 92 + 20

    # 底部提示
    draw.line([bx, _H - 120, bx + bw, _H - 120], fill=(255, 255, 255, 40), width=1)
    draw.text((w // 2, _H - 78), f"菜单 查看功能 · 我的星球 查看星球 · 签到 领取{currency_name()}",
              font=f_footer, fill=(154, 164, 199, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
