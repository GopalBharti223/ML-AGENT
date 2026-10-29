import sqlite3
import os
from datetime import datetime, timedelta

from app.config import settings


class Database:

    def __init__(self):

        db_directory = os.path.dirname(
            settings.DB_PATH
        )

        if db_directory:
            os.makedirs(
                db_directory,
                exist_ok=True
            )

        self.conn = sqlite3.connect(
            settings.DB_PATH
        )

        self.cursor = self.conn.cursor()

        self._init_tables()

    # =====================================================
    # DATABASE SETUP
    # =====================================================

    def _init_tables(self):

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS video_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                date TEXT,

                topic TEXT UNIQUE,

                category TEXT,

                title TEXT,

                video_path TEXT,

                youtube_id TEXT,

                qc_score INTEGER,

                upload_status TEXT,

                indicator_code TEXT,

                story_type TEXT,

                start_year INTEGER,

                end_year INTEGER
            )
            """
        )

        self.conn.commit()

        # -------------------------------------------------
        # Add missing columns to old databases
        # -------------------------------------------------

        existing_columns = self._get_columns(
            "video_history"
        )

        new_columns = {
            "video_path": "TEXT",
            "youtube_id": "TEXT",
            "qc_score": "INTEGER",
            "upload_status": "TEXT",
            "indicator_code": "TEXT",
            "story_type": "TEXT",
            "start_year": "INTEGER",
            "end_year": "INTEGER",
            "voice": "TEXT",
            "title_format": "TEXT",
            "hook_style": "TEXT",
            "ding_variant": "TEXT",
            "chime_variant": "TEXT",
            # -------------------------------------------------
            # ROTATION OBSERVABILITY (additive, optional).
            #
            # provider_id + chart_type are NOT part of any
            # uniqueness rule and NOT read by any existing query,
            # so old rows simply keep NULL and every pre-existing
            # reader behaves exactly as before.  They exist so
            # long-term chart/provider rotation can be audited
            # from the ledger instead of inferred from story
            # metadata (which never recorded the chart that was
            # actually rendered).
            #
            # Backward compatible: ADD COLUMN on an existing
            # database is a metadata-only operation in SQLite.
            # -------------------------------------------------
            "provider_id": "TEXT",
            "chart_type": "TEXT",
        }

        for column_name, column_type in new_columns.items():

            if column_name not in existing_columns:

                self.cursor.execute(
                    f"""
                    ALTER TABLE video_history
                    ADD COLUMN {column_name} {column_type}
                    """
                )

        self.conn.commit()

        # -------------------------------------------------
        # Delayed-publish queue
        #
        # Videos are uploaded UNLISTED and flipped to PUBLIC
        # by publish_worker.py once publish_at has passed.
        # video_id is UNIQUE so re-enqueueing the same video
        # is a no-op (idempotent pipeline re-runs).
        # -------------------------------------------------

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                video_id TEXT UNIQUE,

                channel TEXT,

                publish_at DATETIME,

                published BOOLEAN DEFAULT 0,

                attempts INTEGER DEFAULT 0,

                last_error TEXT,

                created_at DATETIME
            )
            """
        )

        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_publish_queue_due
            ON publish_queue (published, publish_at)
            """
        )

        self.conn.commit()

        # -------------------------------------------------
        # Video performance log (retention feedback loop)
        #
        # Phase 1 appends one row per videos.list statistics
        # pull (views/likes/comments -- youtube.readonly,
        # already granted).  Phase 2 (yt-analytics.readonly,
        # not yet consented) will fill the avg_view_*/est_
        # minutes columns from the Analytics API.  Append-only:
        # repeated collections accumulate, so growth over time
        # is visible per video.
        # -------------------------------------------------

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS video_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                video_id TEXT NOT NULL,

                views INTEGER,

                likes INTEGER,

                comments INTEGER,

                avg_view_duration_s REAL,

                avg_view_percentage REAL,

                est_minutes_watched REAL,

                source TEXT DEFAULT 'videos.list',

                collected_at DATETIME
            )
            """
        )

        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_video_performance_video
            ON video_performance (video_id, collected_at)
            """
        )

        self.conn.commit()

    # =====================================================
    # GET TABLE COLUMNS
    # =====================================================

    def _get_columns(
        self,
        table_name: str
    ):

        self.cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = self.cursor.fetchall()

        return {
            row[1]
            for row in rows
        }

    # =====================================================
    # EXACT TOPIC CHECK
    # =====================================================

    def is_topic_used(
        self,
        topic: str
    ) -> bool:

        self.cursor.execute(
            """
            SELECT 1
            FROM video_history
            WHERE LOWER(topic) = LOWER(?)
            LIMIT 1
            """,
            (topic,)
        )

        return (
            self.cursor.fetchone()
            is not None
        )

    # =====================================================
    # STORY TYPE CHECK
    # =====================================================

    def is_story_type_used_recently(
        self,
        indicator_code: str,
        story_type: str,
        days: int = 30
    ) -> bool:

        cutoff = (
            datetime.now()
            - timedelta(days=days)
        ).isoformat()

        self.cursor.execute(
            """
            SELECT 1
            FROM video_history
            WHERE indicator_code = ?
              AND story_type = ?
              AND date >= ?
            LIMIT 1
            """,
            (
                indicator_code,
                story_type,
                cutoff
            )
        )

        return (
            self.cursor.fetchone()
            is not None
        )

    # =====================================================
    # YEAR RANGE CHECK
    # =====================================================

    def is_year_range_used_recently(
        self,
        indicator_code: str,
        start_year: int,
        end_year: int,
        days: int = 60
    ) -> bool:

        cutoff = (
            datetime.now()
            - timedelta(days=days)
        ).isoformat()

        self.cursor.execute(
            """
            SELECT 1
            FROM video_history
            WHERE indicator_code = ?
              AND start_year = ?
              AND end_year = ?
              AND date >= ?
            LIMIT 1
            """,
            (
                indicator_code,
                start_year,
                end_year,
                cutoff
            )
        )

        return (
            self.cursor.fetchone()
            is not None
        )

    # =====================================================
    # COMBINATION CHECK
    # =====================================================

    def is_content_combination_used(
        self,
        indicator_code: str,
        story_type: str,
        start_year: int,
        end_year: int,
        days: int = 90
    ) -> bool:

        cutoff = (
            datetime.now()
            - timedelta(days=days)
        ).isoformat()

        self.cursor.execute(
            """
            SELECT 1
            FROM video_history
            WHERE indicator_code = ?
              AND story_type = ?
              AND start_year = ?
              AND end_year = ?
              AND date >= ?
            LIMIT 1
            """,
            (
                indicator_code,
                story_type,
                start_year,
                end_year,
                cutoff
            )
        )

        return (
            self.cursor.fetchone()
            is not None
        )

    # =====================================================
    # GET RECENT CONTENT HISTORY
    # =====================================================

    def get_recent_content(
        self,
        limit: int = 30
    ):

        self.cursor.execute(
            """
            SELECT
                topic,
                title,
                indicator_code,
                story_type,
                start_year,
                end_year,
                date,
                youtube_id,
                upload_status
            FROM video_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )

        rows = self.cursor.fetchall()

        history = []

        for row in rows:

            history.append(
                {
                    "topic": row[0],
                    "title": row[1],
                    "indicator_code": row[2],
                    "story_type": row[3],
                    "start_year": row[4],
                    "end_year": row[5],
                    "date": row[6],
                    "youtube_id": row[7],
                    "upload_status": row[8]
                }
            )

        return history

    # =====================================================
    # GET RECENT RECORDS
    #
    # TopicEngine expects this method.
    # =====================================================

    def get_recent_records(
        self,
        limit: int = 100
    ):

        return self.get_recent_content(
            limit=limit
        )

    # =====================================================
    # LAST USED VOICE
    #
    # Voice-rotation support: returns the Edge TTS voice
    # used for the most recently saved video (None when
    # there is no voice history yet or the column is
    # missing on old databases).
    # =====================================================

    def get_last_voice(self):

        try:

            self.cursor.execute(
                """
                SELECT voice
                FROM video_history
                WHERE voice IS NOT NULL AND voice != ''
                ORDER BY id DESC
                LIMIT 1
                """
            )

            row = self.cursor.fetchone()

        except Exception:

            # Old schema / transient error: degrade to
            # "no history" instead of breaking the pipeline.
            return None

        return row[0] if row else None

    # =====================================================
    # LAST USED TITLE FORMAT
    #
    # Title-format-rotation support (mirrors get_last_voice):
    # returns the YouTube title format used by the most
    # recently saved video (None when there is no history yet
    # or the column is missing on old databases).
    # =====================================================

    def get_last_title_format(self):

        try:

            self.cursor.execute(
                """
                SELECT title_format
                FROM video_history
                WHERE title_format IS NOT NULL
                  AND title_format != ''
                ORDER BY id DESC
                LIMIT 1
                """
            )

            row = self.cursor.fetchone()

        except Exception:

            return None

        return row[0] if row else None

    # =====================================================
    # RECENT VOICES
    #
    # Category voice-pool rotation support: returns the most
    # recent voices, NEWEST FIRST, so pick_voice() can pick the
    # pool member that has gone longest unused (Priority 3).
    # Without this a busy category keeps landing on the same
    # narrator no matter how the pool is ordered.
    # =====================================================

    def get_recent_voices(self, limit: int = 8):

        try:

            self.cursor.execute(
                """
                SELECT voice
                FROM video_history
                WHERE voice IS NOT NULL AND voice != ''
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            )

            return [
                row[0] for row in self.cursor.fetchall()
            ]

        except Exception:

            return []

    # =====================================================
    # LAST USED SFX VARIANTS
    #
    # Brand-sound-effect rotation support (mirrors
    # get_last_voice): returns the ding/chime variant indices
    # used by the most recent published video, so the picker
    # can avoid repeating them.  The live ledger lives in
    # data/last_sfx.json (written by the assembler as soon as
    # the cues ship); this DB read is the durable record.
    # =====================================================

    def get_last_sfx_variants(self):

        try:

            self.cursor.execute(
                """
                SELECT ding_variant, chime_variant
                FROM video_history
                WHERE ding_variant IS NOT NULL
                  AND ding_variant != ''
                ORDER BY id DESC
                LIMIT 1
                """
            )

            row = self.cursor.fetchone()

        except Exception:

            return (None, None)

        return (row[0], row[1]) if row else (None, None)

    # =====================================================
    # SAVE VIDEO RECORD
    # =====================================================

    def save_record(
        self,
        topic: str,
        category: str,
        title: str,
        indicator_code: str = None,
        story_type: str = None,
        start_year: int = None,
        end_year: int = None,
        video_path: str = None,
        youtube_id: str = None,
        upload_status: str = "pending",
        qc_score: int = None,
        voice: str = None,
        title_format: str = None,
        hook_style: str = None,
        ding_variant: str = None,
        chime_variant: str = None,
        provider_id: str = None,
        chart_type: str = None
    ):

        # Rotation observability only.  Both are additive and
        # optional: existing callers that do not pass them keep
        # working unchanged, and existing rows keep NULL.
        self.cursor.execute(
            """
            INSERT OR IGNORE INTO video_history
            (
                date,
                topic,
                category,
                title,
                video_path,
                youtube_id,
                qc_score,
                upload_status,
                indicator_code,
                story_type,
                start_year,
                end_year,
                voice,
                title_format,
                hook_style,
                ding_variant,
                chime_variant,
                provider_id,
                chart_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                topic,
                category,
                title,
                video_path,
                youtube_id,
                qc_score,
                upload_status,
                indicator_code,
                story_type,
                start_year,
                end_year,
                voice,
                title_format,
                hook_style,
                ding_variant,
                chime_variant,
                provider_id,
                chart_type
            )
        )

        self.conn.commit()

    # =====================================================
    # VIDEO PERFORMANCE (retention feedback loop)
    #
    # Append-only log consumed by app/youtube/analytics.py.
    # Phase 1 writes source='videos.list' rows (views/likes/
    # comments); phase 2 will write source='analytics.query'
    # rows with the avg_view_* / est_minutes fields filled.
    # =====================================================

    def save_video_performance(
        self,
        video_id: str,
        views: int = None,
        likes: int = None,
        comments: int = None,
        avg_view_duration_s: float = None,
        avg_view_percentage: float = None,
        est_minutes_watched: float = None,
        source: str = "videos.list"
    ):

        self.cursor.execute(
            """
            INSERT INTO video_performance
            (
                video_id,
                views,
                likes,
                comments,
                avg_view_duration_s,
                avg_view_percentage,
                est_minutes_watched,
                source,
                collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                views,
                likes,
                comments,
                avg_view_duration_s,
                avg_view_percentage,
                est_minutes_watched,
                source,
                datetime.now().isoformat()
            )
        )

        self.conn.commit()

        return self.cursor.lastrowid

    def get_settled_performance(
        self,
        min_age_hours: int = 48,
        limit: int = 300
    ) -> list:

        """
        Published videos joined with their NEWEST performance row,
        limited to videos older than `min_age_hours` (a Shorts
        retention signal is not settled before ~48h).

        Used by app.topic.performance_bias to bias topic selection
        toward the categories / country pairs that actually retain
        viewers.  Returns [] when analytics has not been collected
        yet, so the bias is a no-op on a fresh install.
        """

        try:
            min_age_hours = int(min_age_hours)
        except (TypeError, ValueError):
            min_age_hours = 48

        cutoff = (
            datetime.now()
            - timedelta(hours=max(0, min_age_hours))
        ).isoformat()

        try:

            self.cursor.execute(
                """
                SELECT
                    h.youtube_id,
                    h.indicator_code,
                    h.story_type,
                    h.topic,
                    h.title,
                    h.date,
                    p.views,
                    p.avg_view_percentage,
                    p.avg_view_duration_s,
                    p.collected_at
                FROM video_history AS h
                JOIN video_performance AS p
                  ON p.id = (
                        SELECT id
                        FROM video_performance
                        WHERE video_id = h.youtube_id
                        ORDER BY id DESC
                        LIMIT 1
                     )
                WHERE h.youtube_id IS NOT NULL
                  AND h.youtube_id != ''
                  AND h.date <= ?
                ORDER BY h.id DESC
                LIMIT ?
                """,
                (
                    cutoff,
                    limit
                )
            )

            rows = self.cursor.fetchall()

        except Exception:

            # Old schema / missing table: degrade to "no signal".
            return []

        keys = [
            "video_id",
            "indicator_code",
            "story_type",
            "topic",
            "title",
            "date",
            "views",
            "avg_view_percentage",
            "avg_view_duration_s",
            "collected_at"
        ]

        return [
            dict(zip(keys, row))
            for row in rows
        ]

    def get_video_ids_for_collection(
        self,
        limit: int = 25
    ) -> list:

        """
        Most recent uploaded video ids (newest first) for the
        stats collector.  Empty/blank youtube_ids are skipped.
        """

        self.cursor.execute(
            """
            SELECT youtube_id
            FROM video_history
            WHERE upload_status = 'uploaded'
              AND youtube_id IS NOT NULL
              AND youtube_id != ''
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [
            row[0]
            for row in self.cursor.fetchall()
        ]

    def get_latest_performance(
        self,
        video_id: str
    ) -> dict:

        """
        Newest video_performance row for one video, as a dict
        (empty dict when nothing has been collected yet).
        """

        self.cursor.execute(
            """
            SELECT
                video_id,
                views,
                likes,
                comments,
                avg_view_duration_s,
                avg_view_percentage,
                est_minutes_watched,
                source,
                collected_at
            FROM video_performance
            WHERE video_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (video_id,)
        )

        row = self.cursor.fetchone()

        if not row:

            return {}

        keys = [
            "video_id",
            "views",
            "likes",
            "comments",
            "avg_view_duration_s",
            "avg_view_percentage",
            "est_minutes_watched",
            "source",
            "collected_at"
        ]

        return dict(
            zip(
                keys,
                row
            )
        )

    # =====================================================
    # HAS VIDEO BEEN UPLOADED
    #
    # Idempotency guard to prevent accidental duplicate
    # YouTube uploads of the same generated video file.
    #
    # A video is considered "already uploaded" when a
    # database record exists with the same video_path
    # AND upload_status = 'uploaded'.
    # =====================================================

    def has_video_been_uploaded(
        self,
        video_path: str = "",
        topic: str = "",
        title: str = "",
    ) -> bool:

        video_path = str(video_path or "").strip()
        topic = str(topic or "").strip()
        title = str(title or "").strip()

        # Check by exact video_path
        if video_path:
            self.cursor.execute(
                """
                SELECT 1
                FROM video_history
                WHERE video_path = ?
                  AND upload_status = 'uploaded'
                LIMIT 1
                """,
                (video_path,)
            )
            if self.cursor.fetchone() is not None:
                return True

        # Check by topic fingerprint
        if topic:
            self.cursor.execute(
                """
                SELECT 1
                FROM video_history
                WHERE topic = ?
                  AND upload_status = 'uploaded'
                LIMIT 1
                """,
                (topic,)
            )
            if self.cursor.fetchone() is not None:
                return True

        # Check by title
        if title:
            self.cursor.execute(
                """
                SELECT 1
                FROM video_history
                WHERE title = ?
                  AND upload_status = 'uploaded'
                LIMIT 1
                """,
                (title,)
            )
            if self.cursor.fetchone() is not None:
                return True

        return False

    # =====================================================
    # DAILY SUCCESSFUL UPLOAD COUNT
    # =====================================================

    def get_today_video_count(self) -> int:

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        self.cursor.execute(
            """
            SELECT COUNT(*)
            FROM video_history
            WHERE date LIKE ?
              AND upload_status = 'uploaded'
            """,
            (f"{today}%",)
        )

        result = self.cursor.fetchone()

        return int(
            result[0]
            if result
            else 0
        )

    # =====================================================
    # DAILY LIMIT
    # =====================================================

    def daily_limit_reached(self) -> bool:

        return (
            self.get_today_video_count()
            >= settings.DAILY_UPLOADS
        )

    # =====================================================
    # DELAYED PUBLISH: ENQUEUE
    #
    # Called after every successful UNLISTED upload.  The row
    # is picked up by publish_worker.py once publish_at has
    # passed, flipped to public, and marked published = 1.
    # =====================================================

    def enqueue_delayed_publish(
        self,
        video_id: str,
        channel: str,
        publish_at: datetime
    ) -> bool:
        """
        Queue a freshly-uploaded (unlisted) video to be
        flipped to public at `publish_at`.

        Returns True when a NEW row was inserted, False when
        the video was already queued (idempotent re-runs).
        """

        self.cursor.execute(
            """
            INSERT OR IGNORE INTO publish_queue
            (
                video_id,
                channel,
                publish_at,
                published,
                attempts,
                created_at
            )
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (
                video_id,
                channel,
                publish_at.isoformat(
                    timespec="microseconds"
                ),
                datetime.now().isoformat(
                    timespec="microseconds"
                )
            )
        )

        self.conn.commit()

        return (
            self.cursor.rowcount > 0
        )

    # =====================================================
    # DELAYED PUBLISH: DUE JOBS
    #
    # Rows the worker must publish right now:
    #   published = 0  AND  publish_at <= now
    # =====================================================

    def get_due_publish_jobs(
        self,
        now: datetime = None
    ) -> list:

        if now is None:
            now = datetime.now()

        self.cursor.execute(
            """
            SELECT
                id,
                video_id,
                channel,
                publish_at,
                attempts
            FROM publish_queue
            WHERE published = 0
              AND publish_at <= ?
            ORDER BY publish_at ASC
            """,
            (
                now.isoformat(
                    timespec="microseconds"
                ),
            )
        )

        rows = self.cursor.fetchall()

        return [
            {
                "id": row[0],
                "video_id": row[1],
                "channel": row[2],
                "publish_at": row[3],
                "attempts": row[4]
            }
            for row in rows
        ]

    # =====================================================
    # DELAYED PUBLISH: MARK PUBLISHED
    # =====================================================

    def mark_publish_job_published(
        self,
        video_id: str
    ):

        self.cursor.execute(
            """
            UPDATE publish_queue
            SET published = 1
            WHERE video_id = ?
            """,
            (video_id,)
        )

        self.conn.commit()

    # =====================================================
    # DELAYED PUBLISH: MARK FAILED
    #
    # The row stays published = 0, so publish_worker.py
    # simply retries it on the next run.  attempts/last_error
    # exist for diagnostics only.
    # =====================================================

    def mark_publish_job_failed(
        self,
        video_id: str,
        error: str
    ):

        self.cursor.execute(
            """
            UPDATE publish_queue
            SET attempts = attempts + 1,
                last_error = ?
            WHERE video_id = ?
            """,
            (
                str(error),
                video_id
            )
        )

        self.conn.commit()

    # =====================================================
    # DELAYED PUBLISH: PENDING (not yet published)
    # =====================================================

    def get_pending_publish_jobs(self) -> list:

        self.cursor.execute(
            """
            SELECT
                id,
                video_id,
                channel,
                publish_at,
                attempts,
                last_error
            FROM publish_queue
            WHERE published = 0
            ORDER BY publish_at ASC
            """
        )

        rows = self.cursor.fetchall()

        return [
            {
                "id": row[0],
                "video_id": row[1],
                "channel": row[2],
                "publish_at": row[3],
                "attempts": row[4],
                "last_error": row[5]
            }
            for row in rows
        ]

    # =====================================================
    # CLOSE DATABASE
    # =====================================================

    def close(self):

        if self.conn:
            self.conn.close()


db = Database()