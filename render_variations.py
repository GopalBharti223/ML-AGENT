import subprocess
import os

with open("codehelp_style_quiz.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. 3s Urgent State (Clock turns fiery crimson with glowing aura)
html_3s = html.replace("class='timer-pill'", "class='timer-pill urgent'").replace(">7s<", ">3s<")
with open("codehelp_style_quiz_3s.html", "w", encoding="utf-8") as f:
    f.write(html_3s)

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
html_path = os.path.abspath("codehelp_style_quiz_3s.html")
out_path = os.path.abspath("codehelp_style_quiz_3s.png")

cmd = [
    chrome_path,
    "--headless=new",
    f"--screenshot={out_path}",
    "--window-size=1080,1920",
    "--hide-scrollbars",
    "--allow-file-access-from-files",
    "file:///" + html_path.replace("\\", "/")
]
subprocess.run(cmd, check=True)
print("Rendered codehelp_style_quiz_3s.png successfully!")
