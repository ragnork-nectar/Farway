"""
Voice selector for Farway.
Lists Windows SAPI5 voices, lets user pick one, saves to config.
Run this ONCE to set up your preferred voice.
"""

from __future__ import annotations

import pyttsx3

from config import Config


def list_voices() -> list[dict]:
    """Return all SAPI5 voices available on this Windows machine."""
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty("voices") or []
    result = []
    for idx, v in enumerate(voices):
        langs = []
        for lang in (v.languages or []):
            try:
                langs.append(lang.decode("utf-8", errors="ignore"))
            except Exception:
                langs.append(str(lang))
        result.append({
            "index": idx,
            "id": v.id,
            "name": v.name,
            "gender": getattr(v, "gender", "unknown"),
            "languages": langs,
        })
    return result


def preview_voice(voice_id: str, text: str = "Hello, I am Farway. Your offline assistant.") -> None:
    """Speak a short sample with the given voice so the user can hear it."""
    engine = pyttsx3.init("sapi5")
    engine.setProperty("voice", voice_id)
    engine.setProperty("rate", 175)
    engine.say(text)
    engine.runAndWait()


def main() -> None:
    cfg = Config()
    voices = list_voices()

    if not voices:
        print("[Farway] No SAPI5 voices found on this system.")
        return

    print("\n===== Available Voices =====\n")
    for v in voices:
        marker = " *current*" if v["id"] == cfg.get("voice_id") else ""
        print(f"  [{v['index']}] {v['name']}{marker}")
        print(f"       gender: {v['gender']}")
        if v["languages"]:
            print(f"       lang:   {', '.join(v['languages'])}")
        print()

    while True:
        choice = input("Enter the number of the voice you want (or 'q' to quit): ").strip()
        if choice.lower() == "q":
            print("Cancelled. No changes made.")
            return
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue
        idx = int(choice)
        if idx < 0 or idx >= len(voices):
            print(f"Number must be between 0 and {len(voices) - 1}.")
            continue
        break

    selected = voices[idx]
    print(f"\nSelected: {selected['name']}")
    print("Playing sample... (listen)")
    preview_voice(selected["id"])

    confirm = input("\nKeep this voice? (y/n): ").strip().lower()
    if confirm == "y":
        cfg.set("voice_id", selected["id"])
        print(f"[Farway] Voice saved: {selected['name']}")
    else:
        print("Okay, not saved. Run again to try another.")


if __name__ == "__main__":
    main()