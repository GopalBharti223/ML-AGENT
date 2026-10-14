import inspect

from app.visuals import design_system as d

for n in ["resolve_theme", "chart_frame", "fit_label", "wrap_title",
          "label_stack", "title_zone", "bar_face", "ramp"]:
    print("=" * 60)
    print(n)
    print("=" * 60)
    print(inspect.getsource(getattr(d, n)))


