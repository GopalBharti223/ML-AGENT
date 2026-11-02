"""V2 Masterpiece Broadcast Visual Overhaul (Zero Emptiness / Fully Packed Intelligence Layouts):
1. LINE CHART V2 ("Titan Clash: Volumetric Duel"):
   - Top Head-to-Head Duel HUD (India vs UK with live lead badge).
   - Glowing volumetric area gradient fills under curves (lush mountain terrain).
   - Lower historical milestone cards (1990, 2015, 2022).
2. DONUT CHART V2 ("Global Wealth & Energy Matrix"):
   - Top Surprise Clash Hook (Venezuela vs Saudi Arabia).
   - Large, commanding 3D Volumetric Donut Ring with embedded flags and direct slice pills.
   - Full 6-nation detailed leaderboard panel (Reserves, Barrels, Share).
3. SLOPE CHART V2 ("Decade Power Shift Intelligence Matrix"):
   - Top Key Movers Highlight Strip (Clean ascii arrows, no tofu boxes).
   - Rich left & right country cards with flags, spending, and outcome-colored laser slopes.
   - Lower Key Geopolitical Takeaway Card.

Zero dead space. 100% screen utilization. Premium Bloomberg/Vox broadcast aesthetic.
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920

os.makedirs("output", exist_ok=True)

def get_font(size, bold=True):
    font_names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "tahomabd.ttf" if bold else "tahoma.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_hud_tag = get_font(22, bold=True)
font_hud_title = get_font(44, bold=True)
font_hud_kpi_num = get_font(32, bold=True)
font_hud_kpi_lbl = get_font(18, bold=True)
font_card_title = get_font(24, bold=True)
font_card_val = get_font(22, bold=True)
font_card_sub = get_font(17, bold=False)
font_badge = get_font(16, bold=True)
font_donut_pct = get_font(22, bold=True)
font_debate = get_font(22, bold=True)
font_caption = get_font(34, bold=True)
font_source = get_font(18, bold=False)
font_axis = get_font(16, bold=False)

# Flag loading with circular crop helper
FLAG_PATHS = {
    "IND": "assets/flags_hires/in.png",
    "GBR": "assets/flags_hires/gb.png",
    "USA": "assets/flags_hires/us.png",
    "CHN": "assets/flags_hires/cn.png",
    "RUS": "assets/flags/ru.png",
    "SAU": "assets/flags/sa.png",
    "VEN": "assets/flags/ve.png",
    "CAN": "assets/flags/ca.png",
    "IRQ": "assets/flags/iq.png",
    "UAE": "assets/flags/ae.png",
    "IRN": "assets/flags/ir.png",
}

loaded_flags = {}
for code, path in FLAG_PATHS.items():
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA")
            loaded_flags[code] = img
        except Exception:
            pass

def get_circular_flag(code, size=40):
    if code in loaded_flags:
        im = loaded_flags[code].copy()
        im = im.resize((size, size), Image.Resampling.LANCZOS)
    else:
        im = Image.new("RGBA", (size, size), (30, 50, 80, 255))
        d = ImageDraw.Draw(im)
        d.text((size//2, size//2), code[:2], fill=(255, 255, 255), font=font_badge, anchor="mm")

    mask = Image.new("L", (size, size), 0)
    dmask = ImageDraw.Draw(mask)
    dmask.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    draw_out = ImageDraw.Draw(out)
    draw_out.ellipse([(0, 0), (size - 1, size - 1)], outline=(255, 255, 255, 220), width=2)
    return out

# Base Studio Background (V2 Standard)
def create_studio_background():
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 14, 255))
    center_x = WIDTH // 2
    center_y = 750
    max_radius = 1150

    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
    norm_dist = np.clip(dist / max_radius, 0.0, 1.0)
    
    falloff = 0.5 + 0.5 * np.cos(norm_dist * math.pi)
    r = (22 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (36 * falloff + 8 * (1.0 - falloff)).astype(np.uint8)
    b = (64 * falloff + 14 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)

    dot_col = (140, 180, 240, 16)
    for x in range(30, WIDTH, 50):
        for y in range(40, HEIGHT, 50):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=dot_col)

    top_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    tg_draw = ImageDraw.Draw(top_glow)
    for y in range(240):
        a = int(24 * (1.0 - y / 240.0))
        tg_draw.line([(0, y), (WIDTH, y)], fill=(212, 175, 55, a))
    bg = Image.alpha_composite(bg, top_glow)
    return bg

BASE_BACKGROUND = create_studio_background()

def draw_star(draw, cx, cy, r=10, fill=(255, 215, 0, 255)):
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        cur_r = r if i % 2 == 0 else r * 0.45
        points.append((cx + cur_r * math.cos(angle), cy + cur_r * math.sin(angle)))
    draw.polygon(points, fill=fill)

def render_common_header(canvas, tag_text, title_text):
    draw = ImageDraw.Draw(canvas)
    header_y = 95
    draw.text((WIDTH//2, header_y), tag_text, fill=(212, 175, 55, 230), font=font_hud_tag, anchor="mm")
    draw.text((WIDTH//2, header_y + 44), title_text, fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")

def render_common_footer(canvas, debate_text, source_text):
    draw = ImageDraw.Draw(canvas)
    bot_pill_w = 980
    bot_pill_h = 76
    bx = (WIDTH - bot_pill_w) // 2
    by = 1680
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=38, fill=(14, 22, 38, 245), outline=(212, 175, 55, 230), width=2)
    draw.text((WIDTH//2, by + bot_pill_h//2), debate_text, fill=(255, 215, 0, 255), font=font_debate, anchor="mm")
    draw_star(draw, bx + 45, by + bot_pill_h//2, r=10)
    draw_star(draw, bx + bot_pill_w - 45, by + bot_pill_h//2, r=10)
    draw.text((WIDTH//2, 1800), source_text, fill=(130, 150, 180, 240), font=font_source, anchor="mm")

def catmull_rom_spline(pts, num_points=140):
    if len(pts) < 2:
        return pts
    extended = [pts[0]] + list(pts) + [pts[-1]]
    curve = []
    for i in range(len(extended) - 3):
        p0, p1, p2, p3 = extended[i], extended[i+1], extended[i+2], extended[i+3]
        for t in np.linspace(0, 1, num_points // (len(pts) - 1)):
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) +
                       (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) +
                       (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            curve.append((int(x), int(y)))
    return curve


# ======================================================================
# 1. LINE CHART V2: "TITAN CLASH: VOLUMETRIC DUEL"
# ======================================================================
def render_v2_line_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  HISTORIC ECONOMIC CLASH", "INDIA VS UK: THE OVERTAKE")

    # 1. Top Head-to-Head Duel Cards (Y=180 to Y=285)
    hud_y = 180
    card_w = 460
    card_h = 100
    
    # Left Card: India
    draw.rounded_rectangle([(70, hud_y), (70 + card_w, hud_y + card_h)], radius=18, fill=(18, 26, 42, 240), outline=(255, 153, 51, 230), width=2)
    f_ind = get_circular_flag("IND", size=54)
    canvas.paste(f_ind, (85, hud_y + 23), f_ind)
    draw.text((155, hud_y + 32), "INDIA (#5 GLOBAL)", fill=(255, 153, 51, 255), font=font_card_title, anchor="lm")
    draw.text((155, hud_y + 68), "$4.27 TRILLION", fill=(255, 255, 255, 255), font=font_hud_kpi_num, anchor="lm")

    # Right Card: United Kingdom
    draw.rounded_rectangle([(550, hud_y), (550 + card_w, hud_y + card_h)], radius=18, fill=(18, 26, 42, 240), outline=(56, 189, 248, 200), width=2)
    f_gbr = get_circular_flag("GBR", size=54)
    canvas.paste(f_gbr, (565, hud_y + 23), f_gbr)
    draw.text((635, hud_y + 32), "UK (#6 GLOBAL)", fill=(56, 189, 248, 255), font=font_card_title, anchor="lm")
    draw.text((635, hud_y + 68), "$3.49 TRILLION", fill=(255, 255, 255, 255), font=font_hud_kpi_num, anchor="lm")

    # Center VS & Lead Badge
    vs_w, vs_h = 240, 36
    vx = (WIDTH - vs_w) // 2
    vy = hud_y + card_h - 18
    draw.rounded_rectangle([(vx, vy), (vx + vs_w, vy + vs_h)], radius=18, fill=(10, 16, 28, 250), outline=(212, 175, 55, 255), width=2)
    draw.text((WIDTH//2, vy + vs_h//2), "INDIA LEADS BY +$780B", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")

    # 2. Main Volumetric Chart Canvas (Y=325 to Y=1060)
    chart_x1 = 110
    chart_x2 = 970
    chart_y1 = 345
    chart_y2 = 1040

    draw.rounded_rectangle([(chart_x1 - 20, chart_y1 - 20), (chart_x2 + 20, chart_y2 + 20)], radius=24, fill=(12, 18, 30, 220), outline=(56, 189, 248, 70), width=1)

    for val_tril in [0, 1, 2, 3, 4]:
        gy = chart_y2 - int((val_tril / 4.4) * (chart_y2 - chart_y1))
        draw.line([(chart_x1, gy), (chart_x2, gy)], fill=(100, 130, 180, 45), width=1)
        draw.text((chart_x1 - 10, gy), f"${val_tril}T", fill=(148, 163, 184, 240), font=font_axis, anchor="rm")

    pts_years = [1990, 2000, 2010, 2015, 2020, 2022, 2026]
    uk_gdp =    [1.09, 1.66, 2.49, 2.93, 2.71, 3.08, 3.49]
    ind_gdp =   [0.32, 0.47, 1.68, 2.10, 2.67, 3.39, 4.27]

    def get_pt_coords(year, gdp):
        px = chart_x1 + int(((year - 1990) / (2026 - 1990)) * (chart_x2 - chart_x1))
        py = chart_y2 - int((gdp / 4.4) * (chart_y2 - chart_y1))
        return px, py

    for yr in [1990, 2000, 2010, 2020, 2026]:
        tx, _ = get_pt_coords(yr, 0)
        draw.text((tx, chart_y2 + 15), str(yr), fill=(148, 163, 184, 240), font=font_axis, anchor="mt")

    # High-Tech 2022 Overtake Scanner Beam
    scan_x, _ = get_pt_coords(2022, 0)
    for w, a in [(14, 20), (6, 50), (2, 180)]:
        draw.line([(scan_x, chart_y1), (scan_x, chart_y2)], fill=(255, 215, 0, a), width=w)
    draw.rounded_rectangle([(scan_x - 38, chart_y2 - 28), (scan_x + 38, chart_y2 - 4)], radius=6, fill=(20, 30, 50, 240), outline=(255, 215, 0, 220), width=1)
    draw.text((scan_x, chart_y2 - 16), "2022", fill=(255, 215, 0, 255), font=font_axis, anchor="mm")

    # Smooth Spline Generation
    raw_uk = [get_pt_coords(y, v) for y, v in zip(pts_years, uk_gdp)]
    raw_ind = [get_pt_coords(y, v) for y, v in zip(pts_years, ind_gdp)]
    spline_uk = catmull_rom_spline(raw_uk, num_points=140)
    spline_ind = catmull_rom_spline(raw_ind, num_points=140)

    # GLOWING VOLUMETRIC AREA GRADIENT UNDER CURVES
    area_ind = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d_area_ind = ImageDraw.Draw(area_ind)
    ind_poly = [(spline_ind[0][0], chart_y2)] + spline_ind + [(spline_ind[-1][0], chart_y2)]
    d_area_ind.polygon(ind_poly, fill=(255, 153, 51, 55))

    area_uk = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d_area_uk = ImageDraw.Draw(area_uk)
    uk_poly = [(spline_uk[0][0], chart_y2)] + spline_uk + [(spline_uk[-1][0], chart_y2)]
    d_area_uk.polygon(uk_poly, fill=(56, 189, 248, 40))

    canvas = Image.alpha_composite(canvas, area_uk)
    canvas = Image.alpha_composite(canvas, area_ind)
    draw = ImageDraw.Draw(canvas)

    # Draw UK Spline
    for i in range(len(spline_uk) - 1):
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(56, 189, 248, 60), width=10)
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(56, 189, 248, 160), width=5)
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(255, 255, 255, 255), width=2)

    # Draw India Spline
    for i in range(len(spline_ind) - 1):
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 153, 51, 80), width=12)
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 215, 0, 200), width=6)
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 255, 255, 255), width=2)

    # Crossover Milestone Glow (Year 2022)
    cross_x, cross_y = get_pt_coords(2022, 3.20)
    draw.ellipse([(cross_x - 30, cross_y - 30), (cross_x + 30, cross_y + 30)], fill=(255, 215, 0, 80))
    draw.ellipse([(cross_x - 14, cross_y - 14), (cross_x + 14, cross_y + 14)], fill=(255, 255, 255, 240), outline=(255, 215, 0, 255), width=3)
    
    # Milestone Callout Banner
    call_w = 340
    call_h = 48
    cx = cross_x - call_w - 40
    cy = cross_y - 40
    draw.rounded_rectangle([(cx, cy), (cx + call_w, cy + call_h)], radius=12, fill=(18, 28, 48, 245), outline=(255, 215, 0, 240), width=2)
    draw.text((cx + call_w//2, cy + call_h//2), "2022: INDIA OVERTAKES UK!", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")
    draw_star(draw, cx + 22, cy + call_h//2, r=7)
    draw_star(draw, cx + call_w - 22, cy + call_h//2, r=7)
    draw.line([(cx + call_w, cy + call_h//2), (cross_x - 15, cross_y)], fill=(255, 215, 0, 200), width=2)

    # End Badges with Circular Flags
    ix, iy = spline_ind[-1]
    flag_ind = get_circular_flag("IND", size=48)
    canvas.paste(flag_ind, (ix - 24, iy - 24), flag_ind)
    draw.rounded_rectangle([(ix - 235, iy - 22), (ix - 35, iy + 22)], radius=10, fill=(10, 16, 28, 240), outline=(255, 153, 51, 230), width=1)
    draw.text((ix - 135, iy), "INDIA $4.27T (#5)", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")

    ux, uy = spline_uk[-1]
    flag_gbr = get_circular_flag("GBR", size=48)
    canvas.paste(flag_gbr, (ux - 24, uy - 24), flag_gbr)
    draw.rounded_rectangle([(ux - 235, uy - 22), (ux - 35, uy + 22)], radius=10, fill=(10, 16, 28, 240), outline=(56, 189, 248, 200), width=1)
    draw.text((ux - 135, uy), "UK $3.49T (#6)", fill=(220, 235, 255, 255), font=font_badge, anchor="mm")

    # 3. HISTORICAL MILESTONES DATA PANEL (Fills Y=1090 to Y=1480)
    m_y = 1090
    m_h = 106
    milestones = [
        {"year": "1990", "title": "COLONIAL ECONOMIC GAP", "desc": "UK was 3.4x larger than India ($1.09T vs $0.32T)", "tag": "3.4X GAP", "col": (148, 163, 184)},
        {"year": "2015", "title": "RAPID CONVERGENCE", "desc": "India crosses $2 Trillion, closing gap to $830 Billion", "tag": "CLOSING IN", "col": (56, 189, 248)},
        {"year": "2022", "title": "THE HISTORIC OVERTAKE", "desc": "India surges to $3.39T, permanently claiming #5 Global Rank", "tag": "OVERTAKE #5", "col": (255, 215, 0)},
    ]

    for idx, m in enumerate(milestones):
        py = m_y + idx * (m_h + 16)
        draw.rounded_rectangle([(70, py), (1010, py + m_h)], radius=16, fill=(16, 24, 38, 235), outline=m["col"] + (180,), width=2)
        draw.rounded_rectangle([(88, py + 16), (190, py + m_h - 16)], radius=12, fill=(10, 16, 26, 255), outline=m["col"] + (220,), width=1)
        draw.text((139, py + m_h//2), m["year"], fill=m["col"] + (255,), font=font_card_title, anchor="mm")
        draw.text((215, py + 34), m["title"], fill=(255, 255, 255, 255), font=font_card_title, anchor="lm")
        draw.text((215, py + 72), m["desc"], fill=(180, 200, 230, 255), font=font_card_sub, anchor="lm")
        draw.rounded_rectangle([(840, py + 24), (990, py + 60)], radius=8, fill=(10, 16, 26, 240), outline=m["col"] + (200,), width=1)
        draw.text((915, py + 42), m["tag"], fill=m["col"] + (255,), font=font_badge, anchor="mm")

    # 4. Lower-Third Dynamic Subtitle (Y=1530)
    cap_y = 1530
    caption_text = "INDIA OVERTAKES FORMER COLONIAL RULER!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 72
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 245), outline=(255, 215, 0, 220), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "WILL INDIA OVERTAKE GERMANY & JAPAN BY 2027? VOTE BELOW", "Data Source: World Bank & International Monetary Fund (IMF WEO)  •  LR Atlas")
    return canvas


# ======================================================================
# 2. DONUT CHART V2: "GLOBAL WEALTH & ENERGY MATRIX"
# ======================================================================
def render_v2_donut_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  ENERGY GEOPOLITICS", "WHO OWNS THE WORLD'S OIL?")

    # 1. Top Clash Card (Y=180 to Y=285): Venezuela vs Saudi Arabia
    hud_y = 180
    card_w = 460
    card_h = 100

    # Venezuela Card
    draw.rounded_rectangle([(70, hud_y), (70 + card_w, hud_y + card_h)], radius=18, fill=(18, 26, 42, 240), outline=(239, 68, 68, 230), width=2)
    f_ven = get_circular_flag("VEN", size=54)
    canvas.paste(f_ven, (85, hud_y + 23), f_ven)
    draw.text((155, hud_y + 32), "VENEZUELA (#1 OIL GIANT)", fill=(255, 215, 0, 255), font=font_card_title, anchor="lm")
    draw.text((155, hud_y + 68), "303 BILLION BARRELS (18.2%)", fill=(255, 255, 255, 255), font=font_card_val, anchor="lm")

    # Saudi Arabia Card
    draw.rounded_rectangle([(550, hud_y), (550 + card_w, hud_y + card_h)], radius=18, fill=(18, 26, 42, 240), outline=(16, 185, 129, 230), width=2)
    f_sau = get_circular_flag("SAU", size=54)
    canvas.paste(f_sau, (565, hud_y + 23), f_sau)
    draw.text((635, hud_y + 32), "SAUDI ARABIA (#2)", fill=(16, 185, 129, 255), font=font_card_title, anchor="lm")
    draw.text((635, hud_y + 68), "297 BILLION BARRELS (17.2%)", fill=(255, 255, 255, 255), font=font_card_val, anchor="lm")

    # Center Surprise Fact Pill (Clean vector stars, no tofu boxes!)
    vs_w, vs_h = 320, 36
    vx = (WIDTH - vs_w) // 2
    vy = hud_y + card_h - 18
    draw.rounded_rectangle([(vx, vy), (vx + vs_w, vy + vs_h)], radius=18, fill=(10, 16, 28, 250), outline=(212, 175, 55, 255), width=2)
    draw.text((WIDTH//2, vy + vs_h//2), "SURPRISE: SAUDI IS NOT #1!", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")
    draw_star(draw, vx + 22, vy + vs_h//2, r=6)
    draw_star(draw, vx + vs_w - 22, vy + vs_h//2, r=6)

    # 2. Large Volumetric 3D Donut Ring (Center lifted to 615 for generous clearance!)
    cx, cy = WIDTH // 2, 615
    outer_r = 290
    inner_r = 175

    oil_shares = [
        {"name": "Venezuela", "code": "VEN", "share": 18.2, "barrels": "303 B", "years": "300+ Yrs", "color": (239, 68, 68)},
        {"name": "Saudi Arabia", "code": "SAU", "share": 17.2, "barrels": "297 B", "years": "70 Yrs", "color": (16, 185, 129)},
        {"name": "Iran", "code": "IRN", "share": 11.9, "barrels": "208 B", "years": "140 Yrs", "color": (59, 130, 246)},
        {"name": "Canada", "code": "CAN", "share": 9.7, "barrels": "170 B", "years": "90 Yrs", "color": (245, 158, 11)},
        {"name": "Iraq", "code": "IRQ", "share": 8.4, "barrels": "145 B", "years": "95 Yrs", "color": (168, 85, 247)},
        {"name": "United Arab Emirates", "code": "UAE", "share": 6.5, "barrels": "113 B", "years": "85 Yrs", "color": (236, 72, 153)},
        {"name": "Rest of the World", "code": "ROW", "share": 28.1, "barrels": "514 B", "years": "Global", "color": (71, 85, 105)},
    ]

    start_deg = -90.0
    slice_centers = []

    ring_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    for seg in oil_shares:
        sweep = (seg["share"] / 100.0) * 360.0
        end_deg = start_deg + sweep
        mid_deg = start_deg + sweep / 2.0

        poly_pts = []
        for a in np.linspace(start_deg, end_deg, 30):
            rad = math.radians(a)
            poly_pts.append((cx + outer_r * math.cos(rad), cy + outer_r * math.sin(rad)))
        for a in np.linspace(end_deg, start_deg, 30):
            rad = math.radians(a)
            poly_pts.append((cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad)))

        slice_mask = Image.new("L", (WIDTH, HEIGHT), 0)
        s_draw = ImageDraw.Draw(slice_mask)
        s_draw.polygon(poly_pts, fill=255)

        code = seg["code"]
        flag_im = loaded_flags.get(code)

        slice_tex = Image.new("RGBA", (WIDTH, HEIGHT), seg["color"] + (255,))
        if flag_im:
            mid_rad = math.radians(mid_deg)
            mid_dist = (inner_r + outer_r) / 2.0
            scx = cx + mid_dist * math.cos(mid_rad)
            scy = cy + mid_dist * math.sin(mid_rad)

            fw, fh = 260, 160
            f_resized = flag_im.resize((fw, fh), Image.Resampling.LANCZOS)
            f_rot = f_resized.rotate(-mid_deg + 90, expand=True, resample=Image.Resampling.BICUBIC)
            rw, rh = f_rot.size
            slice_tex.paste(f_rot, (int(scx - rw//2), int(scy - rh//2)), f_rot)

            tint = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 45))
            slice_tex = Image.alpha_composite(slice_tex, tint)

        ring_layer.paste(slice_tex, (0, 0), slice_mask)

        for a in [start_deg, end_deg]:
            rad = math.radians(a)
            p_in = (cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad))
            p_out = (cx + outer_r * math.cos(rad), cy + outer_r * math.sin(rad))
            s_draw_ring = ImageDraw.Draw(ring_layer)
            s_draw_ring.line([p_in, p_out], fill=(10, 15, 25, 255), width=4)
            s_draw_ring.line([p_in, p_out], fill=(255, 255, 255, 120), width=1)

        slice_centers.append((seg, mid_deg))
        start_deg = end_deg

    r_draw = ImageDraw.Draw(ring_layer)
    r_draw.ellipse([(cx - outer_r, cy - outer_r), (cx + outer_r, cy + outer_r)], outline=(212, 175, 55, 200), width=3)
    r_draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], outline=(212, 175, 55, 200), width=3)

    canvas = Image.alpha_composite(canvas, ring_layer)
    draw = ImageDraw.Draw(canvas)

    # Direct Badges on/beside slices
    for seg, mid_deg in slice_centers:
        rad = math.radians(mid_deg)
        if seg["share"] >= 10.0:
            tr = (inner_r + outer_r) / 2.0
            tx = cx + tr * math.cos(rad)
            ty = cy + tr * math.sin(rad)
            
            pw, ph = 120, 44
            draw.rounded_rectangle([(tx - pw//2, ty - ph//2), (tx + pw//2, ty + ph//2)], radius=12, fill=(10, 16, 26, 245), outline=(255, 215, 0, 220), width=2)
            flag_mini = get_circular_flag(seg["code"], size=30)
            canvas.paste(flag_mini, (int(tx - pw//2 + 8), int(ty - 15)), flag_mini)
            draw.text((tx + 14, ty), f"{seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_pct, anchor="mm")
        elif seg["share"] >= 6.0:
            tr_in = outer_r - 8
            tr_out = outer_r + 38
            p_in = (cx + tr_in * math.cos(rad), cy + tr_in * math.sin(rad))
            p_out = (cx + tr_out * math.cos(rad), cy + tr_out * math.sin(rad))
            draw.line([p_in, p_out], fill=(255, 255, 255, 220), width=2)
            
            pw, ph = 110, 38
            draw.rounded_rectangle([(p_out[0] - pw//2, p_out[1] - ph//2), (p_out[0] + pw//2, p_out[1] + ph//2)], radius=10, fill=(10, 16, 26, 245), outline=seg["color"] + (240,), width=2)
            flag_mini = get_circular_flag(seg["code"], size=26)
            canvas.paste(flag_mini, (int(p_out[0] - pw//2 + 7), int(p_out[1] - 13)), flag_mini)
            draw.text((p_out[0] + 14, p_out[1]), f"{seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_pct, anchor="mm")

    # Center Hub with #1 Leader Crest
    draw.ellipse([(cx - inner_r + 6, cy - inner_r + 6), (cx + inner_r - 6, cy + inner_r - 6)], fill=(12, 18, 30, 250), outline=(212, 175, 55, 240), width=3)
    ven_flag_center = get_circular_flag("VEN", size=54)
    canvas.paste(ven_flag_center, (cx - 27, cy - 65), ven_flag_center)
    draw.text((cx, cy - 3), "VENEZUELA", fill=(255, 255, 255, 255), font=font_card_title, anchor="mm")
    draw.text((cx, cy + 28), "#1 WORLD LEADER", fill=(212, 175, 55, 255), font=font_badge, anchor="mm")
    draw_star(draw, cx - 88, cy + 28, r=7)
    draw_star(draw, cx + 88, cy + 28, r=7)
    draw.text((cx, cy + 54), "303 BILLION BBL (18.2%)", fill=(56, 189, 248, 255), font=font_badge, anchor="mm")

    # 3. FULL DETAILED GLOBAL LEADERBOARD PANEL (Y=960 to Y=1320)
    card_y = 960
    col_w = 460
    card_h = 76

    for idx, item in enumerate(oil_shares[:6]):
        col = idx % 2
        row = idx // 2
        px = 70 if col == 0 else 550
        py = card_y + row * 92

        draw.rounded_rectangle([(px, py), (px + col_w, py + card_h)], radius=16, fill=(16, 24, 38, 240), outline=item["color"] + (200,), width=2)
        flag_img = get_circular_flag(item["code"], size=48)
        canvas.paste(flag_img, (px + 14, py + 14), flag_img)

        draw.text((px + 74, py + 24), item["name"], fill=(255, 255, 255, 255), font=font_card_title, anchor="lm")
        draw.text((px + 74, py + 54), f"{item['barrels']}  •  {item['years']} Supply", fill=(148, 163, 184, 255), font=font_card_sub, anchor="lm")

        pw, ph = 96, 40
        p_rx = px + col_w - 14 - pw
        draw.rounded_rectangle([(p_rx, py + 18), (p_rx + pw, py + 18 + ph)], radius=10, fill=(10, 16, 26, 240), outline=item["color"] + (220,), width=1)
        draw.text((p_rx + pw//2, py + 18 + ph//2), f"{item['share']}%", fill=(255, 215, 0, 255), font=font_card_val, anchor="mm")

    # Lower Global Stat Strip (Y=1260 to Y=1330)
    strip_y = 1260
    draw.rounded_rectangle([(70, strip_y), (1010, strip_y + 68)], radius=14, fill=(12, 18, 30, 240), outline=(56, 189, 248, 160), width=1)
    draw.text((95, strip_y + 34), "GLOBAL OIL FACT", fill=(56, 189, 248, 255), font=font_badge, anchor="lm")
    draw.text((WIDTH//2 + 50, strip_y + 34), "TOP 6 NATIONS CONTROL 71.9% OF ALL EARTH'S OIL", fill=(255, 255, 255, 255), font=font_card_sub, anchor="mm")

    # 4. Lower-Third Dynamic Subtitle (Y=1430)
    cap_y = 1430
    caption_text = "VENEZUELA HOLDS MORE OIL THAN SAUDI ARABIA!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 72
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 245), outline=(255, 215, 0, 220), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "WHICH NATION CONTROLS THE FUTURE OF ENERGY? VOTE BELOW", "Data Source: OPEC Annual Statistical Bulletin & BP Statistical Review  •  LR Atlas")
    return canvas


# ======================================================================
# 3. SLOPE CHART V2: "DECADE POWER SHIFT INTELLIGENCE MATRIX"
# ======================================================================
def render_v2_slope_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  GEOPOLITICAL POWER SHIFT", "GLOBAL MILITARY EXPENDITURE")

    # 1. Top Movers Highlight Strip (Clean ASCII text, zero tofu boxes!)
    hud_y = 180
    strip_w = 940
    strip_h = 86
    sx = (WIDTH - strip_w) // 2
    draw.rounded_rectangle([(sx, hud_y), (sx + strip_w, hud_y + strip_h)], radius=18, fill=(14, 22, 38, 240), outline=(212, 175, 55, 220), width=2)

    draw.text((sx + 35, hud_y + 24), "GLOBAL DEFENSE TOTAL", fill=(148, 163, 184, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((sx + 35, hud_y + 58), "$840B -> $2.44 TRILLION", fill=(56, 189, 248, 255), font=font_card_val, anchor="lm")

    draw.line([(sx + 340, hud_y + 14), (sx + 340, hud_y + strip_h - 14)], fill=(255, 255, 255, 40), width=2)

    draw.text((sx + 370, hud_y + 24), "#1 BIGGEST SURGE", fill=(16, 185, 129, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((sx + 370, hud_y + 58), "CHINA (+1,245% SURGE)", fill=(255, 255, 255, 255), font=font_card_val, anchor="lm")

    draw.line([(sx + 660, hud_y + 14), (sx + 660, hud_y + strip_h - 14)], fill=(255, 255, 255, 40), width=2)

    draw.text((sx + 690, hud_y + 24), "BIGGEST FALL", fill=(239, 68, 68, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((sx + 690, hud_y + 58), "UK DROPPED #2 -> #6", fill=(239, 68, 68, 255), font=font_card_val, anchor="lm")

    # 2. Main Slope Duel Canvas
    x_left = 180
    x_right = 900
    y_start = 390
    y_gap = 138

    military_data = [
        {"name": "United States", "code": "USA", "v2000": 302, "v2024": 916, "r2000": 1, "r2024": 1, "trend": "+203% (HOLDS #1)", "color": (59, 130, 246), "status": "stable"},
        {"name": "China", "code": "CHN", "v2000": 22, "v2024": 296, "r2000": 5, "r2024": 2, "trend": "+1,245% SURGE", "color": (16, 185, 129), "status": "surging"},
        {"name": "Russia", "code": "RUS", "v2000": 9, "v2024": 109, "r2000": 6, "r2024": 3, "trend": "+1,110% SURGE", "color": (16, 185, 129), "status": "surging"},
        {"name": "India", "code": "IND", "v2000": 14, "v2024": 84, "r2000": 4, "r2024": 4, "trend": "+500% GROWTH", "color": (255, 153, 51), "status": "growth"},
        {"name": "Saudi Arabia", "code": "SAU", "v2000": 20, "v2024": 76, "r2000": 3, "r2024": 5, "trend": "+280% (SLIPPED)", "color": (245, 158, 11), "status": "slip"},
        {"name": "United Kingdom", "code": "GBR", "v2000": 35, "v2024": 75, "r2000": 2, "r2024": 6, "trend": "DROPPED #2 -> #6", "color": (239, 68, 68), "status": "dropped"},
    ]

    # Column Headers (Placed cleanly at Y=305 with zero overlap on USA)
    draw.rounded_rectangle([(x_left - 110, y_start - 75), (x_left + 110, y_start - 25)], radius=12, fill=(18, 28, 48, 240), outline=(56, 189, 248, 180), width=2)
    draw.text((x_left, y_start - 50), "YEAR 2000 ($840B)", fill=(56, 189, 248, 255), font=font_card_title, anchor="mm")

    draw.rounded_rectangle([(x_right - 110, y_start - 75), (x_right + 110, y_start - 25)], radius=12, fill=(18, 28, 48, 240), outline=(255, 215, 0, 200), width=2)
    draw.text((x_right, y_start - 50), "YEAR 2024 ($2.44T)", fill=(255, 215, 0, 255), font=font_card_title, anchor="mm")

    # Draw Slope Connecting Lasers
    for item in military_data:
        y1 = y_start + (item["r2000"] - 1) * y_gap
        y2 = y_start + (item["r2024"] - 1) * y_gap

        col = item["color"]
        draw.line([(x_left + 75, y1), (x_right - 75, y2)], fill=col + (60,), width=10)
        draw.line([(x_left + 75, y1), (x_right - 75, y2)], fill=col + (180,), width=5)
        draw.line([(x_left + 75, y1), (x_right - 75, y2)], fill=(255, 255, 255, 230), width=2)

        # Left Pill (Year 2000)
        draw.rounded_rectangle([(x_left - 120, y1 - 32), (x_left + 70, y1 + 32)], radius=16, fill=(12, 18, 30, 245), outline=col + (180,), width=1)
        draw.text((x_left - 100, y1), f"#{item['r2000']}", fill=(148, 163, 184, 255), font=font_badge, anchor="lm")
        f_left = get_circular_flag(item["code"], size=40)
        canvas.paste(f_left, (x_left - 65, y1 - 20), f_left)
        draw.text((x_left - 15, y1 - 10), item["code"], fill=(255, 255, 255, 255), font=font_card_title, anchor="lm")
        draw.text((x_left - 15, y1 + 14), f"${item['v2000']}B", fill=(56, 189, 248, 255), font=font_axis, anchor="lm")

        # Right Pill (Year 2024)
        draw.rounded_rectangle([(x_right - 70, y2 - 32), (x_right + 120, y2 + 32)], radius=16, fill=(12, 18, 30, 245), outline=col + (230,), width=2)
        f_right = get_circular_flag(item["code"], size=40)
        canvas.paste(f_right, (x_right - 60, y2 - 20), f_right)
        draw.text((x_right - 12, y2 - 10), item["code"], fill=(255, 255, 255, 255), font=font_card_title, anchor="lm")
        draw.text((x_right - 12, y2 + 14), f"${item['v2024']}B", fill=(255, 215, 0, 255), font=font_axis, anchor="lm")
        draw.text((x_right + 100, y2), f"#{item['r2024']}", fill=(255, 215, 0, 255), font=font_badge, anchor="rm")

        # Center Growth Tag on the slope
        mid_x = (x_left + x_right) // 2
        mid_y = (y1 + y2) // 2
        tw = int(draw.textlength(item["trend"], font=font_axis)) + 24
        draw.rounded_rectangle([(mid_x - tw//2, mid_y - 15), (mid_x + tw//2, mid_y + 15)], radius=8, fill=(8, 14, 24, 245), outline=col + (220,), width=1)
        draw.text((mid_x, mid_y), item["trend"], fill=col + (255,), font=font_axis, anchor="mm")

    # 3. GEOPOLITICAL TAKEAWAY CARD (Fills Y=1260 to Y=1370)
    takeaway_y = 1260
    draw.rounded_rectangle([(70, takeaway_y), (1010, takeaway_y + 110)], radius=16, fill=(16, 24, 38, 240), outline=(212, 175, 55, 200), width=2)
    draw.text((95, takeaway_y + 30), "STRATEGIC TAKEAWAY", fill=(212, 175, 55, 255), font=font_badge, anchor="lm")
    draw.text((95, takeaway_y + 60), "Asian military power exploded: China expanded 12x and India grew 6x,", fill=(255, 255, 255, 255), font=font_card_sub, anchor="lm")
    draw.text((95, takeaway_y + 86), "pushing historic European military powers (UK, France) down the ranks.", fill=(180, 200, 230, 255), font=font_card_sub, anchor="lm")

    # 4. Lower-Third Dynamic Subtitle (Y=1430)
    cap_y = 1430
    caption_text = "CHINA SURGES OVER 1,200% IN 24 YEARS!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 72
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 245), outline=(255, 215, 0, 220), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "CAN ANY NATION CHALLENGE US DEFENSE SUPREMACY? VOTE BELOW", "Data Source: Stockholm International Peace Research Institute (SIPRI 2024)  •  LR Atlas")
    return canvas


# ======================================================================
# GENERATE ALL MASTERPIECE SHOWCASES
# ======================================================================
print("Rendering Packed V2 Line Chart (Titan Clash)...")
im_line = render_v2_line_chart()
im_line.save("output/v2_line_chart_preview.png", "PNG")

print("Rendering Packed V2 Donut Chart (Energy Matrix)...")
im_donut = render_v2_donut_chart()
im_donut.save("output/v2_donut_chart_preview.png", "PNG")

print("Rendering Packed V2 Slope Chart (Power Shift Matrix)...")
im_slope = render_v2_slope_chart()
im_slope.save("output/v2_slope_chart_preview.png", "PNG")

print("Creating Combined 3-Panel Storyboard...")
combined = Image.new("RGBA", (WIDTH * 3 + 60, HEIGHT), (6, 8, 14, 255))
combined.paste(im_line, (15, 0))
combined.paste(im_donut, (WIDTH + 30, 0))
combined.paste(im_slope, (WIDTH * 2 + 45, 0))
combined.save("output/v2_all_chart_types_storyboard.png", "PNG")

print("All showcases successfully rendered and saved!")
