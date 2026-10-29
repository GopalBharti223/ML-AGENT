import json
import subprocess
from pathlib import Path

from app.config import settings


class FinalQC:
    """
    Final quality-control gate before YouTube upload.

    Checks:
    - video exists
    - metadata exists
    - script exists
    - 1080x1920
    - duration is valid
    - audio exists
    - title exists
    - description exists
    - #Shorts exists
    - script contains usable narration text
    """

    MIN_DURATION = 1.0
    MAX_DURATION = 180.0

    EXPECTED_WIDTH = 1080
    EXPECTED_HEIGHT = 1920

    # =========================================================
    # VIDEO PROBE
    # =========================================================

    @staticmethod
    def _probe_video(video_path):

        command = [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:

            raise RuntimeError(
                "ffprobe failed:\n"
                + result.stderr
            )

        return json.loads(
            result.stdout
        )

    # =========================================================
    # VIDEO QC
    # =========================================================

    @classmethod
    def check_video(
        cls,
        video_path
    ):

        errors = []

        video_path = Path(
            video_path
        )

        if not video_path.exists():

            return {
                "passed": False,
                "errors": [
                    f"Video does not exist: {video_path}"
                ],
            }

        try:

            probe = cls._probe_video(
                video_path
            )

        except Exception as exc:

            return {
                "passed": False,
                "errors": [
                    str(exc)
                ],
            }

        streams = probe.get(
            "streams",
            []
        )

        video_stream = next(
            (
                stream
                for stream in streams
                if stream.get(
                    "codec_type"
                ) == "video"
            ),
            None,
        )

        audio_stream = next(
            (
                stream
                for stream in streams
                if stream.get(
                    "codec_type"
                ) == "audio"
            ),
            None,
        )

        # -----------------------------------------------------
        # Streams
        # -----------------------------------------------------

        if video_stream is None:

            errors.append(
                "No video stream found."
            )

        if audio_stream is None:

            errors.append(
                "No audio stream found."
            )

        # -----------------------------------------------------
        # Duration
        # -----------------------------------------------------

        duration = 0.0

        try:

            duration = float(
                probe
                .get("format", {})
                .get("duration", 0)
            )

        except (
            ValueError,
            TypeError,
        ):

            errors.append(
                "Could not read video duration."
            )

        if duration < cls.MIN_DURATION:

            errors.append(
                f"Video is too short: "
                f"{duration:.2f}s"
            )

        max_allowed_duration = 600.0 if getattr(settings, "is_landscape", False) else cls.MAX_DURATION
        if duration > max_allowed_duration:

            errors.append(
                f"Video is longer than "
                f"allowed duration: {duration:.2f}s (max {max_allowed_duration:.0f}s)"
            )

        # -----------------------------------------------------
        # Resolution
        # -----------------------------------------------------

        width = None
        height = None

        if video_stream is not None:

            width = video_stream.get(
                "width"
            )

            height = video_stream.get(
                "height"
            )

            exp_w = getattr(settings, "canvas_width", cls.EXPECTED_WIDTH)
            exp_h = getattr(settings, "canvas_height", cls.EXPECTED_HEIGHT)

            if width != exp_w:

                errors.append(
                    f"Wrong width: {width}. "
                    f"Expected "
                    f"{exp_w}."
                )

            if height != exp_h:

                errors.append(
                    f"Wrong height: {height}. "
                    f"Expected "
                    f"{exp_h}."
                )

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "width": width,
            "height": height,
            "duration": round(
                duration,
                2
            ),
            "has_audio": (
                audio_stream is not None
            ),
        }

    # =========================================================
    # METADATA QC
    # =========================================================

    @staticmethod
    def check_metadata(
        metadata_path
    ):

        errors = []

        metadata_path = Path(
            metadata_path
        )

        if not metadata_path.exists():

            return {
                "passed": False,
                "errors": [
                    f"Metadata does not exist: "
                    f"{metadata_path}"
                ],
            }

        try:

            with open(
                metadata_path,
                "r",
                encoding="utf-8",
            ) as file:

                metadata = json.load(
                    file
                )

        except Exception as exc:

            return {
                "passed": False,
                "errors": [
                    f"Could not read metadata: "
                    f"{exc}"
                ],
            }

        # -----------------------------------------------------
        # Title
        # -----------------------------------------------------

        title = str(
            metadata.get("title")
            or metadata.get(
                "youtube_title"
            )
            or ""
        ).strip()

        # -----------------------------------------------------
        # Description
        # -----------------------------------------------------

        description = str(
            metadata.get(
                "description"
            )
            or ""
        ).strip()

        # -----------------------------------------------------
        # Hashtags
        # -----------------------------------------------------

        hashtags = metadata.get(
            "hashtags",
            []
        )

        if hashtags is None:

            hashtags = []

        if isinstance(
            hashtags,
            str
        ):

            hashtags = [
                hashtags
            ]

        hashtags_text = " ".join(
            str(tag)
            for tag in hashtags
        )

        # -----------------------------------------------------
        # Tags
        # -----------------------------------------------------

        tags = metadata.get(
            "tags"
        )

        if tags is None:

            tags = metadata.get(
                "youtube_tags",
                []
            )

        # -----------------------------------------------------
        # Required fields
        # -----------------------------------------------------

        if not title:

            errors.append(
                "YouTube title is missing."
            )

        if not description:

            errors.append(
                "YouTube description is missing."
            )

        # -----------------------------------------------------
        # Shorts validation
        #
        # Accept #Shorts from either:
        #
        # 1. description
        # 2. hashtags
        # -----------------------------------------------------

        shorts_in_description = (
            "#shorts"
            in description.lower()
        )

        shorts_in_hashtags = (
            "#shorts"
            in hashtags_text.lower()
        )

        if not getattr(settings, "is_landscape", False):
            if not (
                shorts_in_description
                or shorts_in_hashtags
            ):

                errors.append(
                    "Metadata does not contain "
                    "#Shorts in description "
                    "or hashtags."
                )

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "tags": tags,
        }

    # =========================================================
    # SCRIPT TEXT EXTRACTION
    # =========================================================

    @classmethod
    def _extract_script_text(
        cls,
        script
    ):

        texts = []

        # -----------------------------------------------------
        # CASE 1
        #
        # {
        #   "scenes": [
        #       {"text": "..."}
        #   ]
        # }
        # -----------------------------------------------------

        if isinstance(
            script,
            dict
        ):

            scenes = script.get(
                "scenes"
            )

            if isinstance(
                scenes,
                list
            ):

                for scene in scenes:

                    if isinstance(
                        scene,
                        dict
                    ):

                        for key in (
                            "text",
                            "narration",
                            "voiceover",
                            "script",
                        ):

                            value = scene.get(
                                key
                            )

                            if isinstance(
                                value,
                                str
                            ) and value.strip():

                                texts.append(
                                    value
                                )

                                break

                    elif isinstance(
                        scene,
                        str
                    ):

                        texts.append(
                            scene
                        )

        # -----------------------------------------------------
        # CASE 2
        #
        # top-level text fields
        # -----------------------------------------------------

        if isinstance(
            script,
            dict
        ):

            for key in (
                "text",
                "narration",
                "voiceover",
                "script",
            ):

                value = script.get(
                    key
                )

                if isinstance(
                    value,
                    str
                ) and value.strip():

                    texts.append(
                        value
                    )

        # -----------------------------------------------------
        # CASE 3
        #
        # Some script models use:
        #
        # {
        #   "sections": [...]
        # }
        # -----------------------------------------------------

        if isinstance(
            script,
            dict
        ):

            sections = script.get(
                "sections"
            )

            if isinstance(
                sections,
                list
            ):

                for section in sections:

                    if isinstance(
                        section,
                        dict
                    ):

                        for key in (
                            "text",
                            "narration",
                            "voiceover",
                            "script",
                        ):

                            value = section.get(
                                key
                            )

                            if isinstance(
                                value,
                                str
                            ) and value.strip():

                                texts.append(
                                    value
                                )

                                break

        # -----------------------------------------------------
        # CASE 4
        #
        # List of scene dictionaries
        # -----------------------------------------------------

        if isinstance(
            script,
            list
        ):

            for item in script:

                if isinstance(
                    item,
                    dict
                ):

                    for key in (
                        "text",
                        "narration",
                        "voiceover",
                        "script",
                    ):

                        value = item.get(
                            key
                        )

                        if isinstance(
                            value,
                            str
                        ) and value.strip():

                            texts.append(
                                value
                            )

                            break

                elif isinstance(
                    item,
                    str
                ):

                    texts.append(
                        item
                    )

        return " ".join(
            texts
        ).strip()

    # =========================================================
    # SCRIPT QC
    # =========================================================

    @classmethod
    def check_script(
        cls,
        script_path
    ):

        errors = []

        script_path = Path(
            script_path
        )

        if not script_path.exists():

            return {
                "passed": False,
                "errors": [
                    f"Script does not exist: "
                    f"{script_path}"
                ],
            }

        try:

            with open(
                script_path,
                "r",
                encoding="utf-8",
            ) as file:

                script = json.load(
                    file
                )

        except Exception as exc:

            return {
                "passed": False,
                "errors": [
                    f"Could not read script: "
                    f"{exc}"
                ],
            }

        # -----------------------------------------------------
        # Extract actual narration
        # -----------------------------------------------------

        total_text = (
            cls._extract_script_text(
                script
            )
        )

        word_count = len(
            total_text.split()
        )

        # -----------------------------------------------------
        # Minimum narration
        #
        # 15 words is enough for basic QC.
        # -----------------------------------------------------

        if word_count < 15:

            errors.append(
                f"Script is too short: "
                f"{word_count} words."
            )

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "word_count": word_count,
            "text": total_text,
        }

    # =========================================================
    # FINAL QC
    # =========================================================

    @classmethod
    def run(
        cls,
        video_path,
        metadata_path,
        script_path,
    ):

        print()
        print("=" * 60)
        print(
            "🔎 FINAL QUALITY CONTROL"
        )
        print("=" * 60)

        # -----------------------------------------------------
        # Run checks
        # -----------------------------------------------------

        video_result = cls.check_video(
            video_path
        )

        metadata_result = cls.check_metadata(
            metadata_path
        )

        script_result = cls.check_script(
            script_path
        )

        # =====================================================
        # VIDEO
        # =====================================================

        if video_result["passed"]:

            print(
                "✅ VIDEO QC PASSED"
            )

            print(
                f"   Resolution: "
                f"{video_result['width']}x"
                f"{video_result['height']}"
            )

            print(
                f"   Duration: "
                f"{video_result['duration']}s"
            )

            print(
                f"   Audio: "
                f"{'YES' if video_result['has_audio'] else 'NO'}"
            )

        else:

            print(
                "❌ VIDEO QC FAILED"
            )

            for error in video_result[
                "errors"
            ]:

                print(
                    f"   - {error}"
                )

        # =====================================================
        # METADATA
        # =====================================================

        if metadata_result["passed"]:

            print(
                "✅ METADATA QC PASSED"
            )

            print(
                f"   Title: "
                f"{metadata_result['title']}"
            )

        else:

            print(
                "❌ METADATA QC FAILED"
            )

            for error in metadata_result[
                "errors"
            ]:

                print(
                    f"   - {error}"
                )

        # =====================================================
        # SCRIPT
        # =====================================================

        if script_result["passed"]:

            print(
                "✅ SCRIPT QC PASSED"
            )

            print(
                f"   Word count: "
                f"{script_result['word_count']}"
            )

        else:

            print(
                "❌ SCRIPT QC FAILED"
            )

            for error in script_result[
                "errors"
            ]:

                print(
                    f"   - {error}"
                )

        # =====================================================
        # FINAL DECISION
        # =====================================================

        all_passed = (
            video_result["passed"]
            and metadata_result["passed"]
            and script_result["passed"]
        )

        print()
        print(
            "-" * 60
        )

        if all_passed:

            print(
                "🎉 FINAL QC PASSED"
            )

            print(
                "✅ Safe to send to YouTube uploader."
            )

        else:

            print(
                "🚫 FINAL QC FAILED"
            )

            print(
                "🚫 VIDEO WILL NOT BE UPLOADED."
            )

        print(
            "=" * 60
        )

        print()

        return all_passed