import random

import pandas as pd


class ChartSelector:

    DEFAULT_MAP = {
        "fastest_growth": "top5_change",
        "biggest_decline": "top5_change",
        "rank_climber": "slope",
        "rank_decline": "slope",
        "current_leader": "bar_race",
        "leader_challenge": "bar_race",
        "trend_over_time": "line",
    }

    # =========================================================
    # CHART TYPE DISTRIBUTION
    #
    # The channel wants these chart types with these weights:
    #   - Horizontal Bar Chart Animation : 70%
    #   - Area Chart Animation           : 15%
    #   - Multi-Line Chart Animation     :  5%
    #   - Bubble point graphs            : 10%
    #
    # Horizontal bar charts include both "bar_race" and
    # "top5_change" (both are horizontal bar animations).
    # =========================================================

    CHART_DISTRIBUTION = {
        "bar_race": 0.50,   # Horizontal bar race (part of 70%)
        "top5_change": 0.20,  # Horizontal top-5 change (part of 70%)
        "area": 0.15,        # Area chart animation
        "line": 0.05,        # Multi-line chart animation
        "bubble": 0.10,      # Bubble point graph
        "pie": 0.06,         # Share-of-total donut (Part 1)
        "waffle": 0.06,      # Share-of-total 10x10 icon grid (Part 2)
    }

    # =========================================================
    # PART-OF-WHOLE CHARTS (pie / waffle)  -- Part 1 and Part 2
    #
    # A pie or a 100-box waffle only means something when the
    # numbers are PARTS OF ONE WHOLE.  These charts are therefore
    # gated on the DATA (shares that add up to 100%) and on the
    # ENTITY COUNT, not handed out blindly by weight -- see
    # _eligible_share_charts().
    #
    # VisualEngine.is_share_of_total() enforces the SAME rule at
    # render time (it cannot be bypassed by calling a renderer
    # directly); test_pie_waffle.py asserts the two agree.
    # =========================================================

    SHARE_MIN_ENTITIES = 3
    SHARE_MAX_ENTITIES = 6
    SHARE_TOTAL_TOLERANCE = 2.0

    # Story types whose subject is a comparison of standing, for
    # which a part-of-whole reading is still honest even when the
    # underlying indicator is not itself a percentage.
    SHARE_OF_TOTAL_STORY_TYPES = {
        "current_leader",
        "leader_challenge",
    }

    @classmethod
    def _entity_count(cls, data) -> int:

        if data is None or data.empty:
            return 0

        try:
            return int(len(data.index))
        except Exception:
            return 0

    @classmethod
    def _share_of_total_data(cls, data) -> bool:
        """Part-of-whole test, mirroring
        VisualEngine.is_share_of_total() without importing
        matplotlib.

        The numbers must be non-negative and must SUM TO A WHOLE
        (100 +/- SHARE_TOTAL_TOLERANCE), with the entity count
        inside SHARE_MIN_ENTITIES .. SHARE_MAX_ENTITIES.
        """

        if data is None or data.empty or len(data.columns) == 0:
            return False

        count = cls._entity_count(data)

        if not (
            cls.SHARE_MIN_ENTITIES
            <= count
            <= cls.SHARE_MAX_ENTITIES
        ):
            return False

        try:
            values = pd.to_numeric(
                data[data.columns[-1]],
                errors="coerce",
            ).dropna()
        except Exception:
            return False

        if values.empty:
            return False

        if (values < 0).any():
            return False

        total = float(values.sum())

        if total <= 0:
            return False

        return (
            abs(total - 100.0)
            <= cls.SHARE_TOTAL_TOLERANCE
        )

    @classmethod
    def _eligible_share_charts(
        cls,
        story_type: str,
        data
    ) -> set:
        """Which part-of-whole charts this story/data may use.

          * pie    -- share-of-total data only: a pie that has to
                      invent a total is a lie.
          * waffle -- share-of-total data, OR a
                      current_leader / leader_challenge story
                      (Part 2's explicit window).

        Returns an empty set when neither applies, so the caller
        leaves the distribution untouched.
        """

        if cls._entity_count(data) < cls.SHARE_MIN_ENTITIES:
            return set()

        if cls._entity_count(data) > cls.SHARE_MAX_ENTITIES:
            return set()

        story = str(story_type or "").strip().lower()

        eligible = set()

        if cls._share_of_total_data(data):
            eligible.add("pie")
            eligible.add("waffle")

        if story in cls.SHARE_OF_TOTAL_STORY_TYPES:
            eligible.add("waffle")

        return eligible

    @classmethod
    def supports_bubble(
        cls,
        data: pd.DataFrame
    ) -> bool:

        if data is None or data.empty:
            return False

        columns = {
            str(column).strip().lower(): column
            for column in data.columns
        }

        if "x" not in columns or "y" not in columns:
            return False

        sample = data[
            [
                columns["x"],
                columns["y"],
            ]
        ].copy()

        sample[columns["x"]] = pd.to_numeric(
            sample[columns["x"]],
            errors="coerce"
        )
        sample[columns["y"]] = pd.to_numeric(
            sample[columns["y"]],
            errors="coerce"
        )

        sample = sample.dropna()

        return len(sample) >= 3

    @classmethod
    def select_chart(
        cls,
        story_type: str,
        metrics: dict,
        data: pd.DataFrame = None
    ) -> str:
        """
        Select a chart type using the channel's preferred
        distribution:

          - Horizontal Bar Chart Animation : 70%
          - Area Chart Animation           : 15%
          - Multi-Line Chart Animation     :  5%
          - Bubble point graphs            : 10%

        The selection is weighted-random so the distribution
        holds over many runs while still producing variety.

        Two gates narrow the pool before the roll:

          * bubble needs x/y data (it cannot be drawn without
            genuine multidimensional values);
          * pie / waffle need a part-of-whole reading (see
            _eligible_share_charts) -- a 3-6 entity share test
            that adds up to 100% for pie, and additionally a
            current_leader / leader_challenge story for waffle.
            Pie and waffle are DROPPED for everything else,
            because a pie of absolute GDP has to invent a total
            to fill its wedges.
        """
        distribution = dict(cls.CHART_DISTRIBUTION)

        # Bubble requires x/y data; if not available, remove it
        # rather than forcing a fallback downstream.
        if not cls.supports_bubble(data):
            distribution.pop("bubble", None)

        # Part-of-whole charts are only allowed where they are
        # honest.
        allowed_share = cls._eligible_share_charts(
            story_type,
            data,
        )

        for chart_type in ("pie", "waffle"):

            if chart_type not in allowed_share:
                distribution.pop(chart_type, None)

        chart_types = list(distribution.keys())
        weights = list(distribution.values())

        return random.choices(
            chart_types,
            weights=weights,
            k=1
        )[0]
