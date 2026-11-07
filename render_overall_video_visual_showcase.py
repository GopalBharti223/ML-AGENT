"""Generate an Overall Video Visual Showcase (Fixed Flags & Clean Studio Backdrop):
1. 4-Stage Storyboard (1970 Hook -> 2023 Overtake)
2. A 5-Second Real Live Animated Demo MP4 showing subtitles, live year counter, and overtake!
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

WIDTH = 1080
HEIGHT = 1920

os.makedirs("output", exist_ok=True)

# Helper for robust fonts
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
font_caption = get_font(44, bold=True)

# Country code to 2-letter flag file map
CODE_TO_FLAG = {
    "IND": "in",
    "CHN": "cn",
    "USA": "us",
    "IDN": "id",
    "PAK": "pk",
    "NGA": "ng",
    "BGD": "bd",
}

flags = {}
for code_3, code_2 in CODE_TO_FLAG.items():
    p = f"assets/flags_hires/{code_2}.png"
    if os.path.exists(p):
        flags[code_3] = Image.open(p).convert("RGBA")

bar_h = 92
radius = bar_h // 2
pad = 20

def create_waving_bar(flag_img, bar_w, phase_t, is_gold=False):
    f_w = bar_w + pad * 2
    f_h = bar_h + pad * 2
    scaled_flag = flag_img.resize((f_w, f_h), Image.Resampling.LANCZOS)
    flag_np = np.array(scaled_flag)

    # Wave ripple
    h, w, c = flag_np.shape
    y_indices, x_indices = np.indices((h, w))
    wave_shift = (5.0 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t)).astype(np.float32)
    new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)
    waved_np = flag_np[new_y, x_indices]

    # Cloth shading (peaks bright, troughs slightly darker)
    shading = (0.88 + 0.16 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t + math.pi/4))[:, :, np.newaxis]
    waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)

    waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))

    # Mask
    bar_mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(bar_mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)

    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_img, (0, 0), bar_mask)

    # Dark gradient for text readability
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(grad)
    for x in range(bar_w):
        alpha = int(40 + 120 * (x / bar_w))
        grad_draw.line([(x, 0), (x, bar_h)], fill=(10, 14, 24, alpha))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))

    # Clean Titanium / Gold Rim (No inside lines)
    rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_col = (255, 215, 0) if is_gold else (220, 230, 245)
    rim_alpha = 200 if is_gold else 120
    rim_draw.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=rim_col + (rim_alpha,), width=2)
    bar = Image.alpha_composite(bar, rim)

    return bar, rim_col, rim_alpha

def render_complete_frame(year_str, world_pop_str, countries_data, caption_text, phase_t=0.0, overtake_gold_pulse=False):
    # Pure Clean Studio Background (NO white alpha circles!)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (11, 15, 25, 255))
    draw = ImageDraw.Draw(canvas)

    # 1. TOP HUD (Header)
    header_y = 120
    draw.text((WIDTH//2, header_y), "LR ATLAS // DEMOGRAPHIC BATTLEGROUND", fill=(212, 175, 55, 255), font=font_hud_tag, anchor="mm")
    draw.text((WIDTH//2, header_y + 44), "WORLD POPULATION RACE", fill=(255, 255, 255, 255), font=font_hud_title, anchor="mm")
    
    # Live Year & World Population Pill
    pill_w = 460
    pill_h = 44
    px = WIDTH//2 - pill_w//2
    py = header_y + 80
    pill_border_col = (255, 215, 0, 180) if overtake_gold_pulse else (56, 189, 248, 140)
    draw.rounded_rectangle([(px, py), (px + pill_w, py + pill_h)], radius=22, fill=(18, 28, 48, 230), outline=pill_border_col, width=2)
    draw.text((WIDTH//2, py + pill_h//2), f"YEAR: {year_str} // WORLD: {world_pop_str}", fill=(255, 215, 0, 255) if overtake_gold_pulse else (56, 189, 248, 255), font=font_hud_sub, anchor="mm")

    # 2. Dynamic Viral Karaoke Subtitle Banner (Upper center, eye level)
    if caption_text:
        cap_y = py + 85
        cap_w = int(draw.textlength(caption_text, font=font_caption)) + 60
        cap_h = 68
        cx = (WIDTH - cap_w) // 2
        draw.rounded_rectangle([(cx, cap_y - cap_h//2), (cx + cap_w, cap_y + cap_h//2)], radius=16, fill=(18, 26, 44, 230), outline=(255, 215, 0, 160) if overtake_gold_pulse else (255, 255, 255, 40), width=2)
        # Drop shadow on subtitle
        draw.text((WIDTH//2 + 2, cap_y + 2), caption_text, fill=(0, 0, 0, 255), font=font_caption, anchor="mm")
        # Bold Yellow Pop
        draw.text((WIDTH//2, cap_y), caption_text, fill=(255, 230, 0, 255), font=font_caption, anchor="mm")

    # 3. Bars Rendering
    start_y = 440
    gap_y = 125
    max_bar_w = 660
    min_bar_w = 340

    max_v = max(c["val"] for c in countries_data)
    min_v = min(c["val"] for c in countries_data)
    if max_v == min_v: max_v += 0.01

    for i, item in enumerate(countries_data):
        cur_y = start_y + i * gap_y
        val_fraction = (item["val"] - min_v) / (max_v - min_v)
        bar_w = int(min_bar_w + val_fraction * (max_bar_w - min_bar_w))

        is_champion = (i == 0)
        c_code = item["code"]
        flag_im = flags.get(c_code, flags["IND"])

        bar, rim_col, rim_alpha = create_waving_bar(flag_im, bar_w, phase_t, is_gold=is_champion)

        # Bar x
        bar_x = 75
        canvas.paste(bar, (bar_x, cur_y), bar)

        # Monogram Crest
        crest_size = 72
        cx = bar_x + 10
        cy = cur_y + (bar_h - crest_size)//2
        draw.ellipse([(cx, cy), (cx + crest_size, cy + crest_size)], fill=(12, 18, 30, 245), outline=rim_col + (rim_alpha,), width=2)
        draw.text((cx + crest_size//2, cy + crest_size//2), item["code"], fill=(255, 255, 255, 255), font=font_badge, anchor="mm")

        # Country Name + Rank
        text_x = cx + crest_size + 16
        text_y = cur_y + bar_h // 2
        name_str = f"{item['name']} #{i+1}"
        draw.text((text_x + 2, text_y + 2), name_str, fill=(0, 0, 0, 255), font=font_label, anchor="lm")
        draw.text((text_x, text_y), name_str, fill=(255, 255, 255, 255), font=font_label, anchor="lm")

        # Badge
        if item.get("badge"):
            badge_w = 120
            badge_h = 24
            bx = text_x + int(draw.textlength(name_str, font=font_label)) + 14
            by = text_y - badge_h // 2
            bg_col = (212, 175, 55, 240) if "1" in item["badge"] else (225, 29, 72, 230)
            draw.rounded_rectangle([(bx, by), (bx + badge_w, by + badge_h)], radius=5, fill=bg_col)
            draw.text((bx + badge_w//2, by + badge_h//2), item["badge"], fill=(0, 0, 0, 255) if "1" in item["badge"] else (255, 255, 255, 255), font=font_badge, anchor="mm")

        # Value on Right
        val_x = bar_x + bar_w + 22
        draw.text((val_x + 2, text_y + 2), item["val_str"], fill=(0, 0, 0, 255), font=font_val, anchor="lm")
        draw.text((val_x, text_y), item["val_str"], fill=(255, 255, 255, 255), font=font_val, anchor="lm")

    # 4. Bottom Floating Debate Pill (Viral Comment Trigger)
    bot_pill_w = 940
    bot_pill_h = 76
    bx = (WIDTH - bot_pill_w) // 2
    by = HEIGHT - 380
    draw.rounded_rectangle([(bx, by), (bx + bot_pill_w, by + bot_pill_h)], radius=38, fill=(18, 26, 44, 240), outline=(212, 175, 55, 200), width=2)
    draw.text((WIDTH//2, by + bot_pill_h//2), "★ WILL ANY NATION OVERTAKE INDIA BY 2050? VOTE BELOW ★", fill=(255, 215, 0, 255), font=font_debate, anchor="mm")

    # Safe Zone Watermark
    draw.text((WIDTH//2, HEIGHT - 180), "LR ATLAS // GLOBAL DEMOGRAPHICS", fill=(100, 116, 139, 255), font=font_hud_tag, anchor="mm")

    return canvas


# -------------------------------------------------------------
# 1. RENDER 4-STAGE STORYBOARD IMAGE
# -------------------------------------------------------------
print("Rendering Storyboard...")

# Scene A: 1970 Hook (China #1, India #2)
data_1970 = [
    {"name": "China", "code": "CHN", "val_str": "820 M", "val": 0.82, "badge": "#1 LEADER"},
    {"name": "India", "code": "IND", "val_str": "550 M", "val": 0.55, "badge": ""},
    {"name": "United States", "code": "USA", "val_str": "205 M", "val": 0.205, "badge": ""},
    {"name": "Indonesia", "code": "IDN", "val_str": "115 M", "val": 0.115, "badge": ""},
    {"name": "Pakistan", "code": "PAK", "val_str": "58 M", "val": 0.058, "badge": ""},
    {"name": "Bangladesh", "code": "BGD", "val_str": "65 M", "val": 0.065, "badge": ""},
    {"name": "Nigeria", "code": "NGA", "val_str": "56 M", "val": 0.056, "badge": ""},
]
frame_hook = render_complete_frame("1970", "3.70B", data_1970, "DID YOU KNOW THIS?", phase_t=0.5)

# Scene B: 2023 Historic Overtake (India takes #1)
data_2023 = [
    {"name": "India", "code": "IND", "val_str": "1.428 B", "val": 1.428, "badge": "★ NEW #1!"},
    {"name": "China", "code": "CHN", "val_str": "1.425 B", "val": 1.425, "badge": "OVERTAKEN"},
    {"name": "United States", "code": "USA", "val_str": "339 M", "val": 0.339, "badge": ""},
    {"name": "Indonesia", "code": "IDN", "val_str": "277 M", "val": 0.277, "badge": ""},
    {"name": "Pakistan", "code": "PAK", "val_str": "240 M", "val": 0.240, "badge": ""},
    {"name": "Nigeria", "code": "NGA", "val_str": "224 M", "val": 0.224, "badge": ""},
    {"name": "Bangladesh", "code": "BGD", "val_str": "172 M", "val": 0.172, "badge": ""},
]
frame_overtake = render_complete_frame("2023", "8.05B", data_2023, "★ INDIA TOOK THE CROWN!", phase_t=1.8, overtake_gold_pulse=True)

# Combine both into side-by-side storyboard
storyboard = Image.new("RGBA", (WIDTH * 2 + 60, HEIGHT), (8, 12, 20, 255))
storyboard.paste(frame_hook, (20, 0))
storyboard.paste(frame_overtake, (WIDTH + 40, 0))
storyboard.save("output/overall_video_storyboard.png", "PNG")
print("Saved storyboard to: output/overall_video_storyboard.png")


# -------------------------------------------------------------
# 2. RENDER 5-SECOND REAL ANIMATED VIDEO DEMO (150 frames @ 30fps)
# -------------------------------------------------------------
print("Rendering 5-Second Real Video Demo...")
video_frames = []
total_frames = 150

for f in range(total_frames):
    progress = f / total_frames
    phase_t = progress * 10 * math.pi

    cur_year = int(2018 + progress * 8)
    cur_world_pop = f"{7.6 + progress * 0.55:.2f}B"
    is_overtaken = (progress >= 0.55)

    if not is_overtaken:
        c_val = 1.41 + progress * 0.02
        i_val = 1.35 + progress * 0.10
        cap = "WATCH THE EPIC RACE..." if progress < 0.3 else "INDIA IS CLOSING IN!"
        d = [
            {"name": "China", "code": "CHN", "val_str": f"{c_val:.2f} B", "val": c_val, "badge": "#1 LEADER"},
            {"name": "India", "code": "IND", "val_str": f"{i_val:.2f} B", "val": i_val, "badge": "CLOSING IN"},
            {"name": "United States", "code": "USA", "val_str": "335 M", "val": 0.335, "badge": ""},
            {"name": "Indonesia", "code": "IDN", "val_str": "272 M", "val": 0.272, "badge": ""},
            {"name": "Pakistan", "code": "PAK", "val_str": "230 M", "val": 0.230, "badge": ""},
            {"name": "Nigeria", "code": "NGA", "val_str": "215 M", "val": 0.215, "badge": ""},
            {"name": "Bangladesh", "code": "BGD", "val_str": "168 M", "val": 0.168, "badge": ""},
        ]
        frm = render_complete_frame(str(cur_year), cur_world_pop, d, cap, phase_t=phase_t, overtake_gold_pulse=False)
    else:
        c_val = 1.415
        i_val = 1.43 + (progress - 0.55) * 0.04
        cap = "★ 2023: INDIA TAKES #1!" if progress < 0.8 else "CAN ANYONE OVERTAKE BY 2050?"
        d = [
            {"name": "India", "code": "IND", "val_str": f"{i_val:.2f} B", "val": i_val, "badge": "★ #1 WORLD"},
            {"name": "China", "code": "CHN", "val_str": f"{c_val:.2f} B", "val": c_val, "badge": "HISTORIC #1"},
            {"name": "United States", "code": "USA", "val_str": "342 M", "val": 0.342, "badge": ""},
            {"name": "Indonesia", "code": "IDN", "val_str": "280 M", "val": 0.280, "badge": ""},
            {"name": "Pakistan", "code": "PAK", "val_str": "245 M", "val": 0.245, "badge": ""},
            {"name": "Nigeria", "code": "NGA", "val_str": "228 M", "val": 0.228, "badge": ""},
            {"name": "Bangladesh", "code": "BGD", "val_str": "175 M", "val": 0.175, "badge": ""},
        ]
        frm = render_complete_frame(str(cur_year), cur_world_pop, d, cap, phase_t=phase_t, overtake_gold_pulse=(progress < 0.75))

    video_frames.append(frm.convert("RGB"))

import subprocess
ffmpeg_cmd = [
    "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
    "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
    "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
    "-movflags", "+faststart", "output/overall_video_live_demo.mp4"
]
p = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
for frm in video_frames:
    p.stdin.write(frm.tobytes())
p.stdin.close()
p.wait()
print("Saved live video demo to: output/overall_video_live_demo.mp4")
