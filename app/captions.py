"""SRT caption generation timed to REAL TTS audio.

The narration audio per scene is generated before assembly;
TTSEngine.generate_narration() returns each scene's real
start_time/end_time measured from the actual MP3 duration.
This module writes an .srt whose cue timings match that real
audio, so captions stay in sync with what is actually spoken
(even when narration runs longer/shorter than the script
plan).
"""

import os


def _format_timestamp(seconds) -> str:
    """SRT timestamp HH:MM:SS,mmm from float seconds."""

    if seconds < 0:
        seconds = 0.0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))

    if millis >= 1000:
        millis = 0
        secs += 1

    return (
        f"{hours:02d}:{minutes:02d}:"
        f"{secs:02d},{millis:03d}"
    )


def _wrap(text, width=42) -> str:
    """Word-wrap a caption, max 2 lines (SRT player friendly)."""

    words = str(text).split()

    lines = []
    current = ""

    for word in words:

        candidate = f"{current} {word}".strip()

        if len(candidate) > width and current:

            lines.append(current)
            current = word

        else:

            current = candidate

    if current:
        lines.append(current)

    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]

    return "\n".join(lines)


def generate_srt(
    audio_data,
    output_dir: str,
    filename: str = "captions.srt",
    time_offset: float = 0.0,
) -> str | None:
    """Write an SRT file cued to the REAL per-scene audio.

    `time_offset` shifts every cue (e.g. by the branded intro
    length, so captions stay aligned when intro/outro cards
    wrap the narration).  Returns the path to the written
    file, or None when there are no usable narration cues
    (caller degrades gracefully).
    """

    cues = []

    for item in audio_data or []:

        if not isinstance(item, dict):
            continue

        narration = str(
            item.get("narration", "") or ""
        ).strip()

        if not narration:
            continue

        try:

            start = float(
                item.get("start_time") or 0.0
            )
            end = float(
                item.get("end_time") or start
            )

        except (TypeError, ValueError):

            continue

        if end <= start:
            continue

        cues.append((start + time_offset, end + time_offset, narration))

    if not cues:

        print(
            "⚠️ No narration cues with usable timing; "
            "SRT caption file skipped."
        )

        return None

    os.makedirs(output_dir, exist_ok=True)

    path = os.path.join(output_dir, filename)

    lines = []

    for index, (start, end, narration) in enumerate(
        cues, start=1
    ):

        lines.append(str(index))
        lines.append(
            f"{_format_timestamp(start)} --> "
            f"{_format_timestamp(end)}"
        )
        lines.append(_wrap(narration))
        lines.append("")

    with open(path, "w", encoding="utf-8-sig") as f:

        f.write("\n".join(lines))

    total_end = _format_timestamp(cues[-1][1])

    print(
        f"💬 Captions written to: {path} "
        f"({len(cues)} cues, ends {total_end})"
    )

    return path