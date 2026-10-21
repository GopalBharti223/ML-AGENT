"""
Intro/outro brand cards + the signature intro ding (B3).

Renders the "MetricForge" intro card and the "Subscribe for more data
stories" outro card with the SAME matplotlib palette as the charts
(BG_COLOR / TEXT_COLOR / gold accents), synthesizes a single fixed
intro-ding cue (saved once to assets/sfx/intro_ding.wav, then reused
in every video), and provides the symmetric audio/video segment builders
so run.py can prepend/append them around the narration and animation
BEFORE the final mux.

Both sides grow identically, so the mux's max(video, audio) logic
and the tpad narration-hold behavior are untouched.  All failures
degrade gracefully -- if any card/ding/audio build fails, the run
continues with an unbranded video (same principle as the caption and
comment steps, which never fail the upload).
"""

import os
import subprocess
import wave
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")

from app.config import settings

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patheffects import withStroke

from app.visuals.scene_engine import VisualEngine

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

INTRO_DURATION_S = 1.2
OUTRO_DURATION_S = 1.2
DING_DURATION_S = 0.75
CARD_FPS = 30

ASSETS_SFX_DIR = Path(
    __file__
).resolve().parents[2] / "assets" / "sfx"

DING_PATH = ASSETS_SFX_DIR / "intro_ding.wav"

_INTRO_FILENAME = "intro_card.mp4"
_OUTRO_FILENAME = "outro_card.mp4"
_BRANDED_FILENAME = "branded_visual.mp4"
_INTRO_AUDIO_FILENAME = "intro_audio.mp3"
_OUTRO_AUDIO_FILENAME = "outro_audio.mp3"


def _channel_name() -> str:

    from app.config import settings

    return str(
        getattr(settings, "CHANNEL_NAME", "") or "MetricForge"
    ).strip()


# ---------------------------------------------------------
# SYNTHESIZED INTRO DING (fixed cue, generated once)
# ---------------------------------------------------------

def synthesize_intro_ding(
    force: bool = False,
    variant: int = 0,
) -> Path | None:

    """
    Synthesize the signature intro ding (sine glide + exponential decay(
    to assets/sfx/intro_ding.wav.

  Idempotent: skips if the file already exists unless force=True.

  Frequencies: 880 Hz (A5) gliding down to  523 Hz (C5) over
    0.75s with a fast exponential decay envelope -- a bright but short
    "brand" chime, not a long melody.  Written as 16-bit PCM mono
    44.1kHz WAV (uncompressed, ~66 KB), compatible with every
    ffmpeg build the pipeline already drives.

  variant=0 (the default) is that original cue, unchanged.
  Higher values pick one of the rotated brand stings defined in
  app.video.sfx -- the synthesis itself lives there so this
  wrapper keeps its original signature/behavior.

    Returns the path, or None on any synthesis failure (caller degrades).
    """

    try:

        from app.video.sfx import (
            synthesize_ding_variant,
        )

        return synthesize_ding_variant(variant, force)

    except Exception as error:

        print(
            f"⚠️ Intro-ding synthesis failed "
            f"({type(error).__name__}: {error}; "
            "video continues unbranded."
        )

        return None

# ---------------------------------------------------------
# CARD RENDER (shared canvas)
# ---------------------------------------------------------

# Fraction of the 1080px card width that card text may occupy.
# YouTube Shorts overlays (caption bar, like buttons, handle)
# cover the edges, so ALL card text stays inside this central
# safe band instead of running edge-to-edge.
CARD_SAFE_WIDTH_FRACTION = 0.80

CARD_ACCENT_GLYPH = "\u2581\u2581\u2581\u2581\u2581\u2581\u2581\u2581\u2581\u2581\u2581"


def _fit_card_text(fig) -> None:
    """Shrink every card text line until it fits inside the safe
    central band of the 1080px card frame.

    A fixed fontsize ("Subscribe for more data stories" at 56pt)
    is far wider than the frame and gets clipped on both edges, so
    we measure each line against the renderer and scale it down
    (a few passes, then stop).  The intro card's "DATA STORIES"
    already fits, and the channel-name line benefit from the same
    guard whenever a longer channel name is configured.
    """
    if fig is None:
        return

    canvas = getattr(fig, "canvas", None)

    if canvas is None:
        return

    try:
        renderer = canvas.get_renderer()

        if renderer is None:
            canvas.draw()
            renderer = canvas.get_renderer()
    except Exception:
        try:
            canvas.draw()
            renderer = canvas.get_renderer()
        except Exception:
            return

    max_width_px = 1080 * CARD_SAFE_WIDTH_FRACTION

    for _ in range(4):

        any_shrunk = False

        for artist in fig.texts:

            text = str(artist.get_text() or "").strip()

            if not text or text == CARD_ACCENT_GLYPH:
                continue

            try:
                width = artist.get_window_extent(
                    renderer=renderer
                ).width
            except Exception:
                continue

            if width <= max_width_px:
                continue

            if artist.get_fontsize() <= 12.0:
                continue

            scale = (max_width_px / width) * 0.97
            artist.set_fontsize(
                max(12.0, artist.get_fontsize() * scale)
            )
            any_shrunk = True

        if not any_shrunk:
            break


def _new_card(
    lines: list,
    accent_y: float,
):
    """
    Build a 1080x1920 card figure holding centered text lines
    with a champagne-gold rule beneath.  `lines` = list of
    (text, fontsize, color, weight) tuples. Returns (fig).
    """

    fig = plt.figure(
        figsize=(10.8, 19.2),
        dpi=100,
    )

    fig.patch.set_facecolor(
        VisualEngine.BG_COLOR
    )

    # Vertical gradient (top → bottom) matching the chart backdrop.



    gradient = np.linspace(
        1.0,
        0.82,
        1920,
    ).reshape(-1, 1)

    gradient_rgb = np.zeros((1920, 3))

    def _hex(hex_color):

        hex_color = str(
            hex_color
        ).lstrip("#")

        return tuple(
            int(hex_color[i:i + 2], 16) / 255.0
            for i in (0, 2, 4)
        )

    top = np.array(
        _hex(VisualEngine.BG_GRADIENT_TOP)
    )
    bottom = np.array(
        _hex(VisualEngine.BG_GRADIENT_BOTTOM)
    )

    for channel in range(3):

        gradient_rgb[:, channel] = (
            top[channel] * gradient[:, 0]
            + bottom[channel] * (1.0 - gradient[:, 0])
        )



    fig.figimage(
        gradient_rgb,
        xo=0,
        yo=0,
        origin="lower",
        zorder=0,
    )



    for index, (text, fontsize, color, weight) in enumerate(lines):

        fig.text(
            0.5,
            0.56 - index * 0.14,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            fontweight=weight,
            color=color,
            zorder=10,
            path_effects=[
                withStroke(
                    linewidth=3,
                    foreground="#0A0D12",
                )
            ],
        )

    fig.text(
        0.5,
        accent_y,
        CARD_ACCENT_GLYPH,
        ha="center",
        va="center",
        fontsize=38,
        color=VisualEngine.ELECTRIC_BLUE,
        zorder=10,
    )

    # Fit every line inside the safe central band so long text
    # (outro CTA / longer channel names) is never clipped.
    _fit_card_text(fig)

    return fig


def _animate_card(
    fig,
    output_dir: str,
    filename: str,
    duration_s: float,
) -> str:

    """
    Save `fig` as a short mp4 card via the same FFMpegWriter the
    main charts use.  A subtle alpha pulse gives the card life
    without any layout complexity.s
    """

    output_path = os.path.join(
        output_dir,
        filename,
    )

    total_frames = max(
        1,
        int(duration_s * CARD_FPS),
    )

    text_layer = [

        artist
        for artist in fig.texts

        if artist.get_text() and artist.get_text() != CARD_ACCENT_GLYPH
    ]

    def update(frame):

        pulse = 0.85 + 0.15 * np.sin(
            2.0 * np.pi * frame / total_frames
        )

        for artist in text_layer:

            artist.set_alpha(pulse)

        return text_layer

    anim = animation.FuncAnimation(
        fig,
        update,
        frames=total_frames,
        interval=1000 / CARD_FPS,
        blit=False,
    )

    writer = animation.FFMpegWriter(
        fps=CARD_FPS,
        bitrate=12000,
    )

    anim.save(
        output_path,
        writer=writer,
    )

    plt.close(fig)

    return output_path
# ---------------------------------------------------------
# BRAND CARDS
# ---------------------------------------------------------

def render_intro_card(
    output_dir: str,
) -> str | None:

    """
    Render the "MetricForge" intro card (~INTRO_DURATION_S) with the
    chart palette.  Returns the mp4 path, or None on failure.

    """

    try:

        name = _channel_name()

        fig = _new_card(
            lines=[
                (name, 120, VisualEngine.TEXT_COLOR, "bold"),
                ("DATA STORIES", 34, VisualEngine.SECONDARY_TEXT, "normal"),
            ],
            accent_y=0.40,
)




        path = _animate_card(
            fig,
            output_dir,
            _INTRO_FILENAME,
            INTRO_DURATION_S,
        )

        print(
            f"🎬 Intro card rendered: {path}"
        )

        return path



    except Exception as error:

        print(
            f"⚠️ Intro card failed "
            f"({type(error).__name__}: {error}; "
            "video continues without it."
        )

        return None


def render_outro_card(
    output_dir: str,
) -> str | None:

    """
    Render the "Subscribe for more data stories — @MetricForge"
    outro card (~OUTRO_DURATION_S).)  Returns the mp4 path, or None.

    """

    try:

        name = _channel_name()

        fig = _new_card(
            lines=[
                (
                    str(
                        getattr(settings, "OUTRO_CTA_TEXT", "")
                        or "Follow for more data stories"
                    ),
                    56, VisualEngine.TEXT_COLOR, "bold",),
                (f"— @{name}", 56, VisualEngine.ELECTRIC_BLUE, "bold",),
            ],
            accent_y=0.36,
        )

        path = _animate_card(
            fig,
            output_dir,
            _OUTRO_FILENAME,
            OUTRO_DURATION_S,
        )

        print(
            f"🎬 Outro card rendered: {path}"
        )

        return path



    except Exception as error:

        print(
            f"⚠️ Outro card failed "
            f"({type(error).__name__}: {error}; "
            "video continues without it."
        )

        return None

    plt.close(fig)

    return output_path
# ---------------------------------------------------------
# BRAND AUDIO SEGMENTS (symmetric with the cards)
# ---------------------------------------------------------

def _write_silence_wav(
    path: str,
    duration_s: float,
) -> bool:

    """16-bit PCM mono silence (pad the ding to the card length)."""

    try:

        sample_rate = 44100
        n_samples = int(sample_rate * duration_s)

        pcm = np.zeros(
            n_samples,
            dtype=np.int16,
        )

        with wave.open(
            path,
            "wb",
        )as handle:

            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())

        return True

    except Exception as error:

        print(
            f"⚠️ Silence-wav generation failed "
            f"({type(error).__name__}: {error})"
        )

        return False


def _build_intro_audio(
    output_dir: str,
    variant: int = 0,
) -> dict | None:

    """Intro ding as MP3 at the TTS narration format.

    Same-codec MP3 output is deliberate: the assembler joins
    brand segments + narration with the ffmpeg concat demuxer,
    which requires identical codec/rate/channels.  WAV output
    here produced mixed-codec concats with truncated audio,
    so this function encodes MP3 directly at 24kHz mono
    (ding padded with silence to INTRO_DURATION_S).

    Returns an audio_data-style dict (audio_path only), or
    None on failure (caller degrades to unbranded audio).
    """

    try:

        ding_path = None

        ding = synthesize_intro_ding(variant=variant)

        if ding:

            ding_path = str(ding)

        intro_path = os.path.join(
            output_dir,
            _INTRO_AUDIO_FILENAME,
        )

        sample_rate = 24000
        total_samples = int(sample_rate * INTRO_DURATION_S)

        ding_pcm = np.zeros(
            0,
            dtype=np.int16,
        )

        if ding_path and Path(ding_path).is_file():

            with wave.open(ding_path, "rb") as handle:

                params = handle.getparams()

                frames = handle.readframes(
                    params.nframes
                )

                raw = np.frombuffer(
                    frames,
                    dtype=np.int16,
                )

                if params.nchannels > 1:

                    raw = raw.reshape(-1, params.nchannels)[
                        :, 0
                    ]

                if params.framerate != sample_rate:

                    # Linear resample 44.1k -> 24k (short cue;
                    # quality loss is inaudible under narration).
                    src_index = (
                        np.arange(len(raw))
                        * sample_rate
                        / params.framerate
                    )
                    dst_index = np.arange(
                        int(
                            len(raw)
                            * sample_rate
                            / params.framerate
                        )
                    )
                    left = np.floor(src_index).astype(int)
                    left = np.clip(left, 0, len(raw) - 1)
                    right = np.clip(left + 1, 0, len(raw) - 1)
                    frac = src_index - left
                    ding_pcm = (
                        raw[left] * (1.0 - frac)
                        + raw[right] * frac
                    ).astype(np.int16)

                else:

                    ding_pcm = raw.astype(np.int16)

        pcm = np.zeros(
            total_samples,
            dtype=np.int16,
        )

        take = min(len(ding_pcm), total_samples)

        if take > 0:

            pcm[:take] = ding_pcm[:take]

        wav_tmp = intro_path + ".tmp.wav"

        with wave.open(wav_tmp, "wb") as handle:

            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())

        conv = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_tmp,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                intro_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:

            os.remove(wav_tmp)

        except OSError:

            pass

        if conv.returncode != 0:

            print(
                f"Intro-audio encode failed "
                f"({conv.stderr.strip()[-200:]}; "
                "video continues without it."
            )

            return None

        return {
            "audio_path": intro_path,
            "is_branding": True,
        }

    except Exception as error:

        print(
            f"Intro-audio build failed "
            f"({type(error).__name__}: {error}; "
            "video continues without it."
        )

        return None


def _build_outro_audio(
    output_dir: str,
    variant: int = 0,
) -> dict | None:

    """Outro chime + silence padding as MP3 at the TTS format.

    DEAD-AIR FIX (published-video review, Issue 1): the outro
    used to be OUTRO_DURATION_S of PURE silence -- the published
    India military-spending video ended with a measured 1.9s
    hole (narration ended at 28.84s; the silent outro plus the
    video-only tail ran to 30.77s with nothing but the subscribe
    card on screen).  A soft two-note descending chime now plays
    under the card so the ending is signed, not silent.

    MP3 (not WAV) for the same concat-codec reason as intro:
    24kHz mono, encoded direct to MP3 so the demuxer sees
    identical segments.  The chime sits at ~35% of the intro
    ding's amplitude: present, but clearly a sign-off.
    """

    try:

        outro_path = os.path.join(
            output_dir,
            _OUTRO_AUDIO_FILENAME,
        )

        sample_rate = 24000
        total_samples = int(sample_rate * OUTRO_DURATION_S)

        pcm = np.zeros(
            total_samples,
            dtype=np.int16,
        )

        # Two-note descending chime (E5 -> B4).  DEAD-AIR FIX
        # (Issue 1 follow-up): the notes used to be 0.30s each
        # followed by PURE SILENCE to the end of the card, which
        # measured 0.67s of dead air -- 55.5% of the shipped
        # outro_audio.mp3 (start=0.53s end=1.20s) and the final
        # 0.66s of the shipped video.  The two notes now span the
        # whole OUTRO_DURATION_S with a gentler decay so the
        # sign-off rings through the card instead of stopping
        # half-way and leaving the tail silent.  Pure numpy, same
        # synthesis approach as the intro ding.
        chime_gain = 0.35

        # Note set rotates per video (PRIORITY 1: the outro was
        # the same two notes in every upload).  The notes still
        # span the WHOLE card because note_seconds divides
        # OUTRO_DURATION_S -- that is the dead-air guarantee, and
        # it holds for every variant including the 3-note one.
        note_freqs = _chime_notes(variant)
        note_seconds = OUTRO_DURATION_S / len(note_freqs)
        decay_rate = 2.0

        for note_index, freq in enumerate(note_freqs):

            note_start = int(
                sample_rate * note_index * note_seconds
            )

            if note_start >= total_samples:
                break

            n_note = min(
                int(sample_rate * note_seconds),
                total_samples - note_start,
            )

            t = np.linspace(
                0.0,
                n_note / sample_rate,
                n_note,
                endpoint=False,
            )

            tone = np.sin(2.0 * np.pi * freq * t)

            envelope = np.exp(-decay_rate * t / note_seconds)

            fade_in = max(
                1,
                min(int(sample_rate * 0.005), n_note),
            )

            fade = np.ones(n_note)
            fade[:fade_in] = np.linspace(
                0.0,
                1.0,
                fade_in,
                endpoint=False,
            )

            note_pcm = tone * envelope * fade * chime_gain

            existing = (
                pcm[note_start:note_start + n_note]
                .astype(np.float64)
                / 32767.0
            )

            mixed = np.clip(
                existing + note_pcm,
                -1.0,
                1.0,
            )

            pcm[note_start:note_start + n_note] = (
                mixed * 32767.0
            ).astype(np.int16)

        # The longer, gentler decay means the last sample is still
        # audible (~-26dB), so fade the final 50ms to zero: the
        # segment must END cleanly, not on a click.
        tail_fade = max(
            1, min(int(sample_rate * 0.05), total_samples)
        )

        pcm[-tail_fade:] = (
            pcm[-tail_fade:]
            * np.linspace(1.0, 0.0, tail_fade, endpoint=False)
        ).astype(np.int16)

        wav_tmp = outro_path + ".tmp.wav"

        with wave.open(wav_tmp, "wb") as handle:

            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())

        conv = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_tmp,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                outro_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:

            os.remove(wav_tmp)

        except OSError:

            pass

        if conv.returncode != 0:

            print(
                f"Outro-audio encode failed "
                f"({conv.stderr.strip()[-200:]}; "
                "video continues without it."
            )

            return None

        return {
            "audio_path": outro_path,
            "is_branding": True,
        }

    except Exception as error:

        print(
            f"Outro-audio build failed "
            f"({type(error).__name__}: {error}; "
            "video continues without it."
        )

        return None


def _chime_notes(variant: int) -> tuple:

    """
    Note frequencies for an outro-chime variant.

    Reads the rotating note table from app.video.sfx; falls
    back to the ORIGINAL pair (E5 -> B4) if that module is
    unavailable, so branding can never hard-fail on an SFX
    import problem.
    """

    try:

        from app.video.sfx import chime_notes

        notes = tuple(chime_notes(variant))

        if notes:
            return notes

    except Exception:
        pass

    return (659.26, 493.88)


def build_brand_audio_segments(
    output_dir: str,
    ding_variant: int = 0,
    chime_variant: int = 0,
):

    """Build (intro_audio, outro_audio) segments (either may be None).

    ding_variant / chime_variant rotate the brand cues per video
    (PRIORITY 1).  Both default to 0, which is the original
    cue for each, so an un-rotated caller is byte-identical to
    the previous behavior.
    """

    return (
        _build_intro_audio(output_dir, variant=ding_variant),
        _build_outro_audio(output_dir, variant=chime_variant),
    )


def build_tail_bridge_audio(
    output_dir: str,
    seconds: float,
) -> dict | None:

    """Silence bridge MP3 matching the animation's tail hold.

    The animation runs AUDIO_TAIL_HOLD (~0.75s) longer than the
    narration so the mux never truncates speech.  Without a
    matching audio segment the branded concat ended the AUDIO
    stream before the VIDEO stream -- the published video
    shipped 0.73s with no audio samples at all (the tail of the
    user-measured 1.9s end hole).  This bridge keeps the audio
    stream exactly as long as the animation, so the outro chime
    lands precisely on the outro card instead of ~0.7s early.

    Returns an audio_data-style dict, or None when no bridge is
    needed (seconds <= 0.05) or the encode fails (caller
    degrades to narration + outro only).
    """

    try:

        if seconds is None or seconds <= 0.05:
            return None

        seconds = min(float(seconds), 5.0)

        # DEAD-AIR GUARD (Issue 1 follow-up): this segment is 100%
        # silence BY DESIGN -- it exists only to keep the audio
        # stream level with the video so the outro chime lands ON the
        # outro card.  Because it is dead air it must stay below the
        # dead-air detection floor: its size comes from
        # VisualEngine.AUDIO_TAIL_HOLD, which is 0.20s by default and
        # yields a ~0.19s bridge (MEASURED: 0.2395s when the hold was
        # 0.25s).  Warn (never fail) if a future change pushes it
        # back above the floor -- that is exactly how the published
        # 0.73s silent hole got shipped.
        warn_after = float(
            getattr(settings, "TAIL_BRIDGE_WARN_S", 0.30) or 0.30
        )

        if seconds > warn_after:

            print(
                f"  -> WARNING: tail bridge is {seconds:.2f}s of "
                f"pure silence (> {warn_after:.2f}s dead-air floor); "
                "lower AUDIO_TAIL_HOLD (currently "
                f"{getattr(settings, 'AUDIO_TAIL_HOLD_S', '?')}s) or "
                "the video will end on a silent hole."
            )

        bridge_path = os.path.join(
            output_dir,
            "tail_bridge_audio.mp3",
        )

        sample_rate = 24000
        total_samples = int(sample_rate * seconds)

        pcm = np.zeros(
            total_samples,
            dtype=np.int16,
        )

        wav_tmp = bridge_path + ".tmp.wav"

        with wave.open(wav_tmp, "wb") as handle:

            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())

        conv = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", wav_tmp,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                bridge_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:

            os.remove(wav_tmp)

        except OSError:

            pass

        if conv.returncode != 0:

            print(
                f"  -> Tail-bridge encode failed "
                f"({conv.stderr.strip()[-200:]}); "
                "continuing without it."
            )

            return None

        return {
            "audio_path": bridge_path,
            "is_branding": True,
        }

    except Exception as error:

        print(
            f"  -> Tail-bridge build failed "
            f"({type(error).__name__}: {error}); "
            "continuing without it."
        )

        return None
# ---------------------------------------------------------
# VIDEO-SIDE CONCAT (intro + animation + outro)
# ---------------------------------------------------------

def build_branded_video(
    animation_path: str,
    output_dir: str,
    intro_path: str | None = None,
    outro_path: str | None = None,
) -> str:

    """
    Concatenate [intro_card] + animation + [outro_card] into
    branded_visual.mp4 via ffmpeg conat demuxer.

    Returns the new path, or the ORIGINAL animation path unchanged when
    no cards were provided (or when concat failed)."""


    segments = []

    if intro_path:

        segments.append(intro_path)

    segments.append(animation_path)

    if outro_path:

        segments.append(outro_path)



    if len(segments) <= 1:

        return animation_path



    try:

        list_path = os.path.join(
            output_dir,
            "brand_concat.txt",
        )

        with open(list_path, "w", encoding="utf-8") as handle:

            for segment in segments:

                handle.write(
                    f"file '{os.path.basename(segment)}'\n"
                )

        branded_path = os.path.join(
            output_dir,
            _BRANDED_FILENAME,
        )

        concat_command = [

            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            branded_path,
        ]

        result = subprocess.run(
            concat_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:

            print(
                f"⚠️ Branded-video concat failed "
                f"({result.stderr.strip()[:200]}; "
                "using the unbranded animation."
            )

            return animation_path



        print(
            f"🎬 Branded visual saved: {branded_path}"
        )

        return branded_path



    except Exception as error:

        print(
            f"⚠️ Branded-video concat failed "
            f"({type(error).__name__}: {error}; "
            "using the unbranded animation."
        )

        return animation_path


# =========================================================
# STANDALONE CLI (render + synth + print, no video run(
# =========================================================

if __name__ == "__main__":

    out = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "_batch",
        "branding_preview",
    )
    os.makedirs(out, exist_ok=True)
    print(f"Intro card: {render_intro_card(out)}")
    print(f"Outro card: {render_outro_card(out)}")
    ding = synthesize_intro_ding()
    print(f"Intro ding: {ding}")
    intro_audio, outro_audio = build_brand_audio_segments(out)
    print(f"Intro audio: {intro_audio}")
    print(f"Outro audio: {outro_audio}")
