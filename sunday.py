"""
Sunday v17 — Full PC Assistant + Code Generator
========================================
NEW:
- Auto code generator (Python, HTML, CSS, JS)
- Auto bug fixer
- Auto code improver
- All previous features intact
"""

import os
import re
import time
import threading
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

import speech_recognition as sr
import win32com.client
import pyautogui
import psutil
from dotenv import load_dotenv

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

TEMP_DIR.mkdir(exist_ok=True)
USER_FILES_DIR.mkdir(exist_ok=True)
CODE_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT_DIR / ".env")
pyautogui.FAILSAFE = False


# ============================================================
# 1) WAKE / SLEEP / EXIT / STOP
# ============================================================
WAKE_PHRASES = [
    "wake up sunday", "hey sunday", "hi sunday", "hello sunday",
    "ok sunday", "sunday suno", "oye sunday", "sunny suno",
]

def is_wake(text):
    t = text.lower().strip()
    return any(p in t for p in WAKE_PHRASES)


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
# 2) LOAD API KEY
# ============================================================
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None

if GEMINI_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_KEY)
        print("[Setup] Gemini AI ready")
    except Exception as e:
        print(f"[Setup] Gemini init failed: {e}")
else:
    print("[Setup] No GEMINI_API_KEY")


# ============================================================
# 3) APP LIBRARY
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
    "store": "ms-windows-store:", "settings": "ms-settings:",
    "photoshop": "photoshop", "notion": "notion", "obsidian": "obsidian",
    "docker": "docker", "postman": "postman",
}


# ============================================================
# 4) VOICE
# ============================================================
print("[Setup] Initializing voice...")
speaker = win32com.client.Dispatch("SAPI.SpVoice")
speaker.Rate = 0

FEMALE_VOICE_KEYWORDS = ["zira", "heera", "hazel", "susan", "samantha", "female"]
sapi_voices = speaker.GetVoices()
female_set = False

for keyword in FEMALE_VOICE_KEYWORDS:
    for i in range(sapi_voices.Count):
        v = sapi_voices.Item(i)
        desc = v.GetDescription()
        if keyword in desc.lower():
            speaker.Voice = v
            print(f"[Setup] Female voice: {desc}")
            female_set = True
            break
    if female_set:
        break

STOP_FLAG = threading.Event()


def speak(text, allow_stop=False):
    if not text:
        return
    print(f"[Sunday] {text}")

    if not allow_stop:
        try:
            speaker.Speak(text)
        except Exception as ex:
            print(f"[TTS Error] {ex}")
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
                                try:
                                    speaker.Speak("", 3)
                                except Exception:
                                    pass
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


# ============================================================
# 5) VOLUME
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
# 6) APP CONTROL
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
# 7) MEDIA
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
# 8) SYSTEM
# ============================================================
def system_lock():
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return "Locking screen"


def system_shutdown(delay=30):
    os.system(f"shutdown /s /t {delay}")
    return f"Shutting down in {delay} seconds"


def system_restart(delay=30):
    os.system(f"shutdown /r /t {delay}")
    return f"Restarting in {delay} seconds"


def system_cancel_shutdown():
    os.system("shutdown /a")
    return "Shutdown cancelled"


def system_sleep_pc():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "Going to sleep"


def system_screenshot():
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
# 9) MUSIC
# ============================================================
def play_song(song_name):
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
# 10) FILE MANAGER
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
    try:
        path.write_text(content, encoding="utf-8")
        return f"Written to {path.name}"
    except Exception as e:
        return f"Error writing: {e}"


def file_append(filename, content):
    path = _resolve_user_path(filename)
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
# 11) AI BRAIN + CODE GENERATOR
# ============================================================
CODE_GEN_SYSTEM = (
    "You are Sunday, an expert programmer. The user wants you to WRITE CODE for them. "
    "Rules:\n"
    "1. Output ONLY the code, no explanations, no markdown, no ```code fences```.\n"
    "2. Start code with a comment saying what it does.\n"
    "3. Make code clean, working, and well-commented.\n"
    "4. For Python: use if __name__ == '__main__': main() pattern.\n"
    "5. For HTML: complete boilerplate with <!DOCTYPE html>.\n"
    "6. For CSS: complete styling.\n"
    "7. For JS: modern ES6 syntax.\n"
    "8. Do not say anything else — code only."
)

CODE_FIX_SYSTEM = (
    "You are Sunday, an expert debugger. The user will give you buggy code. "
    "Rules:\n"
    "1. Output ONLY the fixed code, no explanations, no markdown fences.\n"
    "2. Fix all bugs and issues.\n"
    "3. Keep the original intent.\n"
    "4. Add comments where you fixed something.\n"
    "5. Code only, nothing else."
)

CODE_IMPROVE_SYSTEM = (
    "You are Sunday, a senior developer. The user will give you code to improve. "
    "Rules:\n"
    "1. Output ONLY the improved code, no explanations, no markdown fences.\n"
    "2. Improve readability, add docstrings, better variable names.\n"
    "3. Keep functionality same.\n"
    "4. Code only, nothing else."
)


def _extract_code(raw):
    """Strip markdown fences and return pure code."""
    text = raw.strip()
    # Remove ```python ... ``` or ```html ... ``` etc.
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def ai_generate_code(description):
    """Generate code from natural language description."""
    if not gemini_client:
        return None
    prompt = f"{CODE_GEN_SYSTEM}\n\nTask: {description}"
    for model_name in ["gemini-flash-latest", "gemini-3.8-flash"]:
        try:
            response = gemini_client.models.generate_content(
                model=model_name, contents=prompt,
            )
            code = _extract_code(response.text or "")
            if code:
                return code
        except Exception as e:
            err_lower = str(e).lower()
            if any(k in err_lower for k in ("503", "unavailable", "429")):
                time.sleep(2)
                continue
    return None


def ai_fix_code(code):
    """Fix bugs in given code."""
    if not gemini_client:
        return None
    prompt = f"{CODE_FIX_SYSTEM}\n\nHere is the buggy code:\n\n{code}"
    for model_name in ["gemini-flash-latest", "gemini-3.8-flash"]:
        try:
            response = gemini_client.models.generate_content(
                model=model_name, contents=prompt,
            )
            fixed = _extract_code(response.text or "")
            if fixed:
                return fixed
        except Exception as e:
            err_lower = str(e).lower()
            if any(k in err_lower for k in ("503", "unavailable", "429")):
                time.sleep(2)
                continue
    return None


def ai_improve_code(code):
    """Improve given code."""
    if not gemini_client:
        return None
    prompt = f"{CODE_IMPROVE_SYSTEM}\n\nHere is the code:\n\n{code}"
    for model_name in ["gemini-flash-latest", "gemini-3.8-flash"]:
        try:
            response = gemini_client.models.generate_content(
                model=model_name, contents=prompt,
            )
            improved = _extract_code(response.text or "")
            if improved:
                return improved
        except Exception as e:
            err_lower = str(e).lower()
            if any(k in err_lower for k in ("503", "unavailable", "429")):
                time.sleep(2)
                continue
    return None


def detect_language(description):
    """Detect programming language from description."""
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
    return "py"  # default


def detect_filename(description):
    """Extract or generate filename from description."""
    # Look for explicit filename
    match = re.search(r"in\s+([\w\-\.]+\.\w+)", description)
    if match:
        return match.group(1)
    match = re.search(r"called\s+([\w\-\.]+\.\w+)", description)
    if match:
        return match.group(1)
    match = re.search(r"named\s+([\w\-\.]+\.\w+)", description)
    if match:
        return match.group(1)
    # Generate from description
    ext = detect_language(description)
    # Slugify
    slug = re.sub(r"[^\w\s]", "", description.lower())
    words = [w for w in slug.split() if w not in (
        "make", "create", "write", "build", "a", "an", "the", "me",
        "please", "code", "program", "script", "file", "in", "called",
        "named", "for", "python", "html", "css", "javascript", "js",
    )]
    name = "_".join(words[:3]) or "generated"
    return f"{name}.{ext}"


# ============================================================
# 12) CODE INTENT DETECTION
# ============================================================
CODE_CREATE_TRIGGERS = [
    "make a", "make me", "create a", "create me", "write a", "write me",
    "build a", "build me", "generate a", "generate me", "code a", "code me",
    "banao", "bana do", "likho", "likh do", "make a python", "make a html",
    "make a css", "make a javascript", "write code", "code likho",
    "program banao", "script banao", "program likho", "script likho",
]

CODE_FIX_TRIGGERS = [
    "fix the bug", "fix bug", "fix code", "fix error", "debug",
    "theek karo", "thik karo", "sahi karo", "fix karo",
    "bug fix", "bug theek",
]

CODE_IMPROVE_TRIGGERS = [
    "improve the code", "improve code", "refactor",
    "behtar karo", "improve karo", "clean the code",
    "clean code", "optimize",
]

CODE_OPEN_TRIGGERS = [
    "run the code", "run code", "execute", "chalao", "run karo",
    "run the file", "run file",
]


def is_code_create_request(text):
    t = text.lower()
    # Must have a creation trigger
    has_trigger = any(trig in t for trig in CODE_CREATE_TRIGGERS)
    if not has_trigger:
        return False
    # Should mention a language or a "code-like" noun
    code_words = [
        "python", "html", "css", "javascript", "js",
        "code", "program", "script", "calculator", "website",
        "game", "app", "function", "class", "bot", "tool",
        "calculator", "todo", "timer", "clock", "guess",
    ]
    return any(w in t for w in code_words)


def is_code_fix_request(text):
    return any(t in text.lower() for t in CODE_FIX_TRIGGERS)


def is_code_improve_request(text):
    return any(t in text.lower() for t in CODE_IMPROVE_TRIGGERS)


def is_code_run_request(text):
    return any(t in text.lower() for t in CODE_OPEN_TRIGGERS)


# ============================================================
# 13) CODE WORKFLOWS
# ============================================================
def workflow_generate_code(description):
    """Generate code + save to file."""
    speak("Let me write that code for you")
    code = ai_generate_code(description)
    if not code:
        speak("Sorry, I couldn't generate the code. Try again.")
        return

    filename = detect_filename(description)
    path = _resolve_user_path(filename, code=True)
    try:
        path.write_text(code, encoding="utf-8")
        lines = len(code.splitlines())
        speak(f"Done. I wrote {lines} lines of code in {filename}")
        # Auto-open in VS Code
        try:
            subprocess.Popen(f'code "{path}"', shell=True)
        except Exception:
            pass
        print(f"\n[CODE] Saved to: {path}\n")
        print("=" * 60)
        print(code[:1000])
        print("=" * 60)
    except Exception as e:
        speak(f"Could not save file: {e}")


def workflow_fix_code(filename):
    """Read file, fix bugs, save back."""
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        # Try user_files
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        speak(f"Could not read file: {e}")
        return

    speak("Fixing the bugs")
    fixed = ai_fix_code(original)
    if not fixed:
        speak("Sorry, could not fix the code. Try again.")
        return

    try:
        path.write_text(fixed, encoding="utf-8")
        speak(f"Fixed. I updated {path.name}")
        print(f"\n[CODE FIXED] {path}\n")
    except Exception as e:
        speak(f"Could not save: {e}")


def workflow_improve_code(filename):
    """Improve code in file."""
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        speak(f"Could not read: {e}")
        return

    speak("Improving the code")
    improved = ai_improve_code(original)
    if not improved:
        speak("Sorry, could not improve. Try again.")
        return

    try:
        path.write_text(improved, encoding="utf-8")
        speak(f"Improved {path.name}")
        print(f"\n[CODE IMPROVED] {path}\n")
    except Exception as e:
        speak(f"Could not save: {e}")


def workflow_run_code(filename):
    """Run a Python file."""
    path = _resolve_user_path(filename, code=True)
    if not path.exists():
        path = _resolve_user_path(filename)
        if not path.exists():
            speak(f"File {filename} not found")
            return

    if path.suffix.lower() == ".py":
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
# 14) COMMAND HANDLER
# ============================================================
def process_command(c):
    c = c.lower().strip()
    original = c
    print(f"[You] {original}")
    words = c.split()

    if is_stop_command(c):
        speak("Okay, stopped.")
        return

    # ============ CODE CREATION (highest priority) ============
    if is_code_create_request(c):
        workflow_generate_code(original)
        return

    # ============ CODE FIX ============
    if is_code_fix_request(c):
        # Find filename
        fname = None
        for w in words:
            if w.endswith((".py", ".html", ".css", ".js")):
                fname = w
                break
        if not fname:
            # Try after "in" or "the"
            for kw in ("in ", "the "):
                idx = c.find(kw)
                if idx != -1:
                    fname = c[idx + len(kw):].strip()
                    break
        if fname:
            workflow_fix_code(fname)
        else:
            speak("Which file should I fix?")
        return

    # ============ CODE IMPROVE ============
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

    # ============ CODE RUN ============
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

    # ============ FILE MANAGER ============
    if "open my files" in c or "open user files" in c:
        speak(open_user_files_folder()); return
    if "open code folder" in c or "open my code" in c:
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

    # ============ SYSTEM ============
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

    # ============ VOLUME ============
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

    # ============ MEDIA ============
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

    # ============ CLOSE APP ============
    if any(w in c for w in ("close", "band karo")):
        for app_name in APPS:
            if app_name in c:
                speak(close_app(app_name)); return
        speak("Which app to close?"); return

    # ============ OPEN APP/WEBSITE ============
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

    # ============ MUSIC ============
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

    # ============ TIME / DATE ============
    if "time" in c or "samay" in c:
        speak(datetime.now().strftime("It's %I:%M %p")); return
    if "date" in c or "tareekh" in c:
        speak(datetime.now().strftime("Today is %A, %B %d")); return

    # ============ UNKNOWN → AI ============
    if gemini_client:
        speak("Let me think")
        try:
            response = gemini_client.models.generate_content(
                model="gemini-flash-latest",
                contents=f"You are Sunday, a helpful female voice assistant. Answer in 1-2 short sentences suitable for voice. Question: {c}",
            )
            answer = (response.text or "").strip()
            parts = [p.strip() for p in answer.split(".") if p.strip()]
            short = ". ".join(parts[:2]) + "."
            speak(short, allow_stop=True)
        except Exception as e:
            speak(f"AI error: {e}")
    else:
        speak("I didn't understand that")


# ============================================================
# 15) MAIN LOOP
# ============================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Sunday — v17 (PC Control + Code Generator)")
    print("=" * 60)
    speak("Sunday is ready. Say wake up Sunday to activate me.")
    print("=" * 60)
    print(f"[Sunday] User files: {USER_FILES_DIR}")
    print(f"[Sunday] Code folder: {CODE_DIR}")
    print("=" * 60)

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("[Sunday] Calibrating mic...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

    print("\n😴 SLEEP MODE — Say 'Wake up Sunday'")
    print("💻 Say 'Make a Python calculator' → auto-code!")
    print("🔧 Say 'Fix the bug in test.py' → auto-fix!")
    print("👋 Say 'Bye Sunday' → sleep")
    print("🚪 Say 'Goodbye' → exit\n")

    mode = "sleep"

    while True:
        try:
            with mic as source:
                if mode == "sleep":
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=4)
                else:
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

            try:
                text = recognizer.recognize_google(audio, language="en-IN").lower()
                print(f"[Debug] Heard: '{text}'")
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"[Debug] Google error: {e}")
                continue

            if not text:
                continue

            if mode == "sleep":
                if is_exit(text):
                    speak("Goodbye")
                    print("\n🚪 Sunday exiting...\n")
                    break
                if is_wake(text):
                    mode = "command"
                    speak("Yes, I'm listening")
                    print("\n🎧 COMMAND MODE\n")
                continue

            if mode == "command":
                if is_exit(text):
                    speak("Goodbye")
                    print("\n🚪 Sunday exiting...\n")
                    break
                if is_sleep(text):
                    speak("Okay, going back to sleep")
                    mode = "sleep"
                    print("\n😴 SLEEP MODE\n")
                    continue
                process_command(text)

        except sr.WaitTimeoutError:
            continue
        except KeyboardInterrupt:
            print("\n[Sunday] Ctrl+C — Stopping...")
            break
        except Exception as e:
            print(f"[Error] {e}")
            continue