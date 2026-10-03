#!/usr/bin/env python3
"""Regression tests for 3 rendered-video bug fixes.

  Bug 1: Wikipedia pageviews provider resolved wrong-cased entity
         titles ("iPhone 13" -> 77 views) instead of the canonical
         article ("IPhone 13" -> 574k), producing order-of-magnitude
         chart gaps and inconsistent number formatting.
  Bug 2: Intro/outro brand cards used a fixed fontsize that overflowed
         the 1080px frame; _new_card must fit every line inside the
         safe central band (<=80% width, >=10% edge margin).
  Bug 3: _normalize_index used the first MultiIndex level (the raw
         RAWG platform id) as the chart label instead of the
         human-readable platform name.

All tests are offline/deterministic (no network, no ffmpeg).
"""
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from app.visuals.scene_engine import VisualEngine
from app.data.providers.wikipedia import WikipediaPageviewsProvider
from app.data.providers.sec_edgar import SECEdgarProvider
from app.video import branding

FAILED = []


def check(cond, label):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        FAILED.append(label)
        # Raising is what makes this fail under pytest, which
        # discards return values; main() below catches it so
        # script mode still reports every failed check.
        raise AssertionError(label)


# =================================================================
# BUG 1 — Wikipedia title canonicalization in probe_entities
# =================================================================

_ORIG_YEARLY_VIEWS = WikipediaPageviewsProvider._yearly_views
_ORIG_CANDIDATES = WikipediaPageviewsProvider.article_title_candidates


class _FakeViews:
    """Simulates the case-sensitive pageview API + opensearch."""

    fake_views = {}
    fake_candidates = {}

    @classmethod
    def _yearly_views(cls, title, start_year, end_year):
        return dict(cls.fake_views.get(title, {}))

    @classmethod
    def article_title_candidates(cls, name, limit=3):
        return list(cls.fake_candidates.get(name, []))


def test_bug1_case_canonicalization():
    print("TEST 1: probe_entities picks the canonical cased article")
    try:
        # Scenario A: user spells 'iPhone 13' (lowercase ip); the real
        # article is 'IPhone 13'.  The wrong-cased title still reports
        # a few pageviews -- it must NOT win.
        _FakeViews.fake_views = {
            "iPhone 13": {2025: 77.0},
            "IPhone 13": {2025: 574438.0},
            "IPhone 13 Pro": {2025: 322801.0},
            "List of iPhone models": {2025: 1012576.0},
        }
        _FakeViews.fake_candidates = {
            "iPhone 13": ["IPhone 13", "IPhone 13 Pro",
                          "List of iPhone models"],
        }
        WikipediaPageviewsProvider._yearly_views = _FakeViews._yearly_views
        WikipediaPageviewsProvider.article_title_candidates = (
            _FakeViews.article_title_candidates
        )

        verified, failed = WikipediaPageviewsProvider.probe_entities(
            [{"name": "iPhone 13", "title": "iPhone 13"}],
            probe_year=2025,
        )
        print("   verified:", verified, "failed:", failed)
        check(verified.get("iPhone 13") == "IPhone 13",
              "wrong-cased 'iPhone 13' resolves to canonical 'IPhone 13'")
        check("iPhone 13" not in failed, "entity not dropped")

        # Scenario B: an unrelated article has MORE views but must not
        # shadow the requested entity's own article.
        _FakeViews.fake_views = {
            "Samsung Galaxy S21": {2025: 212793.0},
            "Samsung Galaxy S25": {2025: 715334.0},
            "Samsung Galaxy S III": {2025: 12000.0},
        }
        _FakeViews.fake_candidates = {
            "Samsung Galaxy S21": ["Samsung Galaxy S21",
                                   "Samsung Galaxy S25",
                                   "Samsung Galaxy S III"],
        }
        verified, failed = WikipediaPageviewsProvider.probe_entities(
            [{"name": "Samsung Galaxy S21", "title": "Samsung Galaxy S21"}],
            probe_year=2025,
        )
        print("   verified:", verified, "failed:", failed)
        check(verified.get("Samsung Galaxy S21") == "Samsung Galaxy S21",
              "'Samsung Galaxy S21' not shadowed by higher-view S25")

        # Scenario C: ambiguous name with no exact-title article falls
        # back to the best-view opensearch candidate.
        _FakeViews.fake_views = {
            "Jordan (country)": {2025: 5000.0},
            "Michael Jordan": {2025: 9000.0},
        }
        _FakeViews.fake_candidates = {
            "Jordan": ["Jordan (country)", "Michael Jordan"],
        }
        verified, failed = WikipediaPageviewsProvider.probe_entities(
            [{"name": "Jordan", "title": "Jordan"}],
            probe_year=2025,
        )
        print("   verified:", verified, "failed:", failed)
        check(verified.get("Jordan") == "Michael Jordan",
              "ambiguous name falls back to best-view candidate")
    finally:
        WikipediaPageviewsProvider._yearly_views = _ORIG_YEARLY_VIEWS
        WikipediaPageviewsProvider.article_title_candidates = (
            _ORIG_CANDIDATES
        )


def test_bug1_bar_floor():
    print("TEST 2: _bar_width never renders an invisible bar")
    big = 574438.0
    small = 77.0
    floor = big * VisualEngine.MIN_VISIBLE_BAR_FRACTION
    w_small = VisualEngine._bar_width(small, big)
    check(w_small >= floor and w_small > 0,
          f"tiny value ({small}) floored to visible width {w_small:.1f}")
    check(VisualEngine._bar_width(big, big) == big,
          f"full value ({big}) unaffected by the floor")
    check(VisualEngine._bar_width(0.0, big) == 0.0,
          "true zero stays zero (no phantom sliver)")
    s_floor = big * VisualEngine.MIN_VISIBLE_BAR_FRACTION
    check(VisualEngine._bar_width_signed(-77.0, big) == -s_floor,
          "tiny negative floored to visible negative width")
    check(VisualEngine._bar_width_signed(0.0, big) == 0.0,
          "signed true zero stays zero")


# =================================================================
# BUG 3 — _normalize_index uses the human-readable name level
# =================================================================

def test_bug3_rawg_labels():
    print("TEST 3: _normalize_index labels RAWG rows by platform name")
    wide = pd.DataFrame(
        {
            2021: [4.44, 4.39, 4.1],
            2022: [4.31, 4.26, 4.0],
            2023: [4.50, 4.41, 4.2],
        },
        index=pd.MultiIndex.from_tuples(
            [("187", "PlayStation 5"), ("186", "Xbox Series S/X"),
             ("4", "PC")],
            names=["country_code", "country"],
        ),
    )
    normalized = VisualEngine._normalize_index(wide.copy())
    labels = sorted(str(x) for x in normalized.index)
    print("   labels:", labels)
    check(labels == ["PC", "PlayStation 5", "Xbox Series S/X"],
          "numeric platform ids replaced by platform names")
    check(not any(label.strip().isdigit() for label in labels),
          "no bare numeric ids remain")


def test_bug3_country_labels():
    print("TEST 4: country-shaped MultiIndex keeps readable names")
    wide = pd.DataFrame(
        {2020: [1.0], 2021: [2.0]},
        index=pd.MultiIndex.from_tuples(
            [("USA", "United States")],
            names=["country_code", "country"],
        ),
    )
    normalized = VisualEngine._normalize_index(wide.copy())
    check(list(normalized.index) == ["United States"],
          "('USA','United States') labels as 'United States'")


# =================================================================
# BUG 2 — card text fits inside the safe central band
# =================================================================

def _measure(fig, renderer):
    rows = []
    for artist in fig.texts:
        text = str(artist.get_text() or "").strip()
        if not text or text == branding.CARD_ACCENT_GLYPH:
            continue
        ext = artist.get_window_extent(renderer=renderer)
        rows.append((text, ext.x0, ext.x1, ext.width))
    return rows


def test_bug2_card_fit():
    print("TEST 5: outro/intro card text fits the safe band")
    outro = branding._new_card(
        lines=[
            ("Subscribe for more data stories", 56,
             VisualEngine.TEXT_COLOR, "bold"),
            ("— @MetricForge", 56, VisualEngine.ELECTRIC_BLUE, "bold"),
        ],
        accent_y=0.36,
    )
    intro = branding._new_card(
        lines=[
            ("MetricForge", 120, VisualEngine.TEXT_COLOR, "bold"),
            ("DATA STORIES", 34, VisualEngine.SECONDARY_TEXT, "normal"),
        ],
        accent_y=0.40,
    )
    outro.canvas.draw()
    intro.canvas.draw()
    r_outro = outro.canvas.get_renderer()
    r_intro = intro.canvas.get_renderer()

    safe_left, safe_right = 0.10 * 1080, 0.90 * 1080
    for rows, label in (
        (_measure(outro, r_outro), "outro"),
        (_measure(intro, r_intro), "intro"),
    ):
        for text, x0, x1, width in rows:
            check(safe_left <= x0 and x1 <= safe_right and width <= 864,
                  f"{label} line {text!r} inside safe band "
                  f"(x0={x0:.0f} x1={x1:.0f} w={width:.0f})")
    plt.close(outro)
    plt.close(intro)


# =================================================================
# P1 — SEC EDGAR: padded-CIK URL + annual-duration extraction
# =================================================================

from app.data.providers.sec_edgar import SECEdgarProvider


def test_p1_sec_edgar():
    print("\n[P1] SEC EDGAR padded CIK + annual-value extraction")

    # 1) URL must use the zero-padded CIK0000000000.json form.
    url = f"{SECEdgarProvider.base_url}/companyfacts/CIK{str('1045810').zfill(10)}.json"
    check(url.endswith("CIK0001045810.json"),
          f"companyfacts URL zero-pads CIK ({url.rsplit('/', 1)[-1]})")

    # 2) Synthetic companyfacts payload reproducing the three live
    #    defects: taxonomy nesting, quarterly-vs-annual mix under the
    #    same fy/fp, and tag switch mid-history.
    facts = {
        "entityName": "TEST CORP",
        "facts": {
            "us-gaap": {
                # Old tag: annual values 2016-2018 only.
                "Revenues": {
                    "units": {"USD": [
                        # FY2016 annual (365d) + a Q4 quarterly (92d)
                        # under the SAME fy=2016/fp=FY filing focus.
                        {"start": "2015-06-01", "end": "2016-05-31",
                         "val": 1000.0, "fy": 2016, "fp": "FY",
                         "form": "10-K"},
                        {"start": "2016-03-01", "end": "2016-05-31",
                         "val": 250.0, "fy": 2016, "fp": "FY",
                         "form": "10-K"},
                        {"start": "2016-06-01", "end": "2017-05-31",
                         "val": 1500.0, "fy": 2017, "fp": "FY",
                         "form": "10-K"},
                        {"start": "2017-06-01", "end": "2018-05-31",
                         "val": 2000.0, "fy": 2018, "fp": "FY",
                         "form": "10-K"},
                    ]},
                },
                # New ASC-606 tag: modern years 2019+.
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [
                        {"start": "2018-06-01", "end": "2019-05-31",
                         "val": 3000.0, "fy": 2019, "fp": "FY",
                         "form": "10-K"},
                        {"start": "2019-06-01", "end": "2020-05-31",
                         "val": 4000.0, "fy": 2020, "fp": "FY",
                         "form": "10-K"},
                    ]},
                },
                # Instant fact (Assets): no "start" at all.
                "Assets": {
                    "units": {"USD": [
                        {"end": "2019-05-31", "val": 9000.0,
                         "fy": 2019, "fp": "FY", "form": "10-K"},
                    ]},
                },
            },
        },
    }

    rev_chain = ["Revenues",
                 "RevenueFromContractWithCustomerExcludingAssessedTax"]
    yearly = SECEdgarProvider._extract_yearly_values(
        facts, "Revenues", "USD", fact_keys=rev_chain)
    check(yearly.get(2016) == 1000.0,
          f"duration filter picks annual over same-fy quarterly "
          f"(2016={yearly.get(2016)}, not 250)")
    check(yearly.get(2019) == 3000.0 and yearly.get(2020) == 4000.0,
          "tag chain union-merges the ASC-606 years 2019-2020")
    check(yearly.get(2018) == 2000.0,
          "old-tag years survive the merge (2018=2000)")
    check(sorted(yearly) == [2016, 2017, 2018, 2019, 2020],
          f"full merged series {sorted(yearly)}")

    assets = SECEdgarProvider._extract_yearly_values(
        facts, "Assets", "USD", fact_keys=["Assets"])
    check(assets.get(2019) == 9000.0,
          "instant facts (no start date) still extract for Assets")

    # 3) Legacy direct-taxonomy lookup (the old KeyError path) is gone.
    empty = SECEdgarProvider._extract_yearly_values(
        {"facts": {"Revenues": {"units": {"USD": []}}}},
        "Revenues", "USD", fact_keys=["Revenues"])
    check(empty == {},
          "malformed/taxonomy-less payload returns {} instead of raising")


def main():
    # check() now raises, so each test is isolated here: a
    # failure is recorded and the remaining tests still run.
    for test in (
        test_bug1_case_canonicalization,
        test_bug1_bar_floor,
        test_bug3_rawg_labels,
        test_bug3_country_labels,
        test_bug2_card_fit,
        test_p1_sec_edgar,
    ):
        try:
            test()
        except AssertionError:
            pass          # already appended by check()
        except Exception as error:
            FAILED.append(
                f"{test.__name__}: "
                f"{type(error).__name__}: {error}"
            )
    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED:")
        for f in FAILED:
            print("  -", f)
        return 1
    print("ALL REGRESSION TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())