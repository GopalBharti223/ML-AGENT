import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

path = "app/visuals/scene_engine.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# Build the exact old block from the repr we printed
old_block = '''    @staticmethod
    def _get_bar_color(
        rank,
        is_current_leader=False,
        is_overtake=False
    ):

        if is_overtake:
            return VisualEngine.OVERTAKE_COLOR

        if is_current_leader:
            return VisualEngine.LEADER_COLOR

        # -----------------------------------------------------
        # MULTI-COLOUR MODE (Part 4): one distinct colour per
        # bar, from the curated palette, instead of the single
        # rotated gradient ramp.  Leader / overtake emphasis
        # above still wins, so the story beats stay readable.
        # -----------------------------------------------------

        if VisualEngine._MULTI_COLOR_MODE:

            palette = VisualEngine.MULTI_COLOR_PALETTE

            if palette:

                rank = max(
                    0,
                    min(
                        int(rank),
                        len(palette) - 1
                    )
                )

                return palette[rank]

        # Active themed palette for THIS video (rotated once per
        # render by select_palette; falls back to a lazy pick when
        # a renderer was called directly).
        palette = (
            VisualEngine._ACTIVE_PALETTE
            or VisualEngine.select_palette()
        )

        rank = max(
            0,
            min(
                int(rank),
                len(palette) - 1
            )
        )

        return palette[rank]
'''

# The file uses CRLF. Normalize both to \n for comparison.
src_n = src.replace("\r\n", "\n")
old_n = old_block.replace("\r\n", "\n")

if old_n in src_n:
    src = src_n.replace(old_n, new_block, 1)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(src)
    print("REPLACED OK")
else:
    print("NOT FOUND")
    # Show what's around the marker
    idx = src_n.find("def _get_bar_color(")
    print(repr(src_n[idx:idx+600]))
