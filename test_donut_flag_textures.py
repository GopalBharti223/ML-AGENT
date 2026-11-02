"""Test script for embedding country flags inside the donut ring slices and center hub.
"""
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920

from render_chart_types_v2_showcase import (
    BASE_BACKGROUND, render_common_header, render_common_footer,
    get_circular_flag, draw_star, font_hud_kpi_lbl, font_hud_kpi_num,
    font_badge, font_label, font_donut_slice_pct, font_donut_slice_lbl,
    font_caption, FLAG_PATHS, loaded_flags
)

def render_flag_embedded_donut():
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

    # Dedicated layer for flag-textured slices
    ring_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

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

        # Slice Mask
        slice_mask = Image.new("L", (WIDTH, HEIGHT), 0)
        s_draw = ImageDraw.Draw(slice_mask)
        s_draw.polygon(poly_pts, fill=255)

        # Slice Base Texture
        code = seg["code"]
        flag_im = loaded_flags.get(code)

        slice_tex = Image.new("RGBA", (WIDTH, HEIGHT), seg["color"] + (255,))
        if flag_im:
            # Calculate slice center
            mid_rad = math.radians(mid_deg)
            mid_dist = (inner_r + outer_r) / 2.0
            scx = cx + mid_dist * math.cos(mid_rad)
            scy = cy + mid_dist * math.sin(mid_rad)

            # Fit flag over slice
            fw, fh = 260, 160
            f_resized = flag_im.resize((fw, fh), Image.Resampling.LANCZOS)
            
            # Subtle rotation to match slice angle
            f_rot = f_resized.rotate(-mid_deg + 90, expand=True, resample=Image.Resampling.BICUBIC)
            rw, rh = f_rot.size
            slice_tex.paste(f_rot, (int(scx - rw//2), int(scy - rh//2)), f_rot)

            # Dark translucent tint over flag so slice borders and text pop
            tint = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 45))
            slice_tex = Image.alpha_composite(slice_tex, tint)

        # Composite slice into ring layer using slice_mask
        ring_layer.paste(slice_tex, (0, 0), slice_mask)

        # Slice Border separator (Crisp dark slit + neon highlight)
        for a in [start_deg, end_deg]:
            rad = math.radians(a)
            p_in = (cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad))
            p_out = (cx + outer_r * math.cos(rad), cy + outer_r * math.sin(rad))
            s_draw_ring = ImageDraw.Draw(ring_layer)
            s_draw_ring.line([p_in, p_out], fill=(10, 15, 25, 255), width=4)
            s_draw_ring.line([p_in, p_out], fill=(255, 255, 255, 120), width=1)

        slice_centers.append((seg, mid_deg))
        start_deg = end_deg

    # Outer & Inner glowing ring rims
    r_draw = ImageDraw.Draw(ring_layer)
    r_draw.ellipse([(cx - outer_r, cy - outer_r), (cx + outer_r, cy + outer_r)], outline=(212, 175, 55, 200), width=3)
    r_draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], outline=(212, 175, 55, 200), width=3)

    canvas = Image.alpha_composite(canvas, ring_layer)
    draw = ImageDraw.Draw(canvas)

    # 3. Direct Badges on/beside slices WITH CIRCULAR FLAGS & PERCENTAGES
    for seg, mid_deg in slice_centers:
        rad = math.radians(mid_deg)
        if seg["share"] >= 10.0:
            # Inside the ring band
            tr = (inner_r + outer_r) / 2.0
            tx = cx + tr * math.cos(rad)
            ty = cy + tr * math.sin(rad)
            
            # Frosted pill with Circular Flag + Percentage!
            pw, ph = 118, 44
            draw.rounded_rectangle([(tx - pw//2, ty - ph//2), (tx + pw//2, ty + ph//2)], radius=12, fill=(10, 16, 26, 240), outline=(255, 215, 0, 220), width=2)
            
            # Mini Flag
            flag_mini = get_circular_flag(seg["code"], size=30)
            canvas.paste(flag_mini, (int(tx - pw//2 + 8), int(ty - 15)), flag_mini)
            
            # Percent Number
            draw.text((tx + 14, ty), f"{seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_slice_pct, anchor="mm")
        elif seg["share"] >= 6.0:
            # Callout outside the slice
            tr_in = outer_r - 8
            tr_out = outer_r + 42
            p_in = (cx + tr_in * math.cos(rad), cy + tr_in * math.sin(rad))
            p_out = (cx + tr_out * math.cos(rad), cy + tr_out * math.sin(rad))
            draw.line([p_in, p_out], fill=(255, 255, 255, 220), width=2)
            
            pw, ph = 108, 38
            draw.rounded_rectangle([(p_out[0] - pw//2, p_out[1] - ph//2), (p_out[0] + pw//2, p_out[1] + ph//2)], radius=10, fill=(10, 16, 26, 240), outline=seg["color"] + (240,), width=2)
            flag_mini = get_circular_flag(seg["code"], size=26)
            canvas.paste(flag_mini, (int(p_out[0] - pw//2 + 7), int(p_out[1] - 13)), flag_mini)
            draw.text((p_out[0] + 14, p_out[1]), f"{seg['share']}%", fill=(255, 255, 255, 255), font=font_donut_slice_pct, anchor="mm")

    # 4. Center Frosted Core (The Hub) with Embedded Leader Flag!
    draw.ellipse([(cx - inner_r + 6, cy - inner_r + 6), (cx + inner_r - 6, cy + inner_r - 6)], fill=(12, 18, 30, 250), outline=(212, 175, 55, 240), width=3)
    
    # Embedded circular flag for Venezuela in the center
    ven_flag_center = get_circular_flag("VEN", size=54)
    canvas.paste(ven_flag_center, (cx - 27, cy - 65), ven_flag_center)

    draw.text((cx, cy - 3), "VENEZUELA", fill=(255, 255, 255, 255), font=font_label, anchor="mm")
    draw.text((cx, cy + 28), "★ #1 WORLD LEADER ★", fill=(212, 175, 55, 255), font=font_badge, anchor="mm")
    draw.text((cx, cy + 54), "303 BILLION BBL (18.2%)", fill=(56, 189, 248, 255), font=font_badge, anchor="mm")

    # 5. Ranked Breakdown Cards Below Donut with CIRCULAR COUNTRY FLAGS
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

    # 6. Lower-Third Dynamic Subtitle
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

if __name__ == "__main__":
    im = render_flag_embedded_donut()
    im.save("output/v2_donut_flag_embedded_preview.png", "PNG")
    print("Saved: output/v2_donut_flag_embedded_preview.png")
