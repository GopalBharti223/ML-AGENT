"""Generate High-Fidelity Still Previews for Masterpiece V3.
Produces:
1. preview_still_guessing.jpg (The 4 vibrant neon back-glows + huge highlighted question)
2. preview_still_reveal.jpg (The emerald neon reveal + dimmed wrong options)
"""

import os
import sys
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WIDTH = 1080
HEIGHT = 1920

output_dir = os.path.join("output", "studio_quiz_masterpiece_v3")
os.makedirs(output_dir, exist_ok=True)

def get_font(size, bold=True):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try: return ImageFont.truetype(name, size)
    except: return ImageFont.load_default()

font_badge = get_font(28, bold=True)
font_q_normal = get_font(44, bold=True)
font_q_hero = get_font(54, bold=True)
font_hint = get_font(28, bold=True)
font_timer_num = get_font(84, bold=True)
font_timer_label = get_font(26, bold=True)
font_card_letter = get_font(38, bold=True)
font_card_name = get_font(42, bold=True)
font_bottom_main = get_font(34, bold=True)
font_bottom_sub = get_font(24, bold=True)

# ----------------------------------------------------------------------
# 1. LOAD ROUNDED FLAGS
# ----------------------------------------------------------------------
def load_round_flag(code, size=(96, 64)):
    p1 = os.path.join("assets", "flags_hires", f"{code}.png")
    p2 = os.path.join("assets", "flags", f"{code}.png")
    path = p1 if os.path.exists(p1) else p2
    im = Image.open(path).convert("RGBA")
    im = im.resize(size, Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    draw_m = ImageDraw.Draw(mask)
    draw_m.rounded_rectangle([(0,0), size], radius=12, fill=255)
    im.putalpha(mask)
    border = Image.new("RGBA", size, (0,0,0,0))
    draw_b = ImageDraw.Draw(border)
    draw_b.rounded_rectangle([(0,0), (size[0]-1, size[1]-1)], radius=12, outline=(255,255,255,140), width=2)
    return Image.alpha_composite(im, border)

flag_id = load_round_flag("id")
flag_jp = load_round_flag("jp")
flag_kr = load_round_flag("kr")
flag_nz = load_round_flag("nz")
flag_jp_hero = load_round_flag("jp", size=(260, 172))

# ----------------------------------------------------------------------
# 2. PRECOMPUTE VIBRANT NEON BACKLIGHT HALOS
# ----------------------------------------------------------------------
CARD_W = 940
CARD_H = 126
BLUR_PAD = 60

def make_vibrant_glow(w, h, pad, color_rgb, alpha=210, blur_r=30):
    img = Image.new("RGBA", (w + pad*2, h + pad*2), (0,0,0,0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(pad - 6, pad - 6), (pad + w + 6, pad + h + 6)], radius=26, fill=(*color_rgb, alpha))
    return img.filter(ImageFilter.GaussianBlur(blur_r))

# 4 Distinct Neon Halos (Vivid, saturated, high-contrast)
glow_cyan = make_vibrant_glow(CARD_W, CARD_H, BLUR_PAD, (6, 182, 212), alpha=200, blur_r=32)      # Cyan
glow_gold = make_vibrant_glow(CARD_W, CARD_H, BLUR_PAD, (245, 158, 11), alpha=210, blur_r=32)     # Gold
glow_purple = make_vibrant_glow(CARD_W, CARD_H, BLUR_PAD, (168, 85, 247), alpha=200, blur_r=32)   # Purple
glow_coral = make_vibrant_glow(CARD_W, CARD_H, BLUR_PAD, (244, 63, 94), alpha=200, blur_r=32)     # Coral
glow_emerald = make_vibrant_glow(CARD_W, CARD_H, BLUR_PAD, (16, 185, 129), alpha=240, blur_r=36)  # Reveal Emerald

options_data = [
    {
        "letter": "A",
        "code": "id",
        "name": "INDONESIA",
        "flag": flag_id,
        "glow": glow_cyan,
        "theme_col": (6, 182, 212),
        "card_fill": (10, 22, 38, 245),
        "correct": False
    },
    {
        "letter": "B",
        "code": "jp",
        "name": "JAPAN",
        "flag": flag_jp,
        "glow": glow_gold,
        "theme_col": (245, 158, 11),
        "card_fill": (30, 22, 10, 245),
        "correct": True
    },
    {
        "letter": "C",
        "code": "kr",
        "name": "SOUTH KOREA",
        "flag": flag_kr,
        "glow": glow_purple,
        "theme_col": (168, 85, 247),
        "card_fill": (24, 14, 38, 245),
        "correct": False
    },
    {
        "letter": "D",
        "code": "nz",
        "name": "NEW ZEALAND",
        "flag": flag_nz,
        "glow": glow_coral,
        "theme_col": (244, 63, 94),
        "card_fill": (32, 12, 22, 245),
        "correct": False
    },
]

# ----------------------------------------------------------------------
# 3. BASE STUDIO CANVAS (Velvet Abyss with Subtle Stage Lighting)
# ----------------------------------------------------------------------
def create_studio_canvas():
    base = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 15, 255))
    draw = ImageDraw.Draw(base)
    # Deep vertical gradient
    for y in range(0, HEIGHT, 4):
        ratio = y / HEIGHT
        r = int(9 * (1 - ratio) + 4 * ratio)
        g = int(12 * (1 - ratio) + 6 * ratio)
        b = int(24 * (1 - ratio) + 12 * ratio)
        draw.rectangle([(0, y), (WIDTH, y+4)], fill=(r, g, b, 255))
        
    # Top Stage Spotlight (Electric Blue & Amber)
    spot = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    s_draw = ImageDraw.Draw(spot)
    for r_i in range(450, 0, -15):
        a = int(35 * (1 - r_i/450))
        s_draw.ellipse([(WIDTH//2 - r_i, 200 - r_i), (WIDTH//2 + r_i, 200 + r_i)], fill=(30, 58, 138, a))
        
    return Image.alpha_composite(base, spot)

BASE_CANVAS = create_studio_canvas()

# ----------------------------------------------------------------------
# 4. RENDER GUESSING STILL (Frame during countdown)
# ----------------------------------------------------------------------
def render_guessing_still():
    canvas = BASE_CANVAS.copy()
    draw = ImageDraw.Draw(canvas)
    
    # TOP HEADER BADGE
    badge_w, badge_h = 390, 52
    bx = (WIDTH - badge_w) // 2
    by = 95
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=26, fill=(18, 26, 44, 220), outline=(245, 158, 11, 200), width=2)
    draw.text((WIDTH//2, by + badge_h//2), "⚡ WORLD GEOGRAPHY IQ ⚡", fill=(251, 191, 36, 255), font=font_badge, anchor="mm")
    
    # HUGE HIGH-IMPACT QUESTION WITH HIGHLIGHTS
    # Line 1: Which country has over
    draw.text((WIDTH//2, 195), "Which country has over", fill=(241, 245, 249, 255), font=font_q_normal, anchor="mm")
    
    # Line 2: 🔥 6,800 ISLANDS 🔥 (Radiant Neon Amber)
    draw.text((WIDTH//2 + 3, 260 + 3), "🔥 6,800 ISLANDS 🔥", fill=(0, 0, 0, 220), font=font_q_hero, anchor="mm")
    draw.text((WIDTH//2, 260), "🔥 6,800 ISLANDS 🔥", fill=(251, 191, 36, 255), font=font_q_hero, anchor="mm")
    
    # Line 3: and the world's fastest
    draw.text((WIDTH//2, 325), "and the world's fastest", fill=(241, 245, 249, 255), font=font_q_normal, anchor="mm")
    
    # Line 4: ⚡ BULLET TRAINS? ⚡ (Electric Ice-Cyan)
    draw.text((WIDTH//2 + 3, 390 + 3), "⚡ BULLET TRAINS? ⚡", fill=(0, 0, 0, 220), font=font_q_hero, anchor="mm")
    draw.text((WIDTH//2, 390), "⚡ BULLET TRAINS? ⚡", fill=(56, 189, 248, 255), font=font_q_hero, anchor="mm")
    
    # Clue Pill
    hint_w, hint_h = 760, 54
    hx = (WIDTH - hint_w) // 2
    hy = 465
    draw.rounded_rectangle([(hx, hy), (hx + hint_w, hy + hint_h)], radius=18, fill=(16, 24, 40, 220), outline=(245, 158, 11, 140), width=1)
    draw.text((WIDTH//2, hy + hint_h//2), "💡 CLUE: Famous for Mount Fuji & Cherry Blossoms", fill=(253, 230, 138, 255), font=font_hint, anchor="mm")

    # COUNTDOWN CONSOLE (Centered at Y=640)
    center_y = 630
    draw.text((WIDTH//2 + 3, center_y - 35 + 3), "4", fill=(0, 0, 0, 220), font=font_timer_num, anchor="mm")
    draw.text((WIDTH//2, center_y - 35), "4", fill=(245, 158, 11, 255), font=font_timer_num, anchor="mm")
    draw.text((WIDTH//2, center_y + 30), "SECONDS TO GUESS", fill=(148, 163, 184, 255), font=font_timer_label, anchor="mm")
    
    # Glowing Sleek Countdown Bar
    bar_w = 940
    bar_x = (WIDTH - bar_w) // 2
    bar_y = center_y + 65
    bar_h = 16
    draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], radius=8, fill=(24, 32, 50, 220))
    # Active 80% progress
    draw.rounded_rectangle([(bar_x, bar_y), (bar_x + int(bar_w * 0.75), bar_y + bar_h)], radius=8, fill=(245, 158, 11, 255))

    # 4 OPTIONS WITH VIBRANT NEON GLOWS (Y: 820 to 1480, generous 160px gap)
    card_x = (WIDTH - CARD_W) // 2
    start_y = 820
    gap_y = 160
    
    for i, opt in enumerate(options_data):
        cy = start_y + i * gap_y
        
        # 1. PASTE VIBRANT NEON GLOW BACKLIGHT
        canvas.paste(opt["glow"], (card_x - BLUR_PAD, cy - BLUR_PAD), opt["glow"])
        draw = ImageDraw.Draw(canvas)
        
        # 2. CARD BODY (Deep obsidian tinted glass)
        draw.rounded_rectangle([(card_x, cy), (card_x + CARD_W, cy + CARD_H)], radius=22, fill=opt["card_fill"], outline=(*opt["theme_col"], 230), width=3)
        
        # Top-edge subtle 1px highlight bevel
        draw.line([(card_x + 30, cy + 1), (card_x + CARD_W - 30, cy + 1)], fill=(255, 255, 255, 50), width=1)
        
        # 3. VIBRANT LETTER BADGE [ A / B / C / D ]
        badge_box = [(card_x + 22, cy + 22), (card_x + 102, cy + CARD_H - 22)]
        draw.rounded_rectangle(badge_box, radius=14, fill=opt["theme_col"])
        draw.text((card_x + 62, cy + CARD_H // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
        
        # 4. FLAG
        canvas.paste(opt["flag"], (card_x + 128, cy + (CARD_H - 64)//2), opt["flag"])
        draw = ImageDraw.Draw(canvas)
        
        # 5. COUNTRY NAME (Large, crisp, authoritative)
        draw.text((card_x + 252, cy + CARD_H // 2), opt["name"], fill=(255, 255, 255, 255), font=font_card_name, anchor="lm")
        
    # BOTTOM COMMENT DRIVER
    foot_w = 940
    foot_h = 135
    foot_x = (WIDTH - foot_w) // 2
    foot_y = 1660
    draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=22, fill=(14, 20, 34, 230), outline=(245, 158, 11, 160), width=2)
    draw.text((WIDTH//2, foot_y + 40), "💬 Drop your guess in the comments!", fill=(251, 191, 36, 255), font=font_bottom_main, anchor="mm")
    draw.text((WIDTH//2, foot_y + 92), "Can you guess it before time runs out?", fill=(203, 213, 225, 255), font=font_bottom_sub, anchor="mm")
    
    return canvas

# ----------------------------------------------------------------------
# 5. RENDER REVEAL STILL (Emerald Halo on Japan, wrong dimmed)
# ----------------------------------------------------------------------
def render_reveal_still():
    canvas = BASE_CANVAS.copy()
    draw = ImageDraw.Draw(canvas)
    
    # TOP HEADER BADGE
    badge_w, badge_h = 390, 52
    bx = (WIDTH - badge_w) // 2
    by = 95
    draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=26, fill=(18, 26, 44, 220), outline=(245, 158, 11, 200), width=2)
    draw.text((WIDTH//2, by + badge_h//2), "⚡ WORLD GEOGRAPHY IQ ⚡", fill=(251, 191, 36, 255), font=font_badge, anchor="mm")
    
    # QUESTION (Dimmed slightly so reveal is hero)
    draw.text((WIDTH//2, 195), "Which country has over", fill=(156, 163, 175, 200), font=font_q_normal, anchor="mm")
    draw.text((WIDTH//2, 260), "🔥 6,800 ISLANDS 🔥", fill=(251, 191, 36, 220), font=font_q_hero, anchor="mm")
    draw.text((WIDTH//2, 325), "and the world's fastest", fill=(156, 163, 175, 200), font=font_q_normal, anchor="mm")
    draw.text((WIDTH//2, 390), "⚡ BULLET TRAINS? ⚡", fill=(56, 189, 248, 220), font=font_q_hero, anchor="mm")
    
    # HERO JAPAN FLAG WITH GOLDEN HALO (Y: 520 to 740)
    fw, fh = flag_jp_hero.size
    fx = (WIDTH - fw) // 2
    fy = 510
    
    # Soft Sunburst Halo
    halo = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    h_draw = ImageDraw.Draw(halo)
    for r_i in range(180, 0, -10):
        a = int(45 * (1 - r_i/180))
        h_draw.ellipse([(WIDTH//2 - r_i, fy + fh//2 - r_i), (WIDTH//2 + r_i, fy + fh//2 + r_i)], fill=(245, 158, 11, a))
    canvas = Image.alpha_composite(canvas, halo)
    draw = ImageDraw.Draw(canvas)
    
    # Paste Flag
    canvas.paste(flag_jp_hero, (fx, fy), flag_jp_hero)
    draw = ImageDraw.Draw(canvas)
    
    draw.text((WIDTH//2, fy + fh + 40), "JAPAN 🇯🇵", fill=(255, 255, 255, 255), font=font_q_hero, anchor="mm")

    # 4 OPTIONS (B explodes in Emerald; A, C, D dimmed to near-black)
    card_x = (WIDTH - CARD_W) // 2
    start_y = 820
    gap_y = 160
    
    for i, opt in enumerate(options_data):
        cy = start_y + i * gap_y
        
        if opt["correct"]:
            # OPTION B: EXPLODING NEON EMERALD GREEN HALO
            canvas.paste(glow_emerald, (card_x - BLUR_PAD, cy - BLUR_PAD), glow_emerald)
            draw = ImageDraw.Draw(canvas)
            
            # Rich Emerald Obsidian Card
            draw.rounded_rectangle([(card_x, cy), (card_x + CARD_W, cy + CARD_H)], radius=22, fill=(4, 46, 30, 250), outline=(52, 211, 153, 255), width=3)
            
            # Top-edge gold shimmer line
            draw.line([(card_x + 30, cy + 1), (card_x + CARD_W - 30, cy + 1)], fill=(255, 255, 255, 90), width=1)
            
            # Letter Badge
            badge_box = [(card_x + 22, cy + 22), (card_x + 102, cy + CARD_H - 22)]
            draw.rounded_rectangle(badge_box, radius=14, fill=(16, 185, 129))
            draw.text((card_x + 62, cy + CARD_H // 2), opt["letter"], fill=(255, 255, 255, 255), font=font_card_letter, anchor="mm")
            
            # Flag
            canvas.paste(opt["flag"], (card_x + 128, cy + (CARD_H - 64)//2), opt["flag"])
            draw = ImageDraw.Draw(canvas)
            
            # Country Name
            draw.text((card_x + 252, cy + CARD_H // 2), opt["name"], fill=(255, 255, 255, 255), font=font_card_name, anchor="lm")
            
            # Clean Gold Checkmark
            draw.text((card_x + CARD_W - 65, cy + CARD_H // 2), "✓", fill=(52, 211, 153, 255), font=font_q_hero, anchor="mm")
            
        else:
            # DIMMED WRONG OPTIONS (Dark shadow fade)
            draw.rounded_rectangle([(card_x, cy), (card_x + CARD_W, cy + CARD_H)], radius=20, fill=(10, 14, 22, 120), outline=(30, 40, 58, 80), width=1)
            
            badge_box = [(card_x + 22, cy + 24), (card_x + 102, cy + CARD_H - 24)]
            draw.rounded_rectangle(badge_box, radius=12, fill=(20, 26, 38, 140))
            draw.text((card_x + 62, cy + CARD_H // 2), opt["letter"], fill=(100, 116, 139, 140), font=font_card_letter, anchor="mm")
            
            canvas.paste(opt["flag"], (card_x + 128, cy + (CARD_H - 64)//2), opt["flag"])
            draw = ImageDraw.Draw(canvas)
            
            draw.text((card_x + 252, cy + CARD_H // 2), opt["name"], fill=(100, 116, 139, 140), font=font_card_name, anchor="lm")
            
    # WELCOMING DAILY SUBSCRIBE BANNER
    foot_w = 940
    foot_h = 145
    foot_x = (WIDTH - foot_w) // 2
    foot_y = 1650
    
    sub_glow = make_vibrant_glow(foot_w, foot_h, BLUR_PAD, (220, 38, 38), alpha=180, blur_r=26)
    canvas.paste(sub_glow, (foot_x - BLUR_PAD, foot_y - BLUR_PAD), sub_glow)
    draw = ImageDraw.Draw(canvas)
    
    draw.rounded_rectangle([(foot_x, foot_y), (foot_x + foot_w, foot_y + foot_h)], radius=22, fill=(220, 38, 38, 245), outline=(254, 202, 202, 220), width=2)
    draw.text((WIDTH//2, foot_y + 45), "🔔 SUBSCRIBE FOR DAILY TRIVIA QUIZZES!", fill=(255, 255, 255, 255), font=font_bottom_main, anchor="mm")
    draw.text((WIDTH//2, foot_y + 100), "Test your brain every day • Can you get tomorrow's right?", fill=(254, 226, 226, 255), font=font_bottom_sub, anchor="mm")
    
    return canvas

# ----------------------------------------------------------------------
# 6. SAVE PREVIEWS
# ----------------------------------------------------------------------
print("Rendering preview_still_guessing.jpg...")
img_guessing = render_guessing_still()
p_guessing = os.path.join(output_dir, "preview_still_guessing.jpg")
img_guessing.convert("RGB").save(p_guessing, quality=95)
print("Saved:", p_guessing)

print("Rendering preview_still_reveal.jpg...")
img_reveal = render_reveal_still()
p_reveal = os.path.join(output_dir, "preview_still_reveal.jpg")
img_reveal.convert("RGB").save(p_reveal, quality=95)
print("Saved:", p_reveal)

print("✅ High-fidelity still previews generated successfully!")
