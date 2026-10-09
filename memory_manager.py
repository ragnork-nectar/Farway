"""
Sunday — Memory Manager
Stores user profile, facts, and conversation history persistently.
"""

import json
from pathlib import Path
from datetime import datetime


ROOT_DIR = Path(__file__).parent.resolve()
MEMORY_DIR = ROOT_DIR / "user_files" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_PATH = MEMORY_DIR / "user_profile.json"
FACTS_PATH = MEMORY_DIR / "facts.json"
HISTORY_PATH = MEMORY_DIR / "conversation_history.json"

MAX_HISTORY = 100


class Memory:
    """Persistent memory manager."""

    def __init__(self):
        self.profile = self._load(PROFILE_PATH, {})
        self.facts = self._load(FACTS_PATH, [])
        self.history = self._load(HISTORY_PATH, [])

    def _load(self, path, default):
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default

    def _save(self, path, data):
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[Memory] Save failed: {e}")

    # --- PROFILE ---
    def set_profile(self, key, value):
        self.profile[key] = value
        self._save(PROFILE_PATH, self.profile)
        print(f"[Memory] Profile: {key} = {value}")

    def get_profile(self, key=None):
        if key:
            return self.profile.get(key)
        return self.profile

    def delete_profile(self, key):
        if key in self.profile:
            del self.profile[key]
            self._save(PROFILE_PATH, self.profile)
            return True
        return False

    # --- FACTS ---
    def add_fact(self, fact):
        if fact not in [f["fact"] for f in self.facts]:
            self.facts.append({
                "fact": fact,
                "saved_at": datetime.now().isoformat(),
            })
            self.facts = self.facts[-100:]
            self._save(FACTS_PATH, self.facts)
            print(f"[Memory] Fact: {fact}")

    def get_facts(self, limit=20):
        return [f["fact"] for f in self.facts[-limit:]]

    def clear_facts(self):
        self.facts = []
        self._save(FACTS_PATH, self.facts)

    # --- HISTORY ---
    def add_message(self, role, content):
        self.history.append({
            "role": role,
            "content": content,
            "time": datetime.now().isoformat(),
        })
        self.history = self.history[-MAX_HISTORY:]
        self._save(HISTORY_PATH, self.history)

    def clear_history(self):
        self.history = []
        self._save(HISTORY_PATH, self.history)

    # --- CONTEXT FOR AI ---
    def build_context(self):
        parts = []
        if self.profile:
            profile_str = ", ".join(f"{k}={v}" for k, v in self.profile.items())
            parts.append(f"User profile: {profile_str}")
        recent_facts = self.get_facts(limit=10)
        if recent_facts:
            parts.append("Facts about user: " + "; ".join(recent_facts))
        return "\n".join(parts) if parts else ""

    def clear_all(self):
        self.profile = {}
        self.facts = []
        self.history = []
        self._save(PROFILE_PATH, self.profile)
        self._save(FACTS_PATH, self.facts)
        self._save(HISTORY_PATH, self.history)
        print("[Memory] All cleared")


if __name__ == "__main__":
    m = Memory()
    print("\n=== Memory Test ===\n")
    m.set_profile("name", "Ragnork Nectar")
    m.set_profile("hobby", "writing novels")
    m.add_fact("User is writing The Ring of Cosmos")
    m.add_fact("User lives in India")
    m.add_message("user", "Hello Sunday")
    m.add_message("assistant", "Hello Ragnork!")

    print("\n=== Context for AI ===\n")
    print(m.build_context())
    print("\n=== Profile ===")
    print(m.get_profile())