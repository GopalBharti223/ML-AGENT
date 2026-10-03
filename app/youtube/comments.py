# =========================================================
# COMMENT ENGINE — Auto Pinned Question Comment
# =========================================================
#
# Automates the "first-hour ritual" from CHANNEL_BLUEPRINT.md:
# a question-form seed comment posted AS THE CHANNEL on every
# freshly uploaded Short, so engagement starts before the
# creator even opens Studio.
#
# The comment TEXT is AI-generated when possible (see
# generate_engagement_comment + ENGAGEMENT_COMMENT_PROMPT_
# TEMPLATE below, driven by the same Groq client that writes
# scripts/titles); the rotating QUESTION_TEMPLATES inside
# CommentEngine are the offline fallback.
#
# HOW PINNING WORKS (important limitation)
# ----------------------------------------
# The official YouTube Data API v3 can CREATE comments
# (commentThreads.insert) but has NO pin/unpin method -- the
# fetched docs list only list/insert/update/delete/
# setModerationStatus (verified 2026).  Pinning is Studio-only.
# So this engine:
#   1. posts the question automatically (official API),
#   2. prints a ONE-CLICK pin instruction with a direct link,
#      because unofficial "pin via internal web API" tricks are
#      ToS-violating and fragile -- not used in production code.
#
# OAUTH SCOPE
# -----------
# Posting requires 'youtube.force-ssl'.  The token must be
# (re-)authorized with the combined scope set; run:
#     python -m app.youtube.comments --reauth
# =========================================================

import ast
import json
import os
import random
import sys
import time
from collections import deque
from pathlib import Path

import requests

from googleapiclient.errors import HttpError

from app.countries import display_name, is_widely_recognized


# ---------------------------------------------------------
# AI ENGAGEMENT COMMENT PROMPT
#
# Preferred over the rotating templates further below when
# the SAME Groq client that writes every script/title is
# reachable: the question gets tied to THIS video's topic
# and numbers instead of a generic rotation.  Templates
# remain the offline fallback so engagement never depends
# on the LLM being up.
#
# TONE CONTRACT (CHANNEL_BLUEPRINT §4): contractions, direct
# viewer address, zero AI-speak.  Tweak the wording HERE to
# retune the voice -- no pipeline logic needs to change.
# NOTE: the reply is parsed as JSON {"comment": "..."} via
# GroqLLM.generate_structured, hence the doubled braces.
# ---------------------------------------------------------

ENGAGEMENT_COMMENT_PROMPT_TEMPLATE = (
    "You write the channel's own engagement comment for a "
    "data-story YouTube Short that was just uploaded.\n\n"
    "VIDEO TOPIC: {topic}\n"
    "HEADLINE FACTS SHOWN IN THE VIDEO: {facts}\n\n"
    "Write ONE short comment, posted as the channel itself, "
    "that sparks replies.\n"
    "Hard rules:\n"
    "- Reply with ONLY raw JSON: "
    "{{\"comment\": \"<your comment>\"}}\n"
    "- The comment must be ONE punchy, casual question "
    "inviting viewers to react, argue, or pick a side "
    "about these exact facts (e.g. 'Team Monaco or team "
    "upset? Defend your pick 👇').\n"
    "- Tie it to the specific topic/numbers above -- "
    "generic questions are useless.\n"
    "- Under 100 characters.\n"
    "- Return ONLY the comment text inside the JSON -- no "
    "preamble, no surrounding quotes, no hashtags.\n"
    "- End with ONE fitting emoji such as 👇 🤔 😳 where "
    "it fits naturally."
)

# Hard cap mirroring the prompt rule (~100 chars); keeps a
# chatty model from shipping a paragraph as a comment.
ENGAGEMENT_COMMENT_MAX_CHARS = 100


# ---------------------------------------------------------
# IDEMPOTENCY STATE -- one comment per video, ever
# ---------------------------------------------------------

POSTED_STATE_PATH = str(
    Path(__file__).resolve().parents[2]
    / "data"
    / "posted_comments.json"
)


def _load_posted_state() -> dict:

    try:

        with open(
            POSTED_STATE_PATH,
            "r",
            encoding="utf-8",
        ) as handle:

            return json.load(handle)

    except Exception:

        return {}


def already_posted(video_id) -> bool:

    return str(video_id) in _load_posted_state()


def _record_posted(
    video_id,
    comment_id,
    text,
) -> None:

    state = _load_posted_state()

    state[str(video_id)] = {
        "comment_id": comment_id,
        "text": text,
        "posted_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
    }

    try:

        os.makedirs(
            os.path.dirname(POSTED_STATE_PATH),
            exist_ok=True,
        )

        with open(
            POSTED_STATE_PATH,
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                state,
                handle,
                indent=2,
            )

    except OSError:

        pass


# ---------------------------------------------------------
# CONFIG-DRIVEN QUESTION POOL (human-touch layer)
#
# ENGAGEMENT_COMMENT_FALLBACKS (config.py) appends your own
# question lines to the rotation pool so the wording can be
# tuned without touching code.  Only well-formed questions
# (must end with "?") are accepted; blank or malformed
# entries are silently dropped so a bad .env edit can never
# break the engine.
# ---------------------------------------------------------

def _config_question_templates() -> list:

    try:

        from app.config import parse_json_setting, settings

        raw = parse_json_setting(
            getattr(settings, "ENGAGEMENT_COMMENT_FALLBACKS", ""),
            [],
        )

    except Exception:

        return []

    if not isinstance(raw, list):

        return []

    extra = []

    for index, item in enumerate(raw):

        text = str(item or "").strip()

        if text.endswith("?"):

            extra.append(
                {
                    "id": f"config_{index}",
                    "needs_winner": False,
                    "text": text,
                }
            )

        elif text:

            # Visible, not silent: a malformed .env edit should
            # be noticed and fixed, never quietly swallowed.
            print(
                f"[COMMENTS] ENGAGEMENT_COMMENT_FALLBACKS"
                f"[{index}] dropped (must end with '?'): "
                f"{text!r}"
            )

    return extra


class CommentEngine:

    # -----------------------------------------------------
    # ROTATING QUESTION TEMPLATES
    #
    # Voice rules (CHANNEL_BLUEPRINT §4): contractions, direct
    # viewer address, zero AI-speak.  Every template MUST be a
    # question.  needs_winner=True templates interpolate facts;
    # they drop out of the pool whenever the winner is unknown.
    # -----------------------------------------------------

    QUESTION_TEMPLATES = [
        {"id": "honest_guess", "needs_winner": True,
         "text": "Be honest — did you guess {winner} would top this?"},
        {"id": "expected_win", "needs_winner": True,
         "text": "{winner} at #1… who did YOU expect to win?"},
        {"id": "keep_crown", "needs_winner": True,
         "text": "{year}: {winner} leads {subject}. Think they keep the crown next year?"},
        {"id": "robbed", "needs_winner": True,
         "text": "Who should've been #1 instead of {winner}?"},
        {"id": "guessed_winner", "needs_winner": True,
         "text": "Would you have guessed {winner}? Be honest."},
        {"id": "your_country", "needs_winner": False,
         "text": "Did your country make the list 👀?"},
        {"id": "surprised", "needs_winner": False,
         "text": "Which entry surprised you the most?"},
        {"id": "wrong_answers", "needs_winner": False,
         "text": "Agree with this ranking — or robbed? Wrong answers only."},
        {"id": "first_guess", "needs_winner": False,
         "text": "Before you rewatch: first guess who's #1?"},
        {"id": "dare_rank", "needs_winner": False,
         "text": "Drop your country's rank below if you dare."},
    ]

    # Merge the config pool in (additive, not replacing the
    # curated set) so ENGAGEMENT_COMMENT_FALLBACKS lines join
    # the same anti-repeat rotation.
    QUESTION_TEMPLATES = (
        QUESTION_TEMPLATES + _config_question_templates()
    )

    # Anti-repeat within a process lifetime: don't reuse a
    # template until every other eligible one has been tried.
    _recent_ids: deque = deque()

    # Ledger check exposed on the class too: diagnostics and
    # tests call it either as CommentEngine.already_posted()
    # or as the module-level already_posted(); both resolve
    # to the SAME function defined above the class.
    already_posted = staticmethod(already_posted)

    # -----------------------------------------------------
    # FACT EXTRACTION FROM TOPIC DATA
    # -----------------------------------------------------

    @staticmethod
    def _clean_entity(raw) -> str:
        """
        Normalize a chart entity into a display-ready name.

        Handles wide-data tuple indexes like "('DEU', 'Germany')"
        produced upstream, plain names, and ISO-ish codes.
        """

        text = str(raw or "").strip()

        if not text:
            return ""

        if text.startswith("("):

            try:

                parsed = ast.literal_eval(text)

                if isinstance(parsed, (tuple, list)) and parsed:
                    text = str(parsed[-1]).strip()

            except (ValueError, SyntaxError):

                # Fallback: last quoted segment inside parens.
                tail = text.rstrip(")").split(",")[-1]
                text = tail.strip().strip("'\"")

        if is_widely_recognized(text):

            try:
                return display_name(text)

            except Exception:
                pass

        cleaned = text.replace("_", " ").strip()

        return cleaned[:1].upper() + cleaned[1:] if cleaned else ""

    @classmethod
    def _story_facts(cls, topic_data: dict):
        """
        Pull (winner, subject, year) out of topic_data.

        Anything unavailable degrades gracefully to "" so generic
        templates still work.
        """

        data = topic_data or {}

        metrics = data.get("story_metrics") or {}

        winner = ""

        series = metrics.get("latest_sorted")

        try:

            if series is not None and len(series):
                winner = cls._clean_entity(series.index[0])

        except Exception:
            winner = ""

        subject = str(
            data.get("topic")
            or data.get("indicator_name")
            or ""
        ).strip()

        if not subject:
            subject = "this ranking"

        year = ""

        try:
            year = str(int(metrics.get("end_year") or ""))

        except (TypeError, ValueError):
            year = ""

        return winner, subject, year


    # -----------------------------------------------------
    # QUESTION GENERATION (rotating, personalized)
    # -----------------------------------------------------

    @classmethod
    def generate_question_comment(
        cls,
        topic_data: dict
    ) -> str:
        """
        Build ONE question-form engagement comment for this video.

        Personalizes with winner/subject/year when the story data
        provides them; otherwise rotates generic questions only.
        Guarantees a non-empty string ending with '?'.
        """

        winner, subject, year = cls._story_facts(
            topic_data or {}
        )

        eligible = [
            tpl for tpl in cls.QUESTION_TEMPLATES
            if not (tpl["needs_winner"] and not winner)
        ]

        # Anti-repeat: prefer templates not used recently.
        fresh = [
            tpl for tpl in eligible
            if tpl["id"] not in cls._recent_ids
        ]

        pool = fresh or eligible

        template = random.choice(pool)

        cls._recent_ids.append(template["id"])

        max_recent = max(1, len(cls.QUESTION_TEMPLATES) - 1)

        while len(cls._recent_ids) > max_recent:
            cls._recent_ids.popleft()

        try:

            text = template["text"].format(
                winner=winner or "this entry",
                subject=subject,
                year=year or "today",
            )

        except (KeyError, IndexError, ValueError):

            text = "Which entry surprised you the most?"

        # Normalize whitespace and guarantee CLEAN question
        # form: strip trailing periods/exclamations before the
        # mark so we never emit artifacts like "…honest.?"
        text = " ".join(text.split()).strip()

        text = text.rstrip("!. ").strip()

        if not text.endswith("?"):
            text += "?"

        if len(text) > 280:
            text = text[:277].rstrip() + "?"

        return text

    # -----------------------------------------------------
    # DIAGNOSTICS -- TOKEN / VISIBILITY / AUTO-PIN
    # -----------------------------------------------------

    FORCE_SSL_SCOPE_SUFFIX = "youtube.force-ssl"

    @staticmethod
    def token_has_force_ssl() -> bool:
        """
        Cheap LOCAL check: does the saved OAuth token already
        include the force-ssl scope we need to post comments?
        Reads youtube_token.json without any network call.
        """

        import json as _json

        from app.youtube.uploader import TOKEN_FILE

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
                CommentEngine
                .FORCE_SSL_SCOPE_SUFFIX
                in scopes
            )

        except Exception:

            return False

    @staticmethod
    def _load_credentials():
        """
        Fresh (refreshed if needed) Credentials for internal-API
        calls.  Returns None when unavailable.
        """

        from google.auth.transport.requests import Request

        from google.oauth2.credentials import Credentials

        from app.youtube.uploader import SCOPES, TOKEN_FILE

        if not os.path.exists(TOKEN_FILE):

            return None

        try:

            credentials = (
                Credentials.from_authorized_user_file(
                    TOKEN_FILE,
                    SCOPES,
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

                    handle.write(credentials.to_json())

            if not credentials.valid:

                return None

            return credentials

        except Exception:

            return None

    @classmethod
    def _verify_comment_visible(
        cls,
        youtube,
        video_id: str,
        comment_id,
    ) -> str:
        """
        Confirm where our comment actually landed by scanning the
        video's threads in every moderation bucket:

            published | heldForReview | likelySpam | NOT_FOUND

        This answers WHY a comment might not be shown.
        """

        for bucket in (
            "published",
            "heldForReview",
            "likelySpam",
        ):

            try:

                response = (
                    youtube.commentThreads()
                    .list(
                        part="snippet",
                        videoId=str(video_id),
                        moderationStatus=bucket,
                        maxResults=100,
                    )
                    .execute()
                )

            except Exception:

                continue

            for item in response.get("items", []):

                if item.get("id") == comment_id:

                    return bucket

        return "NOT_FOUND"

    @classmethod
    def _attempt_experimental_pin(
        cls,
        video_id: str,
        comment_id,
    ) -> dict:
        """
        EXPERIMENTAL real auto-pin.

        Uses YouTube's INTERNAL creator endpoint (the same call
        family Studio's own web client uses) with your OAuth
        bearer token.  This endpoint is UNDOCUMENTED, its payload
        shape can change without notice, and automated use sits
        outside the published API Terms.  Gated behind
        AUTO_PIN_INTERNAL_API=true.  NEVER raises.
        """

        if os.getenv(
            "AUTO_PIN_INTERNAL_API",
            "false"
        ).lower() != "true":

            return {
                "pinned": False,
                "pin_note": "INTERNAL_API_DISABLED",
            }

        if not comment_id:

            return {
                "pinned": False,
                "pin_note": "NO_COMMENT_ID",
            }

        credentials = cls._load_credentials()

        if not credentials or not credentials.token:

            return {
                "pinned": False,
                "pin_note": "NO_VALID_TOKEN",
            }

        url = (
            "https://www.youtube.com/youtubei/v1/"
            "comment/perform_comment_action"
            "?prettyPrint=false"
        )

        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20260820.01.00",
                    "hl": "en",
                }
            },
            "actions": [
                {
                    "action": "PIN_COMMENT",
                    "commentId": str(comment_id),
                }
            ],
        }

        headers = {
            "Authorization": (
                f"Bearer {credentials.token}"
            ),
            "Content-Type": "application/json",
        }

        try:

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=15,
            )

        except Exception as exc:

            return {
                "pinned": False,
                "pin_note": f"PIN_NETWORK_ERROR:{exc}",
            }

        if response.status_code == 200:

            return {
                "pinned": True,
                "pin_note": (
                    "PIN_SENT_UNOFFICIAL "
                    "(verify in Studio)"
                ),
            }

        return {
            "pinned": False,
            "pin_note": (
                f"PIN_HTTP_{response.status_code}:"
                f"{response.text[:160]}"
            ),
        }

    # -----------------------------------------------------
    # POSTING (official API; pin = experimental + guidance)
    # -----------------------------------------------------


    @staticmethod
    def _pin_guidance(video_id: str, comment_id) -> str:
        """
        Pinning is not exposed by the Data API v3, so emit the
        exact one-click manual step.  Returns a short note string.
        """

        studio_url = (
            f"https://studio.youtube.com/video/{video_id}/comments"
        )

        print("\n📌 PIN THIS COMMENT (one click):")

        print(
            "   YouTube Studio -> Comments -> find your new "
            "question -> Menu (...) -> Pin"
        )

        print(f"   Direct: {studio_url}")

        return (
            f"PIN_MANUAL (Studio -> {studio_url})"
            if comment_id
            else "PIN_MANUAL"
        )

    @classmethod
    def post_question_comment(
        cls,
        video_id: str,
        topic_data: dict = None,
        youtube=None,
    ) -> dict:
        """
        Post the rotating question AS THE CHANNEL on `video_id`.

        Never raises: every failure mode degrades into the returned
        result dict so the upload pipeline keeps flowing.

        Returns keys:
            posted      bool   -- comment created successfully
            pinned      bool   -- always False (API limitation)
            comment_id  str|None
            text        str    -- the question that was posted
            url         str|None -- permalink to the comment
            note        str    -- human-readable status/detail
        """

        result = {
            "posted": False,
            "pinned": False,
            "comment_id": None,
            "text": "",
            "url": None,
            "note": "",
            "moderation_status": None,
        }

        if not video_id:

            result["note"] = "NO_VIDEO_ID"

            return result

        text = cls.generate_question_comment(topic_data or {})

        result["text"] = text

        if youtube is None:

            # Pre-flight: catch the #1 failure mode BEFORE any
            # network call -- a token authorized before the
            # force-ssl scope was added.
            if not cls.token_has_force_ssl():

                result["note"] = (
                    "SCOPE_MISSING — youtube_token.json lacks "
                    "youtube.force-ssl. Fix: run "
                    "'python -m app.youtube.comments --reauth'"
                )

                print(
                    f"\n⚠️ Comment engine: {result['note']}"
                )

                return result

            from app.youtube.uploader import YouTubeUploader

            youtube = YouTubeUploader.authenticate()

        body = {
            "snippet": {
                "videoId": str(video_id),
                # NOTE: the current Data API requires the
                # CANONICAL nested shape; the legacy flat
                # snippet.textOriginal is rejected with
                # 400 commentTextRequired ("Comments
                # cannot be be empty") even for non-empty
                # text -- which is why production posts
                # silently failed while mocked tests passed.
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": text,
                    }
                },
            }
        }

        try:

            response = (
                youtube.commentThreads()
                .insert(part="snippet", body=body)
                .execute()
            )

        except HttpError as exc:

            result["note"] = _youtube_error_note(
                exc
            )

            print(f"\n⚠️ Comment engine: {result['note']}")

            return result

        except Exception as exc:

            result["note"] = f"ERROR: {exc}"

            print(f"\n⚠️ Comment engine: {result['note']}")

            return result

        comment_id = response.get("id")

        result.update(
            posted=True,
            comment_id=comment_id,
            url=(
                f"https://www.youtube.com/watch?v={video_id}"
                f"&lc={comment_id}"
                if comment_id else None
            ),
        )

        # Idempotency ledger: never auto-comment a
        # video twice, even across batch re-runs.
        _record_posted(
            video_id,
            comment_id,
            text,
        )

        print("\n💬 QUESTION COMMENT POSTED:")

        print(f"   {text}")

        if result["url"]:
            print(f"   {result['url']}")

        # -------------------------------------------------
        # VISIBILITY VERIFICATION -- answers "why is my
        # comment not shown?" by locating it in YouTube's
        # moderation buckets.
        # -------------------------------------------------

        moderation = cls._verify_comment_visible(
            youtube,
            str(video_id),
            comment_id,
        )

        result["moderation_status"] = moderation

        if moderation == "published":

            print("\n✅ Comment confirmed LIVE.")

        elif moderation == "heldForReview":

            print(
                "\n⚠️ Comment is HELD FOR REVIEW by "
                "YouTube — approve it in Studio -> "
                "Comments -> 'Held for review'."
            )

        elif moderation == "likelySpam":

            print(
                "\n⚠️ Comment flagged as LIKELY SPAM — "
                "approve it in Studio to make it visible."
            )

        else:

            print(
                "\n⏳ Comment posted but not indexed yet "
                "(YouTube lag). Recheck in a minute."
            )

        # -------------------------------------------------
        # PINNING: try the EXPERIMENTAL internal endpoint;
        # otherwise fall back to guided one-click (+ optional
        # browser auto-open).
        # -------------------------------------------------

        video_str = str(video_id)

        pin_result = cls._attempt_experimental_pin(
            video_str,
            comment_id,
        )

        result["pinned"] = pin_result.get(
            "pinned", False
        )

        if pin_result.get("pinned"):

            result["note"] = pin_result.get(
                "pin_note", "PIN_SENT"
            )

            print(
                f"\n📌 AUTO-PIN sent "
                f"(experimental): {result['note']}"
            )

        else:

            pin_reason = pin_result.get(
                "pin_note", ""
            )

            print(
                f"\n📌 Auto-pin unavailable "
                f"({pin_reason})."
            )

            studio_url = (
                f"https://studio.youtube.com/"
                f"video/{video_str}/comments"
            )

            result["note"] = cls._pin_guidance(
                video_str,
                comment_id,
            )

            if os.getenv(
                "AUTO_OPEN_PIN_BROWSER",
                "false"
            ).lower() == "true":

                try:

                    import webbrowser

                    webbrowser.open(studio_url)

                    print(
                        f"\n🌐 Opened Studio comments "
                        f"in your browser."
                    )

                except Exception:

                    pass

        return result


# =========================================================
# AI ENGAGEMENT COMMENT -- GENERATE + POST
#
# Two small entry points called by run.py immediately after
# a successful YouTube upload:
#
#   1. generate_engagement_comment(topic_context)
#      Asks the SAME Groq client that writes every
#      script/title for ONE punchy question tied to this
#      video's topic + headline numbers.  RAISES on failure
#      so the caller can fall back to the template engine.
#
#   2. post_comment_to_video(video_id, comment_text)
#      Posts that text AS THE CHANNEL via the official
#      commentThreads.insert endpoint, reusing the same
#      OAuth client/auth that uploads videos.  NEVER raises
#      -- failures degrade into result['note'] exactly like
#      CommentEngine.post_question_comment.
# =========================================================

def _engagement_facts(topic_context: dict) -> tuple:
    """
    Build (subject, facts_line) for the LLM prompt out of the
    SAME topic_data dict that fed the title/script prompts --
    nothing is refetched and nothing is hardcoded here.
    """

    winner, subject, year = (
        CommentEngine._story_facts(
            topic_context or {}
        )
    )

    story_type = str(
        (topic_context or {}).get(
            "story_type",
            ""
        )
    ).strip()

    parts = []

    if subject:

        parts.append(f"subject: {subject}")

    if story_type:

        parts.append(
            f"story angle: "
            f"{story_type.replace('_', ' ')}"
        )

    if winner:

        parts.append(f"#1 entry: {winner}")

    if year:

        parts.append(f"latest year: {year}")

    try:

        series = (
            (topic_context or {})
            .get("story_metrics", {})
            .get("latest_sorted")
        )

        if series is not None and len(series):

            parts.append(
                f"#1 value: {series.iloc[0]:g}"
            )

    except Exception:

        pass

    return subject, "; ".join(parts)


def generate_engagement_comment(
    topic_context: dict = None,
) -> str:
    """
    Generate ONE topic-relevant engagement question via Groq.

    Returns the cleaned comment text (<=
    ENGAGEMENT_COMMENT_MAX_CHARS).  ANY failure raises so
    run.py can log it and fall back to the rotating
    CommentEngine templates without endangering the upload.
    """

    # Imported lazily so importing this module (tests, CLI
    # helpers) never requires GROQ_API_KEY to exist.
    from app.groq_client import GroqLLM

    subject, facts = _engagement_facts(
        topic_context or {}
    )

    if not facts:

        raise ValueError(
            "No topic facts available for an "
            "engagement comment."
        )

    prompt = ENGAGEMENT_COMMENT_PROMPT_TEMPLATE.format(
        topic=subject or "a data ranking",
        facts=facts,
    )

    payload = GroqLLM.generate_structured(
        prompt,
        temperature=0.95,
    )

    comment = ""

    if isinstance(payload, dict):

        comment = str(
            payload.get("comment") or ""
        ).strip()

    # Sanitize: strip markdown fences / stray wrapping
    # quotes, then collapse ALL whitespace (incl. newlines)
    # into single spaces -- comments are one line only.
    comment = comment.strip("`\"' ")

    comment = " ".join(comment.split())

    if not comment:

        raise ValueError(
            "Groq returned an empty "
            "engagement comment."
        )

    if len(comment) > ENGAGEMENT_COMMENT_MAX_CHARS:

        comment = comment[
            :ENGAGEMENT_COMMENT_MAX_CHARS
        ]

        # Cut back to the last full word, then trim dangling
        # punctuation so the truncation stays readable.
        comment = (
            comment.rsplit(" ", 1)[0]
            .rstrip(" ,;:-")
            .strip()
        )

    return comment


def _youtube_error_note(exc) -> str:
    """Collapse an HttpError into an actionable note that keeps
    YouTube's REAL reason visible (quota vs comments-disabled
    vs scope/account state) instead of one blanket guess.
    """

    status = getattr(
        getattr(exc, "resp", None), "status", None
    )

    try:
        status = int(status)

    except (TypeError, ValueError):
        pass

    api_reason = ""

    try:

        import json as _json

        payload = _json.loads(
            (getattr(exc, "content", b"") or b"")
            .decode("utf-8")
        )

        errors = (
            payload.get("error", {})
            .get("errors", [])
        )

        if errors:

            api_reason = str(
                errors[0].get("reason", "")
            )

    except Exception:
        pass

    if status == 403:

        if api_reason == "quotaexceeded":

            return (
                "FORBIDDEN[quotaexceeded] -- daily "
                "YouTube API quota exhausted; retry "
                "after quota reset."
            )

        if api_reason == "commentsDisabled":

            return (
                "FORBIDDEN[commentsDisabled] -- "
                "comments are turned off for this "
                "video."
            )

        return (
            f"FORBIDDEN[{api_reason or 'forbidden'}] "
            "-- insufficient permissions for "
            "commentThreads.insert. Usual causes: "
            "stale/mis-scoped OAuth grant (fix: "
            "'python -m app.youtube.comments "
            "--reauth'), wrong channel identity, or "
            "video state."
        )

    if status == 400:

        return f"BAD_REQUEST: {exc}"

    return f"HTTP_{status}: {exc}"


def post_comment_to_video(
    video_id: str,
    comment_text: str,
    youtube=None,
) -> dict:
    """
    Post `comment_text` as a TOP-LEVEL comment on `video_id`,
    authenticated AS THE CHANNEL (the same OAuth client/auth
    used to upload videos).

    Never raises: every failure mode degrades into
    result['note'] so the upload pipeline keeps flowing.

    Returns keys:
        posted             bool   -- comment created ok
        comment_id         str|None
        text               str    -- exact text posted
        url                str|None -- permalink
        note               str    -- status/detail
        moderation_status  str|None
    """

    result = {
        "posted": False,
        "comment_id": None,
        "text": comment_text or "",
        "url": None,
        "note": "",
        "moderation_status": None,
    }

    if not video_id or not (
        comment_text or ""
    ).strip():

        result["note"] = (
            "MISSING_VIDEO_ID_OR_TEXT"
        )

        return result

    # Idempotency ledger: never auto-comment a video twice,
    # even across batch re-runs.
    if already_posted(video_id):

        result["note"] = "ALREADY_POSTED"

        return result

    if youtube is None:

        # Pre-flight: catch the #1 failure mode BEFORE any
        # network call -- a token authorized before the
        # force-ssl scope was added.
        if not CommentEngine.token_has_force_ssl():

            result["note"] = (
                "SCOPE_MISSING — youtube_token.json lacks "
                "youtube.force-ssl. Fix: run "
                "'python -m app.youtube.comments --reauth'"
            )

            print(
                f"\n⚠️ Engagement comment: "
                f"{result['note']}"
            )

            return result

        from app.youtube.uploader import YouTubeUploader

        youtube = (
            YouTubeUploader.authenticate()
        )

    body = {
        "snippet": {
            "videoId": str(video_id),
            # Canonical nested shape (see note in
            # CommentEngine.post_question_comment): the flat
            # variant gets 400 commentTextRequired in
            # production even for non-empty text.
            "topLevelComment": {
                "snippet": {
                    "textOriginal": comment_text,
                }
            },
        }
    }

    try:

        response = (
            youtube.commentThreads()
            .insert(part="snippet", body=body)
            .execute()
        )

    except HttpError as exc:

        result["note"] = _youtube_error_note(exc)

        print(
            f"\n⚠️ Engagement comment failed: "
            f"{result['note']}"
        )

        return result

    except Exception as exc:

        result["note"] = f"ERROR: {exc}"

        print(
            f"\n⚠️ Engagement comment failed: "
            f"{result['note']}"
        )

        return result

    comment_id = (
        response.get("snippet", {})
        .get("topLevelComment", {})
        .get("id")
    ) or response.get("id")

    result.update(
        posted=True,
        comment_id=comment_id,
        url=(
            f"https://www.youtube.com/watch?v={video_id}"
            f"&lc={comment_id}"
            if comment_id else None
        ),
    )

    # Record BEFORE anything else can go wrong so re-runs
    # can never double-post.
    _record_posted(
        video_id,
        comment_id,
        comment_text,
    )

    # REQUIRED DEBUG LOG: the EXACT text that was posted.
    print("\n💬 ENGAGEMENT COMMENT POSTED:")

    print(f"   {comment_text}")

    if result["url"]:
        print(f"   {result['url']}")

    # -----------------------------------------------------
    # VISIBILITY VERIFICATION -- answers "why is my comment
    # not shown?" by locating it in YouTube's moderation
    # buckets.
    # -----------------------------------------------------

    moderation = (
        CommentEngine._verify_comment_visible(
            youtube,
            str(video_id),
            comment_id,
        )
    )

    result["moderation_status"] = moderation

    if moderation == "published":

        print("\n✅ Comment confirmed LIVE.")

    elif moderation == "heldForReview":

        print(
            "\n⚠️ Comment is HELD FOR REVIEW by "
            "YouTube — approve it in Studio -> "
            "Comments -> 'Held for review'."
        )

    elif moderation == "likelySpam":

        print(
            "\n⚠️ Comment flagged as LIKELY SPAM — "
            "approve it in Studio to make it visible."
        )

    else:

        print(
            "\n⏳ Comment posted but not indexed yet "
            "(YouTube lag). Recheck in a minute."
        )

    # -----------------------------------------------------
    # PINNING: same policy as the template engine --
    # experimental internal auto-pin when enabled, otherwise
    # guided one-click Studio instructions.
    # -----------------------------------------------------

    pin_result = (
        CommentEngine._attempt_experimental_pin(
            str(video_id),
            comment_id,
        )
    )

    if pin_result.get("pinned"):

        result["note"] = pin_result.get(
            "pin_note", "PIN_SENT"
        )

        print(
            f"\n📌 AUTO-PIN sent "
            f"(experimental): {result['note']}"
        )

    else:

        result["note"] = (
            CommentEngine._pin_guidance(
                str(video_id),
                comment_id,
            )
        )

    return result


# ---------------------------------------------------------
# MODULE-LEVEL ALIAS
#
# The CLI (`--post VIDEO_ID`) and post_recent() call this as
# a bare name, and some scripts/tests do too.  Thin
# delegation to the CommentEngine implementation -- no
# behavior change, just makes those call sites valid.
# ---------------------------------------------------------

def post_question_comment(
    video_id: str,
    topic_data: dict = None,
    youtube=None,
) -> dict:

    """
    Module-level wrapper around
    CommentEngine.post_question_comment.
    """

    return CommentEngine.post_question_comment(
        video_id=video_id,
        topic_data=topic_data,
        youtube=youtube,
    )


# =========================================================
# RE-AUTH HELPER + CLI
# =========================================================

def force_reauth() -> bool:
    """
    Delete the stale OAuth token and re-run consent with the
    FULL current scope set (upload + readonly + force-ssl).
    Required once after adding a scope.
    """

    import os

    from app.youtube.uploader import TOKEN_FILE, YouTubeUploader

    if os.path.exists(TOKEN_FILE):

        os.remove(TOKEN_FILE)

        print(f"🗑️ Removed stale token: {TOKEN_FILE}")

    try:

        YouTubeUploader.authenticate()

        print(
            "\n✅ Re-auth complete. Comment posting is now "
            "authorized."
        )

        return True

    except Exception as exc:

        print(f"\n❌ Re-auth failed: {exc}")

        return False


# =========================================================
# BATCH RETRO-POST -- comment the N most recent uploads
# =========================================================

def post_recent(count=1, youtube=None, rows=None):
    """
    Post the rotating question to the N most recent uploads
    found in history.db, SKIPPING any video that already got
    its comment (ledger: data/posted_comments.json).

    `rows` overrides the DB query for offline tests:
        [(youtube_id, title), ...] newest first.
    """

    results = []

    if rows is None:

        import sqlite3

        from app.config import settings

        try:

            con = sqlite3.connect(
                settings.DB_PATH
            )

            rows = con.execute(
                "select youtube_id, title "
                "from video_history "
                "where youtube_id is not null "
                "and youtube_id != '' "
                "order by rowid desc "
                "limit ?",
                (int(count),),
            ).fetchall()

            con.close()

        except Exception as exc:

            print(
                f"❌ Could not read history.db: {exc}"
            )

            return results

    done = 0

    for yid, title in rows:

        yid = str(yid or "").strip()

        if not yid:

            continue

        if already_posted(yid):

            print(
                f"\n⏭️  {yid} already has its "
                f"question comment — skipping."
            )

            results.append((yid, "skipped"))

            continue

        done += 1

        print(f"\n[{done}] {str(title)[:60]}")

        print(f"    https://youtu.be/{yid}")

        outcome = post_question_comment(
            video_id=yid,
            topic_data=None,
            youtube=youtube,
        )

        results.append(
            (
                yid,
                "posted"
                if outcome.get("posted")
                else outcome.get("note", "failed"),
            )
        )

    posted_n = sum(
        1 for _, s in results if s == "posted"
    )

    skipped_n = sum(
        1 for _, s in results if s == "skipped"
    )

    failed_n = sum(
        1
        for _, s in results
        if s not in ("posted", "skipped")
    )

    print(
        f"\n✅ Batch done: {posted_n} posted, "
        f"{skipped_n} skipped, {failed_n} failed."
    )

    return results


# =========================================================
# DOCTOR -- diagnose "comment not shown / not pinned"
# =========================================================

def run_doctor(video_id: str, youtube=None) -> bool:
    """
    Full health check for one video's comment/pin state:

      1. local OAuth token scope audit
      2. video status (public? processing? kids-restricted?)
      3. comment buckets: published / heldForReview / likelySpam
      4. pin capability verdict

    Usage:  python -m app.youtube.comments --doctor VIDEO_ID
    """

    print("\n" + "=" * 60)

    print(f"🩺 COMMENT DOCTOR — video {video_id}")

    print("=" * 60)

    healthy = True

    # -----------------------------------------------------
    # 1. Local token scope
    # -----------------------------------------------------

    has_scope = CommentEngine.token_has_force_ssl()

    print(
        f"\n1️⃣ OAuth token force-ssl scope: "
        f"{'✅ present' if has_scope else '❌ MISSING'}"
    )

    if not has_scope:

        healthy = False

        print(
            "   FIX: python -m app.youtube.comments --reauth"
        )

    # -----------------------------------------------------
    # 2-3. Live checks via the API
    # -----------------------------------------------------

    if youtube is None:

        from app.youtube.uploader import YouTubeUploader

        youtube = YouTubeUploader.authenticate()

    try:

        video = (
            youtube.videos()
            .list(
                part="status,snippet",
                id=str(video_id),
            )
            .execute()
        )

        items = video.get("items", [])

        if not items:

            print(
                f"\n2️⃣ Video lookup: ❌ no video found "
                f"for id {video_id}"
            )

            return False

        vstatus = items[0].get("status", {})

        privacy = vstatus.get(
            "privacyStatus", "?"
        )

        upload_status = vstatus.get(
            "uploadStatus", "?"
        )

        kids = vstatus.get("madeForKids")

        print(
            f"\n2️⃣ Video: upload={upload_status} "
            f"privacy={privacy} "
            f"madeForKids={kids}"
        )

        if privacy != "public":

            healthy = False

            print(
                "   ⚠️ Video is NOT public — comments "
                "won't be visible to viewers until it is."
            )

        if kids is True:

            healthy = False

            print(
                "   ❌ Made-for-Kids videos have "
                "comments DISABLED entirely."
            )

        bucket_counts = {}

        for bucket in (
            "published",
            "heldForReview",
            "likelySpam",
        ):

            try:

                response = (
                    youtube.commentThreads()
                    .list(
                        part="snippet",
                        videoId=str(video_id),
                        moderationStatus=bucket,
                        maxResults=100,
                    )
                    .execute()
                )

                threads = response.get(
                    "items", []
                )

            except Exception as exc:

                print(
                    f"\n3️⃣ Could not list comments "
                    f"({bucket}): {exc}"
                )

                return False

            bucket_counts[bucket] = len(threads)

        held = bucket_counts.get(
            "heldForReview", 0
        )

        spam = bucket_counts.get(
            "likelySpam", 0
        )

        published = bucket_counts.get(
            "published", 0
        )

        print(
            f"\n3️⃣ Comments: {published} published, "
            f"{held} held for review, {spam} flagged spam"
        )

        if held or spam:

            healthy = False

            print(
                "   ⚠️ Some comments need approval in "
                "Studio -> Comments before they show."
            )

    except HttpError as exc:

        print(f"\n❌ YouTube API error: {exc}")

        return False

    # -----------------------------------------------------
    # 4. Pin verdict
    # -----------------------------------------------------

    internal_on = os.getenv(
        "AUTO_PIN_INTERNAL_API",
        "false"
    ).lower() == "true"

    print(
        f"\n4️⃣ Pinning: official API does NOT support it."
    )

    print(
        f"   Experimental auto-pin "
        f"(AUTO_PIN_INTERNAL_API): "
        f"{'🧪 ON' if internal_on else 'off'}"
    )

    print(
        "   Manual: Studio -> this video -> Comments -> "
        "Menu (...) -> Pin"
    )

    print("\n" + "=" * 60)

    print(
        "🩺 VERDICT: "
        + (
            "looks healthy — comment should be live; "
            "pin manually or enable AUTO_PIN_INTERNAL_API=true"
            if healthy
            else "issues found above — fix them and re-run"
        )
    )

    print("=" * 60)

    return healthy


if __name__ == "__main__":

    if "--reauth" in sys.argv:

        sys.exit(0 if force_reauth() else 1)

    if "--post" in sys.argv:

        idx = sys.argv.index("--post")

        target = (
            sys.argv[idx + 1]
            if len(sys.argv) > idx + 1
            else ""
        )

        if not target:

            print(
                "Usage: python -m app.youtube.comments "
                "--post VIDEO_ID"
            )

            sys.exit(2)

        outcome = post_question_comment(target)

        sys.exit(0 if outcome.get("posted") else 1)

    if "--post-recent" in sys.argv:

        idx = sys.argv.index("--post-recent")

        raw = (
            sys.argv[idx + 1]
            if (
                len(sys.argv) > idx + 1
                and sys.argv[idx + 1].isdigit()
            )
            else "1"
        )

        post_recent(int(raw))

        sys.exit(0)

    if "--doctor" in sys.argv:

        idx = sys.argv.index("--doctor")

        target = (
            sys.argv[idx + 1]
            if len(sys.argv) > idx + 1
            else ""
        )

        if not target:

            print(
                "Usage: python -m app.youtube.comments "
                "--doctor VIDEO_ID"
            )

            sys.exit(2)

        sys.exit(
            0 if run_doctor(target) else 1
        )

    print(__doc__)


