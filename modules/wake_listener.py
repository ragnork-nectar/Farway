"""
Wake-word listener for Farway.
Runs a background thread that continuously listens for wake phrases.
Uses a small Whisper model (tiny.en) for speed.

Usage in main loop:
    wl = WakeListener()
    wl.start()
    ...
    if wl.wait_for_wake(timeout=1):
        # user said "hey farway" — now listen for command
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import speech_recognition as sr
from faster_whisper import WhisperModel

from config import Config


WAKE_WAV = Path("farway_wake.wav")


class WakeListener:
    """Background thread that listens for wake phrases."""

    def __init__(self) -> None:
        self.cfg = Config()
        self.phrases: list[str] = [
            p.lower().strip() for p in self.cfg.get("wake_phrases", [])
        ]
        model_size = self.cfg.get("whisper_wake_model", "tiny.en")

        print(f"[Farway] Loading wake model '{model_size}' (this takes a few seconds)...")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5
        self.mic = sr.Microphone()

        # Calibrate ambient noise once
        with self.mic as source:
            print("[Farway] Calibrating ambient noise (1s)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

        self._wake_event = threading.Event()
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None

        # Threshold: how much of the transcript must match a wake phrase
        self.match_threshold = 0.6  # 60% of words must match

    # ---- internal: called by speech_recognition in background thread ----
    def _callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Called whenever a chunk of speech is captured."""
        if self._stop_flag.is_set():
            return
        try:
            WAKE_WAV.write_bytes(audio.get_wav_data())
            segments, _ = self.model.transcribe(
                str(WAKE_WAV), beam_size=1, language="en"
            )
            text = " ".join(s.text for s in segments).strip().lower()
        except Exception:
            return

        if not text:
            return

        # Check each wake phrase
        for phrase in self.phrases:
            phrase_words = phrase.split()
            text_words = text.split()
            # Count how many phrase words appear anywhere in the transcript
            hits = sum(1 for w in phrase_words if w in text_words)
            if phrase_words and hits / len(phrase_words) >= self.match_threshold:
                print(f"[Farway] Wake detected: '{text}' (matched '{phrase}')")
                self._wake_event.set()
                return

    # ---- public API ----
    def start(self) -> None:
        """Start the background listener thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self.recognizer.listen_in_background,
            args=(self.mic, self._callback),
            kwargs={"phrase_time_limit": 3},
            daemon=True,
        )
        self._thread.start()
        print("[Farway] Wake listener started. Say 'hey farway' to trigger.")

    def stop(self) -> None:
        """Stop the background listener."""
        self._stop_flag.set()
        self._wake_event.clear()
        # speech_recognition's background listener stops when mic context exits;
        # setting stop flag is enough for our callback to skip work.
        print("[Farway] Wake listener stopped.")

    def wait_for_wake(self, timeout: float | None = None) -> bool:
        """Block until a wake phrase is heard or timeout expires."""
        triggered = self._wake_event.wait(timeout=timeout)
        if triggered:
            self._wake_event.clear()
        return triggered


if __name__ == "__main__":
    # Standalone test — say "hey farway" and watch the terminal
    print("\n===== Wake Word Test =====")
    print("Say 'hey farway' (or 'hi farway') into your mic.")
    print("Press Ctrl+C to quit.\n")

    wl = WakeListener()
    wl.start()

    try:
        while True:
            if wl.wait_for_wake(timeout=1.0):
                print(">>> WAKE TRIGGERED! <<<\n")
                time.sleep(1)  # small cooldown
    except KeyboardInterrupt:
        print("\n[Test] Stopping...")
        wl.stop()