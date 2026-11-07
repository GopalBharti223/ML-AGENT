"""Demo showing the improved Luxury Frosted Glass / Titanium Edge vs the old green outline."""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

WIDTH = 1080
HEIGHT = 1000

canvas = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 25, 255))
draw = ImageDraw.Draw(canvas)

try:
    font_title = ImageFont.truetype("arialbd.ttf", 36)
    font_sub = ImageFont.truetype("arialbd.ttf", 22)
    font_label = ImageFont.truetype("arialbd.ttf", 26)
    font_val = ImageFont.truetype("arialbd.ttf", 28)
    font_badge = ImageFont.truetype("arialbd.ttf", 20)
except Exception:
    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_label = ImageFont.load_default()
    font_val = ImageFont.load_default()
    font_badge = ImageFont.load_default()

draw.text((WIDTH//2, 80), "BORDER DESIGN COMPARISON", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
draw.text((WIDTH//2, 125), "Which feel is more premium? Old Green Outline vs New Titanium Glass Rim", fill=(148, 163, 184, 255), font=font_sub, anchor="mm")

# Common Bar specs
bar_w = 750
bar_h = 96
radius = bar_h // 2

# Flag setup
flag_path = "assets/flags_hires/in.png"
base_flag = Image.open(flag_path).convert("RGBA").resize((bar_w, bar_h), Image.Resampling.LANCZOS)
enhancer = ImageEnhance.Brightness(base_flag)
base_flag = enhancer.enhance(0.72)

mask = Image.new("L", (bar_w, bar_h), 0)
mask_draw = ImageDraw.Draw(mask)
mask_draw.rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

# Gradient overlay
grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
grad_draw = ImageDraw.Draw(grad)
for x in range(bar_w):
    alpha = int(60 + 130 * (x / bar_w))
    grad_draw.line([(x, 0), (x, bar_h)], fill=(10, 15, 26, alpha))


# -------------------------------------------------------------
# 1. OLD GREEN BORDER (User correctly noted: looks too simple/cheap)
# -------------------------------------------------------------
draw.text((80, 210), "❌ OLD: Flat Green Outline (Looks like cheap plastic)", fill=(244, 63, 94, 255), font=font_sub)

old_bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
old_bar.paste(base_flag, (0, 0), mask)
old_bar = Image.alpha_composite(old_bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

# Old flat green line
old_border = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
old_b_draw = ImageDraw.Draw(old_border)
old_b_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=(34, 197, 94, 240), width=3)
old_bar = Image.alpha_composite(old_bar, old_border)

canvas.paste(old_bar, (80, 260), old_bar)

# Monogram & Text
draw.ellipse([(92, 272), (92+72, 272+72)], fill=(15, 23, 42, 230), outline=(34, 197, 94, 255), width=2)
draw.text((128, 308), "IND", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")
draw.text((185, 308), "India #1", fill=(255, 255, 255, 255), font=font_label, anchor="lm")
draw.text((80 + bar_w + 20, 308), "1.44 Billion", fill=(255, 255, 255, 255), font=font_val, anchor="lm")


# -------------------------------------------------------------
# 2. NEW TITANIUM GLASS RIM (Apple Vision Pro / Luxury Glass Slab)
# -------------------------------------------------------------
draw.text((80, 480), "✨ NEW: Frosted Titanium Glass Rim (Polished Glass Bevel + Dual Lighting)", fill=(34, 197, 94, 255), font=font_sub)

new_bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
new_bar.paste(base_flag, (0, 0), mask)
new_bar = Image.alpha_composite(new_bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

# Top Specular Highlight (Reflection of studio light)
sheen = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
sheen_draw = ImageDraw.Draw(sheen)
sheen_h = int(bar_h * 0.44)
for y in range(sheen_h):
    alpha = int(170 * (1.0 - (y / sheen_h)**1.4))
    sheen_draw.line([(radius//2, y + 2), (bar_w - radius//2, y + 2)], fill=(255, 255, 255, alpha))
new_bar = Image.alpha_composite(new_bar, Image.composite(sheen, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

# Luxury Beveled Glass Rim (Dual light: Bright white top rim, subtle ambient gold/cyan tint)
glass_rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
rim_draw = ImageDraw.Draw(glass_rim)

# 1. Subtle translucent outer stroke (2px)
rim_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=(255, 255, 255, 60), width=2)
# 2. Razor-thin Top Light Catch (1px bright white on upper half)
rim_draw.arc([(1, 1), (bar_w - 2, bar_h - 2)], start=180, end=360, fill=(255, 255, 255, 210), width=2)
# 3. Soft ambient glow on the bottom (ground shadow)
rim_draw.arc([(1, 1), (bar_w - 2, bar_h - 2)], start=0, end=180, fill=(0, 0, 0, 140), width=2)

new_bar = Image.alpha_composite(new_bar, glass_rim)

canvas.paste(new_bar, (80, 530), new_bar)

# Monogram & Text with Glass Ring
draw.ellipse([(92, 542), (92+72, 542+72)], fill=(15, 23, 42, 240), outline=(255, 255, 255, 120), width=2)
draw.arc([(92, 542), (92+72, 542+72)], start=180, end=360, fill=(255, 255, 255, 240), width=2)
draw.text((128, 578), "IND", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

# Text with drop shadow
draw.text((187, 580), "India #1", fill=(0, 0, 0, 255), font=font_label, anchor="lm")
draw.text((185, 578), "India #1", fill=(255, 255, 255, 255), font=font_label, anchor="lm")

# Gold Champion Pill
pill_w = 120
pill_h = 24
draw.rounded_rectangle([(300, 566), (300 + pill_w, 566 + pill_h)], radius=5, fill=(212, 175, 55, 220))
draw.text((360, 578), "★ #1 WORLD", fill=(0, 0, 0, 255), font=font_badge, anchor="mm")

# Value
draw.text((80 + bar_w + 22, 580), "1.44 Billion", fill=(0, 0, 0, 255), font=font_val, anchor="lm")
draw.text((80 + bar_w + 20, 578), "1.44 Billion", fill=(255, 255, 255, 255), font=font_val, anchor="lm")


# -------------------------------------------------------------
# 3. CHINA #2 VARIANT (With Titanium Glass Rim)
# -------------------------------------------------------------
china_flag = Image.open("assets/flags_hires/cn.png").convert("RGBA").resize((bar_w - 60, bar_h), Image.Resampling.LANCZOS)
china_flag = ImageEnhance.Brightness(china_flag).enhance(0.72)

cn_mask = Image.new("L", (bar_w - 60, bar_h), 0)
ImageDraw.Draw(cn_mask).rounded_rectangle([(0, 0), (bar_w - 60, bar_h)], radius=radius, fill=255)

cn_bar = Image.new("RGBA", (bar_w - 60, bar_h), (0, 0, 0, 0))
cn_bar.paste(china_flag, (0, 0), cn_mask)
cn_grad = grad.crop((0, 0, bar_w - 60, bar_h))
cn_bar = Image.alpha_composite(cn_bar, Image.composite(cn_grad, Image.new("RGBA", (bar_w - 60, bar_h), (0,0,0,0)), cn_mask))

# Titanium Glass Rim on China
cn_rim = Image.new("RGBA", (bar_w - 60, bar_h), (0, 0, 0, 0))
cn_r_draw = ImageDraw.Draw(cn_rim)
cn_r_draw.rounded_rectangle([(1, 1), (bar_w - 62, bar_h - 2)], radius=radius, outline=(255, 255, 255, 50), width=2)
cn_r_draw.arc([(1, 1), (bar_w - 62, bar_h - 2)], start=180, end=360, fill=(255, 255, 255, 200), width=2)
cn_r_draw.arc([(1, 1), (bar_w - 62, bar_h - 2)], start=0, end=180, fill=(0, 0, 0, 140), width=2)

cn_sheen = sheen.crop((0, 0, bar_w - 60, bar_h))
cn_bar = Image.alpha_composite(cn_bar, Image.composite(cn_sheen, Image.new("RGBA", (bar_w - 60, bar_h), (0,0,0,0)), cn_mask))
cn_bar = Image.alpha_composite(cn_bar, cn_rim)

canvas.paste(cn_bar, (80, 680), cn_bar)

# Monogram & Text
draw.ellipse([(92, 692), (92+72, 692+72)], fill=(15, 23, 42, 240), outline=(255, 255, 255, 120), width=2)
draw.arc([(92, 692), (92+72, 692+72)], start=180, end=360, fill=(255, 255, 255, 240), width=2)
draw.text((128, 728), "CHN", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")
draw.text((185, 728), "China #2", fill=(255, 255, 255, 255), font=font_label, anchor="lm")
draw.text((80 + bar_w - 60 + 20, 728), "1.41 Billion", fill=(255, 255, 255, 255), font=font_val, anchor="lm")

# Save
output_path = "output/border_design_comparison.png"
canvas.save(output_path, "PNG")
print(f"Comparison saved to: {output_path}")
