#!/usr/bin/env python3
"""
Phase 6B Integration Test - Auto Pinned Question Comment Engine

Verifies (fully offline -- YouTube API is faked):
1. Generated engagement lines are ALWAYS questions ('?'-terminated)
2. Winner/year facts personalize templates (tuple indexes handled)
3. Rotation never repeats back-to-back and produces variety
4. post_question_comment() inserts via commentThreads with correct
   body, reports permalink, keeps pinned=False (API limitation)
5. HTTP 403 (missing force-ssl scope) degrades gracefully with an
   actionable re-auth note instead of crashing
6. Missing video_id short-circuits safely
7. Settings flag AUTO_PIN_COMMENT exists for run.py gating
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.abspath(__file__))
)

for _stream in (sys.stdout, sys.stderr):

    if _stream and hasattr(_stream, "reconfigure"):

        try:

            _stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )

        except (ValueError, OSError):

            pass

from httplib2 import Response as HtResponse

from googleapiclient.errors import HttpError

import pandas as pd

from app.youtube.comments import CommentEngine


# ---------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------

PERSONAL_TOPIC = {
    "topic": "GDP per capita leaders",
    "indicator_name": "GDP per capita",
    "story_metrics": {
        "end_year": 2025,
        "latest_sorted": pd.Series(
            [100.0, 90.0, 80.0],
            index=[
                ("DEU", "Germany"),
                ("FRA", "France"),
                ("ITA", "Italy"),
            ],
        ),
    },
}


class FakeYouTube:
    """Mimics the discovery Resource chain used by the engine."""

    def __init__(self, outcome=None):

        self.outcome = outcome or {"id": "UgxFAKECOMMENT123"}

        self.calls = []

    def commentThreads(self):

        outer = self

        class _Insertable:

            def insert(self, part=None, body=None):

                outer.calls.append(
                    {"part": part, "body": body}
                )

                class _Executable:

                    def execute(self):

                        if isinstance(
                            outer.outcome,
                            Exception,
                        ):

                            raise outer.outcome

                        return dict(outer.outcome)

                return _Executable()

        return _Insertable()


def make_http_error(status):

    return HttpError(
        HtResponse({"status": status}),
        b"simulated api failure",
    )


# ---------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------

def test_always_a_question():
    """Every generated line is non-empty and '?'-terminated."""

    print("=" * 70)
    print("TEST 1: Question form guaranteed")
    print("=" * 70)

    CommentEngine._recent_ids.clear()

    for _ in range(30):

        text = CommentEngine.generate_question_comment(
            PERSONAL_TOPIC
        )

        assert text, "comment must not be empty"
        assert text.endswith("?"), f"not a question: {text}"
        assert not text.endswith(
            ".?"
        ), f"double punctuation: {text}"
        assert not text.endswith(
            "!?"
        ), f"double punctuation: {text}"
        assert len(text) <= 280, f"too long: {text}"

    print("ok - 30/30 generations are proper questions")
    return True


def test_personalization_and_fallback():
    """Winner/year facts personalize; empty data degrades clean."""

    print("\n" + "=" * 70)
    print("TEST 2: Personalization + graceful fallback")
    print("=" * 70)

    CommentEngine._recent_ids.clear()

    seen_winner = False

    for _ in range(40):

        text = CommentEngine.generate_question_comment(
            PERSONAL_TOPIC
        )

        if "Germany" in text:
            seen_winner = True

    assert seen_winner, (
        "expected winner-personalized question within 40 tries"
    )

    # No story data -> generic pool still yields questions.
    CommentEngine._recent_ids.clear()

    for _ in range(10):

        text = CommentEngine.generate_question_comment({})

        assert text.endswith("?")

        assert "Germany" not in text

    print("ok - winner personalizes; missing data falls back clean")
    return True


def test_rotation_no_immediate_repeat():
    """No back-to-back repeats; variety across a run."""

    print("\n" + "=" * 70)
    print("TEST 3: Rotation / anti-repeat")
    print("=" * 70)

    CommentEngine._recent_ids.clear()

    texts = [
        CommentEngine.generate_question_comment(PERSONAL_TOPIC)
        for _ in range(12)
    ]

    for prev, curr in zip(texts, texts[1:]):
        assert prev != curr, f"immediate repeat: {curr}"

    distinct = len(set(texts))

    assert distinct >= 3, f"too little variety: {distinct}"

    print(f"ok - {distinct} distinct lines in 12 draws, "
          f"zero back-to-back repeats")
    return True


def test_post_success_flow():
    """Insert body correct; permalink built; pin guidance surfaced."""

    print("\n" + "=" * 70)
    print("TEST 4: Successful posting flow")
    print("=" * 70)

    fake = FakeYouTube()

    result = CommentEngine.post_question_comment(
        video_id="abc123VIDEO",
        topic_data=PERSONAL_TOPIC,
        youtube=fake,
    )

    assert result["posted"] is True
    assert result["pinned"] is False, "API cannot pin"
    assert result["comment_id"] == "UgxFAKECOMMENT123"
    assert "lc=UgxFAKECOMMENT123" in result["url"]
    assert "abc123VIDEO" in result["url"]
    assert "PIN_MANUAL" in result["note"]

    assert len(fake.calls) == 1

    call = fake.calls[0]

    assert call["part"] == "snippet"

    snippet = call["body"]["snippet"]

    assert snippet["videoId"] == "abc123VIDEO"
    assert snippet["textOriginal"].endswith("?")

    print(f"ok - posted: {snippet['textOriginal']}")
    return True

def test_post_403_degrades_gracefully():
    """Missing force-ssl scope -> actionable note, no crash."""

    print("\n" + "=" * 70)
    print("TEST 5: 403 scope failure handled")
    print("=" * 70)

    fake = FakeYouTube(outcome=make_http_error(403))

    result = CommentEngine.post_question_comment(
        video_id="abc123VIDEO",
        topic_data={},
        youtube=fake,
    )

    assert result["posted"] is False
    assert result["pinned"] is False
    assert result["comment_id"] is None

    note = result["note"]

    assert "FORBIDDEN" in note
    assert "force-ssl" in note
    assert "--reauth" in note

    # Other HTTP errors also stay contained.
    fake2 = FakeYouTube(outcome=make_http_error(500))

    result2 = CommentEngine.post_question_comment(
        video_id="v2",
        topic_data={},
        youtube=fake2,
    )

    assert result2["posted"] is False
    assert result2["note"].startswith("HTTP_")

    print("ok - 403/5xx degrade into notes; pipeline keeps flowing")
    return True


def test_missing_video_id_guard():
    """Empty video id short-circuits without touching the API."""

    print("\n" + "=" * 70)
    print("TEST 6: Missing video_id guard")
    print("=" * 70)

    fake = FakeYouTube()

    result = CommentEngine.post_question_comment(
        video_id=None,
        topic_data={},
        youtube=fake,
    )

    assert result["posted"] is False
    assert result["note"] == "NO_VIDEO_ID"
    assert fake.calls == []

    print("ok - guard trips before any API call")
    return True


def test_settings_flag_exists():
    """run.py gate AUTO_PIN_COMMENT present and boolean."""

    print("\n" + "=" * 70)
    print("TEST 7: Settings flag")
    print("=" * 70)

    from app.config import settings

    assert isinstance(settings.AUTO_PIN_COMMENT, bool)

    print(f"ok - AUTO_PIN_COMMENT = {settings.AUTO_PIN_COMMENT}")
    return True


# ---------------------------------------------------------------
# RUNNER (repo convention: standalone script + exit code)
# ---------------------------------------------------------------

def main():

    print("\n")
    print("*" * 70)
    print("PHASE 6B TESTS -- AUTO PINNED QUESTION COMMENT ENGINE")
    print("*" * 70)

    all_tests = [
        ("ALWAYS_QUESTION", test_always_a_question),
        ("PERSONALIZATION", test_personalization_and_fallback),
        ("ROTATION", test_rotation_no_immediate_repeat),
        ("POST_SUCCESS", test_post_success_flow),
        ("POST_403_GRACEFUL", test_post_403_degrades_gracefully),
        ("NO_VIDEO_ID", test_missing_video_id_guard),
        ("SETTINGS_FLAG", test_settings_flag_exists),
    ]

    results = []

    for name, func in all_tests:

        try:
            passed = func()
            results.append((name, passed))
        except Exception as error:
            print(f"\n✗ EXCEPTION: {error}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        print(f"{'✓ PASS' if ok else '✗ FAIL'}: {name}")

    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n✅ ALL PHASE 6B COMMENT ENGINE TESTS PASSED")
        return True

    print("\n❌ SOME TESTS FAILED")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


