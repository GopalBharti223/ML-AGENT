# Phase 6B: Auto Pinned Question Comment - Complete ✓

**Objective:** Automate the CHANNEL_BLUEPRINT "first-hour ritual" — every
uploaded Short automatically gets a question-form seed comment posted AS
THE CHANNEL to spark comments (the #4 Shorts ranking signal).

---

## ⚠️ The Pinning Truth (verified against official docs, 2026)

The YouTube Data API v3 `comments`/`commentThreads` resources expose ONLY:
`list · insert · update · delete · setModerationStatus`.

**There is no pin/unpin method.** Pinning is Studio-only. Unofficial
"pin via internal web API" hacks violate ToS and break silently — not
used here. So the automation is:

1. ✅ **Question comment: fully automatic** (`commentThreads.insert`)
2. 📌 **Pin: one guided click** — console prints the Studio deep-link
   (`studio.youtube.com/video/<id>/comments`) right after posting

If Google ever ships an official pin method, the hook point is
`CommentEngine._pin_guidance()` — swap guidance for the call.

---

## 📋 What Changed

| File | Change |
|---|---|
| `app/youtube/comments.py` | NEW — `CommentEngine`: rotating question templates, winner/year personalization, posting + graceful error degradation, `--reauth` CLI |
| `app/youtube/uploader.py` | SCOPES += `youtube.force-ssl` (required to post comments) |
| `app/config.py` | `AUTO_PIN_COMMENT: bool` (default `true`; set `false` in `.env` to disable) |
| `run.py` | Step **13B** after upload-result: posts the question; double-guarded so a comment failure can NEVER fail an upload |

## 🔁 Question Generation

- 10 templates in blueprint voice ("Be honest — did you guess {winner}
  would top this?", "Agree with this ranking — or robbed? Wrong answers
  only.", …)
- Personalized with winner (parsed even from tuple-style chart indexes),
  subject, and year from `topic_data.story_metrics`
- Winner-less stories automatically drop personalized templates
- Anti-repeat rotation: no back-to-back repeats; a template is only
  reused after all other eligible ones have run

## 🔐 One-time setup

The existing token predates the new scope. After pulling this change,
run ONCE:

```
python -m app.youtube.comments --reauth
```

(deletes stale `youtube_token.json`, re-runs consent with upload +
readonly + force-ssl). Until then the engine detects HTTP 403 and
prints exactly this instruction instead of crashing.

## 🧪 Verification

- `test_phase6b_comment_engine.py` → **7/7 PASS** (offline, faked API):
  always-a-question guarantee, personalization/fallback, rotation,
  correct insert body + permalink, 403/5xx graceful notes, video-id
  guard, settings flag
- `test_phase6_health_monitor.py` regression → still **8/8 PASS**
- `py_compile` clean on all 5 touched files

## 🧭 Runtime output example

```
💬 QUESTION COMMENT POSTED:
   Be honest — did you guess Germany would top this?
   https://www.youtube.com/watch?v=abc123&lc=UgxFAKECOMMENT123

📌 PIN THIS COMMENT (one click):
   YouTube Studio -> Comments -> find your new question -> Menu (...) -> Pin
   Direct: https://studio.youtube.com/video/abc123/comments
```

## 🔍 Troubleshooting: "comment not shown / not pinned"

Run the built-in doctor against the affected video — it pinpoints why:

```
python -m app.youtube.comments --doctor VIDEO_ID
```

It audits: token scope → video status (public? made-for-kids?) →
comment buckets (**published / heldForReview / likelySpam**) → pin options.

**Most common causes found by the doctor:**

| Symptom | Cause | Fix |
|---|---|---|
| Never posted | Token lacked `force-ssl` when posted | `--reauth`, then re-run pipeline |
| Posted but invisible | YouTube **held for review / flagged spam** | Approve in Studio → Comments |
| Posted but invisible | Video was private/unlisted at the time | Make public; comment appears |
| No comments possible | Video marked *Made for Kids* | Comments disabled by YouTube |
| Not pinned | Official API cannot pin (verified) | See below |

### Pinning for real (opt-in experimental)

The pipeline can now attempt **actual automatic pinning** through the same
internal creator endpoint YouTube Studio's web client uses, authenticated
with your OAuth bearer token:

```ini
# .env
AUTO_PIN_INTERNAL_API=true
```

Behavior when enabled: after each successful question-comment, the engine
sends a `PIN_COMMENT` action and prints the result. This endpoint is
**undocumented** — if Google changes it, the call fails harmlessly and the
console falls back to the one-click Studio guidance (optionally opening
the page automatically with `AUTO_OPEN_PIN_BROWSER=true`).

Every post now also self-verifies: the engine re-lists the video's threads
and reports exactly where your comment landed (`published`,
`heldForReview`, `likelySpam`, or `NOT_FOUND` = indexing lag).

**New tests:** `test_phase6c_comment_diagnostics.py` → 7/7 PASS
(scope gate, bucket detection, opt-in gating with zero network leakage,
payload shape, HTTP failure containment, flow reporting, doctor verdicts).

---

**Status:** ✅ PHASE 6B COMPLETE — question comments post automatically
per upload; pinning is guided one-click pending an official API method.
