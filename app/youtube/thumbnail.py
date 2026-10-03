import os
import subprocess

from PIL import Image, ImageDraw, ImageFont


class ThumbnailEngine:

    # -------------------------------------------------------
    # Sample across the WHOLE video instead of only the first
    # second. The opening frame is the hook slide; the best
    # thumbnail moments usually happen mid-race and at the
    # climax where bars have actually moved.
    # -------------------------------------------------------

    SAMPLE_FRACTIONS = [0.05, 0.38, 0.68, 0.90]

    MIN_TIMESTAMP = 0.5

    # Impact is THE classic high-CTR thumbnail font.
    FONT_CANDIDATES = [
        "impact.ttf",
        "arialbd.ttf",
        "Arial Bold.ttf",
        "segoeuib.ttf",
    ]

    # Three cover layouts - YouTube's "Test & Compare"
    # lets creators A/B test exactly three thumbnails
    # per video, so we render one candidate per style.
    STYLE_ANCHORS = {
        "bottom": 0.74,
        "center": 0.50,
        "top": 0.14,
    }

    @staticmethod
    def _get_video_duration(video_path: str):
        """Probe real video duration with ffprobe."""

        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        except FileNotFoundError:
            return None

        try:
            return float(result.stdout.strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _load_font(size: int):
        """Prefer Impact; gracefully fall back down the list."""

        windows_fonts = r"C:\Windows\Fonts"

        for candidate in ThumbnailEngine.FONT_CANDIDATES:

            path = os.path.join(windows_fonts, candidate)

            if not os.path.exists(path):
                continue

            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue

        try:
            return ImageFont.truetype(
                "DejaVuSans-Bold.ttf", size
            )
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def _wrap_text(text, max_chars=14):
        """Uppercase caption wrap, max 3 short lines."""

        words = str(text).upper().split()

        lines = []
        current = ""

        for word in words:

            trial = f"{current} {word}".strip()

            if len(trial) <= max_chars or not current:
                current = trial
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines[:3]

    @staticmethod
    def _write_overlay(
        source_path,
        destination_path,
        text,
        style="bottom"
    ):
        """
        Burn big caption-style text onto a frame.
        White letters + heavy black stroke - the classic
        Shorts cover look that survives the tiny feed
        preview.

        style: bottom | center | top
        """

        if not str(text).strip():
            return False

        try:

            image = Image.open(source_path).convert("RGB")

        except OSError:
            return False

        width, height = image.size

        draw = ImageDraw.Draw(image)

        font_size = max(36, width // 9)

        font = ThumbnailEngine._load_font(font_size)

        stroke_width = max(3, font_size // 11)

        lines = ThumbnailEngine._wrap_text(text)

        if not lines:
            return False

        line_height = int(font_size * 1.18)

        total_height = line_height * len(lines)

        anchor = ThumbnailEngine.STYLE_ANCHORS.get(
            style,
            0.74,
        )

        y = int(height * anchor) - total_height // 2

        for line in lines:

            box = draw.textbbox(
                (0, 0),
                line,
                font=font,
                stroke_width=stroke_width,
            )

            line_width = box[2] - box[0]

            x = (width - line_width) // 2

            draw.text(
                (x, y),
                line,
                font=font,
                fill="white",
                stroke_width=stroke_width,
                stroke_fill="black",
            )

            y += line_height

        image.save(destination_path, quality=92)

        return True

    @staticmethod
    def generate_candidates(
        video_path: str,
        output_dir: str,
        overlay_text=None
    ):
        """
        Generate thumbnail-frame candidates from the final
        vertical YouTube Short.

        Frames are sampled across the full runtime so the
        candidates include mid-race and climax moments,
        not only the opening hook frame.

        When `overlay_text` is provided, an extra copy of
        each frame is saved with the text burned in -
        ready-to-pick covers instead of bare screenshots.
        """

        # =========================================================
        # CHECK VIDEO
        # =========================================================

        if not os.path.exists(video_path):
            raise FileNotFoundError(
                f"❌ Video not found:\n{video_path}"
            )

        # =========================================================
        # CREATE THUMBNAIL DIRECTORY
        # =========================================================

        thumbnail_dir = os.path.join(
            output_dir,
            "thumbnails"
        )

        os.makedirs(
            thumbnail_dir,
            exist_ok=True
        )

        print("\n" + "=" * 60)
        print("🖼️ STEP 15 — THUMBNAIL FRAME GENERATION")
        print("=" * 60)

        print(
            f"🎥 Source video:\n"
            f"   {video_path}"
        )

        print(
            f"📁 Thumbnail folder:\n"
            f"   {thumbnail_dir}"
        )

        # =========================================================
        # TIMESTAMPS
        # =========================================================

        duration = (
            ThumbnailEngine._get_video_duration(
                video_path
            )
        )

        if duration and duration > 2:

            timestamps = sorted(
                {
                    round(
                        max(
                            ThumbnailEngine.MIN_TIMESTAMP,
                            duration * fraction,
                        ),
                        2,
                    )
                    for fraction in (
                        ThumbnailEngine.SAMPLE_FRACTIONS
                    )
                }
            )

        else:

            # Probe failed - fall back to the classic
            # opening-second candidates.
            timestamps = [0.5, 1.0, 1.5]

        print(
            f"⏱️ Sampling frames at: {timestamps}"
        )

        generated_files = []

        # =========================================================
        # EXTRACT FRAMES
        # =========================================================

        for timestamp in timestamps:

            filename = (
                f"thumbnail_"
                f"{str(timestamp).replace('.', '_')}"
                f"s.jpg"
            )

            output_path = os.path.join(
                thumbnail_dir,
                filename
            )

            print(
                f"\n🎞️ Extracting frame at "
                f"{timestamp:.1f}s..."
            )

            command = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                output_path
            ]

            try:

                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            except FileNotFoundError:

                raise RuntimeError(
                    "❌ FFmpeg was not found.\n\n"
                    "Please make sure FFmpeg is installed "
                    "and available in PATH."
                )

            # =====================================================
            # CHECK FFMPEG RESULT
            # =====================================================

            if result.returncode != 0:

                print(
                    f"⚠️ Failed to extract frame "
                    f"at {timestamp:.1f}s"
                )

                print(
                    result.stderr[-1000:]
                )

                continue

            # =====================================================
            # CHECK OUTPUT
            # =====================================================

            if os.path.exists(output_path):

                generated_files.append(
                    output_path
                )

                print(
                    "✅ Saved:"
                )

                print(
                    f"   {output_path}"
                )

            else:

                print(
                    f"⚠️ Frame was not created "
                    f"at {timestamp:.1f}s"
                )

        # =========================================================
        # TEXT OVERLAYS
        # =========================================================

        if overlay_text:

            stripped = str(overlay_text).strip()

            if stripped:

                print(
                    "\n✍️ Burning thumbnail text: "
                    f"'{stripped}'"
                )

                titled_files = []

                for frame_path in generated_files:

                    stem, ext = os.path.splitext(
                        frame_path
                    )

                    for style in (
                        ThumbnailEngine.STYLE_ANCHORS
                    ):

                        titled_path = (
                            f"{stem}_titled_"
                            f"{style}{ext}"
                        )

                        if ThumbnailEngine._write_overlay(
                            frame_path,
                            titled_path,
                            stripped,
                            style,
                        ):

                            titled_files.append(
                                titled_path
                            )

                            print(
                                f"   🖼️ {titled_path}"
                            )

                generated_files.extend(titled_files)

        # =========================================================
        # FINAL RESULT
        # =========================================================

        print("\n" + "-" * 60)

        if not generated_files:

            raise RuntimeError(
                "❌ No thumbnail candidates were generated."
            )

        print(
            f"✅ Generated "
            f"{len(generated_files)} "
            f"thumbnail candidates."
        )

        for file_path in generated_files:

            print(
                f"   🖼️ {file_path}"
            )

        print("=" * 60)

        return generated_files