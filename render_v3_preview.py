"""
Preview renderer for V3 Interactive Quiz UI with category-specific color themes,
circular SVG countdown depleter, interactive difficulty badge, and "Did You Know" fact card.
"""

import os
import subprocess

WIDTH = 1080
HEIGHT = 1920
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = r"output\preview_v3_interactive"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CATEGORY_THEMES = {
    "SPORTS & SPEED": {
        "beam": "radial-gradient(circle, rgba(249, 115, 22, 0.35) 0%, rgba(234, 88, 12, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#f97316",
        "pill_bg": "rgba(249, 115, 22, 0.12)",
        "pill_border": "rgba(249, 115, 22, 0.45)",
        "pill_text": "#fb923c",
        "glow": "rgba(249, 115, 22, 0.65)"
    },
    "TECH & AI": {
        "beam": "radial-gradient(circle, rgba(6, 182, 212, 0.35) 0%, rgba(14, 165, 233, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#06b6d4",
        "pill_bg": "rgba(6, 182, 212, 0.12)",
        "pill_border": "rgba(6, 182, 212, 0.45)",
        "pill_text": "#22d3ee",
        "glow": "rgba(6, 182, 212, 0.65)"
    },
    "SPACE & COSMIC": {
        "beam": "radial-gradient(circle, rgba(168, 85, 247, 0.35) 0%, rgba(124, 58, 237, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#a855f7",
        "pill_bg": "rgba(168, 85, 247, 0.12)",
        "pill_border": "rgba(168, 85, 247, 0.45)",
        "pill_text": "#c084fc",
        "glow": "rgba(168, 85, 247, 0.65)"
    },
    "MOVIES & POP CULTURE": {
        "beam": "radial-gradient(circle, rgba(236, 72, 153, 0.35) 0%, rgba(219, 39, 119, 0.14) 40%, rgba(8, 7, 13, 0) 70%)",
        "accent": "#ec4899",
        "pill_bg": "rgba(236, 72, 153, 0.12)",
        "pill_border": "rgba(236, 72, 153, 0.45)",
        "pill_text": "#f472b6",
        "glow": "rgba(236, 72, 153, 0.65)"
    }
}

SAMPLE_QUIZ = {
    "category": "MOVIES & POP CULTURE",
    "difficulty": "94% FAIL THIS",
    "question": "Which country produces the highest number of movies in the world every single year?",
    "clue": "Releasing over 1,500 films annually across multiple mega-languages",
    "fact": "India releases over 1,500 to 2,000 films yearly, more than double Hollywood!",
    "options": [
        {"letter": "A", "name": "UNITED STATES", "code": "us", "correct": False},
        {"letter": "B", "name": "NIGERIA", "code": "ng", "correct": False},
        {"letter": "C", "name": "INDIA", "code": "in", "correct": True},
        {"letter": "D", "name": "JAPAN", "code": "jp", "correct": False},
    ]
}

def get_flag_path(code):
    p1 = os.path.abspath(f"assets/flags_hires/{code}.png")
    p2 = os.path.abspath(f"assets/flags/{code}.png")
    path = p1 if os.path.exists(p1) else p2
    return "file:///" + path.replace("\\", "/")

def build_v3_frame(quiz, timer_sec=6, is_reveal=False):
    theme = CATEGORY_THEMES.get(quiz["category"], CATEGORY_THEMES["MOVIES & POP CULTURE"])
    
    # Timer progress math (circumference = 2 * pi * 72 = ~452.4)
    circumference = 452.4
    if is_reveal or timer_sec == 0:
        dash_offset = circumference
    else:
        dash_offset = circumference * (1 - (timer_sec / 6.0))
        
    is_urgent = timer_sec <= 2
    ring_color = "#ef4444" if is_urgent else theme["accent"]
    ring_glow = "rgba(239, 68, 68, 0.85)" if is_urgent else theme["glow"]
    
    cards_html = ""
    card_themes = [
        {"glow": "#00d2ff", "border": "rgba(56, 189, 248, 0.7)", "text": "#7dd3fc", "badge": "linear-gradient(135deg, #0ea5e9, #0284c7)"},
        {"glow": "#6366f1", "border": "rgba(129, 140, 248, 0.7)", "text": "#c4b5fd", "badge": "linear-gradient(135deg, #6366f1, #4f46e5)"},
        {"glow": "#10b981", "border": "rgba(52, 211, 153, 0.7)", "text": "#6ee7b7", "badge": "linear-gradient(135deg, #10b981, #059669)"},
        {"glow": "#f59e0b", "border": "rgba(251, 191, 36, 0.7)", "text": "#fcd34d", "badge": "linear-gradient(135deg, #f59e0b, #d97706)"},
    ]

    for i, opt in enumerate(quiz["options"]):
        th = card_themes[i % len(card_themes)]
        flag_url = get_flag_path(opt["code"])
        
        if is_reveal:
            if opt["correct"]:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#10b981;opacity:0.95;filter:blur(44px);'></div>
                  <div class='option-card' style='border:3.5px solid rgba(52,211,153,0.95);background:rgba(6,44,30,0.94);box-shadow:0 0 55px rgba(16,185,129,0.6);'>
                    <div class='letter-pill' style='background:linear-gradient(135deg,#10b981,#059669);font-size:38px;'>✓</div>
                    <img class='flag-thumb' src='{flag_url}'>
                    <div class='country-title' style='color:#34d399;font-size:45px;'>{opt["name"]}</div>
                  </div>
                </div>"""
            else:
                cards_html += f"""
                <div class='card-wrapper'>
                  <div class='card-glow' style='background:#1e293b;opacity:0.1;'></div>
                  <div class='option-card' style='border:2px solid rgba(51,65,85,0.25);opacity:0.32;'>
                    <div class='letter-pill' style='background:#334155;color:#94a3b8;'>{opt["letter"]}</div>
                    <img class='flag-thumb' src='{flag_url}'>
                    <div class='country-title' style='color:#64748b;'>{opt["name"]}</div>
                  </div>
                </div>"""
        else:
            cards_html += f"""
            <div class='card-wrapper'>
              <div class='card-glow' style='background:{th["glow"]};'></div>
              <div class='option-card' style='border:2px solid {th["border"]};'>
                <div class='letter-pill' style='background:{th["badge"]};'>{opt["letter"]}</div>
                <img class='flag-thumb' src='{flag_url}'>
                <div class='country-title' style='color:{th["text"]};'>{opt["name"]}</div>
              </div>
            </div>"""

    if is_reveal:
        fact_card = f"""
        <div class='fact-box'>
          <div class='fact-badge'>💡 DID YOU KNOW?</div>
          <div class='fact-text'>{quiz["fact"]}</div>
        </div>"""
        footer_html = """
        <div class='footer-bar footer-reveal'>
          <div class='footer-text' style='color:#ffffff;font-size:30px;'>🎯 DID YOU GET IT RIGHT? COMMENT YES OR NO! 👇</div>
        </div>"""
    else:
        fact_card = ""
        footer_html = """
        <div class='footer-bar'>
          <div class='footer-text'>💬 Comment your guess before the timer hits 0!</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Space+Grotesk:wght@500;600;700&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1080px; height: 1920px; background: #08070d; font-family: 'Space Grotesk', sans-serif;
    color: white; display: flex; flex-direction: column; align-items: center;
    padding: 80px 70px 70px 70px; overflow: hidden; position: relative;
  }}
  .light-beam {{
    position: absolute; top: 12%; left: 50%; transform: translate(-50%, -20%);
    width: 1000px; height: 1000px;
    background: {theme["beam"]};
    pointer-events: none; z-index: 1;
  }}
  .channel-name {{
    position: absolute; top: 25px; right: 28px; font-size: 22px; font-weight: 700;
    color: rgba(255, 255, 255, 0.45); letter-spacing: 2px; z-index: 10;
  }}
  .content {{
    position: relative; z-index: 2; width: 100%; display: flex; flex-direction: column;
    align-items: center; height: 100%;
  }}
  .badges-row {{
    display: flex; align-items: center; gap: 16px; margin-bottom: 30px;
  }}
  .category-pill {{
    background: {theme["pill_bg"]}; border: 1.5px solid {theme["pill_border"]};
    backdrop-filter: blur(16px); color: {theme["pill_text"]}; padding: 10px 28px; border-radius: 999px;
    font-size: 20px; font-weight: 700; letter-spacing: 1.8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  }}
  .difficulty-pill {{
    background: rgba(239, 68, 68, 0.15); border: 1.5px solid rgba(239, 68, 68, 0.45);
    backdrop-filter: blur(16px); color: #f87171; padding: 10px 24px; border-radius: 999px;
    font-size: 20px; font-weight: 700; letter-spacing: 1.5px;
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.2);
  }}
  .question-box {{ text-align: center; max-width: 960px; margin-bottom: 30px; }}
  .question-title {{
    font-family: 'Playfair Display', serif; font-size: 54px; font-weight: 700;
    line-height: 1.32; color: #ffffff; letter-spacing: -0.5px;
    text-shadow: 0 4px 25px rgba(0, 0, 0, 0.85);
  }}
  .clue-badge-box {{
    margin-top: 16px; display: inline-flex; align-items: center; gap: 12px;
    background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 8px 24px; border-radius: 999px;
  }}
  .clue-label {{ font-size: 20px; font-weight: 700; color: #fbbf24; letter-spacing: 1px; }}
  .clue-text {{ font-size: 23px; color: #cbd5e1; font-weight: 600; }}
  
  .timer-svg-container {{
    position: relative; width: 175px; height: 175px; margin-bottom: 75px;
    display: flex; align-items: center; justify-content: center;
  }}
  .timer-svg-glow {{
    position: absolute; inset: -20px; border-radius: 50%;
    background: {ring_glow}; filter: blur(36px); opacity: 0.65; z-index: 1;
  }}
  .timer-svg-circle {{
    position: absolute; inset: 0; width: 175px; height: 175px; z-index: 2;
    transform: rotate(-90deg);
  }}
  .timer-inner-card {{
    position: relative; z-index: 3; width: 140px; height: 140px; border-radius: 50%;
    background: rgba(13, 16, 27, 0.94); backdrop-filter: blur(24px);
    display: flex; align-items: center; justify-content: center;
    box-shadow: inset 0 2px 10px rgba(255, 255, 255, 0.1), 0 12px 30px rgba(0,0,0,0.8);
  }}
  .timer-num {{ font-size: 72px; font-weight: 800; color: {ring_color}; letter-spacing: -1px; }}
  
  .options-container {{
    width: 100%; display: flex; flex-direction: column; gap: 34px;
  }}
  .card-wrapper {{ position: relative; width: 100%; height: 136px; }}
  .card-glow {{
    position: absolute; inset: -10px; border-radius: 36px; filter: blur(36px);
    opacity: 0.65; z-index: 1;
  }}
  .option-card {{
    position: relative; z-index: 2; width: 100%; height: 100%; border-radius: 28px;
    display: flex; align-items: center; padding: 0 34px; background: rgba(13, 16, 27, 0.88);
    backdrop-filter: blur(24px); box-shadow: 0 16px 36px rgba(0,0,0,0.85);
  }}
  .letter-pill {{
    width: 68px; height: 68px; border-radius: 20px; display: flex; align-items: center;
    justify-content: center; font-size: 32px; font-weight: 700; margin-right: 28px;
    color: white; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
  }}
  .flag-thumb {{
    width: 92px; height: 62px; border-radius: 12px; object-fit: cover; margin-right: 28px;
    border: 1.5px solid rgba(255, 255, 255, 0.22); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  }}
  .country-title {{ font-size: 40px; font-weight: 700; letter-spacing: 1px; }}

  .fact-box {{
    margin-top: 25px; width: 100%; padding: 20px 30px; border-radius: 22px;
    background: rgba(16, 185, 129, 0.12); border: 1.5px solid rgba(52, 211, 153, 0.5);
    backdrop-filter: blur(20px); display: flex; flex-direction: column; gap: 8px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
  }}
  .fact-badge {{ font-size: 20px; font-weight: 700; color: #34d399; letter-spacing: 1.5px; }}
  .fact-text {{ font-size: 24px; color: #e2e8f0; font-weight: 600; line-height: 1.3; }}

  .footer-bar {{
    margin-top: 35px; width: 100%; padding: 24px 32px; border-radius: 999px;
    background: rgba(245, 158, 11, 0.08); border: 1.5px solid rgba(245, 158, 11, 0.35);
    backdrop-filter: blur(20px); text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 30px rgba(245, 158, 11, 0.15);
  }}
  .footer-reveal {{
    background: rgba(245, 158, 11, 0.18); border: 2px solid rgba(251, 191, 36, 0.85);
    box-shadow: 0 0 50px rgba(245, 158, 11, 0.4);
  }}
  .footer-text {{ font-size: 26px; font-weight: 700; color: #fbbf24; letter-spacing: 0.5px; }}
</style>
</head>
<body>
  <div class='light-beam'></div>
  <div class='channel-name'>LR ATLAS</div>
  <div class='content'>
    <div class='badges-row'>
      <div class='category-pill'>{quiz["category"]}</div>
      <div class='difficulty-pill'>🧠 {quiz["difficulty"]}</div>
    </div>
    <div class='question-box'>
      <div class='question-title'>{quiz["question"]}</div>
      <div class='clue-badge-box'>
        <span class='clue-label'>💡 CLUE:</span>
        <span class='clue-text'>{quiz["clue"]}</span>
      </div>
    </div>
    
    <div class='timer-svg-container'>
      <div class='timer-svg-glow'></div>
      <svg class='timer-svg-circle' viewBox='0 0 175 175'>
        <!-- Background track -->
        <circle cx='87.5' cy='87.5' r='72' stroke='rgba(255,255,255,0.1)' stroke-width='8' fill='none'/>
        <!-- Depleting countdown arc -->
        <circle cx='87.5' cy='87.5' r='72' stroke='{ring_color}' stroke-width='8' fill='none'
                stroke-dasharray='452.4' stroke-dashoffset='{dash_offset}' stroke-linecap='round'/>
      </svg>
      <div class='timer-inner-card'>
        <span class='timer-num'>{timer_sec}</span>
      </div>
    </div>

    <div class='options-container'>
      {cards_html}
    </div>
    {fact_card}
    {footer_html}
  </div>
</body>
</html>"""

def render_frame_img(html_str, out_fp):
    temp_html_fp = os.path.join(OUTPUT_DIR, "_temp.html")
    with open(temp_html_fp, "w", encoding="utf-8") as f:
        f.write(html_str)
    cmd = [
        CHROME, "--headless=new",
        f"--screenshot={os.path.abspath(out_fp)}",
        "--window-size=1080,1920",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        "file:///" + os.path.abspath(temp_html_fp).replace("\\", "/")
    ]
    subprocess.run(cmd, capture_output=True, check=True)

# Render Question Screen (Countdown 4s)
q_fp = os.path.join(OUTPUT_DIR, "v3_interactive_question.png")
render_frame_img(build_v3_frame(SAMPLE_QUIZ, timer_sec=4, is_reveal=False), q_fp)
print(f"✓ Rendered: {q_fp}")

# Render Reveal Screen (Answer C: India + Did you know card)
rev_fp = os.path.join(OUTPUT_DIR, "v3_interactive_reveal.png")
render_frame_img(build_v3_frame(SAMPLE_QUIZ, timer_sec=0, is_reveal=True), rev_fp)
print(f"✓ Rendered: {rev_fp}")
