import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Print the EXACT current text of _get_bar_color block with repr
# so we can build an exact-match old_text for the editor.
src = open("app/visuals/scene_engine.py", encoding="utf-8").read()
lines = src.splitlines(keepends=True)

start = None
end = None
for i, l in enumerate(lines):
    if l.startswith("    @staticmethod\n    def _get_bar_color("):
        start = i
    if start is not None and l.startswith("    # =========================================================\n    # STEP 6"):
        end = i
        break

print("START", start)
print("END", end)
for i in range(start, end):
    print(repr(lines[i]))
