import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# =========================================================
# YOUTUBE API CONFIGURATION
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

TOKEN_FILE = "youtube_token.json"

# Google OAuth client credentials file
CLIENT_SECRET_FILE = "client_secret.json"


class YouTubeUploader:

    # =====================================================
    # AUTHENTICATION
    # =====================================================

    @staticmethod
    def authenticate():

        print("\n" + "=" * 60)
        print("🔐 YOUTUBE AUTHENTICATION")
        print("=" * 60)

        credentials = None

        # -------------------------------------------------
        # Load existing token
        # -------------------------------------------------

        if os.path.exists(TOKEN_FILE):

            print(
                f"🔑 Loading existing OAuth token: "
                f"{TOKEN_FILE}"
            )

            try:

                credentials = (
                    Credentials.from_authorized_user_file(
                        TOKEN_FILE,
                        SCOPES
                    )
                )

            except Exception as exc:

                print(
                    f"⚠️ Could not load existing token: "
                    f"{exc}"
                )

                credentials = None

        # -------------------------------------------------
        # Refresh token if necessary
        # -------------------------------------------------

        if credentials:

            if (
                credentials.expired
                and credentials.refresh_token
            ):

                print(
                    "🔄 OAuth token expired. "
                    "Refreshing..."
                )

                try:

                    credentials.refresh(
                        Request()
                    )

                    print(
                        "✅ OAuth token refreshed."
                    )

                except Exception as exc:

                    print(
                        f"⚠️ Token refresh failed: "
                        f"{exc}"
                    )

                    credentials = None

        # -------------------------------------------------
        # New OAuth login
        # -------------------------------------------------

        if not credentials or not credentials.valid:

            print(
                "\n🌐 Starting Google OAuth authentication..."
            )

            print(
                "A browser window will open."
            )

            print(
                "Sign in with the Google account "
                "that owns the YouTube channel."
            )

            if not os.path.exists(
                CLIENT_SECRET_FILE
            ):

                raise FileNotFoundError(
                    f"Missing OAuth credentials file: "
                    f"{CLIENT_SECRET_FILE}"
                )

            flow = (
                InstalledAppFlow
                .from_client_secrets_file(
                    CLIENT_SECRET_FILE,
                    SCOPES
                )
            )

            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="select_account consent"
            )

            print(
                "✅ Google OAuth authorization completed."
            )

        # -------------------------------------------------
        # Save token
        # -------------------------------------------------

        with open(
            TOKEN_FILE,
            "w",
            encoding="utf-8"
        ) as token_file:

            token_file.write(
                credentials.to_json()
            )

        print(
            f"💾 YouTube OAuth token saved to: "
            f"{TOKEN_FILE}"
        )

        # -------------------------------------------------
        # Verify upload scope
        # -------------------------------------------------

        scope_list = credentials.scopes or []

        upload_scope = (
            "https://www.googleapis.com/auth/youtube.upload"
        )

        readonly_scope = (
            "https://www.googleapis.com/auth/youtube.readonly"
        )

        if upload_scope not in scope_list:

            raise RuntimeError(
                "OAuth token does not contain "
                "youtube.upload scope."
            )

        print(
            "✅ OAuth token contains the "
            "YouTube upload scope."
        )

        if readonly_scope in scope_list:

            print(
                "✅ OAuth token contains the "
                "YouTube readonly scope."
            )

        else:

            print(
                "⚠️ YouTube readonly scope not detected."
            )

        # -------------------------------------------------
        # Build API service
        # -------------------------------------------------

        youtube = build(
            "youtube",
            "v3",
            credentials=credentials
        )

        print(
            "✅ YouTube API service created successfully."
        )

        return youtube

    # =====================================================
    # GET CHANNEL
    # =====================================================

    @staticmethod
    def get_channel(youtube):

        try:

            response = (
                youtube.channels()
                .list(
                    part="snippet,contentDetails",
                    mine=True
                )
                .execute()
            )

            items = response.get(
                "items",
                []
            )

            if not items:

                print(
                    "❌ No YouTube channel found "
                    "for this Google account."
                )

                return None

            channel = items[0]

            channel_name = (
                channel
                .get("snippet", {})
                .get("title", "Unknown")
            )

            channel_id = channel.get(
                "id",
                "Unknown"
            )

            print(
                f"📺 YouTube channel: "
                f"{channel_name}"
            )

            print(
                f"🆔 Channel ID: "
                f"{channel_id}"
            )

            return channel

        except HttpError as exc:

            print(
                "❌ YouTube API channel error:"
            )

            print(exc)

            return None

    # =====================================================
    # UPLOAD VIDEO
    # =====================================================

    @staticmethod
    def upload_video(
        youtube,
        video_path,
        title,
        description,
        tags=None,
        category_id="27",
        privacy_status="private",
        thumbnail_path=None,
        publish_at=None,
    ):

        video_path = Path(
            video_path
        )

        # -------------------------------------------------
        # Validate video
        # -------------------------------------------------

        if not video_path.exists():

            raise FileNotFoundError(
                f"Video does not exist: "
                f"{video_path}"
            )

        if video_path.stat().st_size <= 0:

            raise ValueError(
                "Video file is empty."
            )

        # -------------------------------------------------
        # Normalize metadata
        # -------------------------------------------------

        title = str(
            title or ""
        ).strip()

        description = str(
            description or ""
        ).strip()

        if not title:

            raise ValueError(
                "YouTube title is empty."
            )

        if not description:

            raise ValueError(
                "YouTube description is empty."
            )

        # -------------------------------------------------
        # Ensure #Shorts
        # -------------------------------------------------

        if "#shorts" not in description.lower():

            description += (
                "\n\n#Shorts"
            )

        # Enforce YouTube 500-char limit for comma-separated tags
        valid_tags = []
        total_len = 0
        for tag in (tags or []):
            tag_clean = str(tag).strip().replace(",", "")
            if not tag_clean:
                continue
            added_len = len(tag_clean) + (1 if valid_tags else 0)
            if total_len + added_len <= 480:
                valid_tags.append(tag_clean)
                total_len += added_len
            else:
                break
        tags = valid_tags

        # -------------------------------------------------
        # YouTube request body
        # -------------------------------------------------

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": str(
                    category_id
                )
            },

            "status": {
                "privacyStatus": "private" if publish_at else privacy_status,
                "selfDeclaredMadeForKids": False,
                **({"publishAt": str(publish_at)} if publish_at else {})
            }
        }

        # -------------------------------------------------
        # Media upload
        # -------------------------------------------------

        print("\n" + "=" * 60)

        print(
            "📤 YOUTUBE UPLOAD"
        )

        print("=" * 60)

        print(
            f"🎥 File: "
            f"{video_path}"
        )

        print(
            f"📝 Title: "
            f"{title}"
        )

        print(
            f"🔒 Privacy: "
            f"{privacy_status}"
        )

        print(
            f"📂 Category ID: "
            f"{category_id}"
        )

        print(
            "\n🚀 Uploading video..."
        )

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True
        )

        request = (
            youtube.videos()
            .insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
        )

        response = None

        while response is None:

            try:

                status, response = (
                    request.next_chunk()
                )

                if status:

                    progress = int(
                        status.progress()
                        * 100
                    )

                    print(
                        f"📤 Upload progress: "
                        f"{progress}%"
                    )

            except HttpError as exc:

                print(
                    "\n❌ YouTube upload failed:"
                )

                print(exc)

                raise

        video_id = response.get(
            "id"
        )

        if not video_id:

            raise RuntimeError(
                "YouTube upload completed "
                "but no video ID was returned."
            )

        print(
            "\n✅ VIDEO UPLOADED SUCCESSFULLY"
        )

        print(
            f"🆔 Video ID: "
            f"{video_id}"
        )

        print(
            f"🔗 https://www.youtube.com/watch?v={video_id}"
        )

        # =================================================
        # THUMBNAIL
        # =================================================
        #
        # IMPORTANT:
        #
        # This pipeline generates YouTube Shorts
        # in 1080x1920 format.
        #
        # YouTube Shorts do not support uploading
        # a separate custom thumbnail through the
        # thumbnails.set API in the same way as
        # regular long-form videos.
        #
        # Therefore we intentionally DO NOT call:
        #
        #     youtube.thumbnails().set(...)
        #
        # The thumbnail candidate can still be generated
        # by the visual pipeline, but it is not uploaded
        # through the YouTube API.
        #
        # Our future improvement is to make the opening
        # frame of the Short act as the visual cover.
        # =================================================

        if thumbnail_path:

            thumbnail_path = Path(
                thumbnail_path
            )

            if thumbnail_path.exists():

                print(
                    "\n🖼️ Thumbnail candidate detected:"
                )

                print(
                    f"   {thumbnail_path}"
                )

                print(
                    "ℹ️ Separate custom thumbnail "
                    "upload skipped for YouTube Shorts."
                )

            else:

                print(
                    f"\n⚠️ Thumbnail candidate not found: "
                    f"{thumbnail_path}"
                )

        else:

            print(
                "\nℹ️ No thumbnail candidate supplied."
            )

        # =================================================
        # RESULT
        # =================================================

        return {
            "video_id": video_id,

            "url": (
                f"https://www.youtube.com/watch?v="
                f"{video_id}"
            ),

            "privacy_status": privacy_status,

            "title": title,

            "thumbnail_uploaded": False,

            "thumbnail_status": (
                "not_applicable_for_shorts"
            )
        }


# =========================================================
# CONVENIENCE FUNCTION
# =========================================================

def upload_video(
    video_path,
    metadata,
    thumbnail_path=None,
    # Delayed-publish default: videos go up UNLISTED and are
    # flipped to PUBLIC by publish_worker.py after
    # DELAYED_PUBLISH_DELAY_MINUTES (see README).
    privacy_status="unlisted",
    publish_at=None,
):

    youtube = (
        YouTubeUploader.authenticate()
    )

    # -----------------------------------------------------
    # Verify channel
    # -----------------------------------------------------

    channel = (
        YouTubeUploader.get_channel(
            youtube
        )
    )

    if channel is None:

        raise RuntimeError(
            "Could not verify YouTube channel."
        )

    # -----------------------------------------------------
    # Metadata
    # -----------------------------------------------------

    title = metadata.get(
        "title",
        ""
    )

    description = str(
        metadata.get(
            "description",
            ""
        )
    ).strip()

    tags = metadata.get(
        "tags",
        []
    )

    category = metadata.get(
        "category",
        "Education"
    )

    # -----------------------------------------------------
    # Hashtags
    #
    # IMPORTANT:
    # YouTube only recognizes hashtags that appear in the
    # video description. Hashtags stored separately in
    # metadata["hashtags"] are NOT automatically picked up
    # by the YouTube API. They MUST be appended to the
    # description text, otherwise they have zero effect on
    # discoverability and views.
    # -----------------------------------------------------

    hashtags = metadata.get(
        "hashtags",
        []
    )

    hashtags = [
        str(tag).strip()
        for tag in hashtags
        if str(tag).strip()
    ]

    # Ensure #Shorts is always present -- and ALWAYS FIRST.
    # Appending it at the end would let the [:7] slice evict
    # it when the list is already full, and YouTube reads
    # hashtags from the description (first three surface
    # above the title). Normalize case-variant spellings
    # ('#shorts', '#SHORTS') to one canonical tag.
    hashtags = [
        "#Shorts" if tag.lower() == "#shorts" else tag
        for tag in hashtags
    ]

    hashtags = ["#Shorts"] + [
        tag for tag in hashtags
        if tag.lower() != "#shorts"
    ]

    # Deduplicate while preserving order (case-insensitive so
    # '#PopulationGrowth' and '#populationgrowth' collapse).
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            unique_hashtags.append(tag)

    hashtags = unique_hashtags[:7]

    # Append hashtags to the description
    if hashtags:
        hashtag_line = " ".join(hashtags)
        if description:
            description = (
                description
                + "\n\n"
                + hashtag_line
            )
        else:
            description = hashtag_line

    # -----------------------------------------------------
    # YouTube category
    #
    # Education = 27
    # -----------------------------------------------------

    category_id = "27"

    if str(category).lower() == "education":

        category_id = "27"

    # -----------------------------------------------------
    # Upload
    # -----------------------------------------------------

    return (
        YouTubeUploader.upload_video(
            youtube=youtube,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            privacy_status=privacy_status,
            thumbnail_path=thumbnail_path,
            publish_at=publish_at,
        )
    )


# =========================================================
# CAPTIONS UPLOAD
# =========================================================

def upload_captions(
    video_id: str,
    srt_path: str,
    language: str = "en",
    name: str = "English"
):
    """Upload an SRT caption track for an uploaded video.

    Uses the existing youtube.force-ssl OAuth scope
    (captions require force-ssl, which SCOPES already
    includes - no new authorization is needed for tokens
    granted that scope).

    NON-FATAL BY DESIGN: any failure is logged and None is
    returned; the pipeline never blocks video publishing on
    captions.
    """

    if not video_id or not srt_path:

        print(
            "⚠️ Caption upload skipped: missing video_id "
            "or srt_path."
        )

        return None

    if not os.path.exists(srt_path):

        print(
            f"⚠️ Caption upload skipped: SRT file not found: "
            f"{srt_path}"
        )

        return None

    print(
        f"\n💬 Uploading captions for {video_id} "
        f"(language={language})..."
    )

    try:

        youtube = (
            YouTubeUploader.authenticate()
        )

        result = (
            youtube.captions()
            .insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": language,
                        "name": name,
                        "isDraft": False,
                    }
                },
                media_body=MediaFileUpload(
                    srt_path,
                    mimetype="application/octet-stream",
                ),
            )
            .execute()
        )

        print(
            f"✅ Captions uploaded: {result.get('id')}"
        )

        return result

    except Exception as exc:

        print(
            f"⚠️ Caption upload failed (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

        return None


# =========================================================
# DIRECT AUTH TEST
# =========================================================

def authentication_test():

    print(
        "\n🔐 Testing YouTube authentication..."
    )

    youtube = (
        YouTubeUploader.authenticate()
    )

    channel = (
        YouTubeUploader.get_channel(
            youtube
        )
    )

    if channel:

        print(
            "\n" + "=" * 60
        )

        print(
            "🎉 YOUTUBE AUTHENTICATION TEST PASSED"
        )

        print("=" * 60)

        print(
            "✅ OAuth token valid"
        )

        print(
            "✅ YouTube API service working"
        )

        print(
            "✅ Channel detected"
        )

        print(
            "\n🚫 NO VIDEO WAS UPLOADED."
        )

        return True

    print(
        "\n❌ Authentication test failed."
    )

    return False


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    authentication_test()
