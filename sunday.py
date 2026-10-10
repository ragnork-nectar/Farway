"""
Sunday v39 — Full Assistant + Dual HUD + Hunter + Offline Personal Replies
========================================
- 🎨 Small + Fullscreen HUD — RED in hunter mode
- 🎯 Hunter Mode — legal-first, no AI fallback, auto-bot
- 💬 Offline personal replies (thanks, name, owner) — no API call
- 🛡️ Anti-echo filter
- 🧠 Memory, code gen, volume, apps, files — all intact
"""

import os
import re
import time
import threading
import subprocess
import webbrowser
import queue
import shlex
import sys
from datetime import datetime
from pathlib import Path

import speech_recognition as sr
import win32com.client
import pyautogui
import psutil
from dotenv import load_dotenv

try:
    from pynput import keyboard as pk_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("[Setup] pynput not installed — Tab key HUD toggle disabled")

from memory_manager import Memory
from hud_controller import init_hud

try:
    import sunday_hunter
    HUNTER_AVAILABLE = True
except ImportError as e:
    HUNTER_AVAILABLE = False
    print(f"[Setup] Hunter module not available: {e}")

try:
    import pywhatkit
    PYWHATKIT_AVAILABLE = True
except ImportError:
    PYWHATKIT_AVAILABLE = False
    print("[Setup] pywhatkit not installed")

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    VOLUME_AVAILABLE = True
except ImportError:
    VOLUME_AVAILABLE = False
    print("[Setup] pycaw not installed")


# ============================================================
# 0) PATHS
# ============================================================
ROOT_DIR = Path(__file__).parent.resolve()
TEMP_DIR = ROOT_DIR / "temp"
USER_FILES_DIR = ROOT_DIR / "user_files"
CODE_DIR = USER_FILES_DIR / "code"
MEMORY_DIR = USER_FILES_DIR / "memory"

TEMP_DIR.mkdir(exist_ok=True)
USER_FILES_DIR.mkdir(exist_ok=True)
CODE_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT_DIR / ".env")
pyautogui.FAILSAFE = True


# ============================================================
# 1) LOAD API KEYS
# ============================================================
def _load_api_keys(environ):
    numbered_api_keys = []
    for name, value in environ.items():
        match = re.fullmatch(r"GEMINI_API_KEY_(\d+)", name)
        if match and value and value.strip():
            numbered_api_keys.append((int(match.group(1)), value.strip()))
    keys = [key for _, key in sorted(numbered_api_keys)]

    single_key = environ.get("GEMINI_API_KEY")
    if single_key and single_key.strip():
        keys.append(single_key.strip())

    return list(dict.fromkeys(keys))


API_KEYS = _load_api_keys(os.environ)

EXHAUSTED_KEYS = set()
API_KEY_CURSOR = 0
API_KEY_LOCK = threading.Lock()


# ============================================================
# 2) GLOBAL SINGLETONS
# ============================================================
memory = None
hud = None
speaker = None
kb_listener = None
hud_hidden = False
HUNTER_MODE = False
TEXT_COMMAND_QUEUE = queue.Queue()
TERMINAL_INPUT_READY = threading.Event()
PENDING_PERMISSION_LOCK = threading.Lock()
PENDING_PERMISSION = None
TERMINAL_CWD = ROOT_DIR


def request_permission(action):
    """Ask for explicit approval in the same terminal used for commands."""
    global PENDING_PERMISSION
    if not TERMINAL_INPUT_READY.is_set():
        print(f"[Permission] Refused because terminal input is unavailable: {action}")
        return False

    response = {"approved": False}
    completed = threading.Event()
    with PENDING_PERMISSION_LOCK:
        if PENDING_PERMISSION is not None:
            print("[Permission] Another confirmation is already pending.")
            return False
        PENDING_PERMISSION = (response, completed)

    print(f"\n[Permission] Sunday wants to: {action}")
    print("Terminal mein yes/no type karke Enter dabayein (default: no).")
    if not completed.wait(timeout=120):
        with PENDING_PERMISSION_LOCK:
            PENDING_PERMISSION = None
        print("[Permission] Timed out; action cancelled.")
    return response["approved"]


def _terminal_input_loop():
    global PENDING_PERMISSION
    TERMINAL_INPUT_READY.set()
    print("[Sunday] Text commands isi terminal mein likhein. Permission ke liye yes/no.")
    print("[Sunday] Terminal command example: run command python --version")

    while True:
        try:
            line = input("Sunday > ").strip()
        except (EOFError, OSError):
            TERMINAL_INPUT_READY.clear()
            with PENDING_PERMISSION_LOCK:
                pending = PENDING_PERMISSION
                if pending is not None:
                    response, completed = pending
                    response["approved"] = False
                    PENDING_PERMISSION = None
                    completed.set()
            print("\n[Sunday] Terminal input unavailable; permission-gated actions will be refused.")
            return

        with PENDING_PERMISSION_LOCK:
            pending = PENDING_PERMISSION
            if pending is not None:
                response, completed = pending
                response["approved"] = line.lower() in ("y", "yes")
                PENDING_PERMISSION = None
                completed.set()
                print("[Permission] Approved." if response["approved"] else "[Permission] Denied.")
                continue

        if line:
            TEXT_COMMAND_QUEUE.put(line)


# ============================================================
# 3) PHRASES
# ============================================================
WAKE_PHRASES = [
    "wake up sunday", "hey sunday", "hi sunday", "hello sunday",
    "ok sunday", "sunday suno", "oye sunday", "sunny suno",
]

HUNTER_ACTIVATE_PHRASES = [
    "sunday hunter", "hunter mode on", "activate hunter",
    "sunday hunter mode", "hunter mode activate",
    "hunter mode", "start hunter", "enter hunter",
]

HUNTER_DEACTIVATE_PHRASES = [
    "hunter exit", "hunter mode off", "sunday normal",
    "back to normal", "hunter band karo", "normal mode",
    "exit hunter", "stop hunter",
]


def is_wake(text):
    t = text.lower().strip()
    return any(p in t for p in WAKE_PHRASES)


def is_hunter_activate(text):
    t = text.lower().strip()
    return any(p in t for p in HUNTER_ACTIVATE_PHRASES)


def is_hunter_deactivate(text):
    t = text.lower().strip()
    return any(p in t for p in HUNTER_DEACTIVATE_PHRASES)


def is_exit(text):
    t = text.lower().strip()
    return any(k in t for k in [
        "goodbye", "good bye", "quit",
        "exit program", "shutdown sunday", "shut down sunday",
        "band karo sunday",
    ])


def is_sleep(text):
    t = text.lower().strip()
    if "goodbye" in t or "good bye" in t:
        return False
    sleep_long = [
        "bye sunday", "bye bye sunday", "bye bye",
        "sleep sunday", "sleep mode", "go to sleep",
        "so jao sunday", "soja sunday",
        "band ho jao", "quiet sunday", "silent sunday",
    ]
    for p in sleep_long:
        if p in t:
            return True
    words = t.split()
    if len(words) <= 2:
        for w in ["bye", "by", "buy", "bhai", "bhaiya", "so", "sona"]:
            if w == t or w in words:
                return True
    return False


def is_stop_command(text):
    t = text.lower().strip()
    return any(p in t for p in [
        "stop sunday", "sunday stop", "sunday chup",
        "chup sunday", "chup ho jao", "stop talking",
        "stop talking sunday", "shut up sunday",
        "bas karo sunday", "ruk sunday", "ruk jao sunday",
        "quiet sunday", "silent sunday", "chup karo",
    ])


# ============================================================
# 4) OFFLINE PERSONALITY RESPONSES
# ============================================================
OWNER_NAME = "Ragnork Nectar"
ASSISTANT_NAME = "Sunday"

PERSONAL_REPLIES = {
    # Thanks
    "thanks":          f"You're welcome, {OWNER_NAME.split()[0]}!",
    "thank you":       f"You're welcome, {OWNER_NAME.split()[0]}!",
    "thank u":         f"Anytime, {OWNER_NAME.split()[0]}!",
    "shukriya":        f"Anytime, {OWNER_NAME.split()[0]}!",
    "dhanyavad":       f"Koi baat nahi, {OWNER_NAME.split()[0]}!",
    "dhanyavaad":      f"Koi baat nahi, {OWNER_NAME.split()[0]}!",

    # Name
    "what is your name":       f"I'm {ASSISTANT_NAME}, your AI assistant.",
    "what's your name":        f"I'm {ASSISTANT_NAME}, your AI assistant.",
    "who are you":             f"I'm {ASSISTANT_NAME}, your offline AI assistant.",
    "tumhara naam kya":        f"Mera naam {ASSISTANT_NAME} hai.",
    "tumhara naam":            f"Mera naam {ASSISTANT_NAME} hai.",
    "aapka naam kya":          f"Mera naam {ASSISTANT_NAME} hai.",

    # Owner
    "who is your owner":       f"I was created by {OWNER_NAME}.",
    "who's your owner":        f"I was created by {OWNER_NAME}.",
    "who made you":            f"I was made by {OWNER_NAME}.",
    "who created you":         f"I was created by {OWNER_NAME}.",
    "tumhe kisne banaya":      f"Mujhe {OWNER_NAME} ne banaya hai.",
    "tumhe kisne bnaya":       f"Mujhe {OWNER_NAME} ne banaya hai.",
    "tera owner kaun":         f"Mera owner {OWNER_NAME} hai.",
    "tumhara owner kaun":      f"Mera owner {OWNER_NAME} hai.",
}


def get_personal_reply(text):
    """Check if text matches a personal phrase. Returns reply or None."""
    t = text.lower().strip().rstrip(".!?, ")

    # Exact match first
    if t in PERSONAL_REPLIES:
        return PERSONAL_REPLIES[t]

    # Substring match for longer phrases
    for phrase, reply in PERSONAL_REPLIES.items():
        if phrase in t:
            return reply

    return None


# ============================================================
# 5) ANTI-ECHO FILTER
# ============================================================
KNOWN_COMMAND_KEYWORDS = [
    # Screen interaction
    "move cursor", "move mouse", "cursor to", "mouse to", "click at",
    "cursor center", "cursor beech mein", "move left", "move right",
    "move up", "move down", "double click at", "right click at",
    "left click", "right click", "double click", "click", "scroll up",
    "scroll down", "type ",
    # System
    "open", "khol", "launch", "start", "chalu", "close", "band",
    "volume", "awaaz", "aawaz", "sound", "mute", "unmute",
    "screenshot", "screen shot", "lock", "shutdown", "restart", "reboot",
    "sleep pc", "cancel",
    # Media
    "play", "baja", "sunao", "gaana", "song", "pause", "resume",
    "next", "previous", "prev", "pichla", "stop music",
    # Files / Code
    "file", "folder", "code", "make", "create", "write", "likh",
    "read", "delete", "run", "fix", "debug", "improve",
    "calculator", "website", "program", "script",
    # Memory
    "name", "mera naam", "remember", "yaad", "forget", "bhool",
    "know about me",
    # Info
    "time", "date", "samay", "tareekh",
    # Sleep / Exit
    "bye", "goodbye", "good bye", "sleep",
    # Stop
    "stop", "chup", "ruk",
    # Hunter + scope (STT variants)
    "add to", "add the", "add scope", "add to scope", "add to score",
    "hunter", "scope", "remove from scope", "show scope",
    "dns", "port scan", "subdomain", "http header", "http method",
    "robots", "ssl", "whois", "who is", "tech detect", "wayback", "way back",
    "save finding", "show findings", "clear findings",
    "accept terms", "legal terms", "audit log",
    "payload", "report",
    # Auto-bot
    "bot ", "bot status", "stop bot", "auto bot", "autobot",
    # Personal (offline replies)
    "thanks", "thank you", "thank u", "shukriya", "dhanyavad", "dhanyavaad",
    "your name", "who are you", "your owner", "made you", "created you",
    "tumhara naam", "tumhe kisne", "tera owner", "tumhara owner",
]

SYSTEM_AUDIO_NOISE = [
    "subscribe", "like and", "share", "comment", "click",
    "video", "channel", "notification", "bell", "button",
    "thanks for watching", "watch", "playlist", "next video",
    "intro", "outro", "sponsor", "like this video",
    "welcome back", "guys", "hello everyone",
]


def is_command_like(text):
    t = text.lower().strip()
    return any(kw in t for kw in KNOWN_COMMAND_KEYWORDS)


def is_system_noise(text):
    if not text:
        return True
    t = text.lower().strip()
    if len(t) < 3:
        return True
    if len(t.split()) > 15:
        return True
    for noise in SYSTEM_AUDIO_NOISE:
        if noise in t:
            return True
    return False


# ============================================================
# 6) APP LIBRARY
# ============================================================
APPS = {
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "firefox": "firefox", "brave": "brave",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "pycharm": "pycharm", "notepad++": "notepad++",
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "cmd": "cmd", "command prompt": "cmd",
    "powershell": "powershell", "terminal": "wt",
    "task manager": "taskmgr", "explorer": "explorer",
    "file explorer": "explorer", "settings": "ms-settings:",
    "control panel": "control", "spotify": "spotify", "vlc": "vlc",
    "discord": "discord", "telegram": "telegram",
    "whatsapp": "whatsapp", "zoom": "zoom", "teams": "teams",
    "steam": "steam", "minecraft": "minecraft",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:", "clock": "ms-clock:",
    "store": "ms-windows-store:", "photoshop": "photoshop",
    "notion": "notion", "obsidian": "obsidian",
    "docker": "docker", "postman": "postman",
    "burp": "burp", "burpsuite": "burp",
}


# ============================================================
# 7) VOICE
# ============================================================
def init_speaker():
    global speaker
    print("[Setup] Initializing voice...")
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    speaker.Rate = 0

    FEMALE_VOICE_KEYWORDS = ["zira", "heera", "hazel", "susan", "samantha", "female"]
    sapi_voices = speaker.GetVoices()
    for keyword in FEMALE_VOICE_KEYWORDS:
        for i in range(sapi_voices.Count):
            v = sapi_voices.Item(i)
            desc = v.GetDescription()
            if keyword in desc.lower():
                speaker.Voice = v
                print(f"[Setup] Female voice: {desc}")
                return


STOP_FLAG = threading.Event()


def kill_speech():
    try:
        speaker.Speak("", 3)
    except Exception:
        pass


def speak(text, allow_stop=False):
    if not text:
        return
    print(f"[Sunday] {text}")

    if hud:
        try:
            hud.set_state("speaking")
            hud.set_text(text)
        except Exception:
            pass

    if not allow_stop:
        try:
            speaker.Speak(text)
        except Exception as ex:
            print(f"[TTS Error] {ex}")
        if hud:
            try:
                if HUNTER_MODE:
                    hud.set_state("hunter")
                else:
                    hud.set_state("idle")
                hud.set_text("")
            except Exception:
                pass
        return

    STOP_FLAG.clear()
    speech_done = threading.Event()

    def _speak_thread():
        try:
            speaker.Speak(text)
        except Exception as ex:
            print(f"[TTS Error] {ex}")
        finally:
            speech_done.set()

    def _listener_thread():
        try:
            stop_recognizer = sr.Recognizer()
            stop_mic = sr.Microphone()
            with stop_mic as source:
                stop_recognizer.adjust_for_ambient_noise(source, duration=0.2)
                while not speech_done.is_set():
                    try:
                        audio = stop_recognizer.listen(source, timeout=2, phrase_time_limit=3)
                        try:
                            text_heard = stop_recognizer.recognize_google(
                                audio, language="en-IN"
                            ).lower()
                            if is_stop_command(text_heard):
                                STOP_FLAG.set()
                                kill_speech()
                                break
                        except (sr.UnknownValueError, sr.RequestError):
                            continue
                    except sr.WaitTimeoutError:
                        continue
        except Exception:
            pass

    t_speak = threading.Thread(target=_speak_thread, daemon=True)
    t_listener = threading.Thread(target=_listener_thread, daemon=True)
    t_speak.start()
    t_listener.start()
    t_speak.join(timeout=60)
    speech_done.set()
    if hud:
        try:
            if HUNTER_MODE:
                hud.set_state("hunter")
            else:
                hud.set_state("idle")
            hud.set_text("")
        except Exception:
            pass


# ============================================================
# 8) KEYBOARD LISTENER
# ============================================================
def start_keyboard_listener():
    global hud_hidden
    if not PYNPUT_AVAILABLE:
        return None

    def on_press(key):
        global hud_hidden
        try:
            if key == pk_keyboard.Key.tab:
                if hud:
                    if not hud_hidden:
                        try:
                            hud.hide_fullscreen()
                        except Exception:
                            pass
                        hud_hidden = True
                        print("\n[Keyboard] Tab — HUD hidden\n")
                    else:
                        try:
                            hud.show_fullscreen()
                        except Exception:
                            pass
                        hud_hidden = False
                        print("\n[Keyboard] Tab — HUD shown\n")
            elif key == pk_keyboard.Key.esc:
                if hud:
                    try:
                        hud.hide_fullscreen()
                    except Exception:
                        pass
                hud_hidden = True
                print("\n[Keyboard] Esc — HUD hidden\n")
        except Exception:
            pass

    listener = pk_keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    print("[Keyboard] Tab key listener active")
    return listener


# ============================================================
# 9) VOLUME
# ============================================================
def get_volume_interface():
    if not VOLUME_AVAILABLE:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, "EndpointVolume"):
            return devices.EndpointVolume
        if hasattr(devices, "Activate"):
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        return None
    except Exception as e:
        print(f"[Volume] Error: {e}")
        return None


def volume_up(step=10):
    vol = get_volume_interface()
    if not vol: return "Volume not available"
    try:
        cur = vol.GetMasterVolumeLevelScalar()
        new = min(1.0, cur + step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume up to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_down(step=10):
    vol = get_volume_interface()
    if not vol: return "Volume not available"
    try:
        cur = vol.GetMasterVolumeLevelScalar()
        new = max(0.0, cur - step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume down to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_set(percent):
    vol = get_volume_interface()
    if not vol: return "Volume not available"
    try:
        new = max(0.0, min(1.0, percent / 100))
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume set to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_mute():
    vol = get_volume_interface()
    if not vol: return "Volume not available"
    try:
        is_muted = vol.GetMute()
        vol.SetMute(not is_muted, None)
        return "Muted" if not is_muted else "Unmuted"
    except Exception as e:
        return f"Volume error: {e}"


# ============================================================
# 10) APP CONTROL
# ============================================================
def open_app_smart(app_name):
    key = app_name.lower().strip()
    if key in APPS:
        try:
            subprocess.Popen(f'start "" "{APPS[key]}"', shell=True)
            return f"Opening {app_name}"
        except Exception:
            pass
    try:
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.typewrite(app_name, interval=0.03)
        time.sleep(0.6)
        pyautogui.press("enter")
        return f"Searching {app_name}"
    except Exception as e:
        return f"Could not open {app_name}: {e}"


def close_app(app_name):
    key = app_name.lower().strip()
    target = APPS.get(key, key).replace(":", "")
    proc_map = {
        "chrome": "chrome.exe", "msedge": "msedge.exe", "firefox": "firefox.exe",
        "code": "Code.exe", "notepad": "notepad.exe", "calc": "CalculatorApp.exe",
        "mspaint": "mspaint.exe", "cmd": "cmd.exe", "powershell": "powershell.exe",
        "taskmgr": "Taskmgr.exe", "explorer": "explorer.exe", "spotify": "Spotify.exe",
        "vlc": "vlc.exe", "discord": "Discord.exe", "telegram": "Telegram.exe",
        "whatsapp": "WhatsApp.exe", "zoom": "Zoom.exe", "teams": "Teams.exe",
        "steam": "steam.exe", "winword": "WINWORD.EXE", "excel": "EXCEL.EXE",
        "powerpnt": "POWERPNT.EXE", "outlook": "OUTLOOK.EXE",
    }
    proc_name = proc_map.get(target, target + ".exe" if not target.endswith(".exe") else target)
    try:
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == proc_name.lower():
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return f"Closed {app_name}" if killed > 0 else f"{app_name} not running"
    except Exception as e:
        return f"Could not close: {e}"


# ============================================================
# 11) MEDIA
# ============================================================
def media_play_pause():
    pyautogui.press("playpause")
    return "Toggled play pause"


def media_next():
    pyautogui.press("nexttrack")
    return "Next track"


def media_prev():
    pyautogui.press("prevtrack")
    return "Previous track"


def media_stop():
    pyautogui.press("stop")
    return "Media stopped"


# ============================================================
# 12) SYSTEM
# ============================================================
def system_lock():
    if not request_permission("PC ko lock karna"):
        return "PC lock nahi kiya; permission nahi mili."
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return "Locking screen"


def system_shutdown(delay=30):
    if not request_permission(f"PC ko {delay} seconds mein shutdown karna"):
        return "Shutdown cancel kiya; permission nahi mili."
    subprocess.run(["shutdown", "/s", "/t", str(delay)], check=False)
    return f"Shutting down in {delay} seconds"


def system_restart(delay=30):
    if not request_permission(f"PC ko {delay} seconds mein restart karna"):
        return "Restart cancel kiya; permission nahi mili."
    subprocess.run(["shutdown", "/r", "/t", str(delay)], check=False)
    return f"Restarting in {delay} seconds"


def system_cancel_shutdown():
    subprocess.run(["shutdown", "/a"], check=False)
    return "Shutdown cancelled"


def system_sleep_pc():
    if not request_permission("PC ko sleep mode mein bhejna"):
        return "Sleep nahi kiya; permission nahi mili."
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        check=False,
    )
    return "Going to sleep"


def system_screenshot():
    if not request_permission("Screen ka screenshot lena aur Pictures folder mein save karna"):
        return "Screenshot nahi liya; permission nahi mili."
    SCREENSHOT_DIR = Path.home() / "Pictures" / "Sunday_Screenshots"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        pyautogui.screenshot(str(path))
        return "Screenshot saved"
    except Exception:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(str(path))
            return "Screenshot saved"
        except Exception as e2:
            return f"Screenshot failed: {e2}"


# ============================================================
# 13) MUSIC
# ============================================================
def play_song(song_name):
    if hud:
        try:
            hud.set_now_playing(f"Playing: {song_name}")
        except Exception:
            pass
    if PYWHATKIT_AVAILABLE:
        try:
            pywhatkit.playonyt(song_name)
            return f"Playing {song_name}"
        except Exception:
            pass
    query = song_name.replace(" ", "+")
    webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
    return f"Searching {song_name}"


# ============================================================
# 14) FILE MANAGER
# ============================================================
def _resolve_user_path(filename, code=False):
    filename = filename.strip().strip('"').strip("'")
    for filler in ("file ", "the ", "called ", "named "):
        if filename.lower().startswith(filler):
            filename = filename[len(filler):].strip()
    if filename.lower().endswith(" file"):
        filename = filename[:-5].strip()
    if filename.lower() == "file":
        filename = ""
    filename = filename.replace("..", "").replace("/", "_").replace("\\", "_")
    base = CODE_DIR if code else USER_FILES_DIR
    return base / filename


def file_create(filename):
    path = _resolve_user_path(filename)
    if path.exists():
        return f"File {path.name} already exists"
    try:
        path.touch()
        return f"Created {path.name}"
    except Exception as e:
        return f"Error: {e}"


def file_read(filename):
    path = _resolve_user_path(filename)
    if not path.exists():
        return f"{path.name} not found"
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if not content:
            return f"{path.name} is empty"
        preview = content[:600]
        if len(content) > 600:
            preview += "... and more"
        return f"File {path.name} says: {preview}"
    except Exception as e:
        return f"Error reading: {e}"


def file_write(filename, content, code=False):
    path = _resolve_user_path(filename, code=code)
    action = f"'{path.name}' file mein likhna"
    if path.exists():
        action = f"'{path.name}' file ko overwrite karna"
    if not request_permission(action):
        return "File update nahi ki; permission nahi mili."
    try:
        path.write_text(content, encoding="utf-8")
        return f"Written to {path.name}"
    except Exception as e:
        return f"Error writing: {e}"


def file_append(filename, content):
    path = _resolve_user_path(filename)
    if not request_permission(f"'{path.name}' file ke end mein text jodna"):
        return "File update nahi ki; permission nahi mili."
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(content + "\n")
        return f"Appended to {path.name}"
    except Exception as e:
        return f"Error appending: {e}"


def file_delete(filename):
    path = _resolve_user_path(filename)
    if not path.exists():
        return f"{path.name} not found"
    if not request_permission(f"'{path.name}' file permanently delete karna"):
        return "File delete nahi ki; permission nahi mili."
    try:
        path.unlink()
        return f"Deleted {path.name}"
    except Exception as e:
        return f"Error deleting: {e}"


def folder_create(folder_name):
    path = _resolve_user_path(folder_name)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return f"Created folder {path.name}"
    except Exception as e:
        return f"Error: {e}"


def list_files():
    try:
        items = list(USER_FILES_DIR.iterdir())
        if not items:
            return "No files yet"
        files = [i.name for i in items if i.is_file()]
        folders = [i.name for i in items if i.is_dir()]
        parts = []
        if files:
            parts.append(f"{len(files)} files: {', '.join(files[:10])}")
        if folders:
            parts.append(f"{len(folders)} folders: {', '.join(folders[:10])}")
        return ". ".join(parts)
    except Exception as e:
        return f"Error: {e}"


def open_file(filename):
    path = _resolve_user_path(filename)
    if not path.exists():
        return f"{path.name} not found"
    try:
        os.startfile(str(path))
        return f"Opening {path.name}"
    except Exception as e:
        return f"Error: {e}"


def open_user_files_folder():
    try:
        os.startfile(str(USER_FILES_DIR))
        return "Opening user files"
    except Exception as e:
        return f"Error: {e}"


def open_code_folder():
    try:
        os.startfile(str(CODE_DIR))
        return "Opening code folder"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# 15) MEMORY AUTO-DETECTION
# ============================================================
def detect_and_save_memory(text):
    if memory is None:
        return False
    t = text.lower().strip()
    saved = False

    for pattern in [
        r"my name is ([a-z ]+)",
        r"mera naam ([a-z ]+) hai",
        r"mera naam ([a-z ]+) h",
        r"mera name ([a-z ]+) hai",
    ]:
        m = re.search(pattern, t)
        if m:
            name = m.group(1).strip().title()
            for stop in (" Hai", " H", " Hun", " Hoon"):
                if name.endswith(stop):
                    name = name[:-len(stop)].strip()
            if 2 <= len(name) <= 30:
                memory.set_profile("name", name)
                saved = True
                break

    for pattern in [
        r"i like ([a-z ]+)",
        r"mujhe ([a-z ]+) pasand",
        r"my favourite ([a-z]+) is ([a-z ]+)",
    ]:
        m = re.search(pattern, t)
        if m:
            if "favourite" in pattern:
                key = f"favourite_{m.group(1).strip()}"
                value = m.group(2).strip()
            else:
                key = "likes"
                value = m.group(1).strip()
            memory.set_profile(key, value)
            saved = True
            break

    for pattern in [
        r"i am writing ([a-z ]+)",
        r"my project is ([a-z ]+)",
        r"i am working on ([a-z ]+)",
    ]:
        m = re.search(pattern, t)
        if m:
            fact = f"User is working on: {m.group(1).strip()}"
            memory.add_fact(fact)
            saved = True
            break

    return saved


# ============================================================
# 16) MULTI-KEY GEMINI
# ============================================================
CODE_GEN_SYSTEM = (
    "You are an expert programmer. The user wants you to write code. "
    "Output ONLY the code, no explanations, no markdown, no ``` fences. "
    "Start code with a comment describing what it does. "
    "Make code clean, working, and well-commented. "
    "Code only — no prose, no greetings."
)

CODE_FIX_SYSTEM = (
    "You are an expert debugger. Fix the bugs in the code. "
    "Output ONLY the fixed code, no explanations, no markdown fences. "
    "Keep original intent. Code only."
)

CODE_IMPROVE_SYSTEM = (
    "You are a senior developer. Improve the code. "
    "Output ONLY the improved code, no explanations, no markdown fences. "
    "Keep functionality same. Code only."
)


def _extract_code(raw):
    if not raw:
        return ""
    text = raw.strip()
    text = re.sub(r"^```[a-zA-Z0-9+\-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip("`").strip()
    return text


def _get_available_keys():
    global API_KEY_CURSOR
    if not API_KEYS:
        return []

    with API_KEY_LOCK:
        if len(EXHAUSTED_KEYS) >= len(API_KEYS):
            print("[AI] All keys reached their limit; starting a new key cycle")
            EXHAUSTED_KEYS.clear()

        start = API_KEY_CURSOR % len(API_KEYS)
        ordered_keys = API_KEYS[start:] + API_KEYS[:start]
        return [key for key in ordered_keys if key not in EXHAUSTED_KEYS]


def _is_quota_error(err_lower):
    return any(k in err_lower for k in (
        "429", "quota", "exceeded", "resource_exhausted",
        "rate limit", "rate-limit", "too many requests",
    ))


def _is_server_busy(err_lower):
    return any(k in err_lower for k in (
        "503", "unavailable", "overloaded", "internal",
    ))


def _create_gemini_client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def _call_gemini(prompt, max_attempts_per_key=2):
    global API_KEY_CURSOR
    if not API_KEYS:
        return None

    if hud:
        try:
            hud.set_state("thinking")
            hud.set_text("Let me think...")
        except Exception:
            pass

    models_to_try = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-2.5-flash"]

    for api_key in _get_available_keys():
        key_index = API_KEYS.index(api_key)
        print(f"\n[AI] Trying key #{key_index + 1}")

        try:
            client = _create_gemini_client(api_key)
        except ImportError:
            return None
        except Exception:
            with API_KEY_LOCK:
                EXHAUSTED_KEYS.add(api_key)
                API_KEY_CURSOR = (key_index + 1) % len(API_KEYS)
            continue

        key_exhausted = False

        for model_name in models_to_try:
            for attempt in range(max_attempts_per_key):
                try:
                    print(f"[AI]   Trying {model_name} (attempt {attempt + 1})")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    text = (response.text or "").strip()
                    if text:
                        print(f"[AI] Success with key #{key_index + 1}, {len(text)} chars")
                        with API_KEY_LOCK:
                            API_KEY_CURSOR = (key_index + 1) % len(API_KEYS)
                        if hud:
                            try:
                                if HUNTER_MODE:
                                    hud.set_state("hunter")
                                else:
                                    hud.set_state("idle")
                                hud.set_text("")
                            except Exception:
                                pass
                        return text
                    else:
                        time.sleep(1)
                        continue
                except Exception as e:
                    err_lower = str(e).lower()
                    if _is_quota_error(err_lower):
                        print("[AI]   Quota exhausted")
                        with API_KEY_LOCK:
                            EXHAUSTED_KEYS.add(api_key)
                            API_KEY_CURSOR = (key_index + 1) % len(API_KEYS)
                        key_exhausted = True
                        break
                    if _is_server_busy(err_lower):
                        print("[AI]   Server busy, retrying...")
                        time.sleep(2)
                        continue
                    print(f"[AI] Request failed ({type(e).__name__}); trying next option.")
                    break

            if key_exhausted:
                break

        with API_KEY_LOCK:
            API_KEY_CURSOR = (key_index + 1) % len(API_KEYS)

    print("[AI] All API keys exhausted")
    if hud:
        try:
            if HUNTER_MODE:
                hud.set_state("hunter")
            else:
                hud.set_state("idle")
            hud.set_text("")
        except Exception:
            pass
    return None


# ============================================================
# 17) CODE GENERATION
# ============================================================
def ai_generate_code(description):
    print(f"\n[CodeGen] Generating code for: {description}")
    prompt = f"{CODE_GEN_SYSTEM}\n\nTask: {description}"
    raw = _call_gemini(prompt)
    if not raw:
        print("[CodeGen] Primary failed, trying fallback...")
        simple = f"Write complete working code for: {description}. Output only code."
        raw = _call_gemini(simple)
    if not raw:
        return None
    code = _extract_code(raw)
    print(f"[CodeGen] Extracted {len(code)} chars")
    return code if code else None


def ai_fix_code(code):
    prompt = f"{CODE_FIX_SYSTEM}\n\nBuggy code:\n\n{code}"
    raw = _call_gemini(prompt)
    return _extract_code(raw) if raw else None


def ai_improve_code(code):
    prompt = f"{CODE_IMPROVE_SYSTEM}\n\nCode:\n\n{code}"
    raw = _call_gemini(prompt)
    return _extract_code(raw) if raw else None


def detect_language(description):
    d = description.lower()
    if "python" in d or ".py" in d:
        return "py"
    if "html" in d or ".html" in d:
        return "html"
    if "css" in d or ".css" in d:
        return "css"
    if "javascript" in d or "js" in d or ".js" in d:
        return "js"
    if "java " in d:
        return "java"
    if "c++" in d or "cpp" in d:
        return "cpp"
    if "c#" in d:
        return "cs"
    return "py"


def detect_filename(description):
    for pattern in [
        r"in\s+([\w\-\.]+\.\w+)",
        r"called\s+([\w\-\.]+\.\w+)",
        r"named\s+([\w\-\.]+\.\w+)",
        r"file\s+([\w\-\.]+\.\w+)",
    ]:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1)

    ext = detect_language(description)
    slug = re.sub(r"[^\w\s]", "", description.lower())
    words = [w for w in slug.split() if w not in (
        "make", "create", "write", "build", "a", "an", "the", "me",
        "please", "code", "program", "script", "file", "in", "called",
        "named", "for", "python", "html", "css", "javascript", "js",
        "using", "with",
    )]
    name = "_".join(words[:3]) or "generated"
    return f"{name}.{ext}"


# ============================================================
# 18) INTENT DETECTION
# ============================================================
CODE_CREATE_TRIGGERS = [
    "make a", "make me", "create a", "create me", "write a", "write me",
    "build a", "build me", "generate a", "generate me",
    "banao", "bana do", "likho", "likh do", "code likho",
    "program banao", "script banao", "program likho", "script likho",
]

CODE_FIX_TRIGGERS = [
    "fix the bug", "fix bug", "fix code", "fix error", "debug",
    "theek karo", "thik karo", "sahi karo", "fix karo", "bug fix",
]

CODE_IMPROVE_TRIGGERS = [
    "improve the code", "improve code", "refactor",
    "behtar karo", "improve karo", "clean the code",
    "clean code", "optimize",
]

CODE_RUN_TRIGGERS = [
    "run the code", "run code", "execute", "chalao", "run karo",
    "run the file", "run file", "chala do",
]


def is_code_create_request(text):
    t = text.lower()
    has_trigger = any(trig in t for trig in CODE_CREATE_TRIGGERS)
    if not has_trigger:
        return False
    code_words = [
        "python", "html", "css", "javascript", "js", "java", "c++",
        "code", "program", "script",
        "calculator", "website", "game", "app", "tool",
        "todo", "timer", "clock", "guess", "snake", "form",
        "login", "portfolio", "blog", "counter", "converter",
        "function", "class", "bot", "scraper", "downloader",
    ]
    return any(w in t for w in code_words)


def is_code_fix_request(text):
    return any(t in text.lower() for t in CODE_FIX_TRIGGERS)


def is_code_improve_request(text):
    return any(t in text.lower() for t in CODE_IMPROVE_TRIGGERS)


def is_code_run_request(text):
    return any(t in text.lower() for t in CODE_RUN_TRIGGERS)


# ============================================================
# 19) CODE WORKFLOWS
# ============================================================
def workflow_generate_code(description):
    filename = detect_filename(description)
    path = _resolve_user_path(filename, code=True)
    action = f"AI se code banwana aur '{path.name}' mein save karna"
    if path.exists():
        action = f"AI se code banwana aur '{path.name}' overwrite karna"
    if not request_permission(action):
        speak("Code generate nahi kiya; permission nahi mili.")
        return
    speak("Let me write that code for you")
    code = ai_generate_code(description)
    if not code:
        speak("Cloud AI abhi available nahi hai; code generate nahi ho saka.")
        return

    try:
        path.write_text(code, encoding="utf-8")
        lines = len(code.splitlines())
        speak(f"Done. I wrote {lines} lines of code in {filename}")
        try:
            subprocess.Popen(f'code "{path}"', shell=True)
        except Exception:
            pass
    except Exception as e:
        speak(f"Could not save file: {e}")


def workflow_fix_code(filename):
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    if not request_permission(
        f"'{path.name}' ka content Google AI ko bhejna aur file update karna"
    ):
        speak("File change nahi ki; permission nahi mili.")
        return

    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        speak(f"Could not read file: {e}")
        return

    speak("Fixing the bugs")
    fixed = ai_fix_code(original)
    if not fixed:
        speak("Sorry, could not fix right now.")
        return

    try:
        path.write_text(fixed, encoding="utf-8")
        speak(f"Fixed. I updated {path.name}")
    except Exception as e:
        speak(f"Could not save: {e}")


def workflow_improve_code(filename):
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    if not request_permission(
        f"'{path.name}' ka content Google AI ko bhejna aur file update karna"
    ):
        speak("File change nahi ki; permission nahi mili.")
        return

    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        speak(f"Could not read: {e}")
        return

    speak("Improving the code")
    improved = ai_improve_code(original)
    if not improved:
        speak("Sorry, could not improve right now.")
        return

    try:
        path.write_text(improved, encoding="utf-8")
        speak(f"Improved {path.name}")
    except Exception as e:
        speak(f"Could not save: {e}")


def workflow_run_code(filename):
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    if path.suffix.lower() == ".py":
        if not request_permission(f"'{path.name}' Python code execute karna"):
            speak("Code run nahi kiya; permission nahi mili.")
            return
        speak("Running the code")
        try:
            subprocess.Popen(
                f'start cmd /k "cd /d {path.parent} && python {path.name}"',
                shell=True
            )
        except Exception as e:
            speak(f"Could not run: {e}")
    elif path.suffix.lower() in (".html", ".htm"):
        webbrowser.open(str(path))
        speak("Opening in browser")
    else:
        os.startfile(str(path))
        speak("Opening file")


# ============================================================
# 20) HUNTER MODE HELPERS
# ============================================================
def enter_hunter_mode():
    global HUNTER_MODE
    if not HUNTER_AVAILABLE:
        return "Hunter module not available. Check sunday_hunter.py"

    HUNTER_MODE = True

    if hud:
        try:
            hud.enter_hunter()
        except Exception:
            try:
                hud.set_palette("red")
                hud.set_state("hunter")
            except Exception:
                pass

    try:
        if not sunday_hunter.terms_accepted():
            return (
                "Hunter mode active — HUD red. LEGAL TERMS not accepted. "
                "Say 'accept terms' to acknowledge."
            )
    except Exception:
        pass

    return "Hunter mode active. HUD is red. Stay legal — only test in-scope targets."


def exit_hunter_mode():
    global HUNTER_MODE

    try:
        if HUNTER_AVAILABLE:
            sunday_hunter.stop_autobot()
    except Exception:
        pass

    HUNTER_MODE = False

    if hud:
        try:
            hud.exit_hunter()
        except Exception:
            try:
                hud.set_palette("cyan")
                hud.set_state("idle")
            except Exception:
                pass

    return "Normal mode active. HUD back to cyan."


def handle_hunter_command(text):
    if not HUNTER_AVAILABLE:
        return "Hunter module not available", True
    try:
        reply, handled = sunday_hunter.handle_hunter_command(text)
        return reply, handled
    except Exception as e:
        return f"Hunter error: {e}", True


def handle_screen_command(raw_text, normalized_text):
    if normalized_text in (
        "move cursor to center",
        "move mouse to center",
        "cursor center",
        "cursor beech mein",
    ):
        width, height = pyautogui.size()
        x, y = width // 2, height // 2
        try:
            pyautogui.moveTo(x, y, duration=0.25)
            return f"Cursor center x={x}, y={y} par move kar diya."
        except Exception as e:
            return f"Cursor move nahi ho saka: {e}"

    relative_move = re.fullmatch(
        r"move (?:cursor|mouse) (left|right|up|down)(?:\s+(\d+))?",
        normalized_text,
    )
    if relative_move:
        direction, amount_text = relative_move.groups()
        amount = min(500, max(1, int(amount_text or "100")))
        x, y = pyautogui.position()
        width, height = pyautogui.size()
        offsets = {
            "left": (-amount, 0),
            "right": (amount, 0),
            "up": (0, -amount),
            "down": (0, amount),
        }
        dx, dy = offsets[direction]
        x = min(width - 1, max(0, x + dx))
        y = min(height - 1, max(0, y + dy))
        try:
            pyautogui.moveTo(x, y, duration=0.2)
            return f"Cursor {direction} move kar diya."
        except Exception as e:
            return f"Cursor move nahi ho saka: {e}"

    coordinate_text = normalized_text
    hinglish_move = re.fullmatch(
        r"cursor ko\s+(\d+)[,\s]+(\d+)\s+(?:par\s+)?(?:le jao|move karo)",
        coordinate_text,
    )
    if hinglish_move:
        x_text, y_text = hinglish_move.groups()
        coordinate_text = f"cursor to {x_text} {y_text}"

    coordinate_command = re.fullmatch(
        r"(?:move cursor to|move mouse to|cursor to|mouse to)\s+(\d+)[,\s]+(\d+)",
        coordinate_text,
    )
    if coordinate_command:
        x, y = map(int, coordinate_command.groups())
        width, height = pyautogui.size()
        if x >= width or y >= height:
            return f"Coordinates screen ke bahar hain. Screen: {width}x{height}."
        try:
            pyautogui.moveTo(x, y, duration=0.25)
            return f"Cursor x={x}, y={y} par move kar diya."
        except Exception as e:
            return f"Cursor move nahi ho saka: {e}"

    hinglish_click = re.fullmatch(
        r"(click karo|right click karo|double click karo)\s+(\d+)[,\s]+(\d+)(?:\s+par)?",
        normalized_text,
    )
    click_text = normalized_text
    if hinglish_click:
        kind, x_text, y_text = hinglish_click.groups()
        kind = {
            "click karo": "click at",
            "right click karo": "right click at",
            "double click karo": "double click at",
        }[kind]
        click_text = f"{kind} {x_text} {y_text}"

    click_command = re.fullmatch(
        r"(left click at|click at|right click at|double click at)\s+(\d+)[,\s]+(\d+)",
        click_text,
    )
    if click_command:
        kind, x_text, y_text = click_command.groups()
        x, y = int(x_text), int(y_text)
        width, height = pyautogui.size()
        if x >= width or y >= height:
            return f"Coordinates screen ke bahar hain. Screen: {width}x{height}."
        button = "right" if kind == "right click at" else "left"
        clicks = 2 if kind == "double click at" else 1
        try:
            pyautogui.click(x=x, y=y, clicks=clicks, interval=0.1, button=button)
            return f"{kind.title()} x={x}, y={y} par kar diya."
        except Exception as e:
            return f"Click nahi ho saka: {e}"

    current_clicks = {
        "click": ("left", 1),
        "left click": ("left", 1),
        "right click": ("right", 1),
        "double click": ("left", 2),
    }
    if normalized_text in current_clicks:
        button, clicks = current_clicks[normalized_text]
        try:
            pyautogui.click(button=button, clicks=clicks, interval=0.1)
            return f"{normalized_text.title()} kar diya."
        except Exception as e:
            return f"Click nahi ho saka: {e}"

    scroll_text = normalized_text.replace("scroll upar", "scroll up").replace(
        "scroll neeche", "scroll down"
    )
    scroll_command = re.fullmatch(r"scroll (up|down)(?:\s+(\d+))?", scroll_text)
    if scroll_command:
        direction, amount_text = scroll_command.groups()
        amount = min(10, max(1, int(amount_text or "3")))
        signed_amount = amount if direction == "up" else -amount
        try:
            pyautogui.scroll(signed_amount)
            return f"Screen {direction} scroll kar di."
        except Exception as e:
            return f"Scroll nahi ho saka: {e}"

    text_prefixes = ("screen par type karo ", "type karo ", "type:", "type ")
    prefix = next(
        (item for item in text_prefixes if normalized_text.startswith(item)),
        None,
    )
    if prefix:
        separator_length = len(prefix)
        text_to_type = raw_text[separator_length:].strip()
        if not text_to_type:
            return "Type karne ke liye text bhi dein. Example: type Hello world"
        if len(text_to_type) > 1000:
            return "Ek command mein maximum 1000 characters type kar sakta hoon."
        if not text_to_type.isascii():
            return "Abhi screen typing sirf English/ASCII text support karti hai."
        try:
            print("[Sunday] Target app par switch karein; 3 seconds mein typing shuru hogi.")
            time.sleep(3)
            pyautogui.write(text_to_type, interval=0.01)
            return f"{len(text_to_type)} characters type kar diye."
        except Exception as e:
            return f"Text type nahi ho saka: {e}"

    return None


def _inside_project(path):
    return path == ROOT_DIR or ROOT_DIR in path.parents


def _parse_terminal_command(command):
    if not command or len(command) > 500:
        raise ValueError("Command khaali hai ya 500 characters se lamba hai.")
    if any(char in command for char in ("&", "|", ";", "<", ">", "`", "\n", "\r")):
        raise ValueError("Pipelines, chaining aur shell operators allowed nahi hain.")

    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.escape = ""
    return list(lexer)


def _run_terminal_command(raw_command):
    global TERMINAL_CWD

    try:
        args = _parse_terminal_command(raw_command)
    except ValueError as exc:
        return str(exc)
    if not args:
        return "Command specify karein."

    name = args[0].lower()
    if name in ("pwd",):
        return str(TERMINAL_CWD)
    if name in ("dir", "ls"):
        if len(args) != 1:
            return "Listing ke liye sirf `dir` ya `ls` use karein."
        try:
            entries = sorted(TERMINAL_CWD.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
            return "\n".join(
                f"{'[DIR] ' if path.is_dir() else '       '}{path.name}"
                for path in entries
            ) or "(folder khaali hai)"
        except OSError as exc:
            return f"Folder list nahi ho saka: {exc}"
    if name == "cd":
        target_text = args[1] if len(args) == 2 else "."
        target = (TERMINAL_CWD / target_text).resolve()
        if not _inside_project(target):
            return "Sunday terminal navigation ko project folder ke andar rakhta hai."
        if not target.is_dir():
            return "Folder nahi mila."
        TERMINAL_CWD = target
        return f"Current folder: {TERMINAL_CWD}"
    if name in ("open", "start") and len(args) == 2 and args[1].lower() in ("terminal", "cmd"):
        return "Sunday isi terminal mein chal raha hai; yahin command likhein."

    executable_args = None
    if name in ("python", "py"):
        script_index = 1
        if len(args) > 1 and args[1] in ("--version", "-V"):
            if len(args) != 2:
                return "Version check ke liye `python --version` use karein."
            executable_args = [sys.executable, "--version"]
        else:
            if len(args) <= script_index or args[script_index].startswith("-"):
                return "Sirf `python --version` ya project ke andar `.py` file run kar sakte hain."
            script_path = (TERMINAL_CWD / args[script_index]).resolve()
            if script_path.suffix.lower() != ".py" or not _inside_project(script_path) or not script_path.is_file():
                return "Python script project folder ke andar honi chahiye."
            executable_args = [sys.executable, str(script_path), *args[script_index + 1:]]
    elif name == "pytest":
        pytest_args = [arg for arg in args[1:] if arg not in ("-q", "-v")]
        if any(
            Path(arg).is_absolute()
            or (arg not in ("tests", "tests/") and not arg.startswith("tests\\") and not arg.startswith("tests/"))
            for arg in pytest_args
        ):
            return "Pytest ko sirf `-q`, `-v`, ya `tests` folder ke andar ke paths ke saath chala sakte hain."
        executable_args = [sys.executable, "-m", "pytest", *args[1:]]
    elif name == "git":
        safe_git_commands = {"status", "diff", "log", "show", "branch"}
        if len(args) < 2 or args[1] not in safe_git_commands:
            return "Git ke liye filhaal status, diff, log, show, aur branch read-only commands available hain."
        if any(arg in ("--output", "--exec-path", "-c", "--config-env") for arg in args[2:]):
            return "Yeh git option allowed nahi hai."
        executable_args = args
    elif name in ("where", "whoami", "hostname", "ipconfig", "systeminfo", "tree"):
        if name != "where" and len(args) != 1:
            return f"`{name}` ke saath extra arguments allowed nahi hain."
        if name == "where" and len(args) != 2:
            return "`where` ke saath ek hi program name dein."
        executable_args = args
    else:
        return (
            "Yeh command allow-list mein nahi hai. Abhi python project scripts, pytest, "
            "read-only git, aur basic system-info commands supported hain."
        )

    if not request_permission(f"terminal mein yeh command run karna: {raw_command}"):
        return "Command cancel kar di; permission nahi mili."

    try:
        result = subprocess.run(
            executable_args,
            cwd=TERMINAL_CWD,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "Command 30 seconds mein complete nahi hui; rok di gayi."
    except OSError as exc:
        return f"Command start nahi ho saki: {exc}"

    output = (result.stdout or "") + (result.stderr or "")
    output = output.strip()
    if not output:
        output = "(koi output nahi)"
    if len(output) > 6000:
        output = output[:6000] + "\n...[output truncated]"
    return f"Exit code: {result.returncode}\n{output}"


def handle_terminal_command(raw_text):
    command = raw_text.strip()
    lowered = command.lower()
    if lowered in ("open terminal", "terminal kholo", "cmd kholo"):
        return "Sunday isi terminal mein chal raha hai; yahin text command likh sakte hain."

    prefixes = ("run command ", "terminal run ", "command run ")
    prefix = next((item for item in prefixes if lowered.startswith(item)), None)
    if prefix:
        result = _run_terminal_command(command[len(prefix):].strip())
        print(f"\n[Terminal output]\n{result}\n")
        return "Command ka status aur output terminal mein check karein."
    return None


# ============================================================
# 21) COMMAND HANDLER
# ============================================================
def process_command(c, from_text=False):
    global HUNTER_MODE

    original = c.strip()
    c = original.lower()
    print(f"[You] {c}")
    words = c.split()

    terminal_result = handle_terminal_command(original)
    if terminal_result is not None:
        speak(terminal_result)
        return

    # ---- PERSONAL REPLIES (both modes, offline) ----
    personal = get_personal_reply(c)
    if personal:
        print(f"[Personality] Matched: '{c}'")
        speak(personal)
        return

    # ---- HUNTER MODE: strictly hunter commands only ----
    if HUNTER_MODE:
        if is_hunter_deactivate(c):
            reply = exit_hunter_mode()
            speak(reply)
            return

        reply, handled = handle_hunter_command(c)
        if handled:
            speak(reply)
            return

        print(f"[Hunter] Not a hunter command: '{c}'")
        speak("That's not a hunter command. Say 'hunter help' for the list.")
        return

    # ---- NORMAL MODE ----
    screen_result = handle_screen_command(original, c)
    if screen_result is not None:
        speak(screen_result)
        return

    if not from_text and is_system_noise(c):
        print(f"[Filter] Ignored system audio: '{c}'")
        return

    if not from_text and not is_command_like(c):
        print(f"[Filter] No command keyword — ignoring: '{c}'")
        return

    if is_stop_command(c):
        speak("Okay, stopped.")
        return

    memory_saved = detect_and_save_memory(original)
    if memory_saved is None:
        speak("Memory update nahi ki; permission nahi mili.")
        return
    if memory_saved:
        name = memory.get_profile("name") if memory else None
        if name:
            speak(f"Got it, I will remember that, {name.split()[0]}")
        else:
            speak("Got it, I will remember that.")
        return

    if "what is my name" in c or "mera naam kya" in c or "what's my name" in c:
        name = memory.get_profile("name") if memory else None
        if name:
            speak(f"Your name is {name}")
        else:
            speak("I do not know your name yet.")
        return

    if "what do you know about me" in c or "mere baare mein" in c:
        if not memory:
            speak("Memory not available.")
            return
        profile = memory.get_profile()
        facts = memory.get_facts(limit=10)
        if not profile and not facts:
            speak("I do not know anything about you yet.")
            return
        parts = []
        if profile:
            parts.append("Profile: " + ", ".join(f"{k} is {v}" for k, v in profile.items()))
        if facts:
            parts.append("Facts: " + "; ".join(facts[:5]))
        speak(". ".join(parts))
        return

    if c.startswith("remember ") or c.startswith("yaad rakho "):
        fact = c.replace("remember ", "").replace("yaad rakho ", "").strip()
        if fact and memory:
            if not request_permission("assistant ki saved memory mein yeh fact add karna"):
                speak("Memory update nahi ki; permission nahi mili.")
                return
            memory.add_fact(fact)
            speak(f"Okay, I will remember: {fact}")
        return

    if c.startswith("forget ") or c.startswith("bhool jao "):
        what = c.replace("forget ", "").replace("bhool jao ", "").strip()
        if memory and not request_permission(f"saved memory se '{what}' delete karna"):
            speak("Memory update nahi ki; permission nahi mili.")
            return
        if memory and memory.delete_profile(what):
            speak(f"Forgot {what}")
        else:
            speak(f"I do not have {what} in memory")
        return

    if "forget everything" in c or "clear memory" in c or "sab bhool jao" in c:
        if not request_permission("assistant ki saved memory clear karna"):
            speak("Memory clear nahi ki; permission nahi mili.")
            return
        if memory:
            memory.clear_all()
        speak("All memory cleared")
        return

    if is_code_create_request(c):
        workflow_generate_code(original)
        return

    if is_code_fix_request(c):
        fname = None
        for w in words:
            if w.endswith((".py", ".html", ".css", ".js")):
                fname = w
                break
        if fname:
            workflow_fix_code(fname)
        else:
            speak("Which file should I fix?")
        return

    if is_code_improve_request(c):
        fname = None
        for w in words:
            if w.endswith((".py", ".html", ".css", ".js")):
                fname = w
                break
        if fname:
            workflow_improve_code(fname)
        else:
            speak("Which file should I improve?")
        return

    if is_code_run_request(c):
        fname = None
        for w in words:
            if w.endswith((".py", ".html", ".css", ".js")):
                fname = w
                break
        if fname:
            workflow_run_code(fname)
        else:
            speak("Which file should I run?")
        return

    if "open my files" in c or "open user files" in c:
        speak(open_user_files_folder()); return
    if "open code folder" in c:
        speak(open_code_folder()); return
    if ("list" in c or "show" in c) and ("file" in c or "files" in c):
        speak(list_files()); return

    if "create" in c and "file" in c:
        idx = c.find("file")
        fname = c[idx + 4:].strip()
        for filler in ("named ", "called ", "the "):
            if fname.startswith(filler):
                fname = fname[len(filler):].strip()
        if fname:
            speak(file_create(fname)); return

    if "create" in c and ("folder" in c or "directory" in c):
        idx = -1
        for kw in ("folder", "directory"):
            idx = c.find(kw)
            if idx != -1:
                fname = c[idx + len(kw):].strip()
                for filler in ("named ", "called ", "the "):
                    if fname.startswith(filler):
                        fname = fname[len(filler):].strip()
                if fname:
                    speak(folder_create(fname)); return

    if "open" in c and "file" in c and "file explorer" not in c:
        idx = c.find("file")
        fname = c[idx + 4:].strip()
        for filler in ("named ", "called ", "the "):
            if fname.startswith(filler):
                fname = fname[len(filler):].strip()
        if fname:
            speak(open_file(fname)); return

    if "read" in c:
        idx = c.find("file")
        if idx != -1:
            fname = c[idx + 4:].strip()
        else:
            idx = c.find("read")
            fname = c[idx + 4:].strip()
        for filler in ("named ", "called ", "the "):
            if fname.startswith(filler):
                fname = fname[len(filler):].strip()
        fname = fname.replace(" file", "").strip()
        if fname and fname != "file":
            speak(file_read(fname)); return

    if ("write" in c or "likh" in c) and (" in " in c or " to " in c):
        in_pos = -1
        sep = " in "
        for kw in (" in ", " to ", " inside "):
            in_pos = original.lower().find(kw)
            if in_pos != -1:
                sep = kw
                break
        if in_pos != -1:
            write_pos = -1
            trig = "write"
            for kw in ("write", "likho", "likh"):
                write_pos = original.lower().find(kw)
                if write_pos != -1:
                    trig = kw
                    break
            if write_pos != -1:
                content = original[write_pos + len(trig):in_pos].strip()
                fname = original[in_pos + len(sep):].strip()
                fname = fname.replace(" file", "").replace("file", "").strip()
                if content and fname:
                    speak(file_write(fname, content)); return

    if "delete" in c:
        idx = c.find("file")
        if idx != -1:
            fname = c[idx + 4:].strip()
        else:
            idx = c.find("delete")
            fname = c[idx + 6:].strip()
        for filler in ("named ", "called ", "the "):
            if fname.startswith(filler):
                fname = fname[len(filler):].strip()
        fname = fname.replace(" file", "").strip()
        if fname and fname != "file":
            speak(file_delete(fname)); return

    # SYSTEM
    if "cancel" in c and any(k in c for k in ("shutdown", "shut down", "restart")):
        speak(system_cancel_shutdown()); return
    if "shutdown" in c or "shut down" in c:
        delay = 30
        for w in words:
            if w.isdigit(): delay = int(w); break
        speak(system_shutdown(delay)); return
    if "restart" in c or "reboot" in c:
        delay = 30
        for w in words:
            if w.isdigit(): delay = int(w); break
        speak(system_restart(delay)); return
    if "sleep" in c and ("pc" in c or "computer" in c or "laptop" in c):
        speak(system_sleep_pc()); return
    if "lock" in c and ("screen" in c or "pc" in c or "computer" in c or "karo" in c):
        speak(system_lock()); return
    if any(p in c for p in [
        "screenshot", "screen shot", "take a screenshot", "take screenshot",
        "capture screen", "screenshot lo", "screenshot le",
    ]):
        speak(system_screenshot()); return

    # VOLUME
    if any(w in c for w in ("volume", "awaaz", "aawaz", "sound")):
        if any(w in c for w in ("up", "increase", "badha", "tez")):
            speak(volume_up()); return
        if any(w in c for w in ("down", "decrease", "kam", "dheema")):
            speak(volume_down()); return
        if "unmute" in c:
            speak(volume_mute()); return
        if "mute" in c or "chup" in c:
            speak(volume_mute()); return
        for w in words:
            if w.isdigit():
                speak(volume_set(int(w))); return
        speak("Volume up, down, or mute?"); return

    # MEDIA
    if "next" in c and ("song" in c or "gaana" in c):
        speak(media_next()); return
    if ("previous" in c or "prev" in c or "pichla" in c) and ("song" in c or "gaana" in c):
        speak(media_prev()); return
    if "pause" in c or "roko" in c:
        speak(media_play_pause()); return
    if "resume" in c:
        speak(media_play_pause()); return
    if "stop music" in c:
        speak(media_stop()); return

    # CLOSE
    if any(w in c for w in ("close", "band karo")):
        for app_name in APPS:
            if app_name in c:
                speak(close_app(app_name)); return
        speak("Which app to close?"); return

    # OPEN
    site_map = [
        ("youtube", "https://youtube.com", "Opening YouTube"),
        ("google", "https://google.com", "Opening Google"),
        ("github", "https://github.com", "Opening GitHub"),
        ("gmail", "https://mail.google.com", "Opening Gmail"),
        ("chatgpt", "https://chat.openai.com", "Opening ChatGPT"),
        ("whatsapp", "https://web.whatsapp.com", "Opening WhatsApp"),
        ("facebook", "https://facebook.com", "Opening Facebook"),
        ("instagram", "https://instagram.com", "Opening Instagram"),
    ]
    open_triggers = ("open", "khol", "launch", "start", "chalu")
    if any(t in c for t in open_triggers):
        for keyword, url, response in site_map:
            if keyword in c:
                speak(response); webbrowser.open(url); return
        for app_name in APPS:
            if app_name in c:
                speak(open_app_smart(app_name)); return
        for trigger in open_triggers:
            if trigger in c:
                parts = c.split(trigger, 1)
                if len(parts) > 1:
                    app_query = parts[1].strip()
                    if app_query:
                        speak(open_app_smart(app_query)); return
        speak("Which app to open?"); return

    # MUSIC
    music_triggers = ("play", "baja", "sunao", "gaana", "song")
    if any(t in c for t in music_triggers):
        song_query = ""
        for trigger in music_triggers:
            if trigger in c:
                parts = c.split(trigger, 1)
                if len(parts) > 1:
                    song_query = parts[1].strip()
                    for filler in ("song", "gaana", "music", "please", "the"):
                        song_query = song_query.replace(filler, "").strip()
                    break
        if not song_query:
            speak(media_play_pause()); return
        speak(play_song(song_query)); return

    # TIME / DATE
    if "time" in c or "samay" in c:
        speak(datetime.now().strftime("It's %I:%M %p")); return
    if "date" in c or "tareekh" in c:
        speak(datetime.now().strftime("Today is %A, %B %d")); return

    # UNKNOWN → AI
    if API_KEYS:
        if not request_permission(
            "aapka message aur related saved memory Google AI ko bhejna"
        ):
            speak("Cloud AI request nahi bheji; permission nahi mili.")
            return
        speak("Let me think")
        memory_context = memory.build_context() if memory else ""
        prompt = (
            "You are Sunday, a helpful voice assistant. "
            "Reply in natural Hinglish (Hindi written in Latin script with common English words). "
            "Answer in 1-2 short sentences suitable for voice. "
        )
        if memory_context:
            prompt += f"\n\nMemory about user:\n{memory_context}\n"
        prompt += f"\nQuestion: {c}"
        raw = _call_gemini(prompt)
        if memory:
            memory.add_message("user", c)
        if raw:
            parts = [p.strip() for p in raw.split(".") if p.strip()]
            short = ". ".join(parts[:2]) + "." if parts else raw[:200]
            if memory:
                memory.add_message("assistant", short)
            speak(short, allow_stop=True)
        else:
            speak("Cloud AI abhi available nahi hai; thodi der baad try karein.")
    else:
        speak("I didn't understand that")


# ============================================================
# 22) MAIN ENTRY
# ============================================================
def start_terminal_input():
    threading.Thread(
        target=_terminal_input_loop,
        name="SundayTerminalInput",
        daemon=True,
    ).start()
    TERMINAL_INPUT_READY.wait(timeout=1)


def _process_pending_text_commands():
    while True:
        try:
            command = TEXT_COMMAND_QUEUE.get_nowait()
        except queue.Empty:
            return
        try:
            process_command(command, from_text=True)
        except Exception as e:
            print(f"[Sunday] Text command failed ({type(e).__name__}).")
        finally:
            TEXT_COMMAND_QUEUE.task_done()


def main():
    global memory, hud, kb_listener, HUNTER_MODE

    print("\n" + "=" * 60)
    print("  Sunday — v39 (Personal Replies + PRO Hunter)")
    print("=" * 60)

    memory = Memory()
    init_speaker()

    try:
        if HUNTER_AVAILABLE:
            sunday_hunter.set_speak_callback(speak)
            print("[Sunday] Auto-bot speak callback wired")
    except Exception as e:
        print(f"[Sunday] Auto-bot wiring failed: {e}")

    hud = init_hud(enabled=True, fullscreen=True)
    kb_listener = start_keyboard_listener()
    start_terminal_input()

    speak("Sunday tayyar hai. Voice ke liye wake up Sunday boliye, ya isi terminal mein command type karein.")

    print("=" * 60)
    print(f"[Sunday] Owner: {OWNER_NAME}")
    print(f"[Sunday] API keys: {len(API_KEYS)}")
    print(f"[Sunday] HUD: {'enabled' if hud and hud.enabled else 'disabled'}")
    print(f"[Sunday] Hunter: {'available' if HUNTER_AVAILABLE else 'unavailable'}")

    current_name = memory.get_profile("name")
    if current_name:
        print(f"[Sunday] Memory: I remember {current_name}")
    print("=" * 60)

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 4000
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 0.6
    recognizer.phrase_threshold = 0.4
    recognizer.non_speaking_duration = 0.4

    mic = sr.Microphone()

    with mic as source:
        print("[Sunday] Calibrating mic (stay quiet 2s)...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print(f"[Sunday] Energy threshold: {recognizer.energy_threshold}")

    print("\n😴 SLEEP MODE — Say 'Wake up Sunday'")
    print("💬 Say 'Thanks' / 'Who is your owner' → offline reply")
    print("🎯 Say 'Sunday hunter' → PRO Hunter Mode (RED HUD)")
    print("⌨️  Tab → hide/show HUD")
    print("👋 Say 'Bye Sunday' → sleep")
    print("🚪 Say 'Goodbye' → exit\n")

    mode = "sleep"

    while True:
        _process_pending_text_commands()
        try:
            with mic as source:
                if mode == "sleep":
                    if hud:
                        try:
                            hud.set_state("idle")
                        except Exception:
                            pass
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=4)
                else:
                    if hud:
                        try:
                            if HUNTER_MODE:
                                hud.set_state("hunter")
                            else:
                                hud.set_state("listening")
                        except Exception:
                            pass
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=8)

            try:
                text = recognizer.recognize_google(audio, language="en-IN")
                print(f"[Debug] Heard: '{text}'")
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                print("[Voice] Speech service unavailable; text commands abhi bhi available hain.")
                continue

            if not text:
                continue

            if mode == "sleep":
                if is_exit(text):
                    speak("Goodbye")
                    if hud:
                        try:
                            hud.hide_fullscreen()
                        except Exception:
                            pass
                    print("\n🚪 Sunday exiting...\n")
                    break
                if is_wake(text):
                    mode = "command"
                    if hud:
                        try:
                            hud.show_fullscreen()
                        except Exception:
                            pass
                    globals()['hud_hidden'] = False
                    name = memory.get_profile("name") if memory else None
                    if name:
                        speak(f"Yes {name.split()[0]}, I'm listening")
                    else:
                        speak("Yes, I'm listening")
                    print("\n🎧 COMMAND MODE\n")
                continue

            if mode == "command":
                if is_exit(text):
                    speak("Goodbye")
                    if hud:
                        try:
                            hud.hide_fullscreen()
                        except Exception:
                            pass
                    print("\n🚪 Sunday exiting...\n")
                    break

                if is_sleep(text):
                    speak("Okay, going back to sleep")
                    if hud:
                        try:
                            hud.hide_fullscreen()
                        except Exception:
                            pass
                    mode = "sleep"
                    print("\n😴 SLEEP MODE\n")
                    continue

                if not HUNTER_MODE and is_hunter_activate(text):
                    reply = enter_hunter_mode()
                    speak(reply)
                    print("\n🎯 HUNTER MODE ACTIVE (RED)\n")
                    continue

                process_command(text)

        except sr.WaitTimeoutError:
            continue
        except KeyboardInterrupt:
            print("\n[Sunday] Ctrl+C — Stopping...")
            break
        except Exception as e:
            print(f"[Sunday] Command process nahi ho saka ({type(e).__name__}).")
            continue

    print("\n🚪 Sunday stopped.\n")

    try:
        if HUNTER_AVAILABLE:
            sunday_hunter.stop_autobot()
    except Exception:
        pass

    try:
        if kb_listener:
            try:
                kb_listener.stop()
            except Exception:
                pass
    except Exception:
        pass

    try:
        if hud:
            try:
                hud.hide_fullscreen()
            except Exception:
                pass
            try:
                hud.stop()
            except Exception:
                pass
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    main()