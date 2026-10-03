# ML Agent — Automated Data Shorts Pipeline

Generates data-driven YouTube Shorts end-to-end (topic → data →
script → TTS → voiceover → visuals → assembly → QC → YouTube
upload) and publishes them on a **delayed schedule**: uploaded as
**unlisted** first, flipped to **public** automatically 15 minutes
later — with zero manual action and zero additional cost.

## Quick start

```bash
pip install -r requirements.txt
python run.py                # produce + upload one Short (unlisted)
python publish_worker.py     # flip any due videos to public
```

---

## Delayed publish flow

Videos are **never** uploaded straight to `public`.  The flow is:

```
run.py                         publish_worker.py (cron / Actions, every 2-5 min)
──────────────────────         ─────────────────────────────────────────────────
videos.insert                  SELECT * FROM publish_queue
  privacyStatus = "unlisted"     WHERE published = 0
        │                         AND publish_at <= now
        ▼                                    │
INSERT INTO publish_queue                    ▼
  video_id, channel,               videos.update(part = "status")
  publish_at = now + 15 min,         status.privacyStatus = "public"
  published = 0                                 │
                                                ▼
                                     UPDATE published = 1 (on success)
```

### Components

| Piece | Where | What it does |
|---|---|---|
| Upload | `app/youtube/uploader.py` | `videos.insert` with `privacyStatus = unlisted` |
| Queue insert | `run.py` (step 12B) | Adds a `publish_queue` row after every successful unlisted upload |
| Queue storage | `app/database.py` | `publish_queue` table in `data/history.db` (SQLite) |
| Flip worker | `publish_worker.py` | Publishes due rows via `videos.update`, marks them done, logs failures |

### publish_queue schema

| Column | Type | Meaning |
|---|---|---|
| `video_id` | TEXT UNIQUE | YouTube video id |
| `channel` | TEXT | Channel key (maps to that channel's OAuth token) |
| `publish_at` | DATETIME | Local ISO time when the video should go public |
| `published` | BOOLEAN (default 0) | Flipped to 1 only after a successful API call |
| `attempts` | INTEGER | Diagnostics: how many failed flip attempts |
| `last_error` | TEXT | Diagnostics: last failure message |
| `created_at` | DATETIME | When the row was enqueued |

### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `YOUTUBE_PRIVACY_STATUS` | `unlisted` | Keep `unlisted` for the delayed flow |
| `DELAYED_PUBLISH_ENABLED` | `true` | Set `false` to skip queueing |
| `DELAYED_PUBLISH_DELAY_MINUTES` | `15` | Unlisted → public delay |
| `CHANNEL_NAME` | *(empty → `default`)* | Channel key stored in the queue for this run |
| `CHANNEL_TOKEN_MAP` | `default=youtube_token.json` | `channel=token_file` pairs, `;`-separated |

### Scheduling the worker

**Nothing publishes until this worker runs.**  YouTube will never
flip an unlisted video on its own — the queue row just sits there
waiting.  The worker is **idempotent** (a video can never be
double-processed: the row is only marked published *after* a
successful API call, and `videos.update` with the same body is a
no-op once the video is already public), so run it every 2–5
minutes.

**Windows Task Scheduler (this repo's setup):** a ready-made
wrapper is included.  Register it ONCE from any terminal:

```
schtasks /Create /TN "YouTube Publish Worker" /TR "d:\ML_AGENT\publish_worker.bat" /SC MINUTE /MO 3 /F
```

Each pass appends to `logs\publish_worker.log`.  Remove the task
anytime with:

```
schtasks /Delete /TN "YouTube Publish Worker" /F
```

**Or run it as a self-looping daemon** (one process that checks
the queue every 120 s — sleeping inside the worker is fine; the
"no blocking sleep" rule only applies to the upload pipeline):

```
d:\ML_AGENT\publish_worker.bat --loop 120
```

**cron (Linux/macOS, every 3 minutes):**

```cron
*/3 * * * * cd /path/to/ML_AGENT && python publish_worker.py >> logs/publish_worker.log 2>&1
```

**GitHub Actions** also works (`on: schedule: - cron: "*/3 * * * *"`
→ `pip install -r requirements.txt` → `python publish_worker.py`)
— but ONLY if `data/history.db`, the OAuth token files and the
queue all live on that runner, since SQLite is a local file.  For
this repo's local pipeline, Task Scheduler is the right choice.

> The worker must run on the same machine / file system as
> `data/history.db`, and share the pipeline's clock/timezone,
> because `publish_at` is stored as local time.

**Smoke-test the whole cycle without waiting 15 minutes:** set
`DELAYED_PUBLISH_DELAY_MINUTES=1` in `.env`, upload one Short,
and watch the worker (or `python publish_worker.py --dry-run`)
flip it to public about a minute later.

### Alternative: YouTube-native scheduled publish (no worker)

The Data API also supports `status.publishAt` on `videos.insert`:
upload with `privacyStatus: "private"` **plus** `publishAt = now
+ 15 min` and **YouTube itself** publishes the video at that time
— no queue, no worker, no scheduler at all.  The tradeoff: the
video is fully *private* (not even link-accessible) until the
publish time, instead of *unlisted*.  This repo uses the
unlisted + worker flow per the project spec; switch only if you
prefer zero moving parts over link-accessibility during the
delay window.

### Multiple channels

1. Give each channel its own token file and map it:

   ```
   CHANNEL_TOKEN_MAP=default=youtube_token.json;channel_two=youtube_token_channel2.json
   ```

2. Run the pipeline with `CHANNEL_NAME=channel_two` so uploads are
   queued under the right channel key.

3. Create the second channel's token once (interactive browser
   consent, saved straight to the mapped file):

   ```bash
   python publish_worker.py --auth channel_two
   ```

The worker always authenticates with the token of the channel
stored in each queue row — videos from channel A can never be
published with channel B's credentials.

### Failure handling

The worker never crashes on a bad video.  Per-row failures
(quota exceeded, invalid credentials, video not found, missing
token mapping, …) are logged with an explanation, recorded in
`attempts` / `last_error`, and the row simply retries on the next
run.  Useful flags:

```bash
python publish_worker.py --dry-run   # preview due rows, no API calls
python publish_worker.py -v          # debug logging (shows token map)
python publish_worker.py --now 2026-01-01T12:00:00  # time-travel for testing
```

Validation: `python test_delayed_publish.py` runs the full
offline test suite for the queue + worker (no API calls).

### Cost

Zero additional cost: everything uses the free YouTube Data API
quota (`videos.update` costs ~50 units of the default 10,000
daily units — a handful of flips per day is negligible) and the
local SQLite database.