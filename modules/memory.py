"""
Memory manager for Farway.
Persists conversation history to farway_memory.json.
Keeps only the last N messages (N from config).
"""

from __future__ import annotations

import json
from pathlib import Path

from config import Config


MEMORY_PATH = Path("farway_memory.json")


class Memory:
    """Simple JSON-backed conversation history with rolling limit."""

    def __init__(self, path: Path = MEMORY_PATH) -> None:
        self.path = path
        self.cfg = Config()
        self.limit: int = int(self.cfg.get("memory_limit", 50))
        self.history: list[dict] = []
        self._load()

    def _load(self) -> None:
        """Load history from disk if the file exists and is valid."""
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                # Only keep dict entries with 'role' and 'content'
                clean = [
                    m for m in loaded
                    if isinstance(m, dict)
                    and "role" in m
                    and "content" in m
                    and m["role"] != "system"   # system prompt is re-added at runtime
                ]
                self.history = clean[-self.limit:]
                print(f"[Farway] Memory loaded: {len(self.history)} messages from previous session.")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[Farway] Memory load failed ({exc}); starting fresh.")
            self.history = []

    def save(self) -> None:
        """Persist current history to disk (only last `limit` messages)."""
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.history[-self.limit:], f, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[Farway] Memory save failed: {exc}")

    def add(self, role: str, content: str) -> None:
        """Append a message and trim to limit."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.limit:
            self.history = self.history[-self.limit:]

    def get_all(self) -> list[dict]:
        """Return a copy of the current history."""
        return list(self.history)

    def clear(self) -> None:
        """Wipe history from disk and memory."""
        self.history = []
        self.save()
        print("[Farway] Memory cleared.")


if __name__ == "__main__":
    # Quick self-test
    m = Memory()
    m.add("user", "Hello Farway, this is a test.")
    m.add("assistant", "Test received.")
    m.save()

    m2 = Memory()  # reload
    print(f"[Test] History after reload: {m2.get_all()}")