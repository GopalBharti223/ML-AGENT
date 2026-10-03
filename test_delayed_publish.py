"""
test_delayed_publish.py — offline validation of the
delayed-publish feature (publish_queue + publish_worker).

Covers:
  1. CHANNEL_TOKEN_MAP parsing (valid / empty / malformed)
  2. publish_queue table creation + idempotent enqueue
  3. due-job query semantics (publish_at <= now)
  4. worker publishes due rows with the right API contract
     (part="status", privacyStatus="public", kids flag kept)
  5. idempotent second run (no double publish, no extra calls)
  6. API failure keeps the row queued with diagnostics, then
     a retry succeeds
  7. unknown channel fails safely without crashing the batch
  8. make_public() body contract (direct call)

Run:  python test_delayed_publish.py
"""

import os
import sys
import tempfile
import logging

# ---------------------------------------------------------
# Isolate the test database + channel token map BEFORE any
# app.* import (settings are read at import time).
# ---------------------------------------------------------

_TMP_DIR = tempfile.mkdtemp(
    prefix="delayed_publish_test_"
)

os.environ["DB_PATH"] = os.path.join(
    _TMP_DIR,
    "test_history.db"
)

os.environ["CHANNEL_TOKEN_MAP"] = (
    "default=tok_default.json;second=tok_second.json"
)

from datetime import datetime, timedelta

from googleapiclient.errors import HttpError

from app.database import Database

import publish_worker

from publish_worker import (
    parse_channel_token_map,
    process_due_jobs,
    make_public,
    PublishAuthError,
)

# Show the worker's own log lines interleaved with checks.

logging.basicConfig(
    level=logging.INFO,
    format="[worker] %(levelname)s %(message)s"
)

_failures = []


def check(
    name,
    condition,
    detail=""
):

    status = "✅" if condition else "❌"

    print(
        f"{status} {name}"
        + (
            f" — {detail}"
            if detail and not condition
            else ""
        )
    )

    if not condition:
        _failures.append(name)


# =========================================================

print("\n[1] CHANNEL_TOKEN_MAP parsing")

token_map = parse_channel_token_map(
    "default=youtube_token.json; second=tok2.json"
)

check(
    "simple map parsed",
    token_map == {
        "default": "youtube_token.json",
        "second": "tok2.json"
    },
    str(token_map)
)

check(
    "empty map -> empty dict",
    parse_channel_token_map("") == {}
)

try:

    parse_channel_token_map("broken-entry")

    check(
        "malformed entry raises ValueError",
        False
    )

except ValueError:

    check(
        "malformed entry raises ValueError",
        True
    )

# =========================================================

print("\n[2] publish_queue table + enqueue idempotency")

database = Database()

tables = {
    row[0]
    for row in database.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
}

check(
    "publish_queue table exists",
    "publish_queue" in tables,
    str(tables)
)

publish_at = (
    datetime.now()
    + timedelta(minutes=15)
)

first = database.enqueue_delayed_publish(
    video_id="vid_queue_1",
    channel="default",
    publish_at=publish_at,
)

check(
    "first enqueue returns True",
    first is True
)

duplicate = database.enqueue_delayed_publish(
    video_id="vid_queue_1",
    channel="default",
    publish_at=publish_at,
)

check(
    "duplicate enqueue is ignored (idempotent)",
    duplicate is False
)

database.enqueue_delayed_publish(
    video_id="vid_queue_2",
    channel="second",
    publish_at=publish_at,
)

# =========================================================

print("\n[3] due-job query")

before = database.get_due_publish_jobs(
    now=publish_at - timedelta(seconds=1)
)

check(
    "nothing due before publish_at",
    len(before) == 0,
    str(before)
)

after = database.get_due_publish_jobs(
    now=publish_at
)

check(
    "both jobs due at publish_at",
    len(after) == 2,
    str(after)
)

check(
    "due rows carry channel info",
    {j["channel"] for j in after} == {"default", "second"}
)

# =========================================================

print("\n[4] worker publishes due rows (fake API)")


class FakeUpdate:

    def __init__(
        self,
        recorder,
        fail_with=None
    ):
        self._recorder = recorder
        self._fail_with = fail_with

    def update(
        self,
        part,
        body
    ):
        self._recorder.append(
            (part, body)
        )

        if self._fail_with is not None:
            raise self._fail_with

        return self

    def execute(self):
        return {}


class FakeYouTube:

    def __init__(
        self,
        recorder,
        fail_with=None
    ):
        self._recorder = recorder
        self._fail_with = fail_with

    def videos(self):
        return FakeUpdate(
            self._recorder,
            self._fail_with
        )


recorder = []

factory_calls = []


def fake_factory(channel):

    factory_calls.append(channel)

    return FakeYouTube(recorder)


published, failed = process_due_jobs(
    database=database,
    token_map=token_map,
    now=publish_at,
    service_factory=fake_factory,
)

check(
    "both videos published",
    (published, failed) == (2, 0),
    f"published={published} failed={failed}"
)

check(
    "one service per channel",
    sorted(factory_calls) == ["default", "second"],
    str(factory_calls)
)

check(
    "two update calls made",
    len(recorder) == 2,
    str(recorder)
)

parts = {
    body["id"]: (part, body)
    for part, body in recorder
}

part, body = parts["vid_queue_1"]

check(
    "update uses part='status'",
    part == "status"
)

check(
    "update sets privacyStatus=public",
    body["status"]["privacyStatus"] == "public"
)

check(
    "update preserves kids declaration",
    body["status"]["selfDeclaredMadeForKids"] is False
)

pending_after = database.get_pending_publish_jobs()

check(
    "queue drained after success",
    len(pending_after) == 0,
    str(pending_after)
)

# =========================================================

print("\n[5] idempotent second run")

published, failed = process_due_jobs(
    database=database,
    token_map=token_map,
    now=publish_at,
    service_factory=fake_factory,
)

check(
    "second run is a no-op",
    (published, failed) == (0, 0)
)

check(
    "no extra API calls",
    len(recorder) == 2,
    str(len(recorder))
)

# =========================================================

print("\n[6] API failure keeps row queued and retries later")

database.enqueue_delayed_publish(
    video_id="vid_quota_1",
    channel="default",
    publish_at=publish_at,
)


class _FakeResp:

    status = 403
    reason = "quotaExceeded"


quota_error = HttpError(
    _FakeResp(),
    (
        b'{"error": {"code": 403, '
        b'"message": "Quota exceeded", '
        b'"errors": [{"reason": "quotaExceeded", '
        b'"message": "Quota exceeded"}]}}'
    ),
)


def failing_factory(channel):

    return FakeYouTube(
        recorder,
        fail_with=quota_error
    )


published, failed = process_due_jobs(
    database=database,
    token_map=token_map,
    now=publish_at,
    service_factory=failing_factory,
)

check(
    "failure counted, not raised",
    (published, failed) == (0, 1),
    f"published={published} failed={failed}"
)

still_pending = database.get_pending_publish_jobs()

matching = [
    row
    for row in still_pending
    if row["video_id"] == "vid_quota_1"
]

check(
    "failed row stays queued for retry",
    len(matching) == 1,
    str(still_pending)
)

check(
    "failure recorded on row",
    (
        (matching[0]["attempts"] or 0) >= 1
        and bool(matching[0]["last_error"])
    ),
    str(matching)
)

# next run succeeds (flaky-quota recovery)

published, failed = process_due_jobs(
    database=database,
    token_map=token_map,
    now=publish_at,
    service_factory=fake_factory,
)

check(
    "row publishes on retry",
    (published, failed) == (1, 0),
    f"published={published} failed={failed}"
)

# =========================================================

print("\n[7] unknown channel fails safely")

database.enqueue_delayed_publish(
    video_id="vid_unknown_1",
    channel="mystery_channel",
    publish_at=publish_at,
)

# No service_factory injected on purpose: the default
# authenticate_channel path must raise PublishAuthError for
# an unmapped channel without crashing the batch.

published, failed = process_due_jobs(
    database=database,
    token_map=token_map,
    now=publish_at,
)

check(
    "unknown channel fails without crashing",
    (published, failed) == (0, 1),
    f"published={published} failed={failed}"
)

check(
    "PublishAuthError is a RuntimeError",
    issubclass(PublishAuthError, RuntimeError)
)

# =========================================================

print("\n[8] make_public body contract (direct)")

recorder2 = []

make_public(
    FakeYouTube(recorder2),
    "vid_direct"
)

check(
    "direct call issues status update",
    (
        recorder2[0][0] == "status"
        and recorder2[0][1]["id"] == "vid_direct"
    ),
    str(recorder2)
)

# =========================================================

print("\n" + "=" * 60)

if _failures:

    print(
        f"❌ {len(_failures)} check(s) failed: "
        f"{_failures}"
    )

    sys.exit(1)

print("✅ ALL DELAYED-PUBLISH CHECKS PASSED")