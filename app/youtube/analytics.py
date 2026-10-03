"""
=========================================================
YouTube PERFORMANCE COLLECTOR (retention feedback loop)
=========================================================

Two phases, mirroring the CommentEngine scope pattern:

PHASE 1 (LIVE -- no re-auth needed)
  videos.list statistics (views / likes / comments) for
  recently uploaded videos, using the already-granted
  youtube.readonly scope.  Costs 1 Data API unit per video
  (project quota 10,000/day).  Rows land in the
  video_performance table (source='videos.list').

PHASE 2 (READY, DEGRADED -- needs manual `--reauth` once)
  YouTube Analytics API retention summary
  (averageViewDuration / averageViewPercentage /
  estimatedMinutesWatched) via yt-analytics.readonly.
  That scope is NOT in the current token, so every phase-2
  call degrades gracefully with status=SCOPE_MISSING until
  re-authentication is performed explicitly:

      venv\\Scripts\\python -m app.youtube.analytics --reauth

  (Own consent flow: the uploader's authenticate() consents
  only to uploader.SCOPES, so a generic re-auth would NOT
  grant the analytics scope.  This module requests the full
  uploader scope set PLUS yt-analytics.readonly and saves to
  the same youtube_token.json.)

CLI:
  python -m app.youtube.analytics --status
  python -m app.youtube.analytics --collect [--limit N] [--video VIDEO_ID]
  python -m app.youtube.analytics --reauth
"""

import os
import sys

from app.youtube.uploader import (
    CLIENT_SECRET_FILE,
    SCOPES as UPLOADER_SCOPES,
    TOKEN_FILE,
)

# ---------------------------------------------------------
# Scope constants
# ---------------------------------------------------------

ANALYTICS_SCOPE = (
    "https://www.googleapis.com/auth/"
    "yt-analytics.readonly"
)

ANALYTICS_SCOPE_SUFFIX = "yt-analytics.readonly"

# Full consent set for the one-time phase-2 re-auth.
REAUTH_SCOPES = list(UPLOADER_SCOPES) + [
    ANALYTICS_SCOPE
]


# =========================================================
# TOKEN / SCOPE HELPERS (local, no network)
# =========================================================

def token_has_analytics_scope() -> bool:
    """
    Cheap LOCAL check: does the saved OAuth token already
    include yt-analytics.readonly?  Reads youtube_token.json
    without any network call (CommentEngine pattern).
    """

    import json as _json

    if not os.path.exists(TOKEN_FILE):

        return False

    try:

        with open(
            TOKEN_FILE,
            "r",
            encoding="utf-8"
        ) as handle:

            data = _json.load(handle)

        scopes = " ".join(
            data.get("scopes") or []
        )

        return (
            ANALYTICS_SCOPE_SUFFIX
            in scopes
        )

    except Exception:

        return False


def print_scope_status():

    has_phase1 = os.path.exists(TOKEN_FILE)

    has_phase2 = token_has_analytics_scope()

    print("\n📊 Analytics collector scope status:")

    print(
        f"   Phase 1 (videos.list stats): "
        f"{'✅ ready' if has_phase1 else '❌ no token'}"
    )

    print(
        f"   Phase 2 (retention query):   "
        f"{'✅ scope granted' if has_phase2 else '⚠️ SCOPE_MISSING (run --reauth)'}"
    )

# =========================================================
# CREDENTIALS / SERVICES
# =========================================================

def _load_credentials(expanded: bool = False):
    """
    Fresh (refreshed if needed) OAuth credentials.

    expanded=False -> phase-1 surface (uploader.SCOPES,
    already granted).  expanded=True -> phase-2 surface;
    returns None with a printed SCOPE_MISSING note when the
    saved token lacks yt-analytics.readonly.
    """

    from google.auth.transport.requests import Request

    from google.oauth2.credentials import Credentials

    if not os.path.exists(TOKEN_FILE):

        print(
            "SCOPE_MISSING: no OAuth token at "
            f"{TOKEN_FILE}."
        )

        return None

    if expanded and not token_has_analytics_scope():

        print(
            "SCOPE_MISSING: token lacks "
            "yt-analytics.readonly.  Phase 2 stays "
            "degraded until you run:  "
            "python -m app.youtube.analytics --reauth"
        )

        return None

    try:

        wanted = (
            REAUTH_SCOPES
            if expanded
            else UPLOADER_SCOPES
        )

        credentials = (
            Credentials.from_authorized_user_file(
                TOKEN_FILE,
                wanted,
            )
        )

        if (
            credentials.expired
            and credentials.refresh_token
        ):

            credentials.refresh(Request())

            with open(
                TOKEN_FILE,
                "w",
                encoding="utf-8"
            ) as handle:

                handle.write(
                    credentials.to_json()
                )

        if not credentials.valid:

            return None

        return credentials

    except Exception as exc:

        print(
            f"⚠️ Could not load credentials: "
            f"{type(exc).__name__}: {exc}"
        )

        return None


def _data_service():

    """YouTube Data API v3 service (phase 1)."""

    from googleapiclient.discovery import build

    credentials = _load_credentials(
        expanded=False
    )

    if credentials is None:

        return None

    return build(
        "youtube",
        "v3",
        credentials=credentials
    )


def _analytics_service():

    """YouTube Analytics API v2 service (phase 2)."""

    from googleapiclient.discovery import build

    credentials = _load_credentials(
        expanded=True
    )

    if credentials is None:

        return None

    return build(
        "youtubeanalytics",
        "v2",
        credentials=credentials
    )


def _open_db() -> "Database":

    from app.database import Database

    return Database()


# Default: most recent N uploaded videos per collection
# pass (matches the Database.get_video_ids_for_collection
# LIMIT default).
DEFAULT_COLLECTION_LIMIT = 25


# =========================================================
# COLLECTOR
# =========================================================

class AnalyticsCollector:
    """
    Phase 1: videos.list stats -> video_performance rows.
    Phase 2: Analytics API retention queries (degraded with
    status=SCOPE_MISSING until the manual --reauth).
    """

    @staticmethod
    def collect_phase1(
        video_ids: list = None,
        limit: int = DEFAULT_COLLECTION_LIMIT,
        db=None,
    ) -> dict:
        """
        Pull views/likes/comments for the given video ids
        (default: most recent uploaded rows in history) and
        append one video_performance row per video.

        Never raises: returns a summary dict with per-video
        status so callers/CLI can print a clean report.
        """

        close_db = db is None

        db = db or _open_db()

        summary = {
            "collected": [],
            "failed": [],
            "scope_missing": False,
        }

        try:

            if not video_ids:

                video_ids = (
                    db.get_video_ids_for_collection(
                        limit=limit
                    )
                )

            video_ids = [
                v for v in (video_ids or [])
                if v
            ]

            if not video_ids:

                print(
                    "ℹ️ No uploaded videos found to "
                    "collect stats for."
                )

                return summary

            service = _data_service()

            if service is None:

                summary["scope_missing"] = True

                print(
                    "SCOPE_MISSING: phase-1 collector "
                    "has no usable Data API credentials."
                )

                return summary

            # videos.list accepts up to 50 ids per call.

            for chunk_start in range(
                0,
                len(video_ids),
                50
            ):

                chunk = video_ids[
                    chunk_start:chunk_start + 50
                ]

                try:

                    response = (
                        service.videos()
                        .list(
                            part=(
                                "statistics,"
                                "snippet"
                            ),
                            id=",".join(chunk),
                            maxResults=50,
                        )
                        .execute()
                    )

                except Exception as api_error:

                    print(
                        f"❌ videos.list failed: "
                        f"{type(api_error).__name__}: "
                        f"{api_error}"
                    )

                    summary["failed"].extend(
                        chunk
                    )

                    continue

                items = {
                    item["id"]: item
                    for item in (
                        response.get("items")
                        or []
                    )
                }

                for video_id in chunk:

                    item = items.get(video_id)

                    if item is None:

                        print(
                            f"   ⚠️ {video_id}: not "
                            "returned (unlisted/private "
                            "or removed?)"
                        )

                        summary["failed"].append(
                            video_id
                        )

                        continue

                    stats = item.get(
                        "statistics"
                    ) or {}

                    def _int(key):

                        try:

                            return int(
                                stats.get(key) or 0
                            )

                        except (
                            ValueError,
                            TypeError
                        ):

                            return 0

                    row_id = (
                        db.save_video_performance(
                            video_id=video_id,
                            views=_int("viewCount"),
                            likes=_int("likeCount"),
                            comments=_int(
                                "commentCount"
                            ),
                            source="videos.list",
                        )
                    )

                    title = (
                        item.get("snippet", {})
                        .get("title", "?")
                    )

                    print(
                        f"   ✅ {video_id} "
                        f"(row {row_id}): "
                        f"views={_int('viewCount')} "
                        f"likes={_int('likeCount')} "
                        f"comments={_int('commentCount')} "
                        f"— {title[:48]}"
                    )

                    summary["collected"].append(
                        video_id
                    )

            return summary

        finally:

            if close_db:

                try:

                    db.close()

                except Exception:

                    pass

    # =====================================================
    # PHASE 2 — RETENTION QUERY (degraded until --reauth)
    #
    # YouTube Analytics API v2 reports.query.  Requires
    # yt-analytics.readonly, which the current token does
    # NOT carry: _analytics_service() -> _load_credentials(
    # expanded=True) prints the SCOPE_MISSING note and
    # returns None, so this method degrades gracefully and
    # never fails the pipeline.  After a manual
    #   python -m app.youtube.analytics --reauth
    # this path becomes fully active.
    # =====================================================

    @staticmethod
    def collect_phase2(
        video_ids: list = None,
        limit: int = DEFAULT_COLLECTION_LIMIT,
        db=None,
    ) -> dict:

        from datetime import date, timedelta

        close_db = db is None

        db = db or _open_db()

        summary = {
            "collected": [],
            "failed": [],
            "scope_missing": False,
        }

        try:

            if not video_ids:

                video_ids = (
                    db.get_video_ids_for_collection(
                        limit=limit
                    )
                )

            video_ids = [
                v for v in (video_ids or [])
                if v
            ]

            if not video_ids:

                print(
                    "ℹ️ No uploaded videos found "
                    "for phase-2 collection."
                )

                return summary

            service = _analytics_service()

            if service is None:

                summary["scope_missing"] = True

                return summary

            end_date = date.today().isoformat()

            start_date = (
                date.today() - timedelta(days=30)
            ).isoformat()

            for video_id in video_ids:

                try:

                    response = (
                        service.reports()
                        .query(
                            ids="channel==MINE",
                            startDate=start_date,
                            endDate=end_date,
                            metrics=(
                                "views,likes,comments,"
                                "averageViewDuration,"
                                "averageViewPercentage,"
                                "estimatedMinutesWatched"
                            ),
                            filters=(
                                f"video=={video_id}"
                            ),
                        )
                        .execute()
                    )

                    rows = (
                        response.get("rows") or []
                    )

                    if not rows:

                        print(
                            f"   ⚠️ {video_id}: no "
                            "analytics rows yet "
                            "(24-72h data latency "
                            "is normal)."
                        )

                        summary["failed"].append(
                            video_id
                        )

                        continue

                    headers = [
                        (col.get("name") or "")
                        for col in (
                            response.get(
                                "columnHeaders"
                            )
                            or []
                        )
                    ]

                    values = dict(
                        zip(headers, rows[0])
                    )

                    AnalyticsCollector._store_phase2_row(
                        db=db,
                        video_id=video_id,
                        values=values,
                        summary=summary,
                    )

                    continue

                except Exception as api_error:

                    print(
                        f"❌ analytics.query "
                        f"failed for {video_id}: "
                        f"{type(api_error).__name__}: "
                        f"{api_error}"
                    )

                    summary["failed"].append(
                        video_id
                    )

            return summary

        finally:

            if close_db:

                try:

                    db.close()

                except Exception:

                    pass

    # =====================================================
    # PHASE-2 ROW PERSISTENCE
    #
    # Maps an Analytics-API summary row (columnHeaders order)
    # into save_video_performance's avg_view_* columns.
    # =====================================================

    @staticmethod
    def _store_phase2_row(
        db=None,
        video_id: str = "",
        values: dict = None,
        summary: dict = None,
    ):

        values = values or {}

        summary = summary if (
            summary is not None
        ) else {"collected": [], "failed": []}

        def _float(key):

            try:

                return float(
                    values.get(key) or 0
                )

            except (
                ValueError,
                TypeError
            ):

                return 0.0

        def _int(key):

            try:

                return int(
                    float(
                        values.get(key) or 0
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                return 0

        row_id = db.save_video_performance(
            video_id=video_id,
            views=_int("views"),
            likes=_int("likes"),
            comments=_int("comments"),
            avg_view_duration_s=(
                _float("averageViewDuration")
            ),
            avg_view_percentage=(
                _float("averageViewPercentage")
            ),
            est_minutes_watched=(
                _float("estimatedMinutesWatched")
            ),
            source="analytics.query",
        )

        print(
            f"   ✅ {video_id} (row {row_id}): "
            f"avgViewPct="
            f"{_float('averageViewPercentage'):.1f}% "
            f"avgDur={_float('averageViewDuration'):.1f}s "
            f"watchMin="
            f"{_float('estimatedMinutesWatched'):.1f}"
        )

        summary["collected"].append(
            video_id
        )

# =========================================================
# RE-AUTH (manual, one-time -- phase-2 activation)
#
# The uploader's authenticate() consents ONLY to
# uploader.SCOPES, so a generic re-auth can never grant
# yt-analytics.readonly.  This flow requests the FULL
# uploader scope set PLUS the analytics scope and saves to
# the SAME youtube_token.json (creds.to_json() format, the
# exact format _load_credentials / comments.py read), so a
# single consent upgrades the token for every consumer.
# Never called automatically -- user runs:
#     python -m app.youtube.analytics --reauth
# =========================================================

def run_reauth() -> bool:

    print(
        "\n🔁 Analytics re-auth: requesting consent for "
        "the uploader scopes PLUS yt-analytics.readonly..."
    )

    try:

        from google_auth_oauthlib.flow import (
            InstalledAppFlow,
        )

        flow = (
            InstalledAppFlow
            .from_client_secrets_file(
                CLIENT_SECRET_FILE,
                scopes=REAUTH_SCOPES,
            )
        )

        creds = flow.run_local_server(port=0)

        with open(
            TOKEN_FILE,
            "w",
            encoding="utf-8",
        ) as handle:

            handle.write(creds.to_json())

        granted = " ".join(
            getattr(creds, "scopes", None) or []
        )

        ok = (
            ANALYTICS_SCOPE_SUFFIX in granted
        )

        if ok:

            print(
                "✅ Token saved with "
                "yt-analytics.readonly -- phase-2 "
                "retention collection is now ACTIVE."
            )

        else:

            print(
                "⚠️ Token saved but the analytics scope "
                "was NOT granted; phase-2 stays degraded."
            )

        return ok

    except FileNotFoundError:

        print(
            f"❌ OAuth client secret not found: "
            f"{CLIENT_SECRET_FILE}"
        )

        return False

    except Exception as reauth_error:

        print(
            f"❌ Re-auth failed: "
            f"{type(reauth_error).__name__}: "
            f"{reauth_error}"
        )

        return False


# =========================================================
# CLI  (manual trigger only -- never scheduled)
# =========================================================

def _cli(argv: list) -> int:

    if "--reauth" in argv:

        run_reauth()

        print_scope_status()

        return 0

    if "--status" in argv:

        print_scope_status()

        return 0

    collect = "--collect" in argv

    retention = "--retention" in argv

    if not (collect or retention):

        print(__doc__)

        print_scope_status()

        return 0

    limit = DEFAULT_COLLECTION_LIMIT

    if "--limit" in argv:

        try:

            limit = int(
                argv[argv.index("--limit") + 1]
            )

        except (IndexError, ValueError):

            print("⚠️ --limit N invalid; using default.")

    video_ids = None

    if "--video" in argv:

        try:

            video_ids = [
                argv[argv.index("--video") + 1]
            ]

        except IndexError:

            video_ids = None

    if collect:

        summary = AnalyticsCollector.collect_phase1(
            video_ids=video_ids,
            limit=limit,
        )

        print(
            f"\n📊 Phase-1 summary: "
            f"collected={len(summary['collected'])} "
            f"failed={len(summary['failed'])}"
        )

    if retention:

        summary2 = (
            AnalyticsCollector.collect_phase2(
                video_ids=video_ids,
                limit=limit,
            )
        )

        if summary2.get("scope_missing"):

            print(
                "\n⚠️ Phase-2 SKIPPED: "
                "SCOPE_MISSING -- run "
                "`python -m app.youtube.analytics "
                "--reauth` once to enable retention."
            )

        else:

            print(
                f"\n📊 Phase-2 summary: "
                f"collected="
                f"{len(summary2['collected'])} "
                f"failed={len(summary2['failed'])}"
            )

    print_scope_status()

    return 0


if __name__ == "__main__":

    sys.exit(_cli(sys.argv[1:]))
