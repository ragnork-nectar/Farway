"""
Sunday v14 — Smart Assistant
========================================
NEW:
- 100+ apps in dictionary
- Unknown apps → Windows search auto-launch
- Songs via pywhatkit (no link needed)
- All previous features intact
"""

import os
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

# pywhatkit for YouTube auto-play
try:
    import pywhatkit
    PYWHATKIT_AVAILABLE = True
except ImportError:
    PYWHATKIT_AVAILABLE = False
    print("[Setup] pywhatkit not installed — songs will use search page")

# Volume control
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    VOLUME_AVAILABLE = True
except ImportError:
    VOLUME_AVAILABLE = False
    print("[Setup] pycaw not installed — volume control disabled")


# ============================================================
# 0) PATHS
# ============================================================
ROOT_DIR = Path(__file__).parent.resolve()
TEMP_DIR = ROOT_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
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
    exit_keywords = [
        "goodbye", "good bye", "quit",
        "exit program", "shutdown sunday", "shut down sunday",
        "band karo sunday",
    ]
    return any(k in t for k in exit_keywords)


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
        short_sleep = ["bye", "by", "buy", "bhai", "bhaiya", "so", "sona"]
        for w in short_sleep:
            if w == t or w in words:
                return True
    return False


def is_stop_command(text):
    t = text.lower().strip()
    stop_phrases = [
        "stop sunday", "sunday stop", "sunday chup",
        "chup sunday", "chup ho jao", "stop talking",
        "stop talking sunday", "shut up sunday",
        "bas karo sunday", "ruk sunday", "ruk jao sunday",
        "quiet sunday", "silent sunday", "chup karo",
    ]
    return any(p in t for p in stop_phrases)


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
    print("[Setup] No GEMINI_API_KEY — offline-only mode")


# ============================================================
# 3) MASSIVE APP LIBRARY (100+ apps)
# ============================================================
APPS = {
    # Browsers
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "brave": "brave", "opera": "opera",
    "vivaldi": "vivaldi",

    # Dev Tools
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "visual studio": "devenv", "pycharm": "pycharm",
    "intellij": "idea", "sublime": "sublime_text",
    "atom": "atom", "notepad++": "notepad++",
    "git bash": "git-bash", "github desktop": "github",
    "docker": "docker", "postman": "postman",
    "xampp": "xampp", "wamp": "wampmanager",

    # Office
    "word": "winword", "ms word": "winword",
    "excel": "excel", "ms excel": "excel",
    "powerpoint": "powerpnt", "ppt": "powerpnt",
    "outlook": "outlook", "onenote": "onenote",
    "access": "msaccess", "publisher": "mspub",
    "teams": "teams", "microsoft teams": "teams",

    # Media
    "spotify": "spotify", "vlc": "vlc",
    "media player": "wmplayer", "windows media player": "wmplayer",
    "itunes": "itunes", "audacity": "audacity",
    "obs": "obs64", "obs studio": "obs64",
    "netflix": "netflix", "amazon prime": "primevideo",

    # Communication
    "discord": "discord", "telegram": "telegram",
    "whatsapp": "whatsapp", "zoom": "zoom",
    "skype": "skype", "slack": "slack",
    "signal": "signal", "messenger": "messenger",

    # Gaming
    "steam": "steam", "epic games": "epicgameslauncher",
    "epic": "epicgameslauncher", "battle net": "battle.net",
    "ubisoft": "uplay", "origin": "origin",
    "gog galaxy": "galaxyclient", "minecraft": "minecraft",
    "roblox": "roblox", "valorant": "valorant",
    "league of legends": "leagueclient", "csgo": "csgo",
    "gta": "gta5", "fortnite": "fortnite",

    # Windows Tools
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "ms paint": "mspaint",
    "wordpad": "write", "cmd": "cmd",
    "command prompt": "cmd", "powershell": "powershell",
    "terminal": "wt", "windows terminal": "wt",
    "task manager": "taskmgr", "explorer": "explorer",
    "file explorer": "explorer", "settings": "ms-settings:",
    "control panel": "control", "registry": "regedit",
    "device manager": "devmgmt.msc", "disk management": "diskmgmt.msc",
    "services": "services.msc", "event viewer": "eventvwr.msc",
    "snipping tool": "snippingtool", "magnifier": "magnify",
    "on screen keyboard": "osk", "character map": "charmap",
    "resource monitor": "resmon",

    # Windows Apps (Store)
    "camera": "microsoft.windows.camera:", "photos": "ms-photos:",
    "clock": "ms-clock:", "calendar": "outlookcal:",
    "store": "ms-windows-store:", "microsoft store": "ms-windows-store:",
    "xbox": "xbox:", "calculator uwp": "calculator:",
    "weather": "bingweather:", "news": "bingnews:",
    "maps": "bingmaps:", "mail": "outlookmail:",
    "cortana": "cortana:", "feedback": "feedback-hub:",
    "paint 3d": "ms-paint:", "mixed reality": "ms-mixedreality:",

    # Utility
    "7zip": "7zFM", "winrar": "winrar", "winzip": "winzip32",
    "ccleaner": "ccleaner", "malwarebytes": "mbam",
    "avast": "avastui", "norton": "norton",
    "teamviewer": "teamviewer", "anydesk": "anydesk",
    "filezilla": "filezilla", "putty": "putty",
    "winscp": "winscp", "virtualbox": "virtualbox",
    "vmware": "vmware", "gnome box": "virt-manager",

    # Adobe
    "photoshop": "photoshop", "illustrator": "illustrator",
    "premiere": "adobe premiere pro", "after effects": "afterfx",
    "lightroom": "lightroom", "acrobat": "acrobat",
    "reader": "acroread", "indesign": "indesign",

    # Others
    "kindle": "kindle", "calibre": "calibre",
    "spotify web": "spotify", "anki": "anki",
    "notion": "notion", "obsidian": "obsidian",
    "evernote": "evernote", "todoist": "todoist",
    "lastpass": "lastpass", "bitwarden": "bitwarden",
    "thunderbird": "thunderbird", "utorrent": "utorrent",
    "qbittorrent": "qbittorrent", "bit torrent": "bittorrent",
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
                                print("[Sunday] Stop command detected!")
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
    t_speak.join(timeout=30)
    speech_done.set()


# ============================================================
# 5) VOLUME CONTROL
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
    if not vol: return "Volume control not available"
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new = min(1.0, current + step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume up to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_down(step=10):
    vol = get_volume_interface()
    if not vol: return "Volume control not available"
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new = max(0.0, current - step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume down to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_set(percent):
    vol = get_volume_interface()
    if not vol: return "Volume control not available"
    try:
        new = max(0.0, min(1.0, percent / 100))
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume set to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_mute():
    vol = get_volume_interface()
    if not vol: return "Volume control not available"
    try:
        is_muted = vol.GetMute()
        vol.SetMute(not is_muted, None)
        return "Muted" if not is_muted else "Unmuted"
    except Exception as e:
        return f"Volume error: {e}"


# ============================================================
# 6) APP CONTROL (with smart fallback)
# ============================================================
def open_app_smart(app_name):
    """Open app — try dictionary, then Windows search, then UWP."""
    key = app_name.lower().strip()

    # 1. Dictionary match
    if key in APPS:
        target = APPS[key]
        try:
            subprocess.Popen(f'start "" "{target}"', shell=True)
            return f"Opening {app_name}"
        except Exception:
            pass

    # 2. Try direct exe name
    try:
        subprocess.Popen(f'start "" "{key}"', shell=True)
        time.sleep(1.5)
        # Check if something opened
        return f"Trying to open {app_name}"
    except Exception:
        pass

    # 3. Windows Search fallback — press Win key, type app name, press Enter
    try:
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.typewrite(app_name, interval=0.03)
        time.sleep(0.6)
        pyautogui.press("enter")
        return f"Searching and opening {app_name}"
    except Exception as e:
        return f"Could not open {app_name}: {e}"


def close_app(app_name):
    key = app_name.lower().strip()
    target = APPS.get(key, key)
    target = target.replace(":", "").replace("ms-settings", "SystemSettings")

    proc_map = {
        "chrome": "chrome.exe", "msedge": "msedge.exe", "firefox": "firefox.exe",
        "code": "Code.exe", "notepad": "notepad.exe", "calc": "CalculatorApp.exe",
        "mspaint": "mspaint.exe", "cmd": "cmd.exe", "powershell": "powershell.exe",
        "taskmgr": "Taskmgr.exe", "explorer": "explorer.exe", "spotify": "Spotify.exe",
        "vlc": "vlc.exe", "discord": "Discord.exe", "telegram": "Telegram.exe",
        "whatsapp": "WhatsApp.exe", "zoom": "Zoom.exe", "teams": "Teams.exe",
        "steam": "steam.exe", "winword": "WINWORD.EXE", "excel": "EXCEL.EXE",
        "powerpnt": "POWERPNT.EXE", "outlook": "OUTLOOK.EXE",
        "pycharm": "pycharm64.exe", "idea": "idea64.exe",
        "postman": "Postman.exe", "obs64": "obs64.exe",
        "audacity": "audacity.exe", "skype": "Skype.exe",
        "slack": "slack.exe", "wordpad": "wordpad.exe",
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
        return f"Closed {app_name}" if killed > 0 else f"{app_name} is not running"
    except Exception as e:
        return f"Could not close {app_name}: {e}"


# ============================================================
# 7) MEDIA CONTROL
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
# 8) SYSTEM CONTROL
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
    return "Shutdown or restart cancelled"


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
# 9) MUSIC — via pywhatkit (NO LINK NEEDED!)
# ============================================================
def play_song(song_name):
    """Play song on YouTube — pywhatkit auto-play first result."""
    if PYWHATKIT_AVAILABLE:
        try:
            pywhatkit.playonyt(song_name)
            return f"Playing {song_name}"
        except Exception as e:
            print(f"[Song] pywhatkit failed: {e}")
            # Fallback
    # Fallback: YouTube search page
    query = song_name.replace(" ", "+")
    webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
    return f"Searching {song_name} on YouTube"


# ============================================================
# 10) GEMINI
# ============================================================
def ask_gemini(question):
    if not gemini_client:
        return "AI mode is off."
    prompt = (
        "You are Sunday, a helpful female voice assistant. "
        "Answer in 1-2 short sentences suitable for voice. "
        f"Question: {question}"
    )
    models_to_try = ["gemini-flash-latest", "gemini-3.8-flash"]
    last_error = None
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = gemini_client.models.generate_content(
                    model=model_name, contents=prompt,
                )
                answer = (response.text or "").strip()
                if not answer: continue
                parts = [p.strip() for p in answer.split(".") if p.strip()]
                short = ". ".join(parts[:2])
                if not short.endswith("."): short += "."
                return short
            except Exception as e:
                last_error = str(e)
                err_lower = last_error.lower()
                if any(k in err_lower for k in ("503", "unavailable", "429", "overloaded")):
                    print(f"[AI] {model_name} busy, retrying...")
                    time.sleep(2)
                    continue
                break
    return f"AI error: {last_error}"


# ============================================================
# 11) COMMAND HANDLER
# ============================================================
def process_command(c):
    c = c.lower().strip()
    print(f"[You] {c}")
    words = c.split()

    if is_stop_command(c):
        speak("Okay, stopped.")
        return

    if ("cancel" in c or "cancel karo" in c):
        if "shutdown" in c or "shut down" in c or "restart" in c or "shut" in c:
            speak(system_cancel_shutdown()); return

    if "shutdown" in c or "shut down" in c or "shut computer" in c:
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

    screenshot_phrases = [
        "screenshot", "screen shot", "take a screenshot", "take screenshot",
        "capture screen", "capture the screen", "screenshot lo", "screenshot le",
    ]
    if any(p in c for p in screenshot_phrases):
        speak(system_screenshot()); return

    if any(w in c for w in ("volume", "awaaz", "aawaz", "sound", "vol")):
        if any(w in c for w in ("up", "increase", "badha", "badhao", "tez")):
            speak(volume_up()); return
        if any(w in c for w in ("down", "decrease", "kam", "dheema")):
            speak(volume_down()); return
        if "unmute" in c or "un-mute" in c:
            speak(volume_mute()); return
        if "mute" in c or "chup" in c:
            speak(volume_mute()); return
        for w in words:
            if w.isdigit():
                speak(volume_set(int(w))); return
        speak("Volume up, down, or mute?")
        return

    if "next" in c and ("song" in c or "gaana" in c or "track" in c):
        speak(media_next()); return
    if ("previous" in c or "prev" in c or "pichla" in c) and ("song" in c or "gaana" in c or "track" in c):
        speak(media_prev()); return
    if "pause" in c or "roko" in c or "rok do" in c:
        speak(media_play_pause()); return
    if "resume" in c or ("play" in c and "music" in c):
        speak(media_play_pause()); return
    if "stop music" in c or "music band" in c:
        speak(media_stop()); return

    # Close app
    if any(w in c for w in ("close", "band karo", "band kar", "exit app")):
        for app_name in APPS:
            if app_name in c:
                speak(close_app(app_name)); return
        speak("Which app to close?")
        return

    # Open website
    site_map = [
        ("google maps", "https://maps.google.com", "Opening Google Maps"),
        ("youtube", "https://youtube.com", "Opening YouTube"),
        ("google", "https://google.com", "Opening Google"),
        ("facebook", "https://facebook.com", "Opening Facebook"),
        ("linkedin", "https://linkedin.com", "Opening LinkedIn"),
        ("github", "https://github.com", "Opening GitHub"),
        ("chatgpt", "https://chat.openai.com", "Opening ChatGPT"),
        ("gmail", "https://mail.google.com", "Opening Gmail"),
        ("instagram", "https://instagram.com", "Opening Instagram"),
        ("whatsapp", "https://web.whatsapp.com", "Opening WhatsApp"),
        ("twitter", "https://twitter.com", "Opening Twitter"),
        ("reddit", "https://reddit.com", "Opening Reddit"),
    ]
    open_triggers = ("open", "khol", "launch", "start", "chalu", "dikhao")
    if any(t in c for t in open_triggers):
        for keyword, url, response in site_map:
            if keyword in c:
                speak(response); webbrowser.open(url); return
        # Try app dictionary
        for app_name in APPS:
            if app_name in c:
                speak(open_app_smart(app_name)); return
        # Smart fallback — extract app name after "open"
        for trigger in open_triggers:
            if trigger in c:
                parts = c.split(trigger, 1)
                if len(parts) > 1:
                    app_query = parts[1].strip()
                    if app_query:
                        speak(open_app_smart(app_query))
                        return
        speak("Which app or website to open?")
        return

    # Song / Music — via pywhatkit (no link!)
    music_triggers = ("play", "baja", "sunao", "gaana", "gana", "song", "music")
    if any(t in c for t in music_triggers):
        # Extract song name
        song_query = ""
        for trigger in music_triggers:
            if trigger in c:
                parts = c.split(trigger, 1)
                if len(parts) > 1:
                    song_query = parts[1].strip()
                    # Remove extra words
                    for filler in ("song", "gaana", "music", "please", "the", "a"):
                        song_query = song_query.replace(filler, "").strip()
                    break
        if not song_query:
            # Just "play" — toggle
            speak(media_play_pause())
            return
        speak(play_song(song_query))
        return

    if "time" in c or "samay" in c:
        speak(datetime.now().strftime("It's %I:%M %p")); return
    if "date" in c or "tareekh" in c or "din" in c:
        speak(datetime.now().strftime("Today is %A, %B %d")); return

    # Unknown → Gemini
    if gemini_client:
        speak("Let me think")
        answer = ask_gemini(c)
        speak(answer, allow_stop=True)
    else:
        speak("I didn't understand that")


# ============================================================
# 12) MAIN LOOP
# ============================================================
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Sunday — Smart Assistant (v14)")
    print("=" * 55)
    speak("Sunday is ready. Say wake up Sunday to activate me.")
    print("=" * 55)

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("[Sunday] Calibrating mic...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

    print("\n😴 SLEEP MODE — Say 'Wake up Sunday'")
    print("👋 Say 'Bye Sunday' → sleep")
    print("🛑 Say 'Stop Sunday' → interrupt speech")
    print("🚪 Say 'Goodbye' → exit\n")

    mode = "sleep"

    while True:
        try:
            with mic as source:
                if mode == "sleep":
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=4)
                else:
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)

            try:
                text = recognizer.recognize_google(audio, language="en-IN").lower()
                print(f"[Debug] Heard: '{text}'")
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print(f"[Debug] Google error: {e}")
                continue

            if not text: continue

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