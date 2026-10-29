"""Focused unit tests for Phase 2A Typography Sanitization.

Tests verify:
1. U+2011 non-breaking hyphen is normalized to standard ASCII hyphen '-'.
2. En-dash (U+2013), em-dash (U+2014), figure dash (U+2012), horizontal bar (U+2015),
   and mathematical minus (U+2212) normalize to '-'.
3. Curly single quotes (U+2018, U+2019) and double quotes (U+201C, U+201D) normalize
   to ASCII single and double quotes (' and ").
4. Zero-width spaces (U+200B..U+200F, U+FEFF) and soft hyphens (U+00AD) are cleanly removed.
5. Typographic spaces (U+00A0, U+202F, U+2007, U+2002..U+200A) normalize to ASCII space ' '.
6. Supported Latin accented characters (e.g. São Tomé, Côte d'Ivoire, Türkiye) are
   strictly preserved without blind ASCII conversion.
7. Numbers, currency, percentages, and punctuation intent are preserved.
8. Empty, None, and non-string inputs are safely handled.
9. sanitize_renderable_text alias parity with sanitize_typography.
10. Integration test with VisualEngine._layout_header confirming rendered artist text
    contains no non-breaking hyphens or broken glyphs.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from app.visuals.fonts import sanitize_renderable_text, sanitize_typography
from app.visuals.scene_engine import VisualEngine


def test_sanitize_non_breaking_hyphen_and_dashes():
    """Verify non-breaking hyphen and all dash variations map to standard '-'."""
    # Production defect case: U+2011 in title
    raw = "Under\u20115 Mortality Rate"
    assert sanitize_renderable_text(raw) == "Under-5 Mortality Rate"

    # Year ranges with en-dash (U+2013)
    raw_range = "2010\u20132024"
    assert sanitize_renderable_text(raw_range) == "2010-2024"

    # Title with em-dash (U+2014)
    raw_em = "Lebanon \u2014 A Steep Climb"
    assert sanitize_renderable_text(raw_em) == "Lebanon - A Steep Climb"

    # Mathematical minus (U+2212), figure dash (U+2012), horizontal bar (U+2015)
    assert sanitize_renderable_text("\u22125.2 points") == "-5.2 points"
    assert sanitize_renderable_text("A\u2012B\u2015C") == "A-B-C"

    # Soft hyphen (U+00AD) is removed
    assert sanitize_renderable_text("dis\u00ADcon\u00ADtin\u00ADued") == "discontinued"


def test_sanitize_curly_quotes_and_apostrophes():
    """Verify typographic curly quotes, guillemets, and apostrophes map to ASCII quotes."""
    # Curly single quotes / apostrophes
    raw_single = "\u2018Lebanon\u2019s Trend\u2019"
    assert sanitize_renderable_text(raw_single) == "'Lebanon's Trend'"

    # Curly double quotes
    raw_double = "\u201cThe Real Winner\u201d"
    assert sanitize_renderable_text(raw_double) == '"The Real Winner"'

    # Low-9 quotes and reversed quotes
    raw_low = "\u201eGerman\u201f \u201aFrench\u201b"
    assert sanitize_renderable_text(raw_low) == '"German" \'French\''

    # Modifier letters apostrophe (e.g. Hawaiʻi) and prime
    assert sanitize_renderable_text("Hawai\u02BCi") == "Hawai'i"
    assert sanitize_renderable_text("5\u2032 10\u2033") == "5' 10\""

    # Guillemets and angle quotes
    assert sanitize_renderable_text("\u00ABBonjour\u00BB") == '"Bonjour"'
    assert sanitize_renderable_text("\u2039Hello\u203A") == "'Hello'"


def test_sanitize_zero_width_and_invisible_characters():
    """Verify zero-width spaces, BOM, and direction marks are removed."""
    raw = "Hidden\u200BZero\u200CWidth\u200DChars\uFEFFHere\u200E\u200F"
    assert sanitize_renderable_text(raw) == "HiddenZeroWidthCharsHere"


def test_sanitize_typographic_spaces_and_ellipsis():
    """Verify non-breaking and thin spaces map to regular ASCII space, ellipsis to '...'."""
    # Non-breaking space (U+00A0), narrow non-breaking space (U+202F), figure space (U+2007)
    raw_spaces = "10\u00A0000\u202FUSD\u2007per\u2003capita"
    assert sanitize_renderable_text(raw_spaces) == "10 000 USD per capita"

    # Ellipsis (U+2026)
    assert sanitize_renderable_text("Wait for it\u2026") == "Wait for it..."


def test_preserve_numbers_and_safe_ascii():
    """Verify standard ASCII text, numbers, punctuation, and math symbols are untouched."""
    clean_text = "Child Mortality Under 5: 17.6 vs 13.2 (+4.4 points, 75.5%)!"
    assert sanitize_renderable_text(clean_text) == clean_text


def test_preserve_supported_unicode_latin_characters():
    """Verify supported Latin accented Unicode characters are NOT converted to ASCII."""
    accented_cases = [
        "São Tomé and Príncipe",
        "Côte d'Ivoire",
        "Türkiye",
        "Curaçao",
        "Réunion",
        "Åland Islands",
    ]
    for case in accented_cases:
        assert sanitize_renderable_text(case) == case


def test_edge_cases_and_non_string_inputs():
    """Verify handling of empty string, None, and numeric inputs."""
    assert sanitize_renderable_text("") == ""
    assert sanitize_renderable_text(None) == ""
    assert sanitize_renderable_text(2024) == "2024"
    assert sanitize_renderable_text(4.4) == "4.4"


def test_alias_parity():
    """Verify sanitize_renderable_text and sanitize_typography are identical."""
    sample = "Under\u20115 \u2014 \u2018Lebanon\u2019"
    assert sanitize_renderable_text(sample) == sanitize_typography(sample)
    assert sanitize_renderable_text is sanitize_typography


def test_header_layout_integration_clean_rendering():
    """Integration test: Verify VisualEngine._layout_header sanitizes title and subtitle."""
    fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
    try:
        raw_title = "Under\u20115 Mortality \u2014 \u2018Crisis\u2019"
        raw_subtitle = "Regional\u2011Trend \u2013 2024"

        layout = VisualEngine._layout_header(
            fig,
            title=raw_title,
            subtitle=raw_subtitle,
        )

        # Confirm the layout title_lines have standard '-' and "'" without \u2011 or \u2014
        joined_lines = " ".join(layout["title_lines"])
        assert "\u2011" not in joined_lines
        assert "\u2014" not in joined_lines
        assert "\u2018" not in joined_lines
        assert "\u2019" not in joined_lines
        assert "UNDER-5" in joined_lines
        assert "- 'CRISIS'" in joined_lines

        # Inspect the text artists on the figure
        figure_texts = [t.get_text() for t in fig.texts]
        for txt in figure_texts:
            assert "\u2011" not in txt, f"Found unsanitized U+2011 in figure text: '{txt}'"
            assert "\u2013" not in txt, f"Found unsanitized U+2013 in figure text: '{txt}'"
            assert "\u2014" not in txt, f"Found unsanitized U+2014 in figure text: '{txt}'"
    finally:
        plt.close(fig)


# =====================================================================
# 11. NON-BAR-RACE RENDERER TYPOGRAPHY SANITIZATION REGRESSION TESTS
# =====================================================================


class _MockScript:
    """Mock script model for non-rendering visual tests."""
    title = "Under\u20115 Child Mortality \u2014 Global Shift"
    source_name = "World Bank \u2014 WDI"
    indicator_name = "Mortality Rate (Under\u20115)"
    total_duration = 5.0

    def __init__(self, entities):
        self.scenes = [
            type(
                "Scene",
                (),
                {
                    "highlight_countries": list(entities),
                    "narration": "Test narration",
                    "text_overlay": "Test overlay",
                },
            )()
        ]


def test_render_line_sanitizes_entity_labels(monkeypatch):
    """Verify render_line sanitizes entity names while preserving Latin accents."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)
    monkeypatch.setattr(VisualEngine, "prefetch_flags", lambda *a, **kw: None)
    monkeypatch.setattr(VisualEngine, "_get_flag_image", lambda *a, **kw: None)

    entities = ["São Tomé\u20111", "Côte d\u2019Ivoire \u2014 North"]
    df = pd.DataFrame(
        {
            "2010": [10.0, 20.0],
            "2020": [15.0, 25.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    fig = VisualEngine.render_line(script, df, "_dummy_dir")
    try:
        all_texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("São Tomé-1" in t for t in all_texts)
        assert any("Côte d'Ivoire - North" in t for t in all_texts)
        assert not any("\u2011" in t for t in all_texts)
        assert not any("\u2014" in t for t in all_texts)
        assert not any("\u2019" in t for t in all_texts)
    finally:
        plt.close(fig)


def test_render_area_sanitizes_entity_labels(monkeypatch):
    """Verify render_area sanitizes entity names while preserving Latin accents."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)
    monkeypatch.setattr(VisualEngine, "prefetch_flags", lambda *a, **kw: None)
    monkeypatch.setattr(VisualEngine, "_get_flag_image", lambda *a, **kw: None)

    entities = ["Under\u20115 Zone", "São Tomé \u2013 Island"]
    df = pd.DataFrame(
        {
            "2010": [10.0, 20.0],
            "2020": [15.0, 25.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    fig = VisualEngine.render_area(script, df, "_dummy_dir")
    try:
        all_texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("Under-5 Zone" in t for t in all_texts)
        assert any("São Tomé - Island" in t for t in all_texts)
        assert not any("\u2011" in t for t in all_texts)
        assert not any("\u2013" in t for t in all_texts)
    finally:
        plt.close(fig)


def test_render_slope_sanitizes_entity_labels(monkeypatch):
    """Verify render_slope sanitizes left and right labels."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)
    monkeypatch.setattr(VisualEngine, "prefetch_flags", lambda *a, **kw: None)
    monkeypatch.setattr(VisualEngine, "_get_flag_image", lambda *a, **kw: None)

    entities = ["Türkiye \u2014 South", "Curaçao \u2011 West"]
    df = pd.DataFrame(
        {
            "2010": [10.0, 30.0],
            "2020": [20.0, 15.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    fig = VisualEngine.render_slope(script, df, "_dummy_dir")
    try:
        all_texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("Türkiye - South" in t for t in all_texts)
        assert any("Curaçao - West" in t for t in all_texts)
        assert not any("\u2011" in t for t in all_texts)
        assert not any("\u2014" in t for t in all_texts)
    finally:
        plt.close(fig)


def test_render_top5_change_sanitizes_country_labels(monkeypatch):
    """Verify render_top5_change sanitizes country labels."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)
    monkeypatch.setattr(VisualEngine, "prefetch_flags", lambda *a, **kw: None)
    monkeypatch.setattr(VisualEngine, "_get_flag_image", lambda *a, **kw: None)

    entities = ["Under\u20115 Leader", "Réunion \u2014 Isle"]
    df = pd.DataFrame(
        {
            "2010": [10.0, 20.0],
            "2020": [25.0, 15.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    fig = VisualEngine.render_top5_change(script, df, "_dummy_dir")
    try:
        all_texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("Under-5 Leader" in t for t in all_texts)
        assert any("Réunion - Isle" in t for t in all_texts)
        assert not any("\u2011" in t for t in all_texts)
        assert not any("\u2014" in t for t in all_texts)
    finally:
        plt.close(fig)


def test_render_pie_and_waffle_sanitize_legend_labels(monkeypatch):
    """Verify render_pie and render_waffle sanitize leader and legend labels."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)

    entities = ["Under\u20115 Major", "São Tomé"]
    df = pd.DataFrame(
        {
            2020: [60.0, 40.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    # 1. Pie / Donut
    fig_pie = VisualEngine.render_pie(script, df, "_dummy_dir")
    try:
        pie_texts = [t.get_text() for t in fig_pie.texts] + [t.get_text() for ax in fig_pie.axes for t in ax.texts]
        assert any("Under-5 Major" in t for t in pie_texts)
        assert any("São Tomé" in t for t in pie_texts)
        assert not any("\u2011" in t for t in pie_texts)
    finally:
        plt.close(fig_pie)

    # 2. Waffle
    fig_waffle = VisualEngine.render_waffle(script, df, "_dummy_dir")
    try:
        waffle_texts = [t.get_text() for t in fig_waffle.texts] + [t.get_text() for ax in fig_waffle.axes for t in ax.texts]
        assert any("Under-5 Major" in t for t in waffle_texts)
        assert any("São Tomé" in t for t in waffle_texts)
        assert not any("\u2011" in t for t in waffle_texts)
    finally:
        plt.close(fig_waffle)


def test_render_bubble_sanitizes_labels(monkeypatch):
    """Verify render_bubble sanitizes bubble labels."""
    import pandas as pd
    monkeypatch.setattr(VisualEngine, "_save_animation", lambda fig, *a, **kw: fig)
    monkeypatch.setattr(VisualEngine, "prefetch_flags", lambda *a, **kw: None)
    monkeypatch.setattr(VisualEngine, "_get_flag_image", lambda *a, **kw: None)

    entities = ["Under\u20115 State", "Côte d\u2019Ivoire"]
    df = pd.DataFrame(
        {
            "2020": [50.0, 80.0],
        },
        index=entities,
    )
    script = _MockScript(entities)

    fig = VisualEngine.render_bubble(script, df, "_dummy_dir")
    try:
        bubble_texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        assert any("Under-5 State" in t for t in bubble_texts)
        assert any("Côte d'Ivoire" in t for t in bubble_texts)
        assert not any("\u2011" in t for t in bubble_texts)
        assert not any("\u2019" in t for t in bubble_texts)
    finally:
        plt.close(fig)
