"""
Config manager for Farway.
Loads/saves farway_config.json with sensible defaults.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("farway_config.json")

DEFAULTS: dict[str, Any] = {
    "assistant_name": "Farway",
    "ollama_model": "qwen2.5:1.5b",
    "whisper_wake_model": "tiny.en",
    "whisper_command_model": "base.en",
    "tts_rate": 175,
    "voice_id": None,
    "wake_phrases": ["hey farway", "hi farway", "ok farway", "hello farway"],
    "always_on": False,
    "memory_limit": 50,
    "screenshot_dir": "Farway_Screenshots",
    "temp_wav": "farway_input.wav",
}


class Config:
    """Simple JSON-backed config with defaults and safe load/save."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self.data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        """Load config from disk if valid; otherwise keep defaults."""
        if not self.path.exists():
            self.save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[Farway] Config load failed ({exc}); using defaults.")

    def save(self) -> None:
        """Persist config to disk."""
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError as exc:
            print(f"[Farway] Config save failed: {exc}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()