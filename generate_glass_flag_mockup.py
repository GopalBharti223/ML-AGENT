"""Generate a high-res comparison mockup: Normal Flat Bar vs User's 3D Glassmorphic Flag Bar."""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Canvas Dimensions (Shorts Portrait)
WIDTH = 1080
HEIGHT = 1920

# Create base canvas with dark cyber grid vibe
canvas = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 25, 255))
draw = ImageDraw.Draw(canvas)

# Fonts
try:
    font_title = ImageFont.truetype("arialbd.ttf", 44)
    font_sub = ImageFont.truetype("arialbd.ttf", 24)
    font_label = ImageFont.truetype("arialbd.ttf", 26)
    font_val = ImageFont.truetype("arialbd.ttf", 30)
    font_tag = ImageFont.truetype("arial.ttf", 20)
    font_badge = ImageFont.truetype("arialbd.ttf", 24)
except Exception:
    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_label = ImageFont.load_default()
    font_val = ImageFont.load_default()
    font_tag = ImageFont.load_default()
    font_badge = ImageFont.load_default()

# 1. Header
draw.text((WIDTH//2, 120), "LR ATLAS // VISUAL INNOVATION LABS", fill=(212, 175, 55, 255), font=font_tag, anchor="mm")
draw.text((WIDTH//2, 180), "BAR DESIGN SHOWDOWN", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
draw.text((WIDTH//2, 230), "Normal Flat Bar  vs  3D Glassmorphic Flag Bar", fill=(56, 189, 248, 255), font=font_sub, anchor="mm")

# Subtle glowing horizontal divider
draw.line([(100, 270), (WIDTH - 100, 270)], fill=(30, 41, 59, 255), width=3)


# Function to create a 3D Glassmorphic Flag Bar
def create_glassmorphic_flag_bar(bar_w, bar_h, flag_img_path, border_color=(255, 215, 0), glow=True):
    """Creates a rounded bar with embedded flag, frosted glass overlay, and 3D mirror shine."""
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    radius = bar_h // 2  # Pill shape

    # Create mask for rounded pill
    mask = Image.new("L", (bar_w, bar_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

    # 1. Flag Texture
    if os.path.exists(flag_img_path):
        flag = Image.open(flag_img_path).convert("RGBA")
        # Resize to fill bar height and crop/stretch
        flag_w = int(bar_h * (flag.width / flag.height))
        if flag_w < bar_w:
            flag = flag.resize((bar_w, bar_h), Image.Resampling.LANCZOS)
        else:
            flag = flag.resize((flag_w, bar_h), Image.Resampling.LANCZOS)
            flag = flag.crop((0, 0, bar_w, bar_h))
        # Dim flag slightly for cyber glass feel (contrast with text)
        enhancer = ImageEnhance.Brightness(flag)
        flag = enhancer.enhance(0.75)
    else:
        flag = Image.new("RGBA", (bar_w, bar_h), (40, 60, 90, 255))

    # Apply rounded mask to flag
    bar.paste(flag, (0, 0), mask)

    # 2. Dark Gradient Overlay (from left 20% to right 100% for text readability)
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for x in range(bar_w):
        # subtle dark fade towards the right where numbers sit
        alpha = int(70 + 130 * (x / bar_w))
        grad_draw.line([(x, 0), (x, bar_h)], fill=(10, 15, 26, alpha))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

    # 3. 3D Specular Mirror Highlight (Top Glass Sheen)
    sheen = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    sheen_draw = ImageDraw.Draw(sheen)
    sheen_h = int(bar_h * 0.42)
    for y in range(sheen_h):
        alpha = int(140 * (1.0 - (y / sheen_h)**1.5))
        sheen_draw.line([(radius//2, y + 2), (bar_w - radius//2, y + 2)], fill=(255, 255, 255, alpha))
    bar = Image.alpha_composite(bar, Image.composite(sheen, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

    # 4. Glowing Neon Glass Border
    border_layer = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(border_layer)
    b_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=border_color + (240,), width=3)
    bar = Image.alpha_composite(bar, border_layer)

    return bar


# -------------------------------------------------------------
# SECTION 1: OLD FLAT BAR (Typical / Standard)
# -------------------------------------------------------------
draw.text((100, 330), "❌ STYLE A: STANDARD FLAT BARS (Typical Channels)", fill=(244, 63, 94, 255), font=font_sub)
draw.text((100, 365), "Flat solid color, no texture, no glass depth.", fill=(148, 163, 184, 255), font=font_tag)

flat_samples = [
    ("India #5", "$4.02T", 650, (34, 197, 94)),
    ("United Kingdom #6", "$3.54T", 560, (239, 68, 68)),
]

cur_y = 420
for name, val, b_w, col in flat_samples:
    # Flat bar
    draw.rounded_rectangle([(100, cur_y), (100 + b_w, cur_y + 70)], radius=35, fill=col + (200,), outline=(255,255,255,100), width=2)
    # Circle
    draw.ellipse([(110, cur_y + 10), (160, cur_y + 60)], fill=(15, 23, 42, 255), outline=(255,255,255,200), width=2)
    draw.text((135, cur_y + 35), name[:2].upper(), fill=(255, 255, 255, 255), font=font_badge, anchor="mm")
    # Name
    draw.text((180, cur_y + 35), name, fill=(255, 255, 255, 255), font=font_label, anchor="lm")
    # Value
    draw.text((100 + b_w + 20, cur_y + 35), val, fill=(255, 255, 255, 255), font=font_val, anchor="lm")
    cur_y += 105


# Divider
draw.line([(100, cur_y + 30), (WIDTH - 100, cur_y + 30)], fill=(30, 41, 59, 255), width=3)


# -------------------------------------------------------------
# SECTION 2: USER'S 3D GLASSMORPHIC FLAG BARS
# -------------------------------------------------------------
section_2_y = cur_y + 70
draw.text((100, section_2_y), "✨ STYLE B: 3D GLASSMORPHIC FLAG BARS (Your Concept!)", fill=(34, 197, 94, 255), font=font_sub)
draw.text((100, section_2_y + 35), "Embedded flag texture + Frosted glass tint + Top mirror reflection line + Neon border.", fill=(148, 163, 184, 255), font=font_tag)

glass_samples = [
    ("United States #1", "$29.05T", 800, "assets/flags_hires/us.png", (255, 215, 0), "★ #1 LEADER"),
    ("China #2", "$18.76T", 710, "assets/flags_hires/cn.png", (239, 68, 68), "CHALLENGER"),
    ("Germany #3", "$4.62T", 610, "assets/flags_hires/de.png", (56, 189, 248), ""),
    ("Japan #4", "$4.13T", 580, "assets/flags_hires/jp.png", (168, 85, 247), ""),
    ("India #5", "$4.02T", 570, "assets/flags_hires/in.png", (34, 197, 94), "★ OVERTAKE!"),
    ("United Kingdom #6", "$3.54T", 520, "assets/flags_hires/gb.png", (239, 68, 68), ""),
]

bar_y = section_2_y + 85
for name, val, b_w, flag_path, border_col, badge_text in glass_samples:
    # 1. Render Glass Flag Bar
    bar_h = 92
    glass_bar = create_glassmorphic_flag_bar(b_w, bar_h, flag_path, border_color=border_col)
    canvas.paste(glass_bar, (100, bar_y), glass_bar)

    # 2. Left Monogram / Flag Crest
    crest_x = 112
    crest_y = bar_y + 11
    crest_size = 70
    draw.ellipse([(crest_x, crest_y), (crest_x + crest_size, crest_y + crest_size)], fill=(15, 23, 42, 230), outline=border_col + (255,), width=3)
    code = name.split()[0][:3].upper()
    if "United States" in name: code = "USA"
    if "United Kingdom" in name: code = "UK"
    draw.text((crest_x + crest_size//2, crest_y + crest_size//2), code, fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

    # 3. Country Name (Bold with dark shadow for 100% contrast over flag)
    text_x = crest_x + crest_size + 20
    text_y = bar_y + bar_h // 2
    # Shadow
    draw.text((text_x + 2, text_y + 2), name, fill=(0, 0, 0, 255), font=font_label, anchor="lm")
    draw.text((text_x, text_y), name, fill=(255, 255, 255, 255), font=font_label, anchor="lm")

    # 4. Optional Badge inside bar
    if badge_text:
        badge_w = 140
        badge_h = 28
        bx = text_x + int(draw.textlength(name, font=font_label)) + 20
        by = text_y - badge_h // 2
        draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=6, fill=border_col + (200,))
        draw.text((bx + badge_w//2, by + badge_h//2), badge_text, fill=(0, 0, 0, 255), font=font_tag, anchor="mm")

    # 5. Value outside/edge of bar (Large, Crisp, Unmissable)
    val_x = 100 + b_w + 18
    draw.text((val_x + 2, text_y + 2), val, fill=(0, 0, 0, 255), font=font_val, anchor="lm")
    draw.text((val_x, text_y), val, fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    bar_y += 122

# Bottom watermark
draw.text((WIDTH//2, HEIGHT - 80), "LR ATLAS // NEXT-GEN VIRAL SHORTS ENGINE", fill=(100, 116, 139, 255), font=font_tag, anchor="mm")

output_path = r"output\glassmorphic_flag_mockup_comparison.png"
os.makedirs("output", exist_ok=True)
canvas.save(output_path, "PNG")
print(f"Mockup saved successfully to: {output_path}")
