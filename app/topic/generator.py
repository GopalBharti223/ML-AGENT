import json
import random
import re

from app.config import settings
from app.database import db


class TopicEngine:

    # =========================================================
    # STORY TYPES
    # =========================================================

    STORY_TYPES = [
        "fastest_growth",
        "biggest_jump",
        "most_declined",
        "fastest_decline",
    ]

    # =========================================================
    # SAFE WORLD BANK TOPICS
    # =========================================================

    TOPIC_POOL = [

        {
            "topic": "Internet Users Rise",
            "indicator_code": "IT.NET.USER.ZS",
            "story_type": "fastest_growth",
            "years": 20,
            "category": "Technology",
        },

        {
            "topic": "Internet Leaders Rise",
            "indicator_code": "IT.NET.USER.ZS",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Technology",
        },

        {
            "topic": "Internet Adoption Declines",
            "indicator_code": "IT.NET.USER.ZS",
            "story_type": "most_declined",
            "years": 15,
            "category": "Technology",
        },

        {
            "topic": "GDP Giants Rise Again",
            "indicator_code": "NY.GDP.MKTP.CD",
            "story_type": "fastest_growth",
            "years": 20,
            "category": "Economy",
        },

        {
            "topic": "GDP Giants Make a Jump",
            "indicator_code": "NY.GDP.MKTP.CD",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Economy",
        },

        {
            "topic": "GDP Growth Leaders",
            "indicator_code": "NY.GDP.PCAP.CD",
            "story_type": "fastest_growth",
            "years": 15,
            "category": "Economy",
        },

        {
            "topic": "Population Growth Leaders",
            "indicator_code": "SP.POP.TOTL",
            "story_type": "fastest_growth",
            "years": 20,
            "category": "Population",
        },

        {
            "topic": "Population Giants",
            "indicator_code": "SP.POP.TOTL",
            "story_type": "biggest_jump",
            "years": 20,
            "category": "Population",
        },

        {
            "topic": "Urbanization Leaders",
            "indicator_code": "SP.URB.TOTL.IN.ZS",
            "story_type": "biggest_jump",
            "years": 20,
            "category": "Society",
        },

        {
            "topic": "Electricity Access Takes Off",
            "indicator_code": "EG.ELC.ACCS.ZS",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Development",
        },

        {
            "topic": "Life Expectancy Changes",
            "indicator_code": "SP.DYN.LE00.IN",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Health",
        },

        {
            "topic": "Life Expectancy Leaders",
            "indicator_code": "SP.DYN.LE00.IN",
            "story_type": "fastest_growth",
            "years": 15,
            "category": "Health",
        },

        {
            "topic": "Military Spending Changes",
            "indicator_code": "MS.MIL.XPND.GD.ZS",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Economy",
        },

        {
            "topic": "Education Spending Changes",
            "indicator_code": "SE.XPD.TOTL.GD.ZS",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Education",
        },

        {
            "topic": "Health Spending Changes",
            "indicator_code": "SH.XPD.CHEX.GD.ZS",
            "story_type": "biggest_jump",
            "years": 15,
            "category": "Health",
        },
    ]

    # =========================================================
    # NORMALIZE STORY TYPE
    # =========================================================

    @classmethod
    def normalize_story_type(
        cls,
        story_type
    ):

        if not story_type:

            return "fastest_growth"

        story_type = str(
            story_type
        ).strip().lower()

        aliases = {

            "fastest-growth":
                "fastest_growth",

            "fastest growth":
                "fastest_growth",

            "biggest-jump":
                "biggest_jump",

            "biggest jump":
                "biggest_jump",

            "most-declined":
                "most_declined",

            "most declined":
                "most_declined",

            "fastest-decline":
                "fastest_decline",

            "fastest decline":
                "fastest_decline",
        }

        story_type = aliases.get(
            story_type,
            story_type
        )

        if story_type not in cls.STORY_TYPES:

            return "fastest_growth"

        return story_type

    # =========================================================
    # GET RECENT CONTENT
    # =========================================================

    @classmethod
    def _get_recent_history(cls):

        recent = []

        # -----------------------------------------------------
        # Try common database history interfaces.
        # -----------------------------------------------------

        try:

            if hasattr(
                db,
                "get_recent_records"
            ):

                records = (
                    db.get_recent_records(
                        limit=100
                    )
                )

                if records:

                    recent.extend(
                        records
                    )

        except Exception:

            pass

        return recent

    # =========================================================
    # EXTRACT HISTORY PAIRS
    # =========================================================

    @classmethod
    def _history_pairs(cls):

        pairs = set()

        records = cls._get_recent_history()

        for record in records:

            if not isinstance(
                record,
                dict
            ):

                continue

            indicator = record.get(
                "indicator_code"
            )

            story = record.get(
                "story_type"
            )

            if indicator and story:

                pairs.add(
                    (
                        str(indicator),
                        cls.normalize_story_type(
                            story
                        )
                    )
                )

        return pairs

    # =========================================================
    # CHECK DUPLICATE TOPICS
    # =========================================================

    @classmethod
    def _topic_already_used(
        cls,
        topic
    ):

        topic_name = (
            topic.get("topic", "")
            .strip()
            .lower()
        )

        records = cls._get_recent_history()

        for record in records:

            if not isinstance(
                record,
                dict
            ):

                continue

            old_topic = record.get(
                "topic"
            )

            if not old_topic:

                old_topic = record.get(
                    "title"
                )

            if not old_topic:

                continue

            if (
                str(old_topic)
                .strip()
                .lower()
                == topic_name
            ):

                return True

        return False

    # =========================================================
    # CREATE DYNAMIC TOPIC
    # =========================================================

    @classmethod
    def _dynamic_topic(
        cls,
        base
    ):

        indicator = base[
            "indicator_code"
        ]

        story_type = cls.normalize_story_type(
            base.get(
                "story_type"
            )
        )

        years = base.get(
            "years",
            15
        )

        category = base.get(
            "category",
            "Economy"
        )

        topic_name = base[
            "topic"
        ]

        # -----------------------------------------------------
        # Dynamic variations
        # -----------------------------------------------------

        variations = {

            "fastest_growth": [
                f"{topic_name}: Fastest Rising Countries",
                f"{topic_name}: Countries Pulling Ahead",
                f"{topic_name}: Global Leaders on the Rise",
            ],

            "biggest_jump": [
                f"{topic_name}: Biggest Jumps",
                f"{topic_name}: Countries Making the Biggest Leap",
                f"{topic_name}: Sudden Global Climbers",
            ],

            "most_declined": [
                f"{topic_name}: Biggest Declines",
                f"{topic_name}: Countries Falling Behind",
                f"{topic_name}: Where the Numbers Fell",
            ],

            "fastest_decline": [
                f"{topic_name}: Fastest Declines",
                f"{topic_name}: Countries Losing Ground",
                f"{topic_name}: Sharpest Drops",
            ],
        }

        choices = variations.get(
            story_type,
            variations[
                "fastest_growth"
            ]
        )

        generated_name = random.choice(
            choices
        )

        return {
            "topic": generated_name,

            "indicator_code":
                indicator,

            "story_type":
                story_type,

            "years":
                int(years),

            "category":
                category,
        }

    # =========================================================
    # GENERATE TOPIC
    # =========================================================

    @classmethod
    def generate_topic(
        cls,
        max_attempts=8
    ):

        print(
            "\n🧠 Generating topic..."
        )

        history_pairs = (
            cls._history_pairs()
        )

        # -----------------------------------------------------
        # Shuffle pool so repeated runs aren't deterministic.
        # -----------------------------------------------------

        candidates = list(
            cls.TOPIC_POOL
        )

        random.shuffle(
            candidates
        )

        # -----------------------------------------------------
        # Attempt selection
        # -----------------------------------------------------

        for attempt in range(
            1,
            max_attempts + 1
        ):

            print(
                f"\n🧠 Generating topic "
                f"(attempt {attempt}/{max_attempts})..."
            )

            if not candidates:

                candidates = list(
                    cls.TOPIC_POOL
                )

                random.shuffle(
                    candidates
                )

            base = candidates.pop()

            indicator = base[
                "indicator_code"
            ]

            story_type = cls.normalize_story_type(
                base.get(
                    "story_type"
                )
            )

            # -------------------------------------------------
            # Avoid recently used indicator/story combinations
            # -------------------------------------------------

            if (
                indicator,
                story_type
            ) in history_pairs:

                print(
                    "⚠️ Story type recently used "
                    "for this indicator:"
                )

                print(
                    f"   {indicator} / "
                    f"{story_type}"
                )

                continue

            # -------------------------------------------------
            # Create dynamic variation
            # -------------------------------------------------

            topic = cls._dynamic_topic(
                base
            )

            # -------------------------------------------------
            # Duplicate topic check
            # -------------------------------------------------

            if cls._topic_already_used(
                topic
            ):

                print(
                    f"⚠️ Topic already exists: "
                    f"{topic['topic']}"
                )

                continue

            # -------------------------------------------------
            # FINAL NORMALIZATION
            # -------------------------------------------------

            topic["story_type"] = (
                cls.normalize_story_type(
                    topic["story_type"]
                )
            )

            try:

                topic["years"] = int(
                    topic["years"]
                )

            except (
                ValueError,
                TypeError
            ):

                topic["years"] = 15

            # -------------------------------------------------
            # Print final topic
            # -------------------------------------------------

            print(
                "\n🎯 NEW TOPIC SELECTED"
            )

            print(
                f"Topic: "
                f"{topic['topic']}"
            )

            print(
                f"Indicator: "
                f"{topic['indicator_code']}"
            )

            print(
                f"Story type: "
                f"{topic['story_type']}"
            )

            print(
                f"Years: "
                f"{topic['years']}"
            )

            return topic

        # =====================================================
        # FALLBACK
        # =====================================================

        print(
            "\n⚠️ Could not find a completely unused "
            "topic combination."
        )

        # Pick a random safe topic.
        fallback = random.choice(
            cls.TOPIC_POOL
        ).copy()

        fallback["story_type"] = (
            cls.normalize_story_type(
                fallback.get(
                    "story_type"
                )
            )
        )

        print(
            "\n🎯 FALLBACK TOPIC SELECTED"
        )

        print(
            f"Topic: "
            f"{fallback['topic']}"
        )

        print(
            f"Indicator: "
            f"{fallback['indicator_code']}"
        )

        print(
            f"Story type: "
            f"{fallback['story_type']}"
        )

        print(
            f"Years: "
            f"{fallback['years']}"
        )

        return fallback