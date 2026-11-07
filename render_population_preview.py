"""Render Polished Full 1080x1920 Climax Frame & 3-Second Video Preview for World Population Short."""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

WIDTH = 1080
HEIGHT = 1920

os.makedirs("output", exist_ok=True)

# 7 Countries Data
POPULATION_DATA = [
    {"name": "India", "code": "IND", "val_str": "1.44 B", "val": 1.44, "flag": "assets/flags_hires/in.png", "badge": "★ #1 WORLD"},
    {"name": "China", "code": "CHN", "val_str": "1.41 B", "val": 1.41, "flag": "assets/flags_hires/cn.png", "badge": "HISTORIC #1"},
    {"name": "United States", "code": "USA", "val_str": "342 M", "val": 0.342, "flag": "assets/flags_hires/us.png", "badge": ""},
    {"name": "Indonesia", "code": "IDN", "val_str": "280 M", "val": 0.280, "flag": "assets/flags_hires/id.png", "badge": ""},
    {"name": "Pakistan", "code": "PAK", "val_str": "245 M", "val": 0.245, "flag": "assets/flags_hires/pk.png", "badge": ""},
    {"name": "Nigeria", "code": "NGA", "val_str": "228 M", "val": 0.228, "flag": "assets/flags_hires/ng.png", "badge": ""},
    {"name": "Bangladesh", "code": "BGD", "val_str": "175 M", "val": 0.175, "flag": "assets/flags_hires/bd.png", "badge": ""},
]

# Fonts (using Windows Segoe UI / Arial for clean unicode rendering)
def get_font(size, bold=True):
    font_names = ["segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_hud_tag = get_font(22, bold=True)
font_hud_title = get_font(42, bold=True)
font_hud_sub = get_font(26, bold=True)
font_label = get_font(25, bold=True)
font_val = get_font(28, bold=True)
font_badge = get_font(18, bold=True)
font_debate = get_font(22, bold=True)

# Pre-load flags
prepped_flags = {}
for item in POPULATION_DATA:
    f_path = item["flag"]
    im = Image.open(f_path).convert("RGBA")
    prepped_flags[item["code"]] = im

bar_h = 92
radius = bar_h // 2
pad = 20

def render_frame(phase_t=0.0):
    # Deep Cyber Navy Background
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 25, 255))
    draw = ImageDraw.Draw(canvas)

    # Clean Dark Studio Background Gradient (vertical fade)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(10 + 6 * ratio)
        g = int(14 + 10 * ratio)
        b = int(24 + 16 * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))

    # Subtle Glowing Grid Lines (Cyber aesthetic)
    for gy in range(250, HEIGHT - 250, 180):
        draw.line([(60, gy), (WIDTH - 60, gy)], fill=(25, 35, 55, 60), width=1)

    # 1. TOP HUD (Header)
    header_y = 140
    draw.text((WIDTH//2, header_y), "LR ATLAS // DEMOGRAPHIC BATTLEGROUND", fill=(212, 175, 55, 255), font=font_hud_tag, anchor="mm")
    draw.text((WIDTH//2, header_y + 48), "MOST POPULOUS COUNTRIES", fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")
    
    # Year Pill
    pill_w = 440
    pill_h = 44
    px = WIDTH//2 - pill_w//2
    py = header_y + 86
    draw.rounded_rectangle([(px, py), (px + pill_w, py + pill_h)], radius=22, fill=(18, 28, 48, 230), outline=(56, 189, 248, 140), width=2)
    draw.text((WIDTH//2, py + pill_h//2), "YEAR: 2026 // WORLD: 8.15B", fill=(56, 189, 248, 255), font=font_hud_sub, anchor="mm")

    # Divider
    draw.line([(80, py + 75), (WIDTH - 80, py + 75)], fill=(30, 42, 65, 255), width=2)

    # 2. Bars Rendering
    start_y = 400
    gap_y = 135
    max_bar_w = 660
    min_bar_w = 340  # Minimum 340px ensures name always fits comfortably inside!

    max_val = 1.44
    min_val = 0.175

    for i, item in enumerate(POPULATION_DATA):
        cur_y = start_y + i * gap_y
        val_fraction = (item["val"] - min_val) / (max_val - min_val)
        bar_w = int(min_bar_w + val_fraction * (max_bar_w - min_bar_w))

        # Build Waving Glass Bar
        base_flag = prepped_flags[item["code"]]
        f_w = bar_w + pad * 2
        f_h = bar_h + pad * 2
        scaled_flag = base_flag.resize((f_w, f_h), Image.Resampling.LANCZOS)
        flag_np = np.array(scaled_flag)

        # Sine wave ripple
        h, w, c = flag_np.shape
        y_indices, x_indices = np.indices((h, w))
        wave_shift = (5.0 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t)).astype(np.float32)
        new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)
        waved_np = flag_np[new_y, x_indices]

        # Cloth fold shading
        shading = (0.86 + 0.18 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t + math.pi/4))[:, :, np.newaxis]
        waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)

        waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))

        # Mask for pill bar
        bar_mask = Image.new("L", (bar_w, bar_h), 0)
        ImageDraw.Draw(bar_mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

        bar_composite = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        bar_composite.paste(waved_img, (0, 0), bar_mask)

        # Gradient overlay for text contrast (dark fade towards right)
        grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(grad)
        for x in range(bar_w):
            alpha = int(50 + 130 * (x / bar_w))
            grad_draw.line([(x, 0), (x, bar_h)], fill=(10, 14, 24, alpha))
        bar_composite = Image.alpha_composite(bar_composite, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))

        # Top Specular Highlight (Apple Mirror Sheen)
        sheen = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        sheen_draw = ImageDraw.Draw(sheen)
        sheen_h = int(bar_h * 0.44)
        for y in range(sheen_h):
            alpha = int(170 * (1.0 - (y / sheen_h)**1.4))
            sheen_draw.line([(radius//2, y + 2), (bar_w - radius//2, y + 2)], fill=(255, 255, 255, alpha))
        bar_composite = Image.alpha_composite(bar_composite, Image.composite(sheen, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))

        # Titanium Glass Rim (Beveled Light)
        rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
        rim_draw = ImageDraw.Draw(rim)
        rim_col = (255, 215, 0) if i == 0 else (255, 255, 255)
        rim_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=rim_col + (60,), width=2)
        rim_draw.arc([(1, 1), (bar_w - 2, bar_h - 2)], start=180, end=360, fill=rim_col + (220,), width=2)
        rim_draw.arc([(1, 1), (bar_w - 2, bar_h - 2)], start=0, end=180, fill=(0, 0, 0, 140), width=2)
        bar_composite = Image.alpha_composite(bar_composite, rim)

        # Paste bar onto canvas
        bar_x = 75
        canvas.paste(bar_composite, (bar_x, cur_y), bar_composite)

        # Monogram Crest (Left)
        crest_size = 72
        cx = bar_x + 10
        cy = cur_y + (bar_h - crest_size)//2
        draw.ellipse([(cx, cy), (cx + crest_size, cy + crest_size)], fill=(12, 18, 30, 240), outline=rim_col + (140,), width=2)
        draw.arc([(cx, cy), (cx + crest_size, cy + crest_size)], start=180, end=360, fill=rim_col + (240,), width=2)
        draw.text((cx + crest_size//2, cy + crest_size//2), item["code"], fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

        # Country Name + Rank
        text_x = cx + crest_size + 16
        text_y = cur_y + bar_h // 2
        name_str = f"{item['name']} #{i+1}"
        # Shadow
        draw.text((text_x + 2, text_y + 2), name_str, fill=(0, 0, 0, 255), font=font_label, anchor="lm")
        draw.text((text_x, text_y), name_str, fill=(255, 255, 255, 255), font=font_label, anchor="lm")

        # Badge (if any)
        if item["badge"]:
            badge_w = 120
            badge_h = 24
            bx = text_x + int(draw.textlength(name_str, font=font_label)) + 14
            by = text_y - badge_h // 2
            bg_col = (212, 175, 55, 230) if "WORLD" in item["badge"] else (225, 29, 72, 220)
            draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=5, fill=bg_col)
            draw.text((bx + badge_w//2, by + badge_h//2), item["badge"], fill=(0, 0, 0, 255) if "WORLD" in item["badge"] else (255, 255, 255, 255), font=font_badge, anchor="mm")

        # Value on Right (Outside the bar with generous spacing)
        val_x = bar_x + bar_w + 22
        draw.text((val_x + 2, text_y + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((val_x, text_y), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    # 3. Floating Debate Pill (Bottom Outro Banner)
    bot_pill_w = 940
    bot_pill_h = 76
    bx = (WIDTH - bot_pill_w) // 2
    by = HEIGHT - 380
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=38, fill=(18, 26, 44, 240), outline=(212, 175, 55, 220), width=2)
    draw.text((WIDTH//2, by + bot_pill_h//2), "★ WILL ANY NATION OVERTAKE INDIA BY 2050? VOTE BELOW ★", fill=(255, 215, 0, 255), font=font_debate, anchor="mm")

    # Safe Zone Watermark
    draw.text((WIDTH//2, HEIGHT - 180), "LR ATLAS // GLOBAL DEMOGRAPHICS", fill=(100, 116, 139, 255), font=font_hud_tag, anchor="mm")

    return canvas

# Save single high-res preview frame
preview_frame = render_frame(phase_t=0.0)
preview_path = "output/population_preview_climax.png"
preview_frame.save(preview_path, "PNG")
print(f"Polished High-Res Preview saved to: {preview_path}")

# Generate 2-second animated video preview (60 frames at 30fps)
frames = []
total_frames = 60
print("Rendering 60 frames for animated video preview...")
for f in range(total_frames):
    t = f / total_frames * 2 * math.pi
    frm = render_frame(phase_t=t).convert("RGB")
    frames.append(frm)

import subprocess
ffmpeg_cmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", "output/population_preview_video.mp4"
]
p = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
for frm in frames:
    p.stdin.write(frm.tobytes())
p.stdin.close()
p.wait()
print("Polished Animated Video Preview saved to: output/population_preview_video.mp4")
