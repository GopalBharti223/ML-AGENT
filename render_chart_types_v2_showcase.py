"""V2 Masterpiece Broadcast Visual Showcases:
1. LINE CHART V2 ("Laser Line Duel"): Silky smooth spline curves + Year 2022 glowing scanner line + Milestone crossover badge.
2. DONUT/RING CHART V2 ("Frosted Asset Ring"): Numbers and flags written directly ON/BESIDE each donut slice (18.2%, 17.2%, etc.) + flag badges in lower cards.
3. SLOPE CHART V2 ("Decade Power Shift"): Color-coded outcomes (Green/Gold for surging climbers China & India, Red/Amber for UK drop #2->#6) + circular flag crests.
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
font_hud_title = get_font(46, bold=True)
font_hud_kpi_num = get_font(34, bold=True)
font_hud_kpi_lbl = get_font(20, bold=True)
font_label = get_font(24, bold=True)
font_val = get_font(28, bold=True)
font_badge = get_font(18, bold=True)
font_donut_slice_pct = get_font(22, bold=True)
font_donut_slice_lbl = get_font(16, bold=True)
font_debate = get_font(22, bold=True)
font_caption = get_font(36, bold=True)
font_source = get_font(19, bold=False)
font_axis = get_font(18, bold=False)

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
        # Fallback colored disc with code
        im = Image.new("RGBA", (size, size), (30, 50, 80, 255))
        d = ImageDraw.Draw(im)
        d.text((size//2, size//2), code[:2], fill=(255, 255, 255), font=font_badge, anchor="mm")

    # Make circle mask
    mask = Image.new("L", (size, size), 0)
    dmask = ImageDraw.Draw(mask)
    dmask.ellipse([(0, 0), (size - 1, size - 1)], fill=255)
    
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    # Add gold/white rim
    draw_out = ImageDraw.Draw(out)
    draw_out.ellipse([(0, 0), (size - 1, size - 1)], outline=(255, 255, 255, 220), width=1)
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
    r = (20 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (34 * falloff + 8 * (1.0 - falloff)).astype(np.uint8)
    b = (60 * falloff + 14 * (1.0 - falloff)).astype(np.uint8)
    
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)

    dot_col = (140, 180, 240, 14)
    for x in range(40, WIDTH, 60):
        for y in range(60, HEIGHT, 60):
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
    header_y = 105
    draw.text((WIDTH//2, header_y), tag_text, fill=(212, 175, 55, 230), font=font_hud_tag, anchor="mm")
    draw.text((WIDTH//2, header_y + 45), title_text, fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")

def render_common_footer(canvas, debate_text, source_text):
    draw = ImageDraw.Draw(canvas)
    bot_pill_w = 960
    bot_pill_h = 74
    bx = (WIDTH - bot_pill_w) // 2
    by = 1540
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=37, fill=(14, 22, 38, 240), outline=(212, 175, 55, 220), width=2)
    draw.text((WIDTH//2, by + bot_pill_h//2), debate_text, fill=(255, 215, 0, 255), font=font_debate, anchor="mm")
    draw_star(draw, bx + 45, by + bot_pill_h//2, r=10)
    draw_star(draw, bx + bot_pill_w - 45, by + bot_pill_h//2, r=10)
    draw.text((WIDTH//2, 1720), source_text, fill=(130, 150, 180, 240), font=font_source, anchor="mm")

# Pure Python / NumPy Catmull-Rom Spline for silky smooth lines
def catmull_rom_spline(pts, num_points=120):
    if len(pts) < 2:
        return pts
    # Duplicate ends
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
# 1. LINE CHART V2 ("LASER LINE DUEL")
# With Silky Spline Curves + 2022 Scanner Line + Flags
# ======================================================================
def render_v2_line_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  GLOBAL ECONOMIC DUELS", "INDIA VS UK: GDP OVERTAKE")

    # 1. Timeline & Live Values HUD
    hud_y = 220
    hud_w = 930
    hud_h = 78
    hx = (WIDTH - hud_w) // 2
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(14, 22, 38, 230), outline=(255, 215, 0, 220), width=2)
    draw.text((hx + 55, hud_y + hud_h//2), "OVERTAKE YEAR", fill=(148, 163, 184, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((hx + 235, hud_y + hud_h//2), "2022", fill=(255, 215, 0, 255), font=font_hud_kpi_num, anchor="lm")
    draw.line([(WIDTH//2, hud_y + 14), (WIDTH//2, hud_y + hud_h - 14)], fill=(255, 255, 255, 40), width=2)
    draw.text((WIDTH//2 + 45, hud_y + hud_h//2), "INDIA #5", fill=(255, 153, 51, 255), font=font_hud_kpi_num, anchor="lm")
    draw.text((WIDTH//2 + 225, hud_y + hud_h//2), "$3.40 TRILLION", fill=(56, 189, 248, 255), font=font_hud_kpi_lbl, anchor="lm")

    # 2. Line Chart Grid & Axes (Safe Corridor: Y=380 to Y=1300)
    chart_x1 = 120
    chart_x2 = 960
    chart_y1 = 380
    chart_y2 = 1300

    draw.rounded_rectangle([(chart_x1 - 20, chart_y1 - 20), (chart_x2 + 20, chart_y2 + 20)], radius=24, fill=(10, 16, 28, 190), outline=(56, 189, 248, 70), width=1)

    for val_tril in [0, 1, 2, 3, 4]:
        gy = chart_y2 - int((val_tril / 4.4) * (chart_y2 - chart_y1))
        draw.line([(chart_x1, gy), (chart_x2, gy)], fill=(100, 130, 180, 40), width=1)
        draw.text((chart_x1 - 10, gy), f"${val_tril}T", fill=(148, 163, 184, 240), font=font_axis, anchor="rm")

    pts_years = [1990, 2000, 2010, 2015, 2020, 2022, 2026]
    uk_gdp =    [1.09, 1.66, 2.49, 2.93, 2.71, 3.08, 3.49]
    ind_gdp =   [0.32, 0.47, 1.68, 2.10, 2.67, 3.39, 4.27]

    def get_pt_coords(year, gdp):
        px = chart_x1 + int(((year - 1990) / (2026 - 1990)) * (chart_x2 - chart_x1))
        py = chart_y2 - int((gdp / 4.4) * (chart_y2 - chart_y1))
        return px, py

    # Year ticks on bottom axis
    for yr in [1990, 2000, 2010, 2020, 2026]:
        tx, _ = get_pt_coords(yr, 0)
        draw.text((tx, chart_y2 + 15), str(yr), fill=(148, 163, 184, 240), font=font_axis, anchor="mt")

    # High-Tech Year 2022 Scanner Line (Glowing vertical beam)
    scan_x, _ = get_pt_coords(2022, 0)
    for w, a in [(12, 20), (6, 50), (2, 160)]:
        draw.line([(scan_x, chart_y1), (scan_x, chart_y2)], fill=(255, 215, 0, a), width=w)
    draw.rounded_rectangle([(scan_x - 42, chart_y2 - 32), (scan_x + 42, chart_y2 - 4)], radius=6, fill=(20, 30, 50, 240), outline=(255, 215, 0, 220), width=1)
    draw.text((scan_x, chart_y2 - 18), "2022", fill=(255, 215, 0, 255), font=font_axis, anchor="mm")

    # Generate Silky Spline Paths
    raw_uk = [get_pt_coords(y, v) for y, v in zip(pts_years, uk_gdp)]
    raw_ind = [get_pt_coords(y, v) for y, v in zip(pts_years, ind_gdp)]
    spline_uk = catmull_rom_spline(raw_uk, num_points=140)
    spline_ind = catmull_rom_spline(raw_ind, num_points=140)

    # Draw UK Spline (Neon Blue / Silver Laser)
    for i in range(len(spline_uk) - 1):
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(56, 189, 248, 60), width=10)
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(56, 189, 248, 140), width=5)
        draw.line([spline_uk[i], spline_uk[i+1]], fill=(255, 255, 255, 255), width=2)

    # Draw India Spline (Electric Saffron / Gold Laser)
    for i in range(len(spline_ind) - 1):
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 153, 51, 80), width=12)
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 215, 0, 180), width=6)
        draw.line([spline_ind[i], spline_ind[i+1]], fill=(255, 255, 255, 255), width=2)

    # Crossover Milestone Glow (Year 2022)
    cross_x, cross_y = get_pt_coords(2022, 3.20)
    draw.ellipse([(cross_x - 30, cross_y - 30), (cross_x + 30, cross_y + 30)], fill=(255, 215, 0, 70))
    draw.ellipse([(cross_x - 14, cross_y - 14), (cross_x + 14, cross_y + 14)], fill=(255, 255, 255, 230), outline=(255, 215, 0, 255), width=3)
    
    # Milestone Callout Banner (Safe placement at left)
    call_w = 340
    call_h = 50
    cx = cross_x - call_w - 40
    cy = cross_y - 40
    draw.rounded_rectangle([(cx, cy), (cx + call_w, cy + call_h)], radius=12, fill=(18, 28, 48, 240), outline=(255, 215, 0, 220), width=2)
    draw.text((cx + call_w//2, cy + call_h//2), "2022: INDIA OVERTAKES UK!", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")
    draw_star(draw, cx + 24, cy + call_h//2, r=7)
    draw_star(draw, cx + call_w - 24, cy + call_h//2, r=7)
    draw.line([(cx + call_w, cy + call_h//2), (cross_x - 15, cross_y)], fill=(255, 215, 0, 200), width=2)

    # End Badges with Circular Flags (2026 Projections)
    # India End Point (#5 Global)
    ix, iy = spline_ind[-1]
    flag_ind = get_circular_flag("IND", size=48)
    canvas.paste(flag_ind, (ix - 24, iy - 24), flag_ind)
    draw.rounded_rectangle([(ix - 235, iy - 22), (ix - 35, iy + 22)], radius=10, fill=(10, 16, 28, 230), outline=(255, 153, 51, 220), width=1)
    draw.text((ix - 135, iy), "INDIA $4.27T (#5)", fill=(255, 215, 0, 255), font=font_badge, anchor="mm")

    # UK End Point (#6 Global)
    ux, uy = spline_uk[-1]
    flag_gbr = get_circular_flag("GBR", size=48)
    canvas.paste(flag_gbr, (ux - 24, uy - 24), flag_gbr)
    draw.rounded_rectangle([(ux - 235, uy - 22), (ux - 35, uy + 22)], radius=10, fill=(10, 16, 28, 230), outline=(56, 189, 248, 180), width=1)
    draw.text((ux - 135, uy), "UK $3.49T (#6)", fill=(220, 235, 255, 255), font=font_badge, anchor="mm")

    # 3. Lower-Third Dynamic Subtitle
    cap_y = 1380
    caption_text = "INDIA SURPASSES FORMER COLONIAL RULER!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 68
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 235), outline=(255, 215, 0, 180), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "WILL INDIA OVERTAKE GERMANY & JAPAN BY 2027? VOTE BELOW", "Data Source: World Bank / International Monetary Fund (IMF WEO)  •  LR Atlas")
    return canvas


# ======================================================================
# 2. 3D FROSTED DONUT / RING CHART V2
# With Numbers & Flags directly ON/BESIDE each slice + Circular Flags in Cards!
# ======================================================================
def render_v2_donut_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  ENERGY GEOPOLITICS", "WHO OWNS THE WORLD'S OIL?")

    # 1. Total Reserves HUD
    hud_y = 220
    hud_w = 930
    hud_h = 78
    hx = (WIDTH - hud_w) // 2
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(14, 22, 38, 230), outline=(56, 189, 248, 180), width=2)
    draw.text((hx + 50, hud_y + hud_h//2), "YEAR: 2024", fill=(255, 215, 0, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.line([(hx + 200, hud_y + 14), (hx + 200, hud_y + hud_h - 14)], fill=(255, 255, 255, 40), width=2)
    draw.text((hx + 240, hud_y + hud_h//2), "GLOBAL TOTAL", fill=(148, 163, 184, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((hx + 420, hud_y + hud_h//2), "1,750 BILLION BARRELS", fill=(56, 189, 248, 255), font=font_hud_kpi_num, anchor="lm")

    # 2. Donut Ring Center & Radius
    cx, cy = WIDTH // 2, 680
    outer_r = 300
    inner_r = 180

    oil_shares = [
        {"name": "Venezuela", "code": "VEN", "share": 18.2, "barrels": "303 B", "color": (239, 68, 68)},
        {"name": "Saudi Arabia", "code": "SAU", "share": 17.2, "barrels": "297 B", "color": (16, 185, 129)},
        {"name": "Iran", "code": "IRN", "share": 11.9, "barrels": "208 B", "color": (59, 130, 246)},
        {"name": "Canada", "code": "CAN", "share": 9.7, "barrels": "170 B", "color": (245, 158, 11)},
        {"name": "Iraq", "code": "IRQ", "share": 8.4, "barrels": "145 B", "color": (168, 85, 247)},
        {"name": "United Arab Emirates", "code": "UAE", "share": 6.5, "barrels": "113 B", "color": (236, 72, 153)},
        {"name": "Rest of the World", "code": "ROW", "share": 28.1, "barrels": "514 B", "color": (71, 85, 105)},
    ]

    start_deg = -90.0
    slice_centers = []

    for seg in oil_shares:
        sweep = (seg["share"] / 100.0) * 360.0
        end_deg = start_deg + sweep
        mid_deg = start_deg + sweep / 2.0

        # Build arc polygon
        poly_pts = []
        for a in np.linspace(start_deg, end_deg, 30):
            rad = math.radians(a)
            poly_pts.append((cx + outer_r * math.cos(rad), cy + outer_r * math.sin(rad)))
        for a in np.linspace(end_deg, start_deg, 30):
            rad = math.radians(a)
            poly_pts.append((cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad)))

        c_col = seg["color"] + (235,)
        draw.polygon(poly_pts, fill=c_col)

        # Border separators
        for a in [start_deg, end_deg]:
            rad = math.radians(a)
            draw.line([(cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad)), (cx + outer_r * math.cos(rad), cy + outer_r * math.sin(rad))], fill=(10, 15, 25, 255), width=3)

        slice_centers.append((seg, mid_deg))
        start_deg = end_deg

    # NUMBERS DIRECTLY ON/BESIDE EACH SLICE (USER REQUEST!)
    for seg, mid_deg in slice_centers:
        rad = math.radians(mid_deg)
        # Position badge just inside or outside the donut rim
        if seg["share"] >= 10.0:
            # Inside the ring band
            tr = (inner_r + outer_r) / 2.0
            tx = cx + tr * math.cos(rad)
            ty = cy + tr * math.sin(rad)
            
            # Frosted pill on the slice
            pw, ph = 96, 42
            draw.rounded_rectangle([(tx - pw//2, ty - ph//2), (tx + pw//2, ty + ph//2)], radius=10, fill=(10, 16, 26, 230), outline=(255, 255, 255, 220), width=1)
            draw.text((tx, ty - 6), f"{seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_slice_pct, anchor="mm")
            draw.text((tx, ty + 12), seg["code"], fill=(255, 215, 0, 255), font=font_donut_slice_lbl, anchor="mm")
        elif seg["share"] >= 6.0:
            # Callout outside the slice for smaller segments
            tr_in = outer_r - 10
            tr_out = outer_r + 38
            p_in = (cx + tr_in * math.cos(rad), cy + tr_in * math.sin(rad))
            p_out = (cx + tr_out * math.cos(rad), cy + tr_out * math.sin(rad))
            draw.line([p_in, p_out], fill=(255, 255, 255, 200), width=2)
            
            pw, ph = 86, 36
            draw.rounded_rectangle([(p_out[0] - pw//2, p_out[1] - ph//2), (p_out[0] + pw//2, p_out[1] + ph//2)], radius=8, fill=(10, 16, 26, 230), outline=seg["color"] + (220,), width=1)
            draw.text((p_out[0], p_out[1]), f"{seg['code']} {seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_slice_lbl, anchor="mm")

    # Center Frosted Core (The Hub)
    draw.ellipse([(cx - inner_r + 6, cy - inner_r + 6), (cx + inner_r - 6, cy + inner_r - 6)], fill=(12, 18, 30, 250), outline=(212, 175, 55, 200), width=3)
    draw.text((cx, cy - 35), "WORLD LEADER", fill=(212, 175, 55, 255), font=font_badge, anchor="mm")
    draw_star(draw, cx - 80, cy - 35, r=7)
    draw_star(draw, cx + 80, cy - 35, r=7)
    draw.text((cx, cy + 5), "VENEZUELA", fill=(255, 255, 255, 255), font=font_label, anchor="mm")
    draw.text((cx, cy + 42), "303 BILLION BBL (18.2%)", fill=(56, 189, 248, 255), font=font_badge, anchor="mm")

    # 3. Ranked Breakdown Cards Below Donut with CIRCULAR COUNTRY FLAGS
    card_y = 1055
    col_w = 440
    for idx, item in enumerate(oil_shares[:6]):
        col = idx % 2
        row = idx // 2
        px = 80 if col == 0 else 560
        py = card_y + row * 82

        draw.rounded_rectangle([(px, py), (px + col_w, py + 72)], radius=14, fill=(14, 22, 38, 230), outline=item["color"] + (180,), width=2)
        
        # Real Country Flag Crest
        flag_img = get_circular_flag(item["code"], size=46)
        canvas.paste(flag_img, (px + 14, py + 13), flag_img)

        # Country Name & Percent Share
        draw.text((px + 72, py + 24), item["name"], fill=(255, 255, 255, 255), font=font_label, anchor="lm")
        draw.text((px + 72, py + 52), f"{item['share']}% ({item['barrels']})", fill=(56, 189, 248, 255), font=font_badge, anchor="lm")

    # 4. Lower-Third Dynamic Subtitle
    cap_y = 1380
    caption_text = "VENEZUELA HOLDS MORE OIL THAN SAUDI ARABIA!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 68
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 235), outline=(255, 215, 0, 180), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "WHICH NATION CONTROLS THE FUTURE OF ENERGY? VOTE BELOW", "Data Source: OPEC Annual Statistical Bulletin & BP Statistical Review  •  LR Atlas")
    return canvas


# ======================================================================
# 3. SLOPE CHART V2 ("DECADE POWER SHIFT")
# Dynamic Outcome Colors (Green/Gold Surge vs Amber/Red Drop) + Circular Flags
# ======================================================================
def render_v2_slope_chart():
    canvas = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(canvas)

    render_common_header(canvas, "LR ATLAS  •  GEOPOLITICAL POWER SHIFT", "GLOBAL MILITARY EXPENDITURE")

    # 1. Total Spending HUD
    hud_y = 220
    hud_w = 930
    hud_h = 78
    hx = (WIDTH - hud_w) // 2
    draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(14, 22, 38, 230), outline=(255, 215, 0, 220), width=2)
    draw.text((hx + 40, hud_y + hud_h//2), "2000 TOTAL", fill=(148, 163, 184, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((hx + 185, hud_y + hud_h//2), "$840 BILLION", fill=(56, 189, 248, 255), font=font_hud_kpi_num, anchor="lm")
    draw.line([(WIDTH//2 + 20, hud_y + 14), (WIDTH//2 + 20, hud_y + hud_h - 14)], fill=(255, 255, 255, 40), width=2)
    draw.text((WIDTH//2 + 50, hud_y + hud_h//2), "2024 TOTAL", fill=(148, 163, 184, 255), font=font_hud_kpi_lbl, anchor="lm")
    draw.text((WIDTH//2 + 200, hud_y + hud_h//2), "$2,440 BILLION", fill=(255, 215, 0, 255), font=font_hud_kpi_num, anchor="lm")

    # 2. Slope Pillars
    x_left = 180
    x_right = 900
    y_start = 390
    y_gap = 145

    military_data = [
        {"name": "United States", "code": "USA", "v2000": 302, "v2024": 916, "r2000": 1, "r2024": 1, "trend": "+203% (HOLDS #1)", "color": (59, 130, 246), "status": "stable"},
        {"name": "China", "code": "CHN", "v2000": 22, "v2024": 296, "r2000": 5, "r2024": 2, "trend": "+1,245% SURGE", "color": (16, 185, 129), "status": "surging"},
        {"name": "Russia", "code": "RUS", "v2000": 9, "v2024": 109, "r2000": 6, "r2024": 3, "trend": "+1,110% SURGE", "color": (16, 185, 129), "status": "surging"},
        {"name": "India", "code": "IND", "v2000": 14, "v2024": 84, "r2000": 4, "r2024": 4, "trend": "+500% GROWTH", "color": (255, 153, 51), "status": "growth"},
        {"name": "Saudi Arabia", "code": "SAU", "v2000": 20, "v2024": 76, "r2000": 3, "r2024": 5, "trend": "+280% (SLIPPED)", "color": (245, 158, 11), "status": "slip"},
        {"name": "United Kingdom", "code": "GBR", "v2000": 35, "v2024": 75, "r2000": 2, "r2024": 6, "trend": "DROPPED #2 -> #6", "color": (239, 68, 68), "status": "dropped"},
    ]

    # Column Headers
    draw.rounded_rectangle([(x_left - 100, y_start - 65), (x_left + 100, y_start - 15)], radius=12, fill=(18, 28, 48, 240), outline=(56, 189, 248, 160), width=2)
    draw.text((x_left, y_start - 40), "YEAR 2000", fill=(56, 189, 248, 255), font=font_label, anchor="mm")

    draw.rounded_rectangle([(x_right - 100, y_start - 65), (x_right + 100, y_start - 15)], radius=12, fill=(18, 28, 48, 240), outline=(255, 215, 0, 180), width=2)
    draw.text((x_right, y_start - 40), "YEAR 2024", fill=(255, 215, 0, 255), font=font_label, anchor="mm")

    # Draw Slope Connecting Lasers
    for item in military_data:
        y1 = y_start + (item["r2000"] - 1) * y_gap
        y2 = y_start + (item["r2024"] - 1) * y_gap

        col = item["color"]
        draw.line([(x_left + 70, y1), (x_right - 70, y2)], fill=col + (60,), width=8)
        draw.line([(x_left + 70, y1), (x_right - 70, y2)], fill=col + (180,), width=4)
        draw.line([(x_left + 70, y1), (x_right - 70, y2)], fill=(255, 255, 255, 230), width=1)

        # Left Pill (Year 2000) with Circular Flag
        draw.rounded_rectangle([(x_left - 120, y1 - 28), (x_left + 65, y1 + 28)], radius=14, fill=(12, 18, 30, 240), outline=col + (180,), width=1)
        draw.text((x_left - 100, y1), f"#{item['r2000']}", fill=(148, 163, 184, 255), font=font_badge, anchor="lm")
        f_left = get_circular_flag(item["code"], size=36)
        canvas.paste(f_left, (x_left - 65, y1 - 18), f_left)
        draw.text((x_left - 20, y1 - 8), item["code"], fill=(255, 255, 255, 255), font=font_label, anchor="lm")
        draw.text((x_left - 20, y1 + 14), f"${item['v2000']}B", fill=(56, 189, 248, 255), font=font_axis, anchor="lm")

        # Right Pill (Year 2024) with Circular Flag
        draw.rounded_rectangle([(x_right - 65, y2 - 28), (x_right + 120, y2 + 28)], radius=14, fill=(12, 18, 30, 240), outline=col + (220,), width=2)
        f_right = get_circular_flag(item["code"], size=36)
        canvas.paste(f_right, (x_right - 55, y2 - 18), f_right)
        draw.text((x_right - 10, y2 - 8), item["code"], fill=(255, 255, 255, 255), font=font_label, anchor="lm")
        draw.text((x_right - 10, y2 + 14), f"${item['v2024']}B", fill=(255, 215, 0, 255), font=font_axis, anchor="lm")
        draw.text((x_right + 100, y2), f"#{item['r2024']}", fill=(255, 215, 0, 255), font=font_badge, anchor="rm")

        # Center Dynamic Growth Tag
        mid_x = (x_left + x_right) // 2
        mid_y = (y1 + y2) // 2
        tw = int(draw.textlength(item["trend"], font=font_axis)) + 22
        draw.rounded_rectangle([(mid_x - tw//2, mid_y - 14), (mid_x + tw//2, mid_y + 14)], radius=6, fill=(8, 14, 24, 230), outline=col + (200,), width=1)
        draw.text((mid_x, mid_y), item["trend"], fill=col + (255,), font=font_axis, anchor="mm")

    # 3. Lower-Third Dynamic Subtitle
    cap_y = 1380
    caption_text = "CHINA SURGES OVER 1,200% IN 24 YEARS!"
    cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
    cap_h = 68
    cx_cap = (WIDTH - cap_w) // 2
    draw.rounded_rectangle([(cx_cap, cap_y - cap_h//2), (cx_cap + cap_w, cap_y + cap_h//2)], radius=18, fill=(12, 20, 36, 235), outline=(255, 215, 0, 180), width=2)
    draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
    draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    render_common_footer(canvas, "CAN ANY NATION CHALLENGE US DEFENSE SUPREMACY? VOTE BELOW", "Data Source: Stockholm International Peace Research Institute (SIPRI 2024)  •  LR Atlas")
    return canvas


# ======================================================================
# GENERATE ALL MASTERPIECE SHOWCASES
# ======================================================================
print("Rendering Masterpiece V2 Line Chart...")
im_line = render_v2_line_chart()
im_line.save("output/v2_line_chart_preview.png", "PNG")

print("Rendering Masterpiece V2 Donut Chart (with Slice Numbers & Flags)...")
im_donut = render_v2_donut_chart()
im_donut.save("output/v2_donut_chart_preview.png", "PNG")

print("Rendering Masterpiece V2 Slope Chart (with Outcome Colors & Flags)...")
im_slope = render_v2_slope_chart()
im_slope.save("output/v2_slope_chart_preview.png", "PNG")

print("Creating Combined 3-Panel Storyboard...")
combined = Image.new("RGBA", (WIDTH * 3 + 60, HEIGHT), (6, 8, 14, 255))
combined.paste(im_line, (15, 0))
combined.paste(im_donut, (WIDTH + 30, 0))
combined.paste(im_slope, (WIDTH * 2 + 45, 0))
combined.save("output/v2_all_chart_types_storyboard.png", "PNG")

print("All showcases successfully rendered and saved!")
