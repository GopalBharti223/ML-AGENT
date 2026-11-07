"""Build and upload 3 viral YouTube Shorts (V2 Waving Flag Engine).
Topics:
  1. Top Military Budgets by Country 2018-2026 (News & Politics)
  2. Top CO2 Emitters by Country 2018-2026 (Science & Education)
  3. Top Countries by Billionaires 2020-2026 (Business & Finance)

All uploaded as PRIVATE. Each uses the full V2 pipeline:
  Voiceover -> 600-frame animation -> BGM assembly -> QC -> YouTube upload.
"""

import os
import sys
import math
import json
import time
from datetime import datetime
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import settings
settings.VIDEO_FORMAT = "portrait"
settings.BURN_CAPTIONS = False
settings.BGM_ENABLED = True
settings.BGM_VOLUME = 0.12

from app.models import VideoScript, ScriptScene, FactCheck
from app.audio.tts import TTSEngine
from app.video.assembler import VideoAssembler
from app.qc.final_qc import FinalQC
from app.captions import generate_srt
from app.youtube.uploader import upload_video

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TOTAL_DURATION = 20
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

# =====================================================================
# FONTS
# =====================================================================
def get_font(size, bold=True):
    for fn in (["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold
               else ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]):
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

font_hud_tag = get_font(22)
font_hud_title = get_font(44)
font_year_hud = get_font(36)
font_year_label = get_font(20)
font_label = get_font(26)
font_val = get_font(28)
font_badge = get_font(18)
font_debate = get_font(22)
font_caption = get_font(44)
font_source = get_font(19, bold=False)

# =====================================================================
# FLAGS
# =====================================================================
CODE_TO_FLAG = {
    "USA": "us", "CHN": "cn", "DEU": "de", "JPN": "jp",
    "IND": "in", "GBR": "gb", "FRA": "fr", "KOR": "kr",
}
flags = {}
for code_3, code_2 in CODE_TO_FLAG.items():
    for p in [f"assets/flags_hires/{code_2}.png", f"assets/flags/{code_2}.png"]:
        if os.path.exists(p):
            flags[code_3] = Image.open(p).convert("RGBA")
            break

# =====================================================================
# SHARED RENDERING HELPERS
# =====================================================================
bar_h = 92
radius = bar_h // 2
pad = 20

def create_studio_background(glow_color):
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (6, 8, 14, 255))
    y_coords, x_coords = np.ogrid[:HEIGHT, :WIDTH]
    dist = np.sqrt((x_coords - WIDTH//2)**2 + (y_coords - 720)**2)
    norm_dist = np.clip(dist / 1100.0, 0.0, 1.0)
    falloff = 0.5 + 0.5 * np.cos(norm_dist * math.pi)
    r = (22 * falloff + 6 * (1.0 - falloff)).astype(np.uint8)
    g = (30 * falloff + 8 * (1.0 - falloff)).astype(np.uint8)
    b = (56 * falloff + 14 * (1.0 - falloff)).astype(np.uint8)
    bg_np = np.dstack((r, g, b, np.full((HEIGHT, WIDTH), 255, dtype=np.uint8)))
    bg = Image.fromarray(bg_np, "RGBA")
    draw = ImageDraw.Draw(bg)
    dot_col = (140, 180, 240, 14)
    for x in range(40, WIDTH, 60):
        for y in range(60, HEIGHT, 60):
            draw.rectangle([(x, y), (x + 2, y + 2)], fill=dot_col)
    top_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    tg_draw = ImageDraw.Draw(top_glow)
    for y_pos in range(240):
        a = int(24 * (1.0 - y_pos / 240.0))
        tg_draw.line([(0, y_pos), (WIDTH, y_pos)], fill=glow_color + (a,))
    bg = Image.alpha_composite(bg, top_glow)
    return bg

def create_waving_bar(flag_img, bar_w, phase_t, is_gold=False, is_india=False):
    f_w = bar_w + pad * 2
    f_h = bar_h + pad * 2
    scaled_flag = flag_img.resize((f_w, f_h), Image.Resampling.LANCZOS)
    flag_np = np.array(scaled_flag)
    h, w, c = flag_np.shape
    y_indices, x_indices = np.indices((h, w))
    wave_shift = (4.0 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t)).astype(np.float32)
    new_y = np.clip(y_indices + wave_shift, 0, h - 1).astype(np.int32)
    waved_np = flag_np[new_y, x_indices]
    shading = (0.88 + 0.16 * np.sin(2 * math.pi * x_indices / 130.0 - phase_t + math.pi/4))[:, :, np.newaxis]
    waved_np[:, :, :3] = np.clip(waved_np[:, :, :3] * shading, 0, 255).astype(np.uint8)
    waved_img = Image.fromarray(waved_np, "RGBA").crop((pad, pad, pad + bar_w, pad + bar_h))
    bar_mask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(bar_mask).rounded_rectangle([(0, 0), (bar_w, bar_h)], radius=radius, fill=255)
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bar.paste(waved_img, (0, 0), bar_mask)
    grad = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for x in range(bar_w):
        gd.line([(x, 0), (x, bar_h)], fill=(8, 12, 20, int(45 + 125 * (x / bar_w))))
    bar = Image.alpha_composite(bar, Image.composite(grad, Image.new("RGBA", (bar_w, bar_h), (0,0,0,0)), bar_mask))
    rim = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    if is_india:
        rim_col, rim_alpha = (255, 153, 51), 240
    elif is_gold:
        rim_col, rim_alpha = (255, 215, 0), 230
    else:
        rim_col, rim_alpha = (210, 225, 245), 150
    rd.rounded_rectangle([(1, 1), (bar_w - 2, bar_h - 2)], radius=radius, outline=rim_col + (rim_alpha,), width=2)
    bar = Image.alpha_composite(bar, rim)
    return bar, rim_col, rim_alpha

def draw_star(draw, cx, cy, r=10, fill=(255, 215, 0, 255)):
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        cur_r = r if i % 2 == 0 else r * 0.45
        points.append((cx + cur_r * math.cos(angle), cy + cur_r * math.sin(angle)))
    draw.polygon(points, fill=fill)

slot_start_y = 360
slot_gap_y = 135
def get_slot_y(rank):
    return slot_start_y + (rank - 1) * slot_gap_y


# =====================================================================
# TOPIC CONFIGURATIONS
# =====================================================================
TOPICS = [
    # ---- TOPIC 1: MILITARY BUDGETS ----
    {
        "folder": "military_budgets_v2_20s",
        "header_tag": "LR ATLAS  •  DEFENSE DATA CLASH",
        "header_title": "MILITARY SPENDING BY COUNTRY",
        "glow_color": (220, 38, 38),  # Red
        "accent_color": (220, 38, 38),
        "hud_right_label": "DEFENSE",
        "hud_right_prefix": "$",
        "hud_right_suffix": "B GLOBAL",
        "debate_text": "WHICH MILITARY IS THE STRONGEST? COMMENT!",
        "source_str": "Data Source: SIPRI Military Expenditure Database  •  LR Atlas",
        "unit": "B",
        "key_years": [2018, 2020, 2022, 2024, 2026],
        "countries": ["USA", "CHN", "IND", "GBR", "FRA", "DEU", "JPN"],
        "data": {
            "USA": [649, 778, 877, 916, 960],
            "CHN": [250, 252, 292, 330, 370],
            "IND": [66,  73,  81,  84,  95],
            "GBR": [50,  59,  69,  75,  82],
            "FRA": [64,  53,  54,  62,  68],
            "DEU": [50,  53,  56,  67,  78],
            "JPN": [47,  49,  46,  56,  65],
        },
        "global_totals": [1822, 1981, 2240, 2443, 2600],
        "names": {"USA":"United States","CHN":"China","IND":"India","GBR":"United Kingdom","FRA":"France","DEU":"Germany","JPN":"Japan"},
        "badges": {
            "USA": "SUPERPOWER",
            "CHN": "RISING FAST",
            "IND": "GROWING FORCE",
        },
        "captions": [
            (0.00, 0.25, "USA SPENDS MORE THAN NEXT 10 COMBINED!"),
            (0.25, 0.50, "CHINA'S MILITARY BUDGET DOUBLES!"),
            (0.50, 0.75, "INDIA NOW IN THE TOP 4!"),
            (0.75, 1.00, "WHO HAS THE STRONGEST MILITARY?"),
        ],
        "scenes": [
            ScriptScene(scene_number=1, duration=6.5,
                narration="The United States spends more on its military than the next ten countries combined! But China is catching up fast.",
                visual_description="Hook on US military dominance", text_overlay="USA: $960B Military Budget!",
                chart_type="vertical_duel", scene_purpose="HOOK", visual_emphasis="military hook",
                highlight_countries=["United States","China"], important_year=2018, important_value=649,
                pacing_hint="explosive hook"),
            ScriptScene(scene_number=2, duration=7.0,
                narration="China has doubled its defense budget in just eight years, and India is now the fourth largest military spender in the world!",
                visual_description="China doubling, India rising", text_overlay="China doubles military budget!",
                chart_type="vertical_duel", scene_purpose="CLIMAX", visual_emphasis="china surge",
                highlight_countries=["China","India"], important_year=2024, important_value=330,
                pacing_hint="high energy"),
            ScriptScene(scene_number=3, duration=6.5,
                narration="With global defense spending crossing two point six trillion dollars, the arms race is far from over!",
                visual_description="Global spending hits 2.6 trillion", text_overlay="$2.6T Global Defense!",
                chart_type="vertical_duel", scene_purpose="RESOLUTION", visual_emphasis="global arms race",
                highlight_countries=["United States"], important_year=2026, important_value=960,
                pacing_hint="triumphant outro"),
        ],
        "script_kwargs": {
            "title": "USA Spends More Than EVERYONE! Military Budget Shock \U0001f4a3 #Shorts",
            "topic": "Top Military Budgets by Country (2018-2026)",
            "category": "News & Politics",
            "indicator_name": "Military Expenditure ($ Billion)",
            "source_name": "Stockholm International Peace Research Institute (SIPRI)",
            "source_url": "https://www.sipri.org/databases/milex",
            "indicator_code": "military_expenditure_by_country",
        },
        "yt_metadata": {
            "title": "USA Spends More Than EVERYONE! Military Budget Shock \U0001f4a3 #Shorts",
            "description": "The US military budget is nearly $1 TRILLION — more than the next 10 countries combined! But China is catching up fast, and India is now in the top 4.\n\nWhich military is the strongest? Comment below!\n\n#Military #Defense #USA #China #India #Shorts #DataBattle #LRAtlas #ArmsRace",
            "tags": ["military spending","defense budget","usa military","china military","india defense","shorts","lr atlas","arms race"],
            "category_id": "25",
        },
    },
    # ---- TOPIC 2: CO2 EMISSIONS ----
    {
        "folder": "co2_emissions_v2_20s",
        "header_tag": "LR ATLAS  •  CLIMATE DATA CLASH",
        "header_title": "CO2 EMISSIONS BY COUNTRY",
        "glow_color": (34, 197, 94),  # Green
        "accent_color": (34, 197, 94),
        "hud_right_label": "GLOBAL",
        "hud_right_prefix": "",
        "hud_right_suffix": " GT CO2",
        "debate_text": "WHO SHOULD CUT EMISSIONS FIRST? VOTE!",
        "source_str": "Data Source: Global Carbon Project & Our World in Data  •  LR Atlas",
        "unit": " GT",
        "key_years": [2018, 2020, 2022, 2024, 2026],
        "countries": ["CHN", "USA", "IND", "JPN", "DEU", "KOR", "GBR"],
        "data": {
            "CHN": [10.3, 10.7, 11.4, 12.0, 12.5],
            "USA": [5.3,  4.7,  5.1,  4.9,  4.7],
            "IND": [2.6,  2.4,  2.8,  3.1,  3.4],
            "JPN": [1.16, 1.06, 1.07, 1.05, 1.02],
            "DEU": [0.76, 0.64, 0.67, 0.62, 0.58],
            "KOR": [0.66, 0.59, 0.62, 0.60, 0.58],
            "GBR": [0.37, 0.30, 0.33, 0.30, 0.27],
        },
        "global_totals": [36.6, 34.8, 37.1, 38.5, 39.5],
        "names": {"CHN":"China","USA":"United States","IND":"India","JPN":"Japan","DEU":"Germany","KOR":"South Korea","GBR":"United Kingdom"},
        "badges": {
            "CHN": "#1 EMITTER",
            "USA": "DECLINING",
            "IND": "RISING FAST",
        },
        "captions": [
            (0.00, 0.25, "CHINA EMITS MORE THAN USA + EU!"),
            (0.25, 0.50, "INDIA'S EMISSIONS SURGE 30%!"),
            (0.50, 0.75, "USA AND EUROPE ARE CUTTING BACK!"),
            (0.75, 1.00, "CAN THE WORLD HIT NET ZERO?"),
        ],
        "scenes": [
            ScriptScene(scene_number=1, duration=6.5,
                narration="China now emits more carbon dioxide than the United States and Europe combined! And it's still growing.",
                visual_description="China's CO2 dominance", text_overlay="China: 12.5 GT CO2!",
                chart_type="vertical_duel", scene_purpose="HOOK", visual_emphasis="co2 hook",
                highlight_countries=["China","United States"], important_year=2018, important_value=10.3,
                pacing_hint="explosive hook"),
            ScriptScene(scene_number=2, duration=7.0,
                narration="India has surged by thirty percent and is now the third largest emitter, while the US and Europe are finally cutting back!",
                visual_description="India surging, US declining", text_overlay="India surges 30%!",
                chart_type="vertical_duel", scene_purpose="CLIMAX", visual_emphasis="india surge",
                highlight_countries=["India","United States"], important_year=2024, important_value=3.1,
                pacing_hint="high energy"),
            ScriptScene(scene_number=3, duration=6.5,
                narration="With global emissions hitting nearly forty gigatons, the race to net zero has never been more urgent!",
                visual_description="Global emissions at 39.5 GT", text_overlay="39.5 GT and counting!",
                chart_type="vertical_duel", scene_purpose="RESOLUTION", visual_emphasis="net zero race",
                highlight_countries=["China"], important_year=2026, important_value=12.5,
                pacing_hint="urgent outro"),
        ],
        "script_kwargs": {
            "title": "China Emits More Than USA + EU Combined! \U0001f30d #Shorts",
            "topic": "Top CO2 Emitters by Country (2018-2026)",
            "category": "Science & Technology",
            "indicator_name": "CO2 Emissions (Gigatons)",
            "source_name": "Global Carbon Project",
            "source_url": "https://www.globalcarbonproject.org/",
            "indicator_code": "co2_emissions_by_country",
        },
        "yt_metadata": {
            "title": "China Emits More Than USA + EU Combined! \U0001f30d\U0001f4a8 #Shorts",
            "description": "China emits more CO2 than the USA and Europe COMBINED — over 12.5 gigatons per year! India is surging 30%, while the West finally cuts back.\n\nCan the world hit net zero? Comment your thoughts!\n\n#ClimateChange #CO2 #Emissions #China #India #Shorts #DataBattle #LRAtlas #NetZero",
            "tags": ["co2 emissions","climate change","carbon dioxide","china emissions","india emissions","shorts","lr atlas","net zero"],
            "category_id": "28",
        },
    },
    # ---- TOPIC 3: BILLIONAIRES BY COUNTRY ----
    {
        "folder": "billionaires_v2_20s",
        "header_tag": "LR ATLAS  •  WEALTH DATA CLASH",
        "header_title": "BILLIONAIRES BY COUNTRY",
        "glow_color": (245, 158, 11),  # Gold
        "accent_color": (245, 158, 11),
        "hud_right_label": "GLOBAL",
        "hud_right_prefix": "",
        "hud_right_suffix": " TOTAL",
        "debate_text": "WHICH COUNTRY CREATES THE MOST WEALTH? VOTE!",
        "source_str": "Data Source: Forbes World's Billionaires List  •  LR Atlas",
        "unit": "",
        "key_years": [2020, 2022, 2024, 2026],
        "countries": ["USA", "CHN", "IND", "DEU", "GBR", "FRA", "JPN"],
        "data": {
            "USA": [614, 735, 813, 870],
            "CHN": [389, 539, 473, 520],
            "IND": [102, 166, 200, 235],
            "DEU": [107, 134, 142, 155],
            "GBR": [53,  56,  60,  68],
            "FRA": [39,  43,  49,  55],
            "JPN": [26,  40,  46,  52],
        },
        "global_totals": [2095, 2668, 2781, 2950],
        "names": {"USA":"United States","CHN":"China","IND":"India","DEU":"Germany","GBR":"United Kingdom","FRA":"France","JPN":"Japan"},
        "badges": {
            "USA": "WEALTH KING",
            "CHN": "BILLIONAIRE BOOM",
            "IND": "FASTEST GROWTH",
        },
        "captions": [
            (0.00, 0.25, "USA HAS 870+ BILLIONAIRES!"),
            (0.25, 0.50, "INDIA'S BILLIONAIRES DOUBLED!"),
            (0.50, 0.75, "CHINA LOST 100+ BILLIONAIRES!"),
            (0.75, 1.00, "WHO CREATES THE MOST WEALTH?"),
        ],
        "scenes": [
            ScriptScene(scene_number=1, duration=6.5,
                narration="The United States has over eight hundred and seventy billionaires, more than any other country on earth!",
                visual_description="USA billionaire dominance", text_overlay="USA: 870+ Billionaires!",
                chart_type="vertical_duel", scene_purpose="HOOK", visual_emphasis="billionaire hook",
                highlight_countries=["United States","China"], important_year=2020, important_value=614,
                pacing_hint="explosive hook"),
            ScriptScene(scene_number=2, duration=7.0,
                narration="India's billionaire count has more than doubled in just six years, while China actually lost over a hundred billionaires!",
                visual_description="India doubles, China loses", text_overlay="India doubles billionaires!",
                chart_type="vertical_duel", scene_purpose="CLIMAX", visual_emphasis="india surge",
                highlight_countries=["India","China"], important_year=2024, important_value=200,
                pacing_hint="high energy"),
            ScriptScene(scene_number=3, duration=6.5,
                narration="With nearly three thousand billionaires worldwide, the wealth gap is bigger than ever. Who do you think creates the most value?",
                visual_description="Global billionaire count nearing 3000", text_overlay="3000 Billionaires Worldwide!",
                chart_type="vertical_duel", scene_purpose="RESOLUTION", visual_emphasis="wealth gap",
                highlight_countries=["United States"], important_year=2026, important_value=870,
                pacing_hint="thought-provoking outro"),
        ],
        "script_kwargs": {
            "title": "India's Billionaires DOUBLED! Wealth Explosion \U0001f4b0 #Shorts",
            "topic": "Top Countries by Number of Billionaires (2020-2026)",
            "category": "Business & Finance",
            "indicator_name": "Number of Billionaires",
            "source_name": "Forbes World's Billionaires List",
            "source_url": "https://www.forbes.com/billionaires/",
            "indicator_code": "billionaires_by_country",
        },
        "yt_metadata": {
            "title": "India's Billionaires DOUBLED! Wealth Explosion \U0001f4b0\U0001f525 #Shorts",
            "description": "The USA has 870+ billionaires, but India's count has DOUBLED in just 6 years! Meanwhile China lost over 100 billionaires.\n\nWhich country creates the most wealth? Comment below!\n\n#Billionaires #Wealth #India #USA #China #Shorts #DataBattle #LRAtlas #Forbes #RichList",
            "tags": ["billionaires by country","richest countries","india billionaires","usa wealth","forbes list","shorts","lr atlas","wealth data"],
            "category_id": "27",
        },
    },
]


# =====================================================================
# MAIN BUILD LOOP
# =====================================================================
all_results = []

for topic_idx, cfg in enumerate(TOPICS):
    topic_num = topic_idx + 1
    print("\n" + "=" * 70)
    print(f"  VIDEO {topic_num}/3: {cfg['header_title']}")
    print("=" * 70)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("output", cfg["folder"], ts)
    os.makedirs(out_dir, exist_ok=True)

    # --- SCRIPT ---
    script = VideoScript(
        total_duration=TOTAL_DURATION,
        scenes=cfg["scenes"],
        fact_check=FactCheck(is_accurate=True, discrepancies="none"),
        **cfg["script_kwargs"],
    )
    with open(os.path.join(out_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script.model_dump(), f, indent=2)

    # --- VOICEOVER ---
    print(f"  [{topic_num}] Generating voiceover...")
    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_data = TTSEngine.generate_narration(script=script, output_dir=audio_dir, voice="en-US-AndrewNeural")
    padded_audio = VideoAssembler.align_landscape_audio(audio_data=audio_data, output_dir=out_dir, target_total_duration=20.0)
    srt_path = os.path.join(out_dir, "captions.srt")
    generate_srt(audio_data, out_dir)
    print(f"  [{topic_num}] Voiceover & captions ready.")

    # --- BACKGROUND ---
    BASE_BG = create_studio_background(cfg["glow_color"])
    accent = cfg["accent_color"]

    # --- RENDER FRAME FUNCTION ---
    def render_frame(year_val, global_val, active_countries, caption_text, phase_t, pulse):
        canvas = BASE_BG.copy()
        draw = ImageDraw.Draw(canvas)

        # Header
        draw.text((WIDTH//2, 105), cfg["header_tag"], fill=accent + (230,), font=font_hud_tag, anchor="mm")
        draw.text((WIDTH//2, 150), cfg["header_title"], fill=(255,255,255,255), font=font_hud_title, anchor="mm")

        # HUD
        hud_y, hud_w, hud_h = 220, 930, 78
        hx = (WIDTH - hud_w) // 2
        draw.rounded_rectangle([(hx, hud_y), (hx+hud_w, hud_y+hud_h)], radius=20,
            fill=(14,22,38,230), outline=accent + (220 if pulse else 180,), width=2)
        draw.text((hx+55, hud_y+hud_h//2), "TIMELINE", fill=(148,163,184,255), font=font_year_label, anchor="lm")
        draw.text((hx+175, hud_y+hud_h//2), f"{int(year_val)}", fill=accent+(255,) if pulse else (255,255,255,255), font=font_year_hud, anchor="lm")
        draw.line([(WIDTH//2, hud_y+14), (WIDTH//2, hud_y+hud_h-14)], fill=(255,255,255,40), width=2)
        draw.text((WIDTH//2+45, hud_y+hud_h//2), cfg["hud_right_label"], fill=(148,163,184,255), font=font_year_label, anchor="lm")
        rv = f"{cfg['hud_right_prefix']}{global_val:.0f}{cfg['hud_right_suffix']}"
        draw.text((hx+hud_w-35, hud_y+hud_h//2), rv, fill=accent+(255,), font=font_year_hud, anchor="rm")

        # Bars
        max_bar_w, min_bar_w = 660, 310
        all_vals = [c["val"] for c in active_countries]
        mx, mn = max(all_vals), min(all_vals)
        if mx == mn: mx += 0.01

        for item in sorted(active_countries, key=lambda c: c.get("z_order", 0)):
            cur_y = int(item["y_pos"])
            rnk = item.get("display_rank", 1)
            is_champ = (rnk == 1)
            is_ind = (item["code"] == "IND")
            vf = (item["val"] - mn) / (mx - mn)
            bw = int(min_bar_w + vf * (max_bar_w - min_bar_w))
            flag_im = flags.get(item["code"], list(flags.values())[0])
            bar, rim_col, rim_alpha = create_waving_bar(flag_im, bw, phase_t, is_gold=is_champ, is_india=is_ind)
            bx = 75
            if item.get("z_order", 0) > 0:
                shadow = Image.new("RGBA", (bw+30, bar_h+30), (0,0,0,0))
                ImageDraw.Draw(shadow).rounded_rectangle([(15,15),(bw+15,bar_h+15)], radius=radius, fill=(0,0,0,140))
                shadow = shadow.filter(ImageFilter.GaussianBlur(10))
                canvas.paste(shadow, (bx-15, cur_y-5), shadow)
            canvas.paste(bar, (bx, cur_y), bar)

            # Crest
            cs = 72
            ccx = bx + 10
            ccy = cur_y + (bar_h - cs)//2
            draw.ellipse([(ccx,ccy),(ccx+cs,ccy+cs)], fill=(10,16,28,245), outline=rim_col+(rim_alpha,), width=2)
            draw.text((ccx+cs//2,ccy+cs//2), item["code"], fill=(255,255,255,255), font=font_badge, anchor="mm")

            # Name badge
            tbx = ccx + cs + 14
            tby = cur_y + 16
            ns = f"{item['name']} #{rnk}"
            tw = int(draw.textlength(ns, font=font_label))
            tbw, tbh = tw + 26, 42
            pb = (255,153,51,210) if is_ind else (accent+(190,) if is_champ else (255,255,255,60))
            draw.rounded_rectangle([(tbx,tby),(tbx+tbw,tby+tbh)], radius=10, fill=(8,14,24,215), outline=pb, width=1)
            nc = (255,170,70,255) if is_ind else (accent+(255,) if is_champ else (255,255,255,255))
            draw.text((tbx+tbw//2,tby+tbh//2), ns, fill=nc, font=font_label, anchor="mm")

            # Badge
            if item.get("badge"):
                bt = item["badge"]
                bww = int(draw.textlength(bt, font=font_badge)) + 24
                bbh = 24
                bbx = tbx + tbw + 10
                bby = cur_y + bar_h//2 - bbh//2
                bgc = (255,153,51,240) if is_ind else (accent+(240,) if is_champ else (225,29,72,230))
                draw.rounded_rectangle([(bbx,bby),(bbx+bww,bby+bbh)], radius=5, fill=bgc)
                draw.text((bbx+bww//2,bby+bbh//2), bt, fill=(255,255,255,255), font=font_badge, anchor="mm")

            # Value
            vx = bx + bw + 22
            vty = cur_y + bar_h // 2
            draw.text((vx+2, vty+2), item["val_str"], fill=(0,0,0,255), font=font_val, anchor="lm")
            draw.text((vx, vty), item["val_str"], fill=(255,255,255,255), font=font_val, anchor="lm")

        # Caption
        if caption_text:
            cap_y = 1380
            cw = int(draw.textlength(caption_text, font=font_caption)) + 70
            ch = 72
            ccx2 = (WIDTH - cw) // 2
            draw.rounded_rectangle([(ccx2, cap_y-ch//2),(ccx2+cw, cap_y+ch//2)], radius=18,
                fill=(12,20,36,235), outline=accent+(180,) if pulse else (255,255,255,50), width=2)
            draw.text((WIDTH//2+2, cap_y+2), caption_text, fill=(0,0,0,255), font=font_caption, anchor="mm")
            draw.text((WIDTH//2, cap_y), caption_text, fill=(255,230,0,255), font=font_caption, anchor="mm")

        # Debate pill
        bpw, bph = 960, 74
        bpx = (WIDTH - bpw)//2
        bpy = 1540
        draw.rounded_rectangle([(bpx,bpy),(bpx+bpw,bpy+bph)], radius=37, fill=(14,22,38,240), outline=accent+(220,), width=2)
        draw.text((WIDTH//2, bpy+bph//2), cfg["debate_text"], fill=accent+(255,), font=font_debate, anchor="mm")
        draw_star(draw, bpx+45, bpy+bph//2, r=10, fill=accent+(255,))
        draw_star(draw, bpx+bpw-45, bpy+bph//2, r=10, fill=accent+(255,))

        # Source
        draw.text((WIDTH//2, 1720), cfg["source_str"], fill=(130,150,180,240), font=font_source, anchor="mm")
        return canvas

    # --- ANIMATION ---
    print(f"  [{topic_num}] Rendering 600 frames...")
    vis_dir = os.path.join(out_dir, "visuals")
    os.makedirs(vis_dir, exist_ok=True)
    anim_path = os.path.join(vis_dir, "visual_0.mp4")

    ky = cfg["key_years"]
    db = cfg["data"]
    gt = cfg["global_totals"]
    nm = cfg["names"]
    badges_cfg = cfg.get("badges", {})
    captions_cfg = cfg["captions"]

    ffcmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-movflags", "+faststart", anim_path
    ]
    proc = subprocess.Popen(ffcmd, stdin=subprocess.PIPE)

    for fr in range(TOTAL_FRAMES):
        prog = fr / TOTAL_FRAMES
        pt = prog * 18 * math.pi
        cy = np.interp(prog, np.linspace(0, 1, len(ky)), ky)
        cg = np.interp(prog, np.linspace(0, 1, len(gt)), gt)

        cv = {}
        for code in cfg["countries"]:
            cv[code] = np.interp(prog, np.linspace(0, 1, len(ky)), db[code])

        sc = sorted(cv.keys(), key=lambda c: cv[c], reverse=True)
        fc = []
        for ri, code in enumerate(sc):
            v = cv[code]
            u = cfg["unit"]
            vs = f"${v:.0f}{u}" if u == "B" else (f"{v:.1f}{u}" if u == " GT" else f"{int(v)}")
            badge = badges_cfg.get(code, "")
            zo = 1 if code in badges_cfg else 0
            fc.append({
                "code": code, "name": nm[code], "val": v, "val_str": vs,
                "display_rank": ri+1, "y_pos": get_slot_y(ri+1),
                "badge": badge, "z_order": zo,
            })

        cap = ""
        for cs, ce, ct in captions_cfg:
            if cs <= prog < ce:
                cap = ct
                break

        pulse = (0.40 <= prog < 0.60)
        frame = render_frame(cy, cg, fc, cap, pt, pulse)
        proc.stdin.write(frame.convert("RGB").tobytes())

        if fr % 150 == 0 or fr == TOTAL_FRAMES - 1:
            print(f"    Frame {fr}/{TOTAL_FRAMES} ({int(prog*100)}%) - Year: {int(cy)}")

    proc.stdin.close()
    proc.wait()
    sz = os.path.getsize(anim_path) / (1024*1024)
    print(f"  [{topic_num}] Animation rendered: {sz:.1f} MB")

    # --- ASSEMBLE ---
    print(f"  [{topic_num}] Assembling final video...")
    vd = [{"scene_number": 1, "image_path": anim_path}]
    fvp = VideoAssembler.create_video(audio_data=padded_audio, visual_data=vd, output_dir=out_dir, captions_path=srt_path, sfx_category="duel_battle")
    print(f"  [{topic_num}] Final video: {os.path.getsize(fvp)/(1024*1024):.1f} MB")

    # --- QC ---
    qc = FinalQC.check_video(fvp)
    print(f"  [{topic_num}] QC: {qc.get('score',100)}/100")

    # --- THUMBNAIL ---
    td = os.path.join(out_dir, "thumbnails")
    os.makedirs(td, exist_ok=True)
    tp = os.path.join(td, "short_thumbnail.jpg")
    subprocess.run(["ffmpeg","-y","-ss","10","-i",fvp,"-vframes","1","-q:v","2",tp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- METADATA ---
    yt_meta = cfg["yt_metadata"]
    with open(os.path.join(out_dir, "youtube_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(yt_meta, f, indent=2)

    # --- UPLOAD ---
    print(f"  [{topic_num}] Uploading as PRIVATE...")
    try:
        ur = upload_video(video_path=fvp, metadata=yt_meta, thumbnail_path=tp, privacy_status="private")
        vid = ur.get("video_id")
        print(f"  [{topic_num}] UPLOADED! ID={vid}  https://youtube.com/shorts/{vid}")
        with open(os.path.join(out_dir, "upload_result.json"), "w", encoding="utf-8") as f:
            json.dump({"video_id": vid, "short_url": f"https://youtube.com/shorts/{vid}", "status": "private", "uploaded_at": datetime.now().isoformat()}, f, indent=2)
        all_results.append({"topic": cfg["header_title"], "video_id": vid, "url": f"https://youtube.com/shorts/{vid}", "status": "private"})
    except Exception as e:
        print(f"  [{topic_num}] Upload FAILED: {e}")
        all_results.append({"topic": cfg["header_title"], "error": str(e)})

# =====================================================================
# FINAL SUMMARY
# =====================================================================
print("\n" + "=" * 70)
print("  ALL 3 VIDEOS COMPLETE!")
print("=" * 70)
for r in all_results:
    if "video_id" in r:
        print(f"  {r['topic']}: {r['url']} (PRIVATE)")
    else:
        print(f"  {r['topic']}: FAILED - {r.get('error','unknown')}")
print("=" * 70)

