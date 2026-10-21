import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import inspect
from app.visuals import design_system as d
print("THEME_FOR:", d.theme_for("military spending"))
print("ACTIVE:", d.active_theme("population growth"))
print("SAFE:", d.safe_zone())
print("CHART:", d.chart_frame())
print("BAR_FACE:", d.bar_face(["#a","#b"], 0, 2))
print("RAMP:", d.ramp(["#a","#b"], "ramp"))
print("SHORT:", d.short_name("Democratic Republic of the Congo"))
print("TEXT_FAMILY:", d.text_family())
print("FIT_LABEL:", inspect.signature(d.fit_label))
print("WRAP_TITLE:", inspect.signature(d.wrap_title))
print("GLASS_CARD:", inspect.signature(d.glass_card))
print("PAINT_BG:", inspect.signature(d.paint_background))
print("APPLY_ATMOSPHERE:", inspect.signature(d.apply_atmosphere))
