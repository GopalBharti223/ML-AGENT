"""Generate a static 1080x1920 image for the Xbox vs PlayStation market share short.
The image includes a header, a HUD box with the two percentages, and simple branding.
"""

import os
from PIL import Image, ImageDraw, ImageFont

# Output directory (timestamped)
import datetime
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
output_dir = os.path.join('output', 'gaming_vs_console_20s', timestamp)
os.makedirs(output_dir, exist_ok=True)

WIDTH, HEIGHT = 1080, 1920
canvas = Image.new('RGBA', (WIDTH, HEIGHT), (18, 18, 18, 255))  # dark background
draw = ImageDraw.Draw(canvas)

# Helper to load fonts (fallback to default if missing)
def get_font(size, bold=True):
    names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "tahomabd.ttf" if bold else "tahoma.ttf",
    ]
    for fn in names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

# Fonts
font_header = get_font(36, bold=True)
font_hud_label = get_font(24, bold=True)
font_hud_val = get_font(40, bold=True)
font_footer = get_font(20, bold=False)

# 1. Header
header_text = "Xbox vs PlayStation – 2026 Market Share"
draw.text((WIDTH // 2, 150), header_text, font=font_header, fill=(255, 255, 255, 255), anchor="mm")

# 2. HUD box
hud_w, hud_h = 860, 200
hx = (WIDTH - hud_w) // 2
hud_y = 400
hud_border = (255, 215, 0, 200)
draw.rounded_rectangle([(hx, hud_y), (hx + hud_w, hud_y + hud_h)], radius=20, fill=(30, 30, 30, 230), outline=hud_border, width=3)

# Labels and values
# Left side – Xbox
draw.text((hx + 80, hud_y + hud_h // 2), "Xbox", font=font_hud_label, fill=(255, 255, 255, 255), anchor="lm")
draw.text((hx + 260, hud_y + hud_h // 2), "27%", font=font_hud_val, fill=(0, 255, 0, 255), anchor="lm")
# Right side – PlayStation
draw.text((hx + hud_w - 260, hud_y + hud_h // 2), "PlayStation", font=font_hud_label, fill=(255, 255, 255, 255), anchor="rm")
draw.text((hx + hud_w - 80, hud_y + hud_h // 2), "45%", font=font_hud_val, fill=(0, 120, 255, 255), anchor="rm")

# 3. Footer (call‑to‑action)
footer = "Who are you voting for? #gaming #shorts"
draw.text((WIDTH // 2, HEIGHT - 150), footer, font=font_footer, fill=(200, 200, 200, 255), anchor="mm")

# Save image
image_path = os.path.join(output_dir, "gaming_short.png")
canvas.save(image_path)
print(f"✅ Image saved to {image_path}")

