# core/planet_image.py
import io
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from core.menu_image import _load_font, _make_background, _draw_stars
from core.config import SYSTEM_CONFIG, currency_name

STAGE_NAMES = ["星云", "彗星", "行星", "恒星", "超新星"]
STAGE_ICONS = ["☁", "☄", "🪐", "☀", "✨"]
# (主色, 暗色) 各形态配色
STAGE_COLORS = [
    ((168, 148, 224), (96, 84, 168)),    # 星云 灰紫
    ((130, 205, 240), (66, 130, 195)),   # 彗星 冰蓝
    ((100, 214, 185), (44, 128, 150)),   # 行星 青绿
    ((255, 196, 96), (228, 126, 44)),    # 恒星 橙金
    ((248, 244, 255), (196, 128, 255)),  # 超新星 白紫
]

_W = 860
_H = 1150


def _cfg(key, default):
    val = SYSTEM_CONFIG.get(key, default)
    try:
        if isinstance(default, float):
            return float(val)
        return int(val)
    except (TypeError, ValueError):
        return default


def _bar(draw, x, y, w, h, ratio, color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(255, 255, 255, 26))
    ratio = max(0.0, min(1.0, ratio))
    if ratio > 0:
        draw.rounded_rectangle([x, y, x + w * ratio, y + h], radius=h // 2, fill=color + (255,))
        ex = x + w * ratio - h // 2
        draw.ellipse([ex - 3, y - 1, ex + h + 3, y + h + 1], outline=color + (200,), width=2)


def _draw_sphere(img, cx, cy, r, main, dark, stage):
    """绘制星球本体：双层光晕 + 三档渐变球体 + 大气顶光 + 高光 + 形态装饰"""
    mid = tuple((main[k] + dark[k]) // 2 for k in range(3))
    # 外层光晕（双层）
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r * 2.1, cy - r * 2.1, cx + r * 2.1, cy + r * 2.1], fill=main + (40,))
    gd.ellipse([cx - r * 1.3, cy - r * 1.3, cx + r * 1.3, cy + r * 1.3], fill=main + (66,))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(glow, (0, 0), glow)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 彗星尾巴（曲线分段，画在球体下层）
    if stage == 2:
        for x1r, x2r, wd, a in [(0.9, 1.9, 18, 120), (1.7, 2.7, 10, 80), (2.5, 3.4, 5, 48)]:
            g = Image.new("RGBA", img.size, (0, 0, 0, 0))
            gd2 = ImageDraw.Draw(g)
            gd2.line([cx + r * x1r, cy - r * 0.10, cx + r * x2r, cy - r * 0.34],
                     fill=main + (a,), width=wd)
            g = g.filter(ImageFilter.GaussianBlur(6))
            img.paste(g, (0, 0), g)

    # 行星环（画在球体下层，双层细环增加层次）
    if stage == 3:
        d.ellipse([cx - r * 1.5, cy - r * 0.52, cx + r * 1.5, cy + r * 0.52],
                  outline=(232, 242, 255, 120), width=8)
        d.ellipse([cx - r * 1.5, cy - r * 0.52, cx + r * 1.5, cy + r * 0.52],
                  outline=(200, 216, 255, 70), width=3)

    # 三档渐变球体（逐行色带 + 边缘暗化增强立体感）
    for y in range(int(cy - r), int(cy + r) + 1):
        t = (y - (cy - r)) / max(2 * r, 1)
        if t < 0.55:
            c = tuple(int(main[k] + (mid[k] - main[k]) * (t / 0.55)) for k in range(3))
        else:
            c = tuple(int(mid[k] + (dark[k] - mid[k]) * ((t - 0.55) / 0.45)) for k in range(3))
        dy = y - cy
        half = math.sqrt(max(0.0, r * r - dy * dy))
        edge = abs(dy) / r
        shade = 0.82 + 0.18 * (1 - edge * edge) ** 0.5
        c = tuple(max(0, min(255, int(cc * shade))) for cc in c)
        d.line([cx - half, y, cx + half, y], fill=c + (255,))

    # 大气层顶端高光（rim light）
    d.ellipse([cx - r * 0.96, cy - r * 1.02, cx + r * 0.96, cy - r * 0.66],
              outline=(255, 255, 255, 120), width=2)
    # 高光斑
    d.ellipse([cx - r * 0.60, cy - r * 0.70, cx - r * 0.06, cy - r * 0.26], fill=(255, 255, 255, 64))
    d.ellipse([cx - r * 0.46, cy - r * 0.62, cx - r * 0.18, cy - r * 0.36], fill=(255, 255, 255, 70))

    img.paste(overlay, (0, 0), overlay)

    # 恒星光芒 / 超新星爆光
    if stage in (4, 5):
        ray_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(ray_img)
        a = 110 if stage == 4 else 150
        for i in range(8):
            ang = math.pi * i / 4
            x1 = cx + math.cos(ang) * r * 1.15
            y1 = cy + math.sin(ang) * r * 1.15
            x2 = cx + math.cos(ang) * r * (1.9 if i % 2 == 0 else 1.55)
            y2 = cy + math.sin(ang) * r * (1.9 if i % 2 == 0 else 1.55)
            rd.line([x1, y1, x2, y2], fill=(255, 255, 255, a), width=max(3, r // 28))
        ray_img = ray_img.filter(ImageFilter.GaussianBlur(3))
        img.paste(ray_img, (0, 0), ray_img)

    # 行星环前弧（压在球体上，形成环绕错觉）
    if stage == 3:
        d2 = ImageDraw.Draw(img)
        d2.ellipse([cx - r * 1.5, cy - r * 0.52, cx + r * 1.5, cy + r * 0.52],
                   outline=(232, 242, 255, 100), width=7)


def build_planet_card(planet):
    """生成星球卡片图，返回 PNG 字节。planet 为 get_planet() 的字典。"""
    rng = random.Random(abs(hash(planet.get("name", "?"))) % (2 ** 31))
    w, h = _W, _H
    img = _make_background(w, h, rng)
    _draw_stars(img, rng)

    stage = min(planet.get("stage", 1), len(STAGE_NAMES))
    main, dark = STAGE_COLORS[stage - 1]
    name = planet.get("name", "无名星球")
    level = planet.get("level", 1)
    energy = planet.get("energy", 100)
    max_lv = _cfg("planet_max_level", 10)
    exp_need = level * 100 if level < max_lv else 0
    exp = planet.get("exp", 0)

    draw = ImageDraw.Draw(img, "RGBA")
    f_title = _load_font(52, bold=True)
    f_sub = _load_font(30)
    f_stat = _load_font(32)
    f_small = _load_font(27)
    f_footer = _load_font(27)

    # 标题
    y = 92
    title = f"★ 「{name}」的星球 · {STAGE_NAMES[stage - 1]}形态 · Lv.{level}"
    for ox, oy in [(3, 3), (5, 5)]:
        draw.text((w // 2 + ox, y + oy), title, font=f_title, fill=main + (150,), anchor="mm")
    draw.text((w // 2, y), title, font=f_title, fill=(255, 255, 255, 255), anchor="mm")
    # 渐变下划线
    ul_y = y + 48
    for i in range(140):
        t = i / 139
        c = tuple(int(main[k] + ((79, 195, 247)[k] - main[k]) * t) for k in range(3))
        draw.line([w // 2 - 70 + i, ul_y, w // 2 - 70 + i + 1, ul_y], fill=c + (170,), width=2)

    # 星球本体
    cx, cy, r = w // 2, 430, 150
    _draw_sphere(img, cx, cy, r, main, dark, stage)

    # 经验条
    y = cy + r + 70
    draw.text((_MARGIN_X := 86, y), f"Lv.{level}", font=f_stat, fill=(255, 255, 255, 235), anchor="lm")
    bx, bw, bh = 200, 500, 22
    ratio = exp / exp_need if exp_need else 1.0
    _bar(draw, bx, y - bh // 2, bw, bh, ratio, (139, 195, 255))
    exp_text = f"{exp}/{exp_need}" if exp_need else "MAX"
    draw.text((bx + bw + 22, y), exp_text, font=f_small, fill=(154, 164, 199, 255), anchor="lm")
    y += 66

    # 能量条
    draw.text((_MARGIN_X, y), "能量", font=f_stat, fill=(255, 255, 255, 235), anchor="lm")
    if energy <= 0:
        e_color, e_face = (255, 90, 90), "休眠中"
    elif energy < 30:
        e_color, e_face = (255, 90, 90), "奄奄一息"
    elif energy < 60:
        e_color, e_face = (255, 170, 110), "有点疲惫"
    else:
        e_color, e_face = (90, 255, 160), "元气满满"
    _bar(draw, bx, y - bh // 2, bw, bh, energy / 100.0, e_color)
    draw.text((bx + bw + 22, y), e_face, font=f_small, fill=e_color + (255,), anchor="lm")
    y += 76

    # 统计卡片
    card_x, card_w = 86, w - 172
    draw.rounded_rectangle([card_x, y, card_x + card_w, y + 96], radius=16,
                           fill=(255, 255, 255, 10), outline=(255, 255, 255, 22), width=1)
    now = __import__("time").time()
    hours = max(0.0, (now - planet.get("last_collect", now)) / 3600)
    rate = level * _cfg("planet_collect_per_hour", 1)
    hours = min(hours, _cfg("planet_collect_max_hours", 24))
    pending = int(hours * rate * (0.5 if energy < 30 else 1))
    draw.text((card_x + 30, y + 26), f"连续照料 {planet.get('streak', 0)} 天", font=f_stat,
              fill=(255, 255, 255, 230), anchor="lm")
    draw.text((card_x + 30, y + 62), f"累计投入 {planet.get('stardust_spent', 0)} {currency_name()}", font=f_small,
              fill=(154, 164, 199, 255), anchor="lm")
    draw.text((card_x + card_w - 30, y + 26), f"可收取 ≈ {pending} {currency_name()}", font=f_stat,
              fill=(90, 255, 160, 255), anchor="rm")
    y += 96 + 20

    # 状态徽章
    badges = []
    if planet.get("collect_boost", 1) > 1:
        badges.append(("☄ 陨石雨：下次产出 ×%d" % planet["collect_boost"], (139, 195, 255)))
    if planet.get("merchant_offer"):
        badges.append(("🛸 商人报价 %d（发「卖掉星球」）" % planet["merchant_offer"], (255, 210, 130)))
    if energy <= 0:
        badges.append(("💤 休眠中，快喂星尘唤醒", (255, 140, 140)))
    if badges:
        for text, color in badges:
            tw = draw.textlength(text, font=f_small)
            draw.rounded_rectangle([card_x, y, card_x + tw + 40, y + 52], radius=14,
                                   fill=color + (24,), outline=color + (120,), width=1)
            draw.text((card_x + 20, y + 26), text, font=f_small, fill=color + (255,), anchor="lm")
            y += 64

    # 底部提示
    draw.line([_MARGIN_X, _H - 120, w - _MARGIN_X, _H - 120], fill=(255, 255, 255, 40), width=1)
    draw.text((w // 2, _H - 78),
              "照料星球 · 收取产出 · 星球改名 · 卖掉星球",
              font=f_footer, fill=(154, 164, 199, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
