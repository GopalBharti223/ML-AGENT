"""Year-label coercion shared by rendering, saving, and prompts.

Wide-frame column labels are normally plain integer years, but
sports/season datasets can legitimately arrive with SEASON labels
("2024-25", "2024/25", "2025-26 (in progress)") and the World Bank
family has always carried the "YR" form ("2016YR").  The renderer,
database save, and LLM prompts all need a numeric year from those
labels; before this helper each site parsed them differently
(and some crashed or leaked raw labels -- see the Tier-3c fixes).
"""
import re

_FOUR_DIGIT = re.compile(r"\d{4}")

_PLAUSIBLE_YEAR_MIN = 1900
_PLAUSIBLE_YEAR_MAX = 2100


def coerce_year_label(label):
    """Best-effort numeric year from a wide-frame column label.

    Accepts:
      - plain numbers:        2016, 2016.0
      - World Bank form:      "2016YR"
      - plain year strings:   "2016"
      - season labels:        "2024-25", "2024/25",
                              "2025-26 (in progress)"

    Returns the STARTING year of the label as an int (a season
    label "2024-25" -> 2024, which keeps chronological ordering
    stable) or None when no plausible year is present.  Callers
    treat None as "not a year column" and skip it.
    """
    if label is None:
        return None

    # Fast path: already numeric (pandas int columns).
    if isinstance(label, (int, float)) and not isinstance(
        label, bool
    ):
        try:
            year = int(label)
        except (ValueError, OverflowError):
            return None
        if (
            _PLAUSIBLE_YEAR_MIN
            <= year
            <= _PLAUSIBLE_YEAR_MAX
        ):
            return year
        return None

    text = str(label).strip()

    if not text:
        return None

    # World Bank "YR" form: identical to the historical
    # renderer behavior (int(str(col).replace("YR", ""))).
    stripped = text.replace("YR", "").strip()

    if stripped.isdigit():
        year = int(stripped)
        if (
            _PLAUSIBLE_YEAR_MIN
            <= year
            <= _PLAUSIBLE_YEAR_MAX
        ):
            return year
        return None

    # Season labels: the first plausible 4-digit year wins
    # ("2024-25" -> 2024, "2024/25" -> 2024,
    #  "2025-26 (in progress)" -> 2025).
    match = _FOUR_DIGIT.search(stripped)

    if match:
        year = int(match.group())
        if (
            _PLAUSIBLE_YEAR_MIN
            <= year
            <= _PLAUSIBLE_YEAR_MAX
        ):
            return year

    return None
