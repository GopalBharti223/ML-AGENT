"""Background Music (BGM) Engine for YouTube Shorts retention.

Provides dynamic, driving background music tracks to eliminate dead-air,
maintain viewer adrenaline, and boost Average Percentage Viewed (APV).

Features:
1. Auto-discovers any user-provided tracks (.mp3, .wav, .m4a) in `assets/audio/music/`.
2. If no custom tracks are provided, procedurally synthesizes 3 distinct,
   copyright-free cinematic suspense & driving rhythm tracks using pure numpy:
   - cinematic_pulse: Driving 124 BPM heartbeat kick + D-minor suspense drone.
   - tension_riser: Dark 110 BPM cinematic ambient drone with rising tension.
   - cyber_groove: Upbeat 128 BPM electronic synth bassline.
3. Rotates tracks per video based on topic key / category to prevent repetition.
4. Auto-ducking level configuration (BGM_VOLUME, default 0.12 or -18dB) to keep
   narration speech crystal-clear at -14 LUFS while driving the video pace.
"""

import hashlib
import os
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings

ASSETS_MUSIC_DIR = (
    Path(__file__).resolve().parents[2] / "assets" / "audio" / "music"
)

SAMPLE_RATE = 44100


class BGMEngine:
    """Manages background music discovery, procedural synthesis, and selection."""

    TRACK_NAMES = [
        "battle_rush.wav",
        "cinematic_pulse.wav",
        "tension_riser.wav",
        "cyber_groove.wav",
    ]

    @classmethod
    def get_music_dir(cls) -> Path:
        """Ensure music assets directory exists and return it."""
        ASSETS_MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        return ASSETS_MUSIC_DIR

    @classmethod
    def list_available_tracks(cls) -> List[Path]:
        """List all valid audio files in the music directory."""
        music_dir = cls.get_music_dir()
        valid_extensions = {".mp3", ".wav", ".m4a", ".aac"}
        tracks = [
            p for p in music_dir.iterdir()
            if p.is_file() and p.suffix.lower() in valid_extensions
        ]
        return sorted(tracks)

    # =========================================================
    # PROCEDURAL SYNTHESIS (100% Royalty-Free & Pure Python)
    # =========================================================

    @staticmethod
    def _save_wav(filepath: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
        """Write float32 [-1, 1] samples to 16-bit PCM WAV."""
        samples = np.clip(samples, -0.98, 0.98)
        int16_samples = (samples * 32767).astype(np.int16)
        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(int16_samples.tobytes())

    @classmethod
    def synthesize_cinematic_pulse(cls, duration_s: float = 35.0) -> Path:
        """Synthesize a 124 BPM driving cinematic pulse with sub-bass kick."""
        music_dir = cls.get_music_dir()
        filepath = music_dir / "cinematic_pulse.wav"
        if filepath.exists() and filepath.stat().st_size > 1000:
            return filepath

        total_samples = int(duration_s * SAMPLE_RATE)
        time = np.linspace(0, duration_s, total_samples, endpoint=False)
        output = np.zeros(total_samples, dtype=np.float32)

        bpm = 124.0
        beat_interval = 60.0 / bpm
        beat_samples = int(beat_interval * SAMPLE_RATE)

        # 1. Heartbeat / Sub Kick Drum on each beat
        kick_duration = 0.22
        kick_samples = int(kick_duration * SAMPLE_RATE)
        k_time = np.linspace(0, kick_duration, kick_samples, endpoint=False)
        freq_env = 140.0 * np.exp(-k_time * 24.0) + 45.0
        phase = np.cumsum(freq_env / SAMPLE_RATE) * 2.0 * np.pi
        kick = np.sin(phase) * np.exp(-k_time * 12.0)

        for b_start in range(0, total_samples, beat_samples):
            b_end = min(total_samples, b_start + kick_samples)
            length = b_end - b_start
            output[b_start:b_end] += kick[:length] * 0.45

        # 2. D-Minor Suspense Sub-Bass Drone (D2: 73.4Hz + F2: 87.3Hz + A1: 55Hz)
        vibrato = 1.0 + 0.015 * np.sin(2.0 * np.pi * 0.5 * time)
        sub1 = np.sin(2.0 * np.pi * 73.42 * vibrato * time) * 0.22
        sub2 = np.sin(2.0 * np.pi * 55.00 * time) * 0.18
        drone = (sub1 + sub2) * (0.8 + 0.2 * np.sin(2.0 * np.pi * 0.1 * time))
        output += drone

        # 3. 16th-Note Shaker / High Pulse (creates forward motion)
        step_samples = beat_samples // 4
        rng = np.random.RandomState(42)
        noise = rng.normal(0, 0.05, 400).astype(np.float32)
        decay = np.exp(-np.linspace(0, 15.0, 400))
        hat = noise * decay

        for s_start in range(0, total_samples, step_samples):
            s_end = min(total_samples, s_start + len(hat))
            length = s_end - s_start
            output[s_start:s_end] += hat[:length] * 0.08

        cls._save_wav(filepath, output)
        return filepath

    @classmethod
    def synthesize_tension_riser(cls, duration_s: float = 35.0) -> Path:
        """Synthesize a 110 BPM dark atmospheric suspense drone."""
        music_dir = cls.get_music_dir()
        filepath = music_dir / "tension_riser.wav"
        if filepath.exists() and filepath.stat().st_size > 1000:
            return filepath

        total_samples = int(duration_s * SAMPLE_RATE)
        time = np.linspace(0, duration_s, total_samples, endpoint=False)
        output = np.zeros(total_samples, dtype=np.float32)

        bpm = 110.0
        beat_interval = 60.0 / bpm
        beat_samples = int(beat_interval * SAMPLE_RATE)

        # 1. Heavy low-tom heartbeat (beats 1 and 3)
        tom_samples = int(0.35 * SAMPLE_RATE)
        t_time = np.linspace(0, 0.35, tom_samples, endpoint=False)
        tom_freq = 95.0 * np.exp(-t_time * 10.0) + 40.0
        tom_phase = np.cumsum(tom_freq / SAMPLE_RATE) * 2.0 * np.pi
        tom = np.sin(tom_phase) * np.exp(-t_time * 7.0)

        step = 0
        for b_start in range(0, total_samples, beat_samples):
            if step % 2 == 0:
                b_end = min(total_samples, b_start + tom_samples)
                length = b_end - b_start
                output[b_start:b_end] += tom[:length] * 0.40
            step += 1

        # 2. C-Minor Chord Swell (C2: 65.4Hz, Eb2: 77.8Hz, G2: 98.0Hz)
        chord = (
            np.sin(2.0 * np.pi * 65.41 * time) * 0.20
            + np.sin(2.0 * np.pi * 77.78 * time) * 0.16
            + np.sin(2.0 * np.pi * 97.99 * time) * 0.12
        )
        # Rising tension envelope over the video
        rise = 0.6 + 0.4 * (time / duration_s)
        output += chord * rise

        cls._save_wav(filepath, output)
        return filepath

    @classmethod
    def synthesize_cyber_groove(cls, duration_s: float = 35.0) -> Path:
        """Synthesize an upbeat 128 BPM electronic rhythm bassline."""
        music_dir = cls.get_music_dir()
        filepath = music_dir / "cyber_groove.wav"
        if filepath.exists() and filepath.stat().st_size > 1000:
            return filepath

        total_samples = int(duration_s * SAMPLE_RATE)
        time = np.linspace(0, duration_s, total_samples, endpoint=False)
        output = np.zeros(total_samples, dtype=np.float32)

        bpm = 128.0
        beat_interval = 60.0 / bpm
        beat_samples = int(beat_interval * SAMPLE_RATE)

        # 1. Four-on-the-floor Kick
        kick_samples = int(0.18 * SAMPLE_RATE)
        k_time = np.linspace(0, 0.18, kick_samples, endpoint=False)
        k_phase = np.cumsum((160.0 * np.exp(-k_time * 30.0) + 50.0) / SAMPLE_RATE) * 2.0 * np.pi
        kick = np.sin(k_phase) * np.exp(-k_time * 16.0)

        for b_start in range(0, total_samples, beat_samples):
            b_end = min(total_samples, b_start + kick_samples)
            length = b_end - b_start
            output[b_start:b_end] += kick[:length] * 0.45

        # 2. Rolling Synth Bass (8th-notes alternating F2 and G2)
        step_samples = beat_samples // 2
        notes = [87.31, 87.31, 98.00, 87.31, 103.83, 98.00, 87.31, 77.78]
        note_idx = 0
        for s_start in range(0, total_samples, step_samples):
            s_end = min(total_samples, s_start + step_samples)
            length = s_end - s_start
            n_time = np.linspace(0, length / SAMPLE_RATE, length, endpoint=False)
            freq = notes[note_idx % len(notes)]
            bass = (
                np.sin(2.0 * np.pi * freq * n_time) * 0.22
                + np.sin(2.0 * np.pi * freq * 2.0 * n_time) * 0.08
            ) * np.exp(-n_time * 6.0)
            output[s_start:s_end] += bass
            note_idx += 1

        cls._save_wav(filepath, output)
        return filepath

    @classmethod
    def synthesize_battle_rush(cls, duration_s: float = 115.0, bpm: float = 142.0) -> Path:
        """Synthesize a high-energy 142 BPM driving battle rhythm for duels & long-format races."""
        music_dir = cls.get_music_dir()
        filepath = music_dir / "battle_rush.wav"
        if filepath.exists() and filepath.stat().st_size > 50000:
            return filepath

        total_samples = int(duration_s * SAMPLE_RATE)
        time = np.linspace(0, duration_s, total_samples, endpoint=False)
        output = np.zeros(total_samples, dtype=np.float32)

        beat_interval = 60.0 / bpm
        beat_samples = int(beat_interval * SAMPLE_RATE)

        # 1. Punchy 142 BPM Sub-Kick Drum (every beat)
        kick_samples = int(0.19 * SAMPLE_RATE)
        k_time = np.linspace(0, 0.19, kick_samples, endpoint=False)
        k_phase = np.cumsum((170.0 * np.exp(-k_time * 28.0) + 48.0) / SAMPLE_RATE) * 2.0 * np.pi
        kick = np.sin(k_phase) * np.exp(-k_time * 14.0)

        for b_start in range(0, total_samples, beat_samples):
            b_end = min(total_samples, b_start + kick_samples)
            length = b_end - b_start
            output[b_start:b_end] += kick[:length] * 0.48

        # 2. Snare / Clap Hit on Beats 2 and 4
        snare_samples = int(0.14 * SAMPLE_RATE)
        snare_rng = np.random.RandomState(1337)
        s_noise = snare_rng.normal(0, 0.12, snare_samples).astype(np.float32)
        s_decay = np.exp(-np.linspace(0, 18.0, snare_samples))
        snare = s_noise * s_decay

        step_idx = 0
        for b_start in range(0, total_samples, beat_samples):
            if step_idx % 2 == 1:  # Beats 2 and 4
                b_end = min(total_samples, b_start + snare_samples)
                length = b_end - b_start
                output[b_start:b_end] += snare[:length] * 0.35
            step_idx += 1

        # 3. Driving 16th-Note Shakers / Hi-Hats (creates intense speed sensation)
        step_samples = beat_samples // 4
        h_rng = np.random.RandomState(42)
        h_noise = h_rng.normal(0, 0.08, 300).astype(np.float32)
        h_decay = np.exp(-np.linspace(0, 24.0, 300))
        hihat = h_noise * h_decay

        for s_start in range(0, total_samples, step_samples):
            s_end = min(total_samples, s_start + len(hihat))
            length = s_end - s_start
            output[s_start:s_end] += hihat[:length] * 0.10

        # 4. Rolling Driving Bassline (D-Minor: D2 73.4Hz, F2 87.3Hz, G2 98.0Hz, A2 110Hz)
        bass_step = beat_samples // 2
        bass_notes = [73.42, 73.42, 87.31, 73.42, 97.99, 87.31, 110.00, 97.99]
        b_idx = 0
        for s_start in range(0, total_samples, bass_step):
            s_end = min(total_samples, s_start + bass_step)
            length = s_end - s_start
            n_time = np.linspace(0, length / SAMPLE_RATE, length, endpoint=False)
            freq = bass_notes[b_idx % len(bass_notes)]
            bass = (
                np.sin(2.0 * np.pi * freq * n_time) * 0.24
                + np.sin(2.0 * np.pi * freq * 2.0 * n_time) * 0.08
            ) * np.exp(-n_time * 5.0)
            output[s_start:s_end] += bass
            b_idx += 1

        cls._save_wav(filepath, output)
        return filepath

    @classmethod
    def ensure_default_tracks(cls) -> List[Path]:
        """Ensure all default procedural tracks are synthesized."""
        paths = []
        try:
            paths.append(cls.synthesize_battle_rush())
            paths.append(cls.synthesize_cinematic_pulse())
            paths.append(cls.synthesize_tension_riser())
            paths.append(cls.synthesize_cyber_groove())
        except Exception as err:
            print(f"⚠️ BGM synthesis error: {err}")
        return [p for p in paths if p.exists()]

    @classmethod
    def pick_bgm(cls, topic_key: str = "", category: str = "") -> Optional[Path]:
        """Pick a background music track rotated per topic/category."""
        tracks = cls.list_available_tracks()
        if not tracks:
            tracks = cls.ensure_default_tracks()

        if not tracks:
            return None

        # Prefer high-energy battle rush for landscape / duel / subscriber wars
        is_landscape = getattr(settings, "is_landscape", False)
        topic_lower = str(topic_key or "").strip().lower()
        cat_lower = str(category or "").strip().lower()

        if is_landscape or "race" in topic_lower or "war" in topic_lower or "vs" in topic_lower or "subscribers" in topic_lower:
            matching = [t for t in tracks if "battle_rush" in t.name.lower()]
            if matching:
                return matching[0]

        if "defense" in cat_lower or "military" in cat_lower or "rivalry" in cat_lower:
            matching = [t for t in tracks if "tension" in t.name.lower()]
            if matching:
                return matching[0]
        elif "tech" in cat_lower or "ai" in cat_lower or "gaming" in cat_lower:
            matching = [t for t in tracks if "cyber" in t.name.lower()]
            if matching:
                return matching[0]

        # Stable hash rotation
        key = f"{topic_key}|{category}".strip().lower()
        if key:
            digest = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
            index = digest % len(tracks)
        else:
            index = 0

        return tracks[index]
