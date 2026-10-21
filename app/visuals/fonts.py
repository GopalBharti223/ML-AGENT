# -*- coding: utf-8 -*-
"""Premium font registry for the Shorts canvas.

Bundles open-source (SIL OFL) fonts in ``assets/fonts`` and registers
them with matplotlib once per process.  Every visual module asks THIS
module for a family name, so a missing font file degrades to DejaVu
Sans in exactly one place instead of crashing a render.

Bundled families
----------------
``Montserrat``  ExtraBold / Bold  -> titles, year counter
``Inter``       Bold / SemiBold  -> entity labels, values, axis text

Sizing contract
---------------
The canvas is 1080x1920 at ``dpi=100``, so::

    1 px  == 1/100 inch == 0.72 pt   =>   px == pt * 100 / 72

``FONT_MIN_PX`` is the absolute legibility floor.  Auto-fit may never
return a size below it: a label that still does not fit at the floor is
ellipsised by the caller instead.
"""
import os

import matplotlib
matplotlib.use("Agg")

from matplotlib import font_manager

from app.config import settings


# Absolute legibility floor on a 1080-wide canvas.  Nothing may be
# drawn smaller than this -- it is the value the short-name map,
# auto-fit and ellipsis all treat as "cannot shrink any further".
FONT_MIN_PX = float(getattr(settings, "UI_MIN_FONT_PX", 30))

FALLBACK_FAMILY = "DejaVu Sans"

_STATE = {"registered": False, "families": frozenset()}


def px_to_pt(px):
    """Convert a pixel size at dpi=100 into matplotlib points."""
    return float(px) * 72.0 / 100.0


def pt_to_px(pt):
    """Convert matplotlib points into delivered pixels at dpi=100."""
    return float(pt) * 100.0 / 72.0


def min_pt():
    """The legibility floor expressed in points."""
    return px_to_pt(FONT_MIN_PX)


def _font_dirs():
    """Candidate directories that may hold bundled .ttf/.otf files."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)
    )))  # repo root (app/visuals/fonts.py -> repo)
    return [
        os.path.join(base, "assets", "fonts"),
        os.path.join(base, "app", "assets", "fonts"),
    ]


def register_fonts(force=False):
    """Add every bundled font to matplotlib.  Safe to call repeatedly.

    Returns the frozenset of family names that were actually installed.
    Never raises: an unreadable file is skipped.
    """
    if _STATE["registered"] and not force:
        return _STATE["families"]

    found = set()
    for directory in _font_dirs():
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.lower().endswith((".ttf", ".otf")):
                continue
            path = os.path.join(directory, name)
            try:
                font_manager.fontManager.addfont(path)
            except Exception:  # unreadable / corrupt / not a font
                continue
            try:
                found.add(font_manager.FontProperties(fname=path).get_name())
            except Exception:
                continue

    if not found:
        # Nothing bundled -- make sure the default is resolvable.
        try:
            font_manager.findfont(
                font_manager.FontProperties(family=FALLBACK_FAMILY),
                fallback_to_default=True,
            )
        except Exception:
            pass

    _STATE["families"] = frozenset(found)
    _STATE["registered"] = True
    return _STATE["families"]


def installed_families():
    """Family names available from the bundle (registers on demand)."""
    return register_fonts()


def _resolve(preferred):
    """Pick `preferred` when its family really exists, else DejaVu."""
    families = register_fonts()

    if not preferred:
        return FALLBACK_FAMILY

    lowered = {f.lower(): f for f in families}
    hit = lowered.get(str(preferred).lower())
    if hit:
        return hit

    # Partial match: "Montserrat ExtraBold" -> "Montserrat".
    for key, actual in lowered.items():
        if str(preferred).lower() in key or key in str(preferred).lower():
            return actual

    return FALLBACK_FAMILY


def title_family():
    """Display family for titles / year counter."""
    return _resolve(getattr(settings, "UI_FONT_TITLE", "Montserrat"))


def text_family():
    """Text family for entity labels / values / axis text."""
    return _resolve(getattr(settings, "UI_FONT_TEXT", "Inter"))


def title_weight():
    """Heaviest usable weight for the title family."""
    return "bold"


def label_weight():
    """Weight used for entity labels and values."""
    return "bold"


# Register eagerly so import cost is paid once, not per render.
register_fonts()
