"""Generate a smooth waving flag demo inside a 3D glassmorphic bar."""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

WIDTH = 900
HEIGHT = 200

os.makedirs("output", exist_ok=True)

# Load Indian flag
flag_path = "assets/flags_hires/in.png"
if not os.path.exists(flag_path):
    import urllib.request
    urllib.request.urlretrieve("https://flagcdn.com/w640/in.png", flag_path)

base_flag = Image.open(flag_path).convert("RGBA")

# Target bar dimensions
bar_w = 700
bar_h = 96
radius = bar_h // 2

# Resize flag to cover bar with extra padding for wave
pad = 20
flag_w = bar_w + pad * 2
flag_h = bar_h + pad * 2
base_flag = base_flag.resize((flag_w, flag_h), Image.Resampling.LANCZOS)
flag_np = np.array(base_flag)

frames = []
total_frames = 30  # 1 second loop at 30fps

# Rounded mask for the bar
mask = Image.new("L", (bar_w, bar_h), 0)
mask_draw = ImageDraw.Draw(mask)
mask_draw.rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

# Fonts
try:
    font_label = ImageFont.truetype("arialbd.ttf", 26)
    font_val = ImageFont.truetype("arialbd.ttf", 28)
    font_badge = ImageFont.truetype("arialbd.ttf", 22)
except Exception:
    font_label = ImageFont.load_default()
    font_val = ImageFont.load_default()
    font_badge = ImageFont.load_default()

for f in range(total_frames):
    t = f / total_frames * 2 * math.pi  # Phase angle

    # 1. Apply Sine Wave Ripple Displacement using NumPy
    # Wave traveling from left to right: y' = y + A * sin(kx - omega*t)
    h, w, c = flag_np.shape
    y_indices, x_indices = np.indices((h, w))

    # Amplitude 6px, wavelength ~140px
    wave_shift = (6.0 * np.sin(2 * math.pi * x_indices / 140.0 - t)).astype(np.float32)
    new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)

    # Displaced flag
    waved_flag_np = flag_np[new_y, x_indices]

    # Add realistic cloth fold shading (peaks brighter, troughs slightly darker)
    shading = (0.88 + 0.18 * np.sin(2 * math.pi * x_indices / 140.0 - t + math.pi/4))[:, :, np.newaxis]
    waved_flag_np[:, :, :3] = np.clip(waved_flag_np[:, :, :3] * shading, 0, 255).astype(np.uint8)

    waved_flag = Image.fromarray(waved_flag_np, "RGBA")
    # Crop to bar_w, bar_h
    waved_flag = waved_flag.crop((pad, pad, pad + bar_w, pad + bar_h))

    # 2. Build Glassmorphic Bar
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_flag, (0, 0), mask)

    # Dark gradient overlay for text readability
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for x in range(bar_w):
        alpha = int(70 + 130 * (x / bar_w))
        grad_draw.line([(x, 0), (x, bar_h)], fill=(10, 15, 26, alpha))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

    # Top Mirror Specular Highlight
    sheen = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    sheen_draw = ImageDraw.Draw(sheen)
    sheen_h = int(bar_h * 0.42)
    for y in range(sheen_h):
        alpha = int(140 * (1.0 - (y / sheen_h)**1.5))
        sheen_draw.line([(radius//2, y + 2), (bar_w - radius//2, y + 2)], fill=(255, 255, 255, alpha))
    bar = Image.alpha_composite(bar, Image.composite(sheen, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), mask))

    # Neon Emerald Border
    border_layer = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(border_layer)
    b_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=(34, 197, 94, 240), width=3)
    bar = Image.alpha_composite(bar, border_layer)

    # 3. Canvas Composition
    frame_canvas = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 25, 255))
    f_draw = ImageDraw.Draw(frame_canvas)

    bar_x = 40
    bar_y = 50
    frame_canvas.paste(bar, (bar_x, bar_y), bar)

    # Left Crest
    crest_x = bar_x + 12
    crest_y = bar_y + 12
    crest_size = 72
    f_draw.ellipse([(crest_x, crest_y), (crest_x + crest_size, crest_y + crest_size)], fill=(15, 23, 42, 230), outline=(34, 197, 94, 255), width=3)
    f_draw.text((crest_x + crest_size//2, crest_y + crest_size//2), "IND", fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

    # Name
    text_x = crest_x + crest_size + 20
    text_y = bar_y + bar_h // 2
    f_draw.text((text_x + 2, text_y + 2), "India #5", fill=(0, 0, 0, 255), font=font_label, anchor="lm")
    f_draw.text((text_x, text_y), "India #5", fill=(255, 255, 255, 255), font=font_label, anchor="lm")

    # Value
    val_x = bar_x + bar_w + 18
    f_draw.text((val_x + 2, text_y + 2), "$4.02T", fill=(0, 0, 0, 255), font=font_val, anchor="lm")
    f_draw.text((val_x, text_y), "$4.02T", fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    frames.append(frame_canvas.convert("RGB"))

# Save as GIF demo
gif_path = "output/waving_flag_bar_demo.gif"
frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=33, loop=0)
print(f"Demo GIF saved to: {gif_path}")
