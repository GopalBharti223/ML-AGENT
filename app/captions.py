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


def _chunk_cue(narration: str, start: float, end: float, max_words: int = 5) -> list:
    """Split a scene narration into punchy 3-5 word dynamic subtitle cues."""
    words = str(narration or "").strip().split()
    if not words:
        return []
    if len(words) <= max_words:
        return [(start, end, " ".join(words))]

    chunks = []
    current = []
    for w in words:
        current.append(w)
        if len(current) >= max_words:
            chunks.append(" ".join(current))
            current = []
    if current:
        if len(current) <= 2 and chunks:
            chunks[-1] = chunks[-1] + " " + " ".join(current)
        else:
            chunks.append(" ".join(current))

    total_chars = max(1, sum(len(c) for c in chunks))
    total_time = max(0.1, end - start)
    cur_t = start
    result = []
    for idx, c in enumerate(chunks):
        c_dur = total_time * (len(c) / total_chars)
        c_end = cur_t + c_dur if idx < len(chunks) - 1 else end
        result.append((cur_t, c_end, c))
        cur_t = c_end
    return result


def generate_srt(
    audio_data,
    output_dir: str,
    filename: str = "captions.srt",
    time_offset: float = 0.0,
    chunk_cues: bool = True,
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

        if chunk_cues:
            sub_cues = _chunk_cue(
                narration,
                start + time_offset,
                end + time_offset,
            )
            cues.extend(sub_cues)
        else:
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


def _format_ass_timestamp(seconds: float) -> str:
    """Format float seconds to ASS format: H:MM:SS.cc"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 0
        secs += 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def generate_ass_word_glow(
    audio_data,
    output_dir: str,
    filename: str = "captions.ass",
    time_offset: float = 0.0,
    active_color_bgr: str = "&H0024E5FF&",  # Bright Neon Yellow / Gold
    default_color_bgr: str = "&H00FFFFFF&", # Crisp White
) -> str | None:
    """Generate high-retention, word-by-word highlighted ASS captions for YouTube Shorts.

    Each phrase (2-4 words) is displayed while the active spoken word lights up
    in bright neon gold/yellow (active_color_bgr) while surrounding words stay crisp white.
    """
    if not audio_data:
        return None

    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,50,&H00FFFFFF,&H000000FF,&H00080808,&H80000000,-1,0,0,0,100,100,0,0,1,3.8,1.2,2,40,40,240,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    event_count = 0

    for item in audio_data:
        if not isinstance(item, dict):
            continue
        narration = str(item.get("narration", "") or "").strip()
        if not narration:
            continue
        try:
            start = float(item.get("start_time") or 0.0) + time_offset
            end = float(item.get("end_time") or start) + time_offset
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue

        words = narration.split()
        if not words:
            continue

        # Split into short 3-word punchy phrases
        phrases = []
        cur_phrase = []
        for w in words:
            cur_phrase.append(w)
            if len(cur_phrase) >= 3:
                phrases.append(cur_phrase)
                cur_phrase = []
        if cur_phrase:
            if len(cur_phrase) == 1 and phrases:
                phrases[-1].extend(cur_phrase)
            else:
                phrases.append(cur_phrase)

        total_words = sum(len(p) for p in phrases)
        if total_words == 0:
            continue

        total_duration = end - start
        cur_t = start

        for phrase in phrases:
            p_len = len(phrase)
            p_duration = total_duration * (p_len / total_words)
            p_end = cur_t + p_duration
            w_duration = p_duration / p_len

            for w_idx, active_word in enumerate(phrase):
                w_start = cur_t + (w_idx * w_duration)
                w_finish = w_start + w_duration if (w_idx < p_len - 1) else p_end

                t_start_str = _format_ass_timestamp(w_start)
                t_end_str = _format_ass_timestamp(w_finish)

                # Build line with active word highlighted
                parts = []
                for idx, w in enumerate(phrase):
                    clean_w = w.strip().upper()
                    if idx == w_idx:
                        parts.append(f"{{\\c{active_color_bgr}\\b1}}{clean_w}{{\\c{default_color_bgr}\\b0}}")
                    else:
                        parts.append(clean_w)

                dialogue_text = " ".join(parts)
                ass_lines.append(f"Dialogue: 0,{t_start_str},{t_end_str},Default,,0,0,0,,{dialogue_text}")
                event_count += 1

            cur_t = p_end

    if event_count == 0:
        return None

    os.makedirs(output_dir, exist_ok=True)
    ass_path = os.path.join(output_dir, filename)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines))

    print(f"✨ Kinetic Glow ASS Subtitles generated: {ass_path} ({event_count} word events)")
    return ass_path