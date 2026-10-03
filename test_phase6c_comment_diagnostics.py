#!/usr/bin/env python3
"""
Phase 6C Test - Comment Visibility Verification + Experimental Auto-Pin

Covers the "comment not shown / not pinned" failure modes,
fully offline:

1. Pre-flight scope gate blocks posting before any API call
   when the OAuth token lacks youtube.force-ssl
2. _verify_comment_visible locates our comment in each
   moderation bucket (published / heldForReview / likelySpam /
   NOT_FOUND)
3. Experimental auto-pin is OFF by default and never touches
   the network unless AUTO_PIN_INTERNAL_API=true
4. When enabled, pin request hits the internal creator endpoint
   with Bearer auth + PIN_COMMENT action; HTTP failures degrade
   into notes
5. Full post flow reports moderation_status end-to-end
6. --doctor verdict logic (healthy video, held comments)
"""

import os
import sys
import types

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

import app.youtube.comments as comments_module

from app.youtube.comments import CommentEngine, run_doctor


# ---------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------

class FakeResponse:

    def __init__(self, status_code=200, text=""):

        self.status_code = status_code

        self.text = text


class FakeYouTube2:
    """
    Supports commentThreads.insert/list AND videos.list so the
    full posting flow and doctor can run without network.
    """

    def __init__(self):

        self.insert_calls = []

        self.list_calls = []

        self.insert_outcome = {"id": "UgxNEWCOMMENT"}

        self.buckets = {
            "published": [],
            "heldForReview": [],
            "likelySpam": [],
        }

        self.video_items = [
            {
                "status": {
                    "privacyStatus": "public",
                    "uploadStatus": "processed",
                    "madeForKids": False,
                },
                "snippet": {},
            }
        ]

    def commentThreads(self):

        return FakeYouTube2._Threads(self)

    def videos(self):

        return FakeYouTube2._Videos(self)

    class _Threads:

        def __init__(self, svc):

            self.svc = svc

        def insert(self, part=None, body=None):

            self.svc.insert_calls.append(
                {"part": part, "body": body}
            )

            return FakeYouTube2._Exe(
                self.svc, "insert"
            )

        def list(self, **kwargs):

            self.svc.list_calls.append(kwargs)

            return FakeYouTube2._Exe(
                self.svc, "thread_list"
            )

    class _Videos:

        def __init__(self, svc):

            self.svc = svc

        def list(self, **kwargs):

            self.svc.list_calls.append(
                {"_videos": kwargs}
            )

            return FakeYouTube2._Exe(
                self.svc, "video_list"
            )

    class _Exe:

        def __init__(self, svc, kind):

            self.svc = svc

            self.kind = kind

        def execute(self):

            if self.kind == "insert":

                outcome = self.svc.insert_outcome

                if isinstance(outcome, Exception):

                    raise outcome

                return dict(outcome)

            if self.kind == "thread_list":

                bucket = (
                    self.svc.list_calls[-1]
                    .get("moderationStatus")
                )

                return {
                    "items": list(
                        self.svc.buckets.get(
                            bucket or "", []
                        )
                    )
                }

            return {"items": list(self.svc.video_items)}


def test_preflight_scope_gate():
    """Missing force-ssl locally -> blocked BEFORE any API call."""

    print("=" * 70)
    print("TEST 1: Pre-flight scope gate")
    print("=" * 70)

    original = CommentEngine.token_has_force_ssl

    CommentEngine.token_has_force_ssl = (
        staticmethod(lambda: False)
    )

    try:

        fake = FakeYouTube2()

        result = CommentEngine.post_question_comment(
            video_id="vid123",
            topic_data={},
            youtube=None,  # forces the pre-flight path
        )

        # Fake service untouched AND authenticate never ran
        # (it would have raised -- credentials file is real).
        assert fake.insert_calls == []

        assert result["posted"] is False

        assert "SCOPE_MISSING" in result["note"]

        assert "--reauth" in result["note"]

    finally:

        CommentEngine.token_has_force_ssl = original

    print("ok - scope-less token stopped pre-network")
    return True


def test_verify_buckets():
    """Our comment id is located in each moderation bucket."""

    print("\n" + "=" * 70)
    print("TEST 2: Visibility buckets")
    print("=" * 70)

    for expected in (
        "published",
        "heldForReview",
        "likelySpam",
    ):

        fake = FakeYouTube2()

        fake.buckets[expected].append(
            {"id": "UgxTARGET"}
        )

        status = (
            CommentEngine._verify_comment_visible(
                fake,
                "vid123",
                "UgxTARGET",
            )
        )

        assert status == expected, (
            f"expected {expected}, got {status}"
        )

    # Absent everywhere -> NOT_FOUND (indexing lag).
    fake = FakeYouTube2()

    status = CommentEngine._verify_comment_visible(
        fake, "vid123", "UgxMISSING"
    )

    assert status == "NOT_FOUND"

    print("ok - published/held/spam/NOT_FOUND all detected")
    return True


def test_pin_disabled_by_default():
    """No env flag -> no network call, clear disabled note."""

    print("\n" + "=" * 70)
    print("TEST 3: Auto-pin OFF by default")
    print("=" * 70)

    os.environ.pop("AUTO_PIN_INTERNAL_API", None)

    called = []

    original = comments_module.requests.post

    comments_module.requests.post = (
        lambda *a, **k: called.append(1)
    )

    try:

        result = (
            CommentEngine._attempt_experimental_pin(
                "vid123",
                "UgxX",
            )
        )

        assert result["pinned"] is False
        assert result["pin_note"] == (
            "INTERNAL_API_DISABLED"
        )
        assert called == [], "network call leaked!"

    finally:

        comments_module.requests.post = original

    print("ok - disabled by default; zero network calls")
    return True


def test_pin_enabled_payload_and_success():
    """AUTO_PIN_INTERNAL_API=true -> Bearer + PIN_COMMENT."""

    print("\n" + "=" * 70)
    print("TEST 4: Experimental pin payload (opt-in)")
    print("=" * 70)

    os.environ["AUTO_PIN_INTERNAL_API"] = "true"

    captured = {}

    class FakeResp:

        status_code = 200

        text = "{}"

    def fake_post(url, json=None, headers=None,
                  timeout=None):

        captured["url"] = url

        captured["json"] = json

        captured["headers"] = headers

        return FakeResp()

    orig_post = comments_module.requests.post

    orig_creds = CommentEngine._load_credentials

    comments_module.requests.post = fake_post

    CommentEngine._load_credentials = staticmethod(
        lambda: types.SimpleNamespace(token="TOK123")
    )

    try:

        result = (
            CommentEngine._attempt_experimental_pin(
                "vid123",
                "UgxPINME",
            )
        )

        assert result["pinned"] is True

        assert "perform_comment_action" in (
            captured["url"]
        )

        assert captured["headers"][
            "Authorization"
        ] == "Bearer TOK123"

        action = captured["json"]["actions"][0]

        assert action["action"] == "PIN_COMMENT"

        assert action["commentId"] == "UgxPINME"

    finally:

        comments_module.requests.post = orig_post

        CommentEngine._load_credentials = orig_creds

        os.environ.pop(
            "AUTO_PIN_INTERNAL_API", None
        )

    print("ok - correct endpoint, bearer, PIN_COMMENT body")
    return True


def test_pin_http_failure_degrades():
    """Non-200 from internal endpoint -> note, pinned False."""

    print("\n" + "=" * 70)
    print("TEST 5: Pin HTTP failure contained")
    print("=" * 70)

    os.environ["AUTO_PIN_INTERNAL_API"] = "true"

    class BadResp:

        status_code = 404

        text = "endpoint moved"

    orig_post = comments_module.requests.post

    orig_creds = CommentEngine._load_credentials

    comments_module.requests.post = (
        lambda *a, **k: BadResp()
    )

    CommentEngine._load_credentials = staticmethod(
        lambda: types.SimpleNamespace(token="TOK123")
    )

    try:

        result = (
            CommentEngine._attempt_experimental_pin(
                "vid123",
                "UgxX",
            )
        )

        assert result["pinned"] is False

        assert result["pin_note"].startswith(
            "PIN_HTTP_404"
        )

    finally:

        comments_module.requests.post = orig_post

        CommentEngine._load_credentials = orig_creds

        os.environ.pop(
            "AUTO_PIN_INTERNAL_API", None
        )

    print("ok - failure surfaced as PIN_HTTP_404 note")
    return True

def test_post_flow_reports_moderation():
    """Full flow: posted -> moderation_status surfaced."""

    print("\n" + "=" * 70)
    print("TEST 6: End-to-end posting with verification")
    print("=" * 70)

    fake = FakeYouTube2()

    result = CommentEngine.post_question_comment(
        video_id="vid123",
        topic_data={},
        youtube=fake,
    )

    assert result["posted"] is True

    assert result["comment_id"] == "UgxNEWCOMMENT"

    assert result["moderation_status"] == "NOT_FOUND"

    # Internal pin API disabled by default -> guided fallback.
    assert result["pinned"] is False

    assert "PIN_MANUAL" in result["note"]

    assert len(fake.insert_calls) == 1

    print("ok - flow reports moderation status + pin fallback")
    return True


def test_doctor_healthy_and_held():
    """Doctor returns True when healthy, flags held comments."""

    print("\n" + "=" * 70)
    print("TEST 7: Doctor verdicts")
    print("=" * 70)

    orig_scope = CommentEngine.token_has_force_ssl

    CommentEngine.token_has_force_ssl = staticmethod(
        lambda: True
    )

    try:

        healthy_fake = FakeYouTube2()

        assert run_doctor(
            "vidOK", youtube=healthy_fake
        ) is True

        held_fake = FakeYouTube2()

        held_fake.buckets["heldForReview"].append(
            {"id": "UgxHELD"}
        )

        assert run_doctor(
            "vidHELD", youtube=held_fake
        ) is False

    finally:

        CommentEngine.token_has_force_ssl = orig_scope

    print("ok - healthy=True; held-for-review=False")
    return True


def test_posted_state_idempotency():
    """Ledger records once; already_posted flips per video."""

    print("\n" + "=" * 70)
    print("TEST 8: Posted-state ledger")
    print("=" * 70)

    import json
    import tempfile

    orig_path = comments_module.POSTED_STATE_PATH

    tmp = tempfile.mkdtemp()

    comments_module.POSTED_STATE_PATH = os.path.join(
        tmp, "posted.json"
    )

    try:

        assert (
            CommentEngine.already_posted("vidX")
            is False
        )

        comments_module._record_posted(
            "vidX", "Ugx1", "Question here?"
        )

        assert (
            CommentEngine.already_posted("vidX")
            is True
        )

        assert (
            CommentEngine.already_posted("vidY")
            is False
        )

        with open(
            comments_module.POSTED_STATE_PATH,
            encoding="utf-8",
        ) as handle:

            state = json.load(handle)

        assert state["vidX"]["comment_id"] == "Ugx1"

        assert state["vidX"]["text"].endswith("?")

        assert "posted_at" in state["vidX"]

    finally:

        comments_module.POSTED_STATE_PATH = orig_path

    print("ok - ledger persists; per-video skip works")
    return True


def test_post_recent_batch():
    """Batch posts once per video; re-run skips everything."""

    print("\n" + "=" * 70)
    print("TEST 9: post_recent batch + skip on re-run")
    print("=" * 70)

    import tempfile

    os.environ.pop("AUTO_PIN_INTERNAL_API", None)

    fake = FakeYouTube2()

    orig_path = comments_module.POSTED_STATE_PATH

    tmp = tempfile.mkdtemp()

    comments_module.POSTED_STATE_PATH = os.path.join(
        tmp, "posted.json"
    )

    try:

        rows = [
            ("vidNEW1", "Title One"),
            ("vidNEW2", "Title Two"),
        ]

        results = comments_module.post_recent(
            count=2, youtube=fake, rows=rows
        )

        assert len(results) == 2

        assert all(
            s == "posted" for _, s in results
        )

        assert len(fake.insert_calls) == 2

        # Re-run: ledger must skip BOTH, no new posts.
        results2 = comments_module.post_recent(
            count=2, youtube=fake, rows=rows
        )

        assert all(
            s == "skipped" for _, s in results2
        )

        assert len(fake.insert_calls) == 2

    finally:

        comments_module.POSTED_STATE_PATH = orig_path

    print("ok - 2 posted first run; 2 skipped on re-run")
    return True


# ---------------------------------------------------------------
# RUNNER (repo convention: standalone script + exit code)
# ---------------------------------------------------------------

def main():

    print("\n")
    print("*" * 70)
    print("PHASE 6C TESTS -- VISIBILITY VERIFY + AUTO-PIN + DOCTOR")
    print("*" * 70)

    all_tests = [
        ("PREFLIGHT_SCOPE", test_preflight_scope_gate),
        ("VERIFY_BUCKETS", test_verify_buckets),
        ("PIN_DISABLED_DEFAULT", test_pin_disabled_by_default),
        ("PIN_PAYLOAD_OPTIN",
         test_pin_enabled_payload_and_success),
        ("PIN_HTTP_FAILURE", test_pin_http_failure_degrades),
        ("FLOW_MODERATION",
         test_post_flow_reports_moderation),
        ("DOCTOR_VERDICTS", test_doctor_healthy_and_held),
        ("POSTED_STATE", test_posted_state_idempotency),
        ("POST_RECENT_BATCH", test_post_recent_batch),
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
        print("\n✅ ALL PHASE 6C DIAGNOSTIC TESTS PASSED")
        return True

    print("\n❌ SOME TESTS FAILED")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)



