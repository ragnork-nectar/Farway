"""
Farway (Simple Version)
One file. Mic suno, samjho, kaam karo, bolo.
Run: python farway_simple.py
"""

import json
import subprocess
import webbrowser

import ollama
import pyttsx3
import speech_recognition as sr
from faster_whisper import WhisperModel

# ---------- Settings ----------
OLLAMA_MODEL = "qwen2.5:1.5b"
WHISPER_MODEL = "base.en"      # "tiny.en" faster, "base.en" more accurate
VOICE_RATE = 175

# ---------- Voice (Mouth) ----------
engine = pyttsx3.init("sapi5")
engine.setProperty("rate", VOICE_RATE)
voices = engine.getProperty("voices")
if voices:
    engine.setProperty("voice", voices[1].id)  # index 1 = Zira (female)

def speak(text):
    print(f"[Farway] {text}")
    engine.say(text)
    engine.runAndWait()


# ---------- Ear (Mic) ----------
print("[Farway] Loading Whisper...")
whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
recognizer = sr.Recognizer()
mic = sr.Microphone()

with mic as source:
    print("[Farway] Calibrating mic (1s)... stay quiet.")
    recognizer.adjust_for_ambient_noise(source, duration=1)

def listen():
    try:
        with mic as source:
            print("[Farway] Listening...")
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)
        with open("temp.wav", "wb") as f:
            f.write(audio.get_wav_data())
        segments, _ = whisper.transcribe("temp.wav", beam_size=5, language="en")
        text = " ".join(s.text for s in segments).strip()
        return text
    except sr.WaitTimeoutError:
        return ""
    except Exception as e:
        print(f"[Error] {e}")
        return ""


# ---------- Hands (Tools) ----------
def open_application(app_name):
    """Open a desktop app by friendly name."""
    apps = {
        "chrome": "chrome", "google chrome": "chrome",
        "vscode": "code", "vs code": "code",
        "notepad": "notepad", "cmd": "cmd",
        "calculator": "calc", "calc": "calc",
        "spotify": "spotify", "explorer": "explorer",
        "task manager": "taskmgr", "paint": "mspaint",
    }
    exe = apps.get(app_name.lower().strip(), app_name.lower().strip())
    try:
        subprocess.Popen(f'start "" "{exe}"', shell=True)
        return f"Opened {app_name}."
    except Exception as e:
        return f"Could not open {app_name}: {e}"


def open_website(url):
    """Open a website in default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Opened {url}."
    except Exception as e:
        return f"Could not open: {e}"


# ---------- Tool Schemas for Ollama ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Launch a desktop app (chrome, vscode, notepad, cmd, spotify, calculator, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "App name like 'chrome', 'vscode', 'notepad'"}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website (youtube.com, github.com, any URL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL or domain"}
                },
                "required": ["url"],
            },
        },
    },
]

TOOL_FUNCS = {
    "open_application": open_application,
    "open_website": open_website,
}


# ---------- Brain Loop ----------
SYSTEM = (
    "You are Farway, a concise Windows voice assistant. "
    "Use tools to open apps or websites. "
    "Keep replies to ONE short sentence. "
    "Never show reasoning or  thinking tags."
)

def handle(user_text):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text},
    ]

    for _ in range(3):  # max 3 tool-call rounds
        try:
            resp = ollama.chat(model=OLLAMA_MODEL, messages=messages, tools=TOOLS)
        except Exception as e:
            return f"Brain error: {e}"

        msg = resp.get("message", {})
        calls = msg.get("tool_calls") or []

        if not calls:
            return msg.get("content", "") or "Done."

        messages.append(msg)
        for call in calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = TOOL_FUNCS.get(name, lambda **_: "Unknown tool")(**args)
            print(f"[Tool] {name}({args}) -> {result}")
            messages.append({"role": "tool", "content": result})

    return "Done."


# ---------- Main Loop ----------
def main():
    speak("Farway online. How can I help?")

    while True:
        text = listen()
        if not text:
            continue
        print(f"[You] {text}")

        # Exit
        low = text.lower().strip()
        if any(w in low for w in ("goodbye farway", "bye farway", "exit", "quit", "shutdown assistant")):
            speak("Goodbye.")
            break

        # Think + Act
        reply = handle(text)
        # Strip  thinking tags if any
        import re
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL | re.IGNORECASE)
        reply = re.sub(r"</?think>", "", reply, flags=re.IGNORECASE).strip()
        speak(reply or "Done.")


if __name__ == "__main__":
    main()