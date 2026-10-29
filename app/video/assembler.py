
import subprocess
import os

from app.config import settings
_settings = settings


class VideoAssembler:

    @staticmethod
    def _run_ffmpeg_command(
        cmd: list
    ):
        """Run FFmpeg and raise an error if it fails."""

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            print(
                f"FFmpeg Error:\n"
                f"{result.stderr}"
            )

            raise RuntimeError(
                "FFmpeg failed to execute."
            )

    # =====================================================
    # LOUDNESS MEASUREMENT (pass 1 of two-pass loudnorm)
    # =====================================================

    @staticmethod
    def _measure_loudness(
        input_path: str
    ) -> dict:
        """
        Measure integrated loudness of an audio input using the
        loudnorm filter's print_format=json analysis mode.

        `input_path` may be a media file OR an ffmpeg concat
        list (parsed with -f concat -safe 0).

        Returns a dict with the keys loudnorm's second pass
        expects (measured_I, measured_TP, measured_LRA,
        measured_thresh, offset), or an empty dict when the
        analysis output cannot be parsed -- callers then fall
        back to single-pass normalization.
        """

        command = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", input_path,
            "-af",
            (
                "loudnorm=I=-14:TP=-1.5:LRA=11"
                ":print_format=json"
            ),
            "-f", "null",
            "-",
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:

            print(
                "⚠️ Loudness analysis pass failed; "
                "falling back to single-pass normalization."
            )

            return {}

        stderr = result.stderr or ""

        # loudnorm prints its JSON report at the end of stderr.

        start = stderr.rfind("{")

        end = stderr.rfind("}")

        if start == -1 or end <= start:
            return {}

        try:

            import json

            report = json.loads(stderr[start:end + 1])

            measured = {
                "measured_I": report["input_i"],
                "measured_TP": report["input_tp"],
                "measured_LRA": report["input_lra"],
                "measured_thresh": report["input_thresh"],
                "offset": report["target_offset"],
            }

            required = (
                "measured_I",
                "measured_TP",
                "measured_LRA",
                "measured_thresh",
                "offset",
            )

            if any(
                measured[key] in (None, "")
                for key in required
            ):
                return {}

            return measured

        except (ValueError, KeyError, TypeError):

            print(
                "⚠️ Could not parse loudnorm analysis "
                "output; falling back to single-pass "
                "normalization."
            )

            return {}

    @staticmethod
    def measure_media_loudness(
        input_path: str,
        concat_list: bool = False,
    ):
        """
        Integrated loudness (LUFS, ITU-R BS.1770) of a media file,
        measured with ffmpeg's loudnorm analysis pass.

        `concat_list=True` treats `input_path` as an ffmpeg concat
        list (the narration segment list) instead of a media file.

        Used to VERIFY that normalization really landed on target:
        the loudnorm passes previously carried `-c copy`, which
        ffmpeg rejects ("Filtering and streamcopy cannot be used
        together"), so every video shipped unnormalized without a
        single error surfacing.  Returns None when measurement
        fails.
        """

        if concat_list:

            command = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", input_path,
            ]

        else:

            command = [
                "ffmpeg", "-y",
                "-i", input_path,
            ]

        command += [
            "-af",
            (
                "loudnorm=I=-14:TP=-1.5:LRA=11"
                ":print_format=json"
            ),
            "-f", "null",
            "-",
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            return None

        stderr = result.stderr or ""

        start = stderr.rfind("{")
        end = stderr.rfind("}")

        if start == -1 or end <= start:
            return None

        try:

            import json

            report = json.loads(stderr[start:end + 1])

            return float(report["input_i"])

        except (ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _loudnorm_filter(measured: dict) -> str:
        """
        Build the loudnorm filter string.

        With a measurement dict (pass-1 output) this is the
        linear two-pass filter; with an empty dict it is the
        dynamic single-pass filter.
        """

        if measured:

            return (
                "loudnorm=I=-14:TP=-1.5:LRA=11"
                ":measured_I={measured_I}"
                ":measured_TP={measured_TP}"
                ":measured_LRA={measured_LRA}"
                ":measured_thresh={measured_thresh}"
                ":offset={offset}:linear=true"
            ).format(**measured)

        return "loudnorm=I=-14:TP=-1.5:LRA=11"

    # =====================================================
    # AUDIO DURATION
    # =====================================================

    @staticmethod
    def _get_media_duration(
        file_path: str
    ) -> float:
        """
        Get media duration using ffprobe.
        """

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Could not read media duration:\n"
                f"{result.stderr}"
            )

        return float(
            result.stdout.strip()
        )

    # =====================================================
    # STEP 8 — LOUDNESS ALIGNMENT (closed loop)
    # =====================================================

    @staticmethod
    def _align_loudness(
        file_path: str,
        label: str = "narration"
    ):
        """
        Close the loudness loop on an already-encoded track.

        Two-pass loudnorm alone lands ~1.7 LU SHORT of the
        -14 LUFS target on short narration: loudnorm's linear
        mode clamps at its measured linear headroom, and every
        limiter pass removes a little more energy, so a single
        `volume=residual` pass always under-shoots.

        This stage measures the file, applies an over-driven
        residual gain + true-peak limiter, and re-measures until
        the result is inside LOUDNESS_TOLERANCE_LU.

        Measured on real narration (raw -20.89 LUFS, LRA 2.90
        LU / +1.21 dB of linear headroom):

          two-pass loudnorm alone ....... -15.66 LUFS
          + residual gain x1.0 .......... -14.66 LUFS
          + residual gain x1.5 .......... -14.55 LUFS
          + residual gain x1.8 .......... -14.34 LUFS
          + residual gain x2.2 .......... -14.09 LUFS

        Driving the residual by LOUDNESS_CORRECTION_GAIN closes
        the gap in 1-3 steps, with the limiter holding true peak
        at or under the -1.5 dBTP ceiling (verified -1.46 dBTP).

        Called TWICE per render: once on the narration track
        (`_create_audio_concat`) and once AFTER branding, because
        the brand concat (ding + narration + outro) rebuilds the
        track and would otherwise ship at the un-re-aligned level.

        Returns the final measured LUFS, or None when the file
        cannot be measured.
        """

        for attempt in range(
            VideoAssembler.LOUDNESS_MAX_CORRECTIONS + 1
        ):

            achieved = (
                VideoAssembler.measure_media_loudness(
                    file_path
                )
            )

            if achieved is None:

                print(
                    f"  -> Loudness verification unavailable "
                    f"for the {label} track (could not be "
                    "measured)."
                )

                return None

            residual = (
                VideoAssembler.LOUDNESS_TARGET_LUFS
                - achieved
            )

            if abs(residual) <= (
                VideoAssembler.LOUDNESS_TOLERANCE_LU
            ):

                print(
                    f"  -> {label.capitalize()} loudness "
                    f"verified: {achieved:.2f} LUFS "
                    f"(target "
                    f"{VideoAssembler.LOUDNESS_TARGET_LUFS:.0f}"
                    " LUFS)."
                )

                return achieved

            if attempt == (
                VideoAssembler.LOUDNESS_MAX_CORRECTIONS
            ):

                print(
                    f"  ⚠️ {label.capitalize()} loudness off "
                    f"target after {attempt} correction(s): "
                    f"{achieved:.2f} LUFS (target "
                    f"{VideoAssembler.LOUDNESS_TARGET_LUFS:.0f}"
                    " LUFS)."
                )

                return achieved

            # Over-driven by LOUDNESS_CORRECTION_GAIN: the
            # limiter removes energy, so a naive
            # `volume=residual` under-shoots every pass.
            drive = (
                residual
                * VideoAssembler.LOUDNESS_CORRECTION_GAIN
            )

            # Hold the limiter below the ceiling by the codec
            # overshoot margin, so the SHIPPED lossy file honours
            # the true-peak spec rather than the pre-encode one.
            limiter_limit = (
                VideoAssembler.LOUDNESS_TRUE_PEAK_DBTP
                - VideoAssembler.LOUDNESS_LIMITER_MARGIN_DB
            )

            correction_command = [
                "ffmpeg", "-y",
                "-i", file_path,
                "-af",
                (
                    f"volume={drive:.2f}dB,"
                    "alimiter="
                    f"limit={limiter_limit:.2f}dB:level=0"
                ),
                "-ar", "24000",
                "-ac", "1",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                file_path + ".tmp.mp3",
            ]

            VideoAssembler._run_ffmpeg_command(
                correction_command
            )

            os.replace(
                file_path + ".tmp.mp3",
                file_path,
            )

            print(
                f"  -> {label.capitalize()} loudness correction "
                f"{attempt + 1}: {achieved:.2f} -> target "
                f"(applied {drive:+.2f}dB + true-peak limiter)."
            )

        return None

    @staticmethod
    def _trim_trailing_silence(
        file_path: str,
        keep_seconds: float = 0.05,
    ) -> bool:
        """Trim the trailing silence off an already-encoded track.

        DEAD-AIR FIX (Issue 1 follow-up): the shipped video must never
        END on silence.  The narration clips are trimmed upstream
        (_trim_clip_edges), but the brand-audio concat REBUILDS the
        track (ding + narration + tail bridge + outro), so whatever
        the last brand segment looks like is what actually ships --
        and the published video ended on a measured 1.20s of pure
        dead air.  Same areverse / silenceremove / areverse recipe
        the TTS engine uses, applied to the assembled track as a
        final guarantee.  Returns True when the file was replaced;
        non-fatal (the untrimmed track is kept on any failure).
        """

        source = str(file_path)

        if not os.path.exists(source):
            return False

        trimmed = source + ".tailtrim.mp3"

        command = [
            "ffmpeg", "-y",
            "-i", source,
            "-af",
            (
                "areverse,"
                "silenceremove=start_periods=1:"
                "start_threshold=-40dB:"
                f"start_duration={keep_seconds},"
                "areverse"
            ),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            trimmed,
        ]

        try:

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if (
                result.returncode == 0
                and os.path.exists(trimmed)
                and os.path.getsize(trimmed) > 0
            ):
                os.replace(trimmed, source)
                return True

            try:
                os.remove(trimmed)
            except OSError:
                pass

        except Exception:

            try:
                os.remove(trimmed)
            except OSError:
                pass

        return False

    # =====================================================
    # STEP 8 — AUDIO CONCAT & LANDSCAPE SYNC
    # =====================================================

    @staticmethod
    def align_landscape_audio(
        audio_data: list,
        output_dir: str,
        target_total_duration: float = None,
    ) -> list:
        """Align each scene's audio narration to start at its planned visual timestamp,
        inserting clean silence MP3 padding segments between scenes when narration finishes early.
        Updates item['start_time'] and item['end_time'] in audio_data for exact subtitle sync.
        Returns a new concat-ready list containing both scene audio and silence pad segments.
        """
        audio_dir = os.path.join(output_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        padded_concat_list = []
        timeline_cursor = 0.0
        planned_cursor = 0.0

        for idx, item in enumerate(audio_data):
            if item.get("is_silence"):
                padded_concat_list.append(item)
                timeline_cursor += float(item.get("actual_duration") or 0.0)
                continue

            script_dur = float(item.get("script_duration") or 0.0)
            actual_dur = float(item.get("actual_duration") or 0.0)

            # Planned start time based on cumulative script durations
            target_start = planned_cursor

            # If current timeline is behind target_start, insert a silence pad
            if target_start > timeline_cursor + 0.05:
                silence_dur = round(target_start - timeline_cursor, 3)
                silence_path = os.path.join(audio_dir, f"silence_pad_{idx}.mp3")
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", str(silence_dur),
                        "-c:a", "libmp3lame", "-b:a", "128k",
                        silence_path
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                padded_concat_list.append({
                    "audio_path": silence_path,
                    "actual_duration": silence_dur,
                    "is_silence": True
                })
                timeline_cursor += silence_dur

            # Now assign scene audio real start & end times
            item["start_time"] = timeline_cursor
            padded_concat_list.append(item)
            timeline_cursor += actual_dur
            item["end_time"] = timeline_cursor

            # Advance planned cursor for the next scene
            planned_cursor += max(script_dur, actual_dur)

        # If a target_total_duration is specified and timeline_cursor is short, add tail silence pad
        if target_total_duration and target_total_duration > timeline_cursor + 0.05:
            tail_dur = round(target_total_duration - timeline_cursor, 3)
            tail_path = os.path.join(audio_dir, "silence_tail.mp3")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(tail_dur),
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    tail_path
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            padded_concat_list.append({
                "audio_path": tail_path,
                "actual_duration": tail_dur,
                "is_silence": True
            })
            timeline_cursor += tail_dur

        return padded_concat_list

    @staticmethod
    def _create_audio_concat(
        audio_data: list,
        output_dir: str
    ) -> str:

        # Auto-align landscape audio if not already padded
        if getattr(settings, "is_landscape", False) and not any(item.get("is_silence") for item in audio_data):
            audio_data = VideoAssembler.align_landscape_audio(audio_data, output_dir)

        audio_list_path = os.path.join(
            output_dir,
            "audio_concat.txt"
        )

        with open(
            audio_list_path,
            "w",
            encoding="utf-8"
        ) as f:

            for audio in audio_data:
                abs_audio_path = os.path.abspath(audio["audio_path"]).replace("\\", "/")
                # FFmpeg concat format
                f.write(
                    f"file '{abs_audio_path}'\n"
                )

        full_audio_path = os.path.join(
            output_dir,
            "full_narration.mp3"
        )

        # -----------------------------------------------------
        # Loudness normalization: target the streaming standard
        # (-14 LUFS integrated, -1.5 dBTP ceiling) using a
        # TWO-PASS loudnorm (measure, then apply with the
        # measured values) -- single-pass regularly misses the
        # target by >1 LU on short narration.  Degradation
        # ladder: two-pass -> single-pass -> plain concat, so
        # the pipeline never breaks on an odd ffmpeg build.
        # The filtered passes re-encode at `-ar 24000 -ac 1` --
        # the pipeline's native narration format (Edge-TTS MP3
        # segments and the lame-converted brand segments), so the
        # normalized track never gets resampled twice.
        #
        # The loudnorm passes RE-ENCODE the audio (libmp3lame):
        # ffmpeg rejects a filtergraph combined with `-c copy`
        # ("Filtering and streamcopy cannot be used together"),
        # which silently disabled normalization on EVERY video
        # (the old commands kept `-c copy` and always fell back
        # to the plain concat).  Only the no-filter fallback
        # still stream-copies.
        # -----------------------------------------------------

        concat_command = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", audio_list_path,
            "-c", "copy",
            full_audio_path
        ]

        # Base for filtered passes: everything except the
        # trailing "-c copy <output>" triple.
        reencode_base = concat_command[:-3]

        normalized_command = (
            reencode_base
            + [
                "-af",
                VideoAssembler._loudnorm_filter({}),
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                full_audio_path
            ]
        )

        measured = None

        try:

            measured = (
                VideoAssembler._measure_loudness(
                    audio_list_path
                )
            )

            if measured:

                two_pass_command = (
                    reencode_base
                    + [
                        "-af",
                        VideoAssembler._loudnorm_filter(
                            measured
                        ),
                        "-ar",
                        "24000",
                        "-ac",
                        "1",
                        "-c:a",
                        "libmp3lame",
                        "-b:a",
                        "128k",
                        full_audio_path
                    ]
                )

                VideoAssembler._run_ffmpeg_command(
                    two_pass_command
                )

                print(
                    "  -> Loudness normalization "
                    f"applied (two-pass, target -14 LUFS; "
                    "measured input "
                    f"{float(measured['measured_I']):.2f} "
                    "LUFS)."
                )

            else:

                VideoAssembler._run_ffmpeg_command(
                    normalized_command
                )

                print(
                    "  -> Loudness normalization "
                    "applied (single-pass, target "
                    "-14 LUFS)."
                )

            # --------------------------------------------------
            # ALIGN + VERIFY (shared with the post-branding pass)
            #
            # Two-pass loudnorm alone lands ~1.7 LU short of the
            # -14 LUFS target on short narration.  _align_loudness
            # closes the loop -- residual gain + true-peak limiter,
            # re-measured until inside LOUDNESS_TOLERANCE_LU --
            # and reports the level that actually ships.
            # --------------------------------------------------

            VideoAssembler._align_loudness(
                full_audio_path,
                label="narration"
            )

        except RuntimeError as error:

            print(
                "⚠️ Loudness normalization unavailable "
                f"({type(error).__name__}); using plain "
                "concatenation."
            )

            try:

                VideoAssembler._run_ffmpeg_command(
                    concat_command
                )

            except RuntimeError:

                print(
                    "⚠️ Plain audio concatenation also "
                    "failed; continuing without a merged "
                    "narration file."
                )

        return full_audio_path

    # =====================================================
    # STEP 8 — TIMELINE REPORT
    # =====================================================

    @staticmethod
    def _print_sync_report(
        audio_data: list,
        visual_duration: float,
        audio_duration: float
    ):

        print(
            "\n" + "=" * 55
        )

        print(
            "🎬 STEP 8 — AUDIO / VIDEO SYNC REPORT"
        )

        print(
            "=" * 55
        )

        for item in audio_data:
            if item.get("is_silence"):
                continue

            start = item.get(
                "start_time",
                0.0
            )

            end = item.get(
                "end_time",
                0.0
            )

            actual = item.get(
                "actual_duration",
                0.0
            )

            script_duration = item.get(
                "script_duration",
                0.0
            )

            difference = (
                actual
                - script_duration
            )

            scene_num = item.get("scene_number", "?")
            print(
                f"Scene {scene_num}: "
                f"{start:.2f}s → "
                f"{end:.2f}s | "
                f"Audio: {actual:.2f}s | "
                f"Script: {script_duration:.2f}s | "
                f"Diff: {difference:+.2f}s"
            )

        print(
            "-" * 55
        )

        print(
            f"Visual duration: "
            f"{visual_duration:.2f}s"
        )

        print(
            f"Audio duration:  "
            f"{audio_duration:.2f}s"
        )

        difference = (
            visual_duration
            - audio_duration
        )

        print(
            f"Final difference: "
            f"{difference:+.2f}s"
        )

        if abs(difference) <= 0.10:

            print(
                "✅ Excellent synchronization."
            )

        elif abs(difference) <= 0.30:

            print(
                "🟡 Minor timing difference."
            )

        else:

            print(
                "⚠️ Significant timing difference."
            )

        print(
            "=" * 55
        )

    # =====================================================
    # CREATE FINAL VIDEO
    # =====================================================

    # Hard safety ceiling for the final video length (seconds).
    # Exceeding this only triggers a loud warning -- content is
    # never silently truncated (see create_video step 5).
    MAX_FINAL_DURATION_S = 90.0

    # Deltas below this are considered render/encoder rounding.
    DURATION_EPSILON_S = 0.05

    # -----------------------------------------------------
    # LOUDNESS NORMALIZATION (streaming standard)
    #
    # Two-pass linear loudnorm alone lands ~1.7 LU SHORT of the
    # target on short narration: the measured LRA/offset let the
    # linear gate lift only as far as the true-peak ceiling
    # allows (pass-1 reported "+6.89 dB needed, +1.21 dB
    # available").  _align_loudness() therefore closes the loop:
    # residual gain + true-peak limiter, re-measured until the
    # level is inside LOUDNESS_TOLERANCE_LU, and run BOTH on the
    # narration track and again after branding rebuilds it.
    # The gain is deliberately OVER-DRIVEN by
    # LOUDNESS_CORRECTION_GAIN to compensate the energy the
    # limiter removes -- measured on a real render, x2.2 landed
    # -14.09 LUFS with true peak -1.46 dBTP (recipes
    # x1.5 -> -14.55, x2.8 -> -13.83).
    # -----------------------------------------------------

    LOUDNESS_TARGET_LUFS = -14.0

    LOUDNESS_TRUE_PEAK_DBTP = -1.5

    # Safety margin under the ceiling for the limiter itself.
    # alimiter bounds the SAMPLE peak, while loudnorm/the
    # streaming spec measure TRUE peak (ITU-R BS.1770), so the
    # lossy encodes after it (MP3 128k/24k, then the AAC track in
    # the MP4) overshoot by ~0.3 dB inter-sample: with the limiter
    # at the ceiling the shipped files measured -1.41 dBTP.
    # Measured chain with the margin at 0.25: limiter -1.75 ->
    # narration mp3 -1.45 -> mp4 -1.41 (spec breached on the
    # shipped file).  Raised to 0.55 so the SHIPPED file honours
    # the -1.5 dBTP spec.
    LOUDNESS_LIMITER_MARGIN_DB = 0.55

    # |achieved - target| <= this counts as on target.
    LOUDNESS_TOLERANCE_LU = 0.5

    LOUDNESS_CORRECTION_GAIN = 2.2

    # Bounded so a pathological input can never loop ffmpeg.
    LOUDNESS_MAX_CORRECTIONS = 5

    @staticmethod
    def create_video(
        audio_data: list,
        visual_data: list,
        output_dir: str,
        sfx_category: str = None,
        captions_path: str = None
    ) -> str:

        """
        Assemble the final video.

        sfx_category (optional) biases the rotating brand sound
        effects (PRIORITY 1) toward a subset of the variant pool.
        It is additive, so every existing caller that omits it
        behaves exactly as before.
        """

        print(
            "🎬 Assembling final video..."
        )

        if not audio_data:
            raise ValueError(
                "No audio data provided."
            )

        if not visual_data:
            raise ValueError(
                "No visual data provided."
            )

        os.makedirs(
            output_dir,
            exist_ok=True
        )

        # =================================================
        # 1. VERIFY AUDIO FILES
        # =================================================

        for audio in audio_data:

            if not os.path.exists(
                audio["audio_path"]
            ):

                raise FileNotFoundError(
                    f"Audio file missing: "
                    f"{audio['audio_path']}"
                )

        # =================================================
        # 2. CONCATENATE AUDIO
        # =================================================

        full_audio_path = (
            VideoAssembler
            ._create_audio_concat(
                audio_data,
                output_dir
            )
        )

        print(
            "  -> Voiceover tracks merged."
        )

        # =================================================
        # 3. GET REAL MEDIA DURATIONS
        # =================================================

        first_item = visual_data[0]
        video_path = first_item if isinstance(first_item, str) else first_item["image_path"]

        if not os.path.exists(
            video_path
        ):

            raise FileNotFoundError(
                f"Visual video missing: "
                f"{video_path}"
            )

        # -------------------------------------------------
        # TAIL-BRIDGE SIZING (published-video review, Issue 1)
        #
        # The animation is rendered AUDIO_TAIL_HOLD (~0.75s)
        # longer than the narration by design.  Measured on
        # the RAW animation BEFORE branding so the branded
        # AUDIO track can carry an exact-length silence
        # bridge: previously the audio stream ended
        # ~0.73s before the video stream (no samples at
        # all), which showed up as the tail of the 1.9s
        # dead-air hole at the end of the published video.
        # -------------------------------------------------

        animation_duration = (
            VideoAssembler
            ._get_media_duration(
                video_path
            )
        )

        narration_audio_duration = (
            VideoAssembler
            ._get_media_duration(
                full_audio_path
            )
        )

        # =================================================
        # 3B. BRANDING (intro/outro cards + audio)
        # =================================================
        # Wrap the animation with MetricForge intro/outro cards
        # and prepend/append the matching audio segments.
        # All failures degrade gracefully (unbranded video).

        try:
            from app.video.branding import (
                render_intro_card,
                render_outro_card,
                build_branded_video,
                build_brand_audio_segments,
                build_tail_bridge_audio,
            )

            # INTRO CARD GATE (human-touch layer): the static
            # brand card delayed the payoff by ~1.2s and the ding
            # another 0.75s, directly conflicting with the
            # opening-payoff fix -- so both are OFF by default
            # (config: INTRO_CARD_ENABLED=true to restore).
            from app.config import settings as _settings

            # SFX ROTATION (PRIORITY 1): the brand sting and the
            # outro chime used to be one fixed cue in every single
            # upload.  Pick a variant per video, remembering the
            # last one used so consecutive uploads never repeat.
            sfx_ding_variant = 0
            sfx_chime_variant = 0

            try:

                from app.video.sfx import (
                    describe_chime,
                    describe_ding,
                    pick_chime_variant,
                    pick_ding_variant,
                    remember_sfx,
                )

                sfx_key = os.path.join(
                    str(output_dir or ""), "video"
                )

                sfx_ding_variant = pick_ding_variant(
                    topic_key=sfx_key,
                    category=sfx_category,
                )
                sfx_chime_variant = pick_chime_variant(
                    topic_key=sfx_key,
                    category=sfx_category,
                )

                print(
                    f"  -> SFX intro {describe_ding(sfx_ding_variant)}"
                    f" / outro {describe_chime(sfx_chime_variant)}"
                )

            except Exception as sfx_error:

                print(
                    f"  -> SFX rotation unavailable "
                    f"({type(sfx_error).__name__}: {sfx_error}); "
                    "using the default brand cue."
                )

            outro_enabled = bool(
                getattr(_settings, "OUTRO_CARD_ENABLED", False)
            )
            intro_path = (
                render_intro_card(output_dir)
                if _settings.INTRO_CARD_ENABLED
                else None
            )
            outro_path = (
                render_outro_card(output_dir)
                if outro_enabled
                else None
            )

            branded_video_path = build_branded_video(
                video_path, output_dir, intro_path, outro_path
            )
            if branded_video_path != video_path:
                video_path = branded_video_path
                print("  -> Branded visual (intro + animation + outro).")

            intro_audio, outro_audio = build_brand_audio_segments(
                output_dir,
                ding_variant=sfx_ding_variant,
                chime_variant=sfx_chime_variant,
            )
            if not outro_enabled:
                outro_audio = None
            if not _settings.INTRO_CARD_ENABLED:
                intro_audio = None
            converted_entries = []
            if intro_audio or outro_audio:
                branded_audio_list = os.path.join(
                    output_dir, "brand_audio_concat.txt"
                )
                entries = []
                # The intro ding belongs to the intro card: when
                # the card is gated off, its 0.75s of audio must
                # not delay the payoff either.
                if intro_audio and _settings.INTRO_CARD_ENABLED:
                    entries.append(intro_audio["audio_path"])
                entries.append(full_audio_path)

                # -------------------------------------------------
                # TAIL BRIDGE: size a silence segment to the
                # animation's tail hold so the audio stream lasts
                # exactly as long as the video and the outro
                # chime lands ON the outro card (not ~0.7s
                # before it, leaving a no-audio tail).
                # -------------------------------------------------
                if outro_audio:

                    bridge_seconds = (
                        animation_duration
                        - narration_audio_duration
                    )

                    bridge_audio = (
                        build_tail_bridge_audio(
                            output_dir,
                            bridge_seconds,
                        )
                    )

                    if bridge_audio:

                        entries.append(
                            bridge_audio["audio_path"]
                        )

                        print(
                            f"  -> Tail bridge "
                            f"{bridge_seconds:.2f}s keeps the "
                            "audio stream level with the "
                            "animation (outro chime lands on "
                            "the outro card)."
                        )

                if outro_audio:
                    entries.append(outro_audio["audio_path"])
                # NOTE: the ffmpeg concat demuxer requires ALL
                # segments to share codec/sample-rate/channels.
                def _wav_to_mp3(wav_path):
                    try:
                        mp3_path = os.path.splitext(wav_path)[0] + ".mp3"
                        conv = subprocess.run(
                            [
                                "ffmpeg", "-y",
                                "-i", wav_path,
                                "-ar", "24000",
                                "-ac", "1",
                                "-c:a", "libmp3lame",
                                "-b:a", "128k",
                                mp3_path,
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        if conv.returncode != 0:
                            print(
                                "  -> Brand segment convert failed "
                                f"({conv.stderr.strip()[-200:]}); "
                                "using narration only."
                            )
                            return None
                        return mp3_path
                    except Exception as conv_error:
                        print(
                            "  -> Brand segment convert failed "
                            f"({type(conv_error).__name__}: {conv_error}); "
                            "using narration only."
                        )
                        return None

                converted_entries = []
                for entry in entries:
                    if entry.lower().endswith(".wav"):
                        converted = _wav_to_mp3(entry)
                        if converted is None:
                            converted_entries = []
                            break
                        converted_entries.append(converted)
                    else:
                        converted_entries.append(entry)
            if not converted_entries:
                print(
                    "  -> Brand audio concat skipped; "
                    "using narration only."
                )
            else:
                with open(
                    branded_audio_list, "w", encoding="utf-8"
                ) as f:
                    for entry in converted_entries:
                        f.write(
                            f"file '{os.path.abspath(entry)}'\n"
                        )

                branded_audio_path = os.path.join(
                    output_dir, "full_branded_audio.mp3"
                )
                brand_audio_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", branded_audio_list,
                    # Re-encode: stream-copy (-c copy) on the concat
                    # demuxer corrupts mixed-source MP3s (Edge-TTS
                    # narration + lame-converted brand segments have
                    # different encoder params -> truncated output).
                    "-ar", "24000",
                    "-ac", "1",
                    "-c:a", "libmp3lame",
                    "-b:a", "128k",
                    branded_audio_path,
                ]
                brand_audio_result = subprocess.run(
                    brand_audio_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if brand_audio_result.returncode == 0:
                    full_audio_path = branded_audio_path
                    print(
                        "  -> Branded audio (ding + narration + outro)."
                    )
                    # FINAL SILENT-TAIL GUARANTEE (dead-air fix,
                    # Issue 1 follow-up): the concat may end on the
                    # outro's pad, so trim any trailing silence off
                    # the assembled track.  Runs BEFORE the loudness
                    # pass so the alignment measures what ships.
                    VideoAssembler._trim_trailing_silence(
                        full_audio_path,
                    )
                    # The brand concat REBUILDS the track (the
                    # already-aligned narration + the ding/outro
                    # segments), so the shipped level drifts off
                    # target unless the loop runs again here --
                    # measured -14.61 LUFS on a real render before
                    # this pass, i.e. -0.61 LU off the target.
                    VideoAssembler._align_loudness(
                        full_audio_path,
                        label="branded"
                    )

                    # Persist the SFX pick only now that the cues
                    # actually shipped, so a failed render doesn't
                    # consume a variant (same rule as the intro
                    # hook ledger).
                    try:
                        remember_sfx(
                            sfx_ding_variant,
                            sfx_chime_variant,
                        )
                    except Exception:
                        pass
                else:
                    print(
                        "  -> Brand audio concat failed; "
                        "using narration only."
                    )
        except Exception as brand_error:
            print(
                f"  -> Branding skipped "
                f"({type(brand_error).__name__}: {brand_error}); "
                f"using unbranded video."
            )

        # =================================================
        # 4. GET REAL MEDIA DURATIONS
        # =================================================

        video_duration = (
            VideoAssembler
            ._get_media_duration(
                video_path
            )
        )

        audio_duration = (
            VideoAssembler
            ._get_media_duration(
                full_audio_path
            )
        )

        # =================================================
        # 4. PRINT SYNC REPORT
        # =================================================

        VideoAssembler._print_sync_report(
            audio_data,
            video_duration,
            audio_duration
        )

        # =================================================
        # 5. FINAL OUTPUT
        # =================================================

        final_output = os.path.join(
            output_dir,
            "final_video.mp4"
        )

        # =================================================
        # IMPORTANT
        #
        # Narration is NEVER truncated.
        #
        # Scenes are rendered to match the REAL measured TTS
        # audio (run.py passes audio_duration to
        # VisualEngine.render_scenes), so video_duration
        # should already equal audio_duration.  This mux uses
        # the LONGER of the two streams instead of the
        # previous min() cut:
        #
        # - audio longer than video (render fell short of the
        #   measured audio): the final frame is HELD via tpad
        #   so the narration plays out in full.
        # - video longer than audio (small render overshoot /
        #   rounding): the animation tail plays over silence
        #   rather than chopping narration mid-sentence.
        #
        # A warning is logged if the result exceeds the Shorts
        # length guideline, but content is never cut silently.
        # =================================================

        final_duration = max(
            video_duration,
            audio_duration
        )

        if final_duration > (
            VideoAssembler.MAX_FINAL_DURATION_S
        ):

            print(
                f"\n  ⚠️ Final duration "
                f"{final_duration:.1f}s exceeds the "
                f"{VideoAssembler.MAX_FINAL_DURATION_S:.0f}s "
                "Shorts guideline. Consider a shorter script "
                "for future runs (content is NOT truncated)."
            )

        hold_seconds = (
            video_duration - audio_duration
        )

        if hold_seconds < -(
            VideoAssembler.DURATION_EPSILON_S
        ):

            print(
                f"\n  ⏱️ Narration runs "
                f"{-hold_seconds:.2f}s past the animation; "
                "holding the final frame so the full "
                "voiceover plays."
            )

        # Base video filter: normalize to target canvas (1080x1920 or 1920x1080).
        target_w = getattr(settings, "canvas_width", 1080)
        target_h = getattr(settings, "canvas_height", 1920)
        video_filter = (
            f"scale={target_w}:{target_h}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:"
            "(ow-iw)/2:"
            "(oh-ih)/2"
        )

        # Extend the video to the audio length by cloning its
        # final frame (no frozen-gap, no abrupt cutoff).
        if hold_seconds < -(
            VideoAssembler.DURATION_EPSILON_S
        ):

            video_filter += (
                ",tpad=stop_mode=clone:"
                f"stop_duration={-hold_seconds:.3f}"
            )

        # -----------------------------------------------------
        # KINETIC SUBTITLE BURN-IN
        # -----------------------------------------------------
        from app.config import settings as _cfg
        burn_captions = bool(
            getattr(_cfg, "BURN_CAPTIONS", True)
        )
        if captions_path is None:
            candidate_srt = os.path.join(output_dir, "captions.srt")
            if os.path.isfile(candidate_srt):
                captions_path = candidate_srt

        if burn_captions and captions_path and os.path.isfile(captions_path):
            try:
                escaped_sub = (
                    str(os.path.abspath(captions_path))
                    .replace("\\", "/")
                    .replace(":", "\\:")
                )
                # Subtitle styling:
                # Landscape uses sleek 13pt crisp white documentary captions (&H00FFFFFF) with subtle outline.
                # Vertical shorts retain large 20pt golden-yellow captions.
                if getattr(_settings, "is_landscape", False):
                    sub_filter = (
                        f"subtitles='{escaped_sub}':force_style="
                        "'FontName=Arial,Bold=1,FontSize=13,"
                        "PrimaryColour=&H00FFFFFF,OutlineColour=&H000A0A0A,"
                        "BorderStyle=1,Outline=1.2,Shadow=0.8,Alignment=2,MarginV=38'"
                    )
                else:
                    sub_filter = (
                        f"subtitles='{escaped_sub}':force_style="
                        "'FontName=Arial,Bold=1,FontSize=20,"
                        "PrimaryColour=&H0000FFFF,OutlineColour=&H000A0A0A,"
                        "BorderStyle=1,Outline=2.8,Shadow=1.5,Alignment=2,MarginV=35'"
                    )
                video_filter += f",{sub_filter}"
                print("  -> Kinetic on-screen captions burned into video.")
            except Exception as sub_err:
                print(f"  -> Caption burning skipped ({sub_err}); continuing.")

        # -----------------------------------------------------
        # BACKGROUND MUSIC (BGM) AUTO-DUCKING MIX
        # -----------------------------------------------------
        bgm_enabled = bool(getattr(_cfg, "BGM_ENABLED", True))
        bgm_volume = float(getattr(_cfg, "BGM_VOLUME", 0.12))
        bgm_path = None
        if bgm_enabled:
            try:
                from app.audio.bgm import BGMEngine
                bgm_path = BGMEngine.pick_bgm(
                    topic_key=str(output_dir or ""),
                    category=str(sfx_category or ""),
                )
                if bgm_path and not os.path.isfile(str(bgm_path)):
                    bgm_path = None
            except Exception as bgm_err:
                print(f"  -> BGM engine unavailable ({bgm_err}); continuing without BGM.")
                bgm_path = None

        if bgm_path:
            print(
                f"  -> Background music active: {os.path.basename(str(bgm_path))} "
                f"at {bgm_volume*100:.0f}% volume (auto-ducked)."
            )
            amix_dur = "longest" if getattr(settings, "is_landscape", False) else "first"
            filter_complex = (
                f"[0:v]{video_filter}[vout];"
                f"[2:a]aloop=loop=-1:size=2e+09,volume={bgm_volume:.3f}[bgm];"
                f"[1:a][bgm]amix=inputs=2:duration={amix_dur}:dropout_transition=2[aout]"
            )
            merge_command = [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-i",
                full_audio_path,
                "-i",
                str(bgm_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "16",
                "-b:v",
                "10M",
                "-maxrate",
                "14M",
                "-bufsize",
                "20M",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-t",
                f"{final_duration:.3f}",
                "-movflags",
                "+faststart",
                final_output,
            ]
        else:
            merge_command = [
                "ffmpeg",
                "-y",
                "-i",
                video_path,
                "-i",
                full_audio_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "16",
                "-b:v",
                "10M",
                "-maxrate",
                "14M",
                "-bufsize",
                "20M",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                video_filter,
                "-t",
                f"{final_duration:.3f}",
                "-movflags",
                "+faststart",
                final_output,
            ]

        try:
            VideoAssembler._run_ffmpeg_command(
                merge_command
            )
        except Exception as merge_err:
            if bgm_path or (burn_captions and captions_path):
                print(
                    f"\n⚠️ Enhanced merge with BGM/captions failed ({merge_err}); "
                    "falling back to clean standard video+voiceover merge..."
                )
                fallback_command = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_path,
                    "-i",
                    full_audio_path,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "16",
                    "-b:v",
                    "10M",
                    "-maxrate",
                    "14M",
                    "-bufsize",
                    "20M",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-pix_fmt",
                    "yuv420p",
                    "-vf",
                    f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2",
                    "-t",
                    f"{final_duration:.3f}",
                    "-movflags",
                    "+faststart",
                    final_output,
                ]
                VideoAssembler._run_ffmpeg_command(fallback_command)
            else:
                raise

        # =================================================
        # 6. VERIFY FINAL VIDEO
        # =================================================

        final_video_duration = (
            VideoAssembler
            ._get_media_duration(
                final_output
            )
        )

        print(
            "\n🎥 Final video duration: "
            f"{final_video_duration:.2f}s"
        )

        print(
            f"🎬 Final video saved to: "
            f"{final_output}"
        )

        return final_output
