"""
publish_worker.py — DELAYED-PUBLISH WORKER
==========================================

The main pipeline uploads every Short as UNLISTED and queues a
row in the SQLite `publish_queue` table (see app/database.py)
with publish_at = upload time + DELAYED_PUBLISH_DELAY_MINUTES.

This worker:

  1. Queries `publish_queue` for rows where
        published = 0 AND publish_at <= now
  2. For every due row, calls videos.update() with
        status.privacyStatus = "public"
     authenticated as the row's channel (channel -> token file
     mapping comes from CHANNEL_TOKEN_MAP).
  3. Marks the row published = 1 on success.  On any API error
     the row stays published = 0 and is simply retried on the
     next run — the worker logs the failure and never crashes
     the batch.

Run it on a schedule every 2-5 minutes (cron / GitHub Actions).
It is IDEMPOTENT: running it any number of times never
double-publishes (queue rows are only flipped after a successful
API response, and videos.update with the same body is a no-op
once a video is already public).

Usage:

    python publish_worker.py                      # process due rows
    python publish_worker.py --dry-run            # list, no API calls
    python publish_worker.py --loop 120           # daemon: check every 120 s forever
    python publish_worker.py --auth channel_two   # one-time OAuth consent
    python publish_worker.py --now 2026-01-01T12:00:00   # pretend it is later
    python publish_worker.py -v                   # debug logging

Zero additional cost: SQLite (local file) + YouTube Data API
(free quota; videos.update costs ~50 quota units per call).
"""

import os
import sys
import time
import argparse
import logging

from datetime import datetime

# ---------------------------------------------------------
# UNICODE-SAFE OUTPUT
# Same guard as run.py: emoji log lines crash under cp1252
# whenever output is redirected (cron, CI pipes, log files).
# ---------------------------------------------------------

for _stream in (sys.stdout, sys.stderr):

    if _stream and hasattr(_stream, "reconfigure"):

        try:

            _stream.reconfigure(
                encoding="utf-8",
                errors="replace",
            )

        except (ValueError, OSError):

            pass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.database import Database

from app.youtube.uploader import (
    SCOPES,
    CLIENT_SECRET_FILE,
)

# Scope required by videos.update (the upload scope alone is
# NOT sufficient to change a video's status).
FORCE_SSL_SCOPE = (
    "https://www.googleapis.com/auth/youtube.force-ssl"
)

logger = logging.getLogger("publish_worker")


class PublishAuthError(RuntimeError):
    """
    Raised when a queued video's channel cannot be
    authenticated (no token mapping / missing token file /
    unrefreshable credentials).
    """


# =========================================================
# CHANNEL -> TOKEN FILE MAPPING
# =========================================================

def parse_channel_token_map(raw: str) -> dict:
    """
    Parse CHANNEL_TOKEN_MAP, e.g.

        "default=youtube_token.json;second=tok2.json"

    into {"default": "youtube_token.json",
          "second": "tok2.json"}.
    """

    token_map = {}

    for entry in (raw or "").split(";"):

        entry = entry.strip()

        if not entry:
            continue

        if "=" not in entry:

            raise ValueError(
                "Invalid CHANNEL_TOKEN_MAP entry "
                f"'{entry}'. Expected 'channel=token_file' "
                "pairs separated by ';'."
            )

        name, path = entry.split("=", 1)

        name = name.strip()
        path = path.strip()

        if name and path:
            token_map[name] = path

    return token_map


# =========================================================
# AUTHENTICATION (per channel)
# =========================================================

def authenticate_channel(
    channel: str,
    token_map: dict
):
    """
    Build a YouTube API service authenticated AS `channel`
    using that channel's own OAuth token file.

    Raises PublishAuthError (never crashes the whole batch)
    when the channel has no usable credentials.
    """

    token_file = token_map.get(channel)

    if not token_file:

        raise PublishAuthError(
            f"No OAuth token file mapped for channel "
            f"'{channel}'. Add it to CHANNEL_TOKEN_MAP "
            f"(e.g. '{channel}=<token>.json') and, if the "
            f"token does not exist yet, run: "
            f"python publish_worker.py --auth {channel}"
        )

    if not os.path.exists(token_file):

        raise PublishAuthError(
            f"OAuth token file not found for channel "
            f"'{channel}': {token_file}. Run "
            f"'python publish_worker.py --auth {channel}' "
            "once to create it."
        )

    credentials = (
        Credentials.from_authorized_user_file(
            token_file,
            SCOPES
        )
    )

    if (
        credentials.expired
        and credentials.refresh_token
    ):

        logger.info(
            "Refreshing OAuth token for channel '%s'...",
            channel
        )

        credentials.refresh(Request())

        # Persist the refreshed token so the next worker run
        # (and the pipeline itself) starts from a warm token.

        with open(
            token_file,
            "w",
            encoding="utf-8"
        ) as handle:

            handle.write(
                credentials.to_json()
            )

    if not credentials.valid:

        raise PublishAuthError(
            f"OAuth credentials for channel '{channel}' "
            f"are not valid (file: {token_file}). "
            "Re-authorize with: "
            f"python publish_worker.py --auth {channel}"
        )

    if FORCE_SSL_SCOPE not in (credentials.scopes or []):

        logger.warning(
            "Token for channel '%s' lacks the "
            "youtube.force-ssl scope; videos.update will "
            "fail until you re-auth with: "
            "python publish_worker.py --auth %s",
            channel,
            channel
        )

    return build(
        "youtube",
        "v3",
        credentials=credentials
    )

def authorize_channel_interactively(
    channel: str,
    token_map: dict
) -> str:
    """
    One-time OAuth consent for `channel`; saves the token to
    the file mapped in CHANNEL_TOKEN_MAP.  Run this once per
    channel (a browser window opens).
    """

    token_file = token_map.get(channel)

    if not token_file:

        raise PublishAuthError(
            f"Channel '{channel}' is not in CHANNEL_TOKEN_MAP. "
            "Add '<channel>=<token_file>.json' first."
        )

    if not os.path.exists(CLIENT_SECRET_FILE):

        raise PublishAuthError(
            f"Missing OAuth client file: {CLIENT_SECRET_FILE}"
        )

    flow = (
        InstalledAppFlow
        .from_client_secrets_file(
            CLIENT_SECRET_FILE,
            SCOPES
        )
    )

    print(
        "\n🌐 Starting Google OAuth for channel "
        f"'{channel}' — a browser window will open. "
        "Sign in with the Google account that owns "
        "that YouTube channel."
    )

    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent"
    )

    with open(
        token_file,
        "w",
        encoding="utf-8"
    ) as handle:

        handle.write(
            credentials.to_json()
        )

    logger.info(
        "💾 Token for channel '%s' saved to %s",
        channel,
        token_file
    )

    return token_file


# =========================================================
# PUBLISH ONE VIDEO
# =========================================================

def make_public(
    youtube,
    video_id: str
) -> None:
    """
    Flip one video to public via videos.update.

    NOTE: videos.update rewrites the whole `status` part, so
    the body mirrors the status block used at upload time
    (privacyStatus + selfDeclaredMadeForKids) to avoid
    resetting anything.
    """

    body = {
        "id": video_id,

        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    youtube.videos().update(
        part="status",
        body=body
    ).execute()


def describe_http_error(exc: HttpError) -> str:
    """
    Human-readable one-liner for a YouTube API error, with a
    hint for the common failure modes.
    """

    status = getattr(
        getattr(exc, "resp", None),
        "status",
        None
    )

    try:
        reason = exc._get_reason()

    except Exception:
        reason = str(exc)

    hint = ""

    if status == 401:

        hint = (
            "(invalid/expired credentials — re-auth with "
            "'python publish_worker.py --auth <channel>')"
        )

    elif (
        status == 403
        and "quota" in str(reason).lower()
    ):

        hint = (
            "(YouTube Data API daily quota exceeded — the "
            "row stays queued and retries on a later run)"
        )

    elif status == 403:

        hint = (
            "(forbidden — wrong channel token, missing "
            "youtube.force-ssl scope, or video owned by "
            "another channel)"
        )

    elif status == 404:

        hint = (
            "(video not found — it may have been deleted)"
        )

    return (
        f"HTTP {status} {reason} {hint}".strip()
    )

# =========================================================
# PROCESS THE QUEUE
# =========================================================

def process_due_jobs(
    database: Database,
    token_map: dict,
    now: datetime = None,
    dry_run: bool = False,
    service_factory=None,
):
    """
    Publish every due queue row.

    Returns (published_count, failed_count).  Failed rows stay
    published = 0 and are retried automatically on the next
    run; failures are logged and never crash the batch.
    """

    if now is None:
        now = datetime.now()

    if service_factory is None:

        def service_factory(channel_name):
            return authenticate_channel(
                channel_name,
                token_map
            )

    due_jobs = database.get_due_publish_jobs(now=now)

    if not due_jobs:

        logger.info(
            "No videos are due for publish right now."
        )

        return 0, 0

    logger.info(
        "Found %d video(s) due for publish.",
        len(due_jobs)
    )

    services = {}

    published_count = 0
    failed_count = 0

    for job in due_jobs:

        video_id = job["video_id"]
        channel = job["channel"] or "default"

        try:

            # Build ONE service per channel and reuse it for
            # every video of that channel in this run.

            if channel not in services:

                services[channel] = service_factory(channel)

                logger.info(
                    "Authenticated channel '%s'.",
                    channel
                )

            if dry_run:

                logger.info(
                    "[dry-run] Would make video %s PUBLIC "
                    "(channel '%s', scheduled %s, attempts %d).",
                    video_id,
                    channel,
                    job["publish_at"],
                    job["attempts"]
                )

                continue

            make_public(
                services[channel],
                video_id
            )

            # Only mark done AFTER the API call succeeded, so
            # a crash between the two simply re-publishes on
            # the next run (idempotent no-op).

            database.mark_publish_job_published(video_id)

            published_count += 1

            logger.info(
                "✅ Video %s is now PUBLIC (channel '%s', "
                "scheduled %s).",
                video_id,
                channel,
                job["publish_at"]
            )

        except PublishAuthError as exc:

            failed_count += 1

            database.mark_publish_job_failed(
                video_id,
                str(exc)
            )

            logger.error(
                "❌ Cannot authenticate channel '%s' for "
                "video %s: %s",
                channel,
                video_id,
                exc
            )

        except HttpError as exc:

            failed_count += 1

            description = describe_http_error(exc)

            database.mark_publish_job_failed(
                video_id,
                description
            )

            logger.error(
                "❌ YouTube API error while publishing "
                "video %s (channel '%s'): %s",
                video_id,
                channel,
                description
            )

        except Exception as exc:

            failed_count += 1

            description = (
                f"{type(exc).__name__}: {exc}"
            )

            database.mark_publish_job_failed(
                video_id,
                description
            )

            logger.exception(
                "❌ Unexpected error while publishing "
                "video %s (channel '%s'): %s",
                video_id,
                channel,
                description
            )

    logger.info(
        "Delayed-publish pass finished: %d published, "
        "%d failed (failed rows retry on the next run).",
        published_count,
        failed_count
    )

    return published_count, failed_count

# =========================================================
# MAIN
# =========================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Delayed-publish worker: flips queued unlisted "
            "YouTube videos to public once they are due."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List due videos without calling the API."
    )

    parser.add_argument(
        "--auth",
        metavar="CHANNEL",
        help=(
            "One-time OAuth consent for CHANNEL; saves its "
            "token file (no publishing is done)."
        )
    )

    parser.add_argument(
        "--now",
        metavar="ISO_DATETIME",
        help=(
            "Override the current local time, e.g. "
            "2026-01-01T12:00:00 (mainly for testing)."
        )
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose (DEBUG) logging."
    )

    parser.add_argument(
        "--loop",
        nargs="?",
        const=180,
        default=None,
        type=int,
        metavar="SECONDS",
        help=(
            "Keep running forever and re-check the queue "
            "every SECONDS seconds (default 180).  Ctrl+C "
            "stops it.  Without this flag the worker does "
            "ONE pass and exits (cron-friendly)."
        )
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=(
            logging.DEBUG if args.verbose else logging.INFO
        ),
        format=(
            "%(asctime)s [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
    )

    token_map = parse_channel_token_map(
        settings.CHANNEL_TOKEN_MAP
    )

    logger.debug(
        "Channel token map: %s",
        token_map
    )

    if args.auth:

        authorize_channel_interactively(
            args.auth,
            token_map
        )

        return 0

    now = None

    if args.now:

        now = datetime.fromisoformat(args.now)

    database = Database()

    # --loop N: keep running and re-check the queue every N
    # seconds (daemon mode).  Sleeping HERE is perfectly
    # safe -- the "no blocking sleep" rule only applies to
    # the main upload pipeline, never to this dedicated
    # worker process.

    while True:

        pending = database.get_pending_publish_jobs()

        logger.info(
            "publish_queue: %d row(s) waiting "
            "(published = 0).",
            len(pending)
        )

        for row in pending:

            logger.info(
                "  - video %s | channel '%s' | publish_at %s "
                "| attempts %d%s",
                row["video_id"],
                row["channel"],
                row["publish_at"],
                row["attempts"],
                (
                    f" | last error: {row['last_error']}"
                    if row["last_error"]
                    else ""
                )
            )

        process_due_jobs(
            database=database,
            token_map=token_map,
            now=now,
            dry_run=args.dry_run,
        )

        if args.loop is None:
            break

        logger.info(
            "Next queue check in %d s (Ctrl+C to stop)...",
            args.loop
        )

        try:

            time.sleep(args.loop)

        except KeyboardInterrupt:

            logger.info(
                "Publish worker stopped by user."
            )

            return 0

    return 0


if __name__ == "__main__":

    raise SystemExit(main())