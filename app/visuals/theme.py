# -*- coding: utf-8 -*-
"""PREMIUM TOPIC THEMES.

Wires each video's visual identity to a per-topic theme:
background gradient, accent, glow, and an 8-colour bar ramp.

ThemeEngine is deliberately pure data: it knows nothing about
matplotlib.  The renderers that need pixel-level background work
call design_system.build_theme() and draw with those pixels.

Theme resolution follows the existing keyword pipeline in
app.config (Settings._TOPIC_KEYWORD_MAP) so topics resolve the
same way they already do.  Unmatched topics fall through to a
persistent cursor rotation so two consecutive videos NEVER share
a theme.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-theme design tokens.  Every token is a hex string (matplotlib-safe).
# ---------------------------------------------------------------------------

def _theme(
    *,
    bg_top,
    bg_bottom,
    accent,
    accent2,
    glow,
    ramp,
    text_primary="#F8F6F0",
    text_secondary="#A8B3C7",
):
    return {
        "bg_top": bg_top,
        "bg_bottom": bg_bottom,
        "accent": accent,
        "accent2": accent2,
        "glow": glow,
        "text_primary": text_primary,
        "text_secondary": text_secondary,
        "ramp": ramp,
    }


# ---------------------------------------------------------------------------
# The eight themes, prioritised in design spec order.
# ---------------------------------------------------------------------------

def _theme_world():
    return _theme(
        bg_top="#0B1020",
        bg_bottom="#151C36",
        accent="#D4AF37",
        accent2="#F0D48A",
        glow="#D4AF37",
        ramp=[
            "#F4E4A8",
            "#E8D08A",
            "#D9B870",
            "#C8A058",
            "#B08840",
            "#966F2E",
            "#7A5526",
            "#5A3D16",
        ],
    )


def _theme_economy():
    return _theme(
        bg_top="#07140F",
        bg_bottom="#0F2A20",
        accent="#F5C15C",
        accent2="#2ECC9A",
        glow="#F5C15C",
        ramp=[
            "#FFE2B0", "#F5CC8A", "#E8B86E", "#D9A358", "#C48E48",
            "#A9753A", "#8A5C2E", "#6B4422",
        ],
    )


def _theme_population():
    return _theme(
        bg_top="#071A2E",
        bg_bottom="#0E3556",
        accent="#4FC3F7",
        accent2="#A9DFFF",
        glow="#4FC3F7",
        ramp=[
            "#8FD9FF", "#6FB6F0", "#5A9FE0", "#4588D2", "#346BA8",
            "#27508A", "#1E3666", "#142040",
        ],
    )


def _theme_military():
    return _theme(
        bg_top="#140C0E",
        bg_bottom="#2A1317",
        accent="#FF5A4F",
        accent2="#FFB4A8",
        glow="#FF5A4F",
        ramp=[
            "#FF8F8A", "#FF7A6E", "#FF6A5A", "#FF5A4A", "#E64A3F",
            "#CC3B32", "#B02B24", "#8A1E1D",
        ],
    )

def _theme_technology():
    return _theme(
        bg_top="#0A0B1F",
        bg_bottom="#1A1445",
        accent="#22D3EE",
        accent2="#A78BFA",
        glow="#22D3EE",
        ramp=[
            "#86E4FF", "#6BC0FF", "#51A6FF", "#3A8EF0", "#2876E8",
            "#1F5FBE", "#164694", "#0D2E60",
        ],
    )


def _theme_health():
    return _theme(
        bg_top="#06171A",
        bg_bottom="#0C3A3F",
        accent="#34D399",
        accent2="#99F6E4",
        glow="#34D399",
        ramp=[
            "#7CF0C0", "#5DE8AA", "#44CFA0", "#2DA984", "#1A8C68",
            "#127050", "#0A543A", "#04382A",
        ],
    )


def _theme_sports():
    return _theme(
        bg_top="#120A24",
        bg_bottom="#2A1250",
        accent="#F472B6",
        accent2="#FBBF24",
        glow="#F472B6",
        ramp=[
            "#FFA6C4", "#FF8FB0", "#FF7898", "#FF5F80", "#FF4768",
            "#F73450", "#E62038", "#CC1220",
        ],
    )


def _theme_energy():
    return _theme(
        bg_top="#0A1409",
        bg_bottom="#17301A",
        accent="#A3E635",
        accent2="#FDE047",
        glow="#A3E635",
        ramp=[
            "#BEFE3A", "#A5E635", "#8DD92E", "#75C627", "#5EAF20",
            "#479819", "#307F12", "#1D620B",
        ],
    )


# ---------------------------------------------------------------------------
# Registry.  Map keyword groups (economy, population, military, ...) to
# an *immutable* theme key.  Resolution lives in resolve_theme().
# ---------------------------------------------------------------------------

_THEME_REGISTRY = {
    "world": _theme_world,
    "economy": _theme_economy,
    "population": _theme_population,
    "military": _theme_military,
    "technology": _theme_technology,
    "ai": _theme_technology,
    "health": _theme_health,
    "sports": _theme_sports,
    "gaming": _theme_sports,
    "energy": _theme_energy,
    "environment": _theme_energy,
    "environment_climate": _theme_energy,
}


def build_theme(theme_key):
    """Return a theme dict for a registered key, or None."""
    builder = _THEME_REGISTRY.get(theme_key)
    if builder is None:
        return None
    return builder()


def theme_keys():
    return sorted(_THEME_REGISTRY.keys())


def default_theme_key():
    """The first/primary theme, used as the identity anchor."""
    return "world"


def resolve_theme(haystack):
    """Pick a theme from a title/topic/category string.

    1. Exact keyword match on the design tokens.
    2. Otherwise rotate through the full registry with a persistent
       caller-side cursor, so consecutive videos never share a
       theme.
    """
    haystack = haystack.lower() if isinstance(haystack, str) else ""

    # Exact subsystem keywords -> theme key.
    for key in ("economy", "population", "military", "technology", "ai"):
        if key in haystack:
            return key

    # Topic keyword families that should map to a theme.
    for token, keys in (
        ("gdp", "economy"),
        ("inflation", "economy"),
        ("income", "economy"),
        ("debt", "economy"),
        ("defense", "military"),
        ("military", "military"),
        ("sports", "sports"),
        ("gym", "sports"),
        ("gaming", "sports"),
        ("health", "health"),
        ("population", "population"),
        ("energy", "energy"),
        ("environment", "energy"),
        ("climate", "energy"),
    ):
        if token in haystack:
            return keys

    return None


# ---------------------------------------------------------------------------
# Persisted cursor (module global).  Callers must reset via reset_cursor()
# between separate render runs so the rotation is stable within a batch.
# ---------------------------------------------------------------------------

_CURSOR = {"index": 0}


def reset_cursor():
    _CURSOR["index"] = 0


def next_theme_key(haystack):
    """Pick a theme for a single video.  Returns a theme KEY (not a dict)."""
    key = resolve_theme(haystack)
    if key is not None and key in _THEME_REGISTRY:
        return key

    # Round-robin through every registered theme.
    keys = theme_keys()
    if not keys:
        return "world"
    idx = _CURSOR["index"] % len(keys)
    _CURSOR["index"] += 1
    return keys[idx]
