"""Season-label safety tests (Tier 3c).

The renderer, database save, and LLM-prompt paths previously
assumed plain integer year columns.  Season-label datasets
("2024-25", "2024/25", "2025-26 (in progress)") used to crash the
renderer ("No valid year columns found"), silently skip the
database record (int() ValueError), and leak raw labels into LLM
prompts and YouTube titles.  These tests pin the sanitized
behavior.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

import pandas as pd

from app.time_labels import coerce_year_label
from app.visuals.scene_engine import VisualEngine
from app.ai.script import ScriptEngine


def check(name, condition):
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {name}")
    # pytest DISCARDS a test's return value, so relying on
    # `ok &= check(...)` / `return ok` means the test is
    # collected, runs, and reports PASS no matter what the
    # condition was.  Raising here is what makes it fail.
    assert condition, name
    return True


def test_coerce_year_label():
    print("\nTEST 1: coerce_year_label forms")
    ok = True
    ok &= check("plain int", coerce_year_label(2016) == 2016)
    ok &= check("float column", coerce_year_label(2016.0) == 2016)
    ok &= check("plain string", coerce_year_label("2016") == 2016)
    ok &= check("YR form", coerce_year_label("2016YR") == 2016)
    ok &= check("season dash", coerce_year_label("2024-25") == 2024)
    ok &= check("season slash", coerce_year_label("2024/25") == 2024)
    ok &= check(
        "in progress",
        coerce_year_label("2025-26 (in progress)") == 2025,
    )
    ok &= check("junk -> None", coerce_year_label("Population") is None)
    ok &= check("empty -> None", coerce_year_label("") is None)
    ok &= check("none -> None", coerce_year_label(None) is None)
    ok &= check(
        "absurd year -> None", coerce_year_label("99999") is None
    )
    return ok


def test_render_bar_race_season_columns():
    print("\nTEST 2: render_bar_race data prep handles season labels")
    frame = pd.DataFrame(
        {
            "2023-24": [10.0, 20.0],
            "2024/25": [11.0, 21.0],
            "2025-26 (in progress)": [12.0, 22.0],
        },
        index=["Alpha", "Beta"],
    )

    # The renderer mutates its own copy; simulate via the same
    # cleaning code path used before animation begins.
    data = frame.copy()
    data = VisualEngine._normalize_index(data)

    valid = []
    seen = set()
    for column in data.columns:
        year = coerce_year_label(column)
        if year is None or year in seen:
            continue
        seen.add(year)
        valid.append((column, year))

    ok = check("3 season labels parsed", len(valid) == 3)
    ok &= check(
        "starting years",
        [year for _, year in valid] == [2023, 2024, 2025],
    )
    return ok


def test_prepare_chart_data_season_columns():
    print("\nTEST 3: _prepare_chart_data accepts season labels")
    frame = pd.DataFrame(
        {
            "2023-24": [10.0, 20.0, 30.0],
            "2024/25": [11.0, 21.0, 31.0],
            "junk": [1.0, 2.0, 3.0],
        },
        index=["Alpha", "Beta", "Gamma"],
    )

    prepared = VisualEngine._prepare_chart_data(frame.copy())
    ok = check(
        "season columns coerced, junk dropped",
        list(prepared.columns) == [2023, 2024],
    )
    return ok


def test_prepare_chart_data_mixed_duplicates():
    print("\nTEST 4: duplicate years keep first occurrence")
    frame = pd.DataFrame(
        {
            "2024": [1.0, 2.0],
            "2024-25": [3.0, 4.0],
            "2025": [5.0, 6.0],
        },
        index=["Alpha", "Beta"],
    )
    prepared = VisualEngine._prepare_chart_data(frame.copy())
    ok = check(
        "duplicate year deduped",
        list(prepared.columns) == [2024, 2025],
    )
    return ok


def test_prepare_chart_data_all_junk_raises():
    print("\nTEST 5: no year columns still fails clearly")
    frame = pd.DataFrame(
        {"junk": [1.0, 2.0], "more junk": [3.0, 4.0]},
        index=["Alpha", "Beta"],
    )
    try:
        VisualEngine._prepare_chart_data(frame.copy())
    except ValueError as error:
        return check(
            "exact error message",
            "No valid year columns found" in str(error),
        )
    raise AssertionError(
        "expected ValueError for an all-junk frame, none raised"
    )


def test_script_data_context_sanitized():
    print("\nTEST 6: script prompt data context never leaks labels")
    frame = pd.DataFrame(
        {
            "2023-24": [10.0, 20.0],
            "2024/25": [11.0, 21.0],
            "2025-26 (in progress)": [12.0, 22.0],
        },
        index=["Alpha", "Beta"],
    )
    context = ScriptEngine._build_data_context(frame)
    ok = check(
        "first year coerced",
        context["first_year"]["year"] == 2023,
    )
    ok &= check(
        "last year coerced",
        context["last_year"]["year"] == 2025,
    )
    ok &= check(
        "rankings still populated",
        context["last_year"]["ranking"] != [],
    )
    return ok


def main():
    tests = [
        test_coerce_year_label,
        test_render_bar_race_season_columns,
        test_prepare_chart_data_season_columns,
        test_prepare_chart_data_mixed_duplicates,
        test_prepare_chart_data_all_junk_raises,
        test_script_data_context_sanitized,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as error:
            print(f"  EXCEPTION: {type(error).__name__}: {error}")
            failed += 1
    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
