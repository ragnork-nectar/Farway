"""
Sunday v12 — Full PC Control Assistant (with Stop Command)
========================================
NEW:
- "Stop Sunday" — interrupts speech mid-sentence
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
# 1) WAKE / SLEEP / EXIT / STOP CHECKS
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
    """Detect 'stop sunday', 'chup', 'stop talking', etc."""
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
        print("[Setup] Gemini AI ready (online smart mode)")
    except Exception as e:
        print(f"[Setup] Gemini init failed: {e}")
else:
    print("[Setup] No GEMINI_API_KEY — offline-only mode")


# ============================================================
# 3) MUSIC LIBRARY
# ============================================================
music = {
    "stealth": "https://www.youtube.com/watch?v=U47Tr9BB_wE",
    "march": "https://www.youtube.com/watch?v=Xqeq4b5u_Xw",
    "skyfall": "https://www.youtube.com/watch?v=DeumyOzKqgI",
    "wolf": "https://www.youtube.com/watch?v=ThCH0U6aJpU",
    "arzu": "https://www.youtube.com/results?search_query=arzu+song",
    "arzi": "https://www.youtube.com/results?search_query=arzu+song",
    "dil lagana": "https://www.youtube.com/results?search_query=dil+lagana+song",
    "sweeter weather": "https://www.youtube.com/results?search_query=sweeter+weather+song",
    "sweet weather": "https://www.youtube.com/results?search_query=sweeter+weather+song",
    "kesariya": "https://www.youtube.com/results?search_query=kesariya+song",
    "tum hi ho": "https://www.youtube.com/results?search_query=tum+hi+ho+song",
    "channa mereya": "https://www.youtube.com/results?search_query=channa+mereya+song",
    "raabta": "https://www.youtube.com/results?search_query=raabta+song",
    "shayad": "https://www.youtube.com/results?search_query=shayad+song",
    "agar tum saath ho": "https://www.youtube.com/results?search_query=agar+tum+saath+ho+song",
    "kabira": "https://www.youtube.com/results?search_query=kabira+song",
    "tum mile": "https://www.youtube.com/results?search_query=tum+mile+song",
    "bekhayali": "https://www.youtube.com/results?search_query=bekhayali+song",
    "tera ban jaunga": "https://www.youtube.com/results?search_query=tera+ban+jaunga+song",
    "hawayein": "https://www.youtube.com/results?search_query=hawayein+song",
    "pehla nasha": "https://www.youtube.com/results?search_query=pehla+nasha+song",
    "tu chahiye": "https://www.youtube.com/results?search_query=tu+chahiye+song",
    "jeene laga hoon": "https://www.youtube.com/results?search_query=jeene+laga+hoon+song",
    "sun raha hai": "https://www.youtube.com/results?search_query=sun+raha+hai+song",
    "main rahoon ya na rahoon": "https://www.youtube.com/results?search_query=main+rahoon+ya+na+rahoon+song",
    "tujhe kitna chahne lage": "https://www.youtube.com/results?search_query=tujhe+kitna+chahne+lage+song",
    "kaun tujhe": "https://www.youtube.com/results?search_query=kaun+tujhe+song",
    "dil diyan gallan": "https://www.youtube.com/results?search_query=dil+diyan+gallan+song",
    "lahyray": "https://www.youtube.com/results?search_query=lahyray+song",
    "tum se hi": "https://www.youtube.com/results?search_query=tum+se+hi+song",
    "o re piya": "https://www.youtube.com/results?search_query=o+re+piya+song",
    "kun faya kun": "https://www.youtube.com/results?search_query=kun+faya+kun+song",
    "ilahi": "https://www.youtube.com/results?search_query=ilahi+song",
    "chaiyya chaiyya": "https://www.youtube.com/results?search_query=chaiyya+chaiyya+song",
    "gerua": "https://www.youtube.com/results?search_query=gerua+song",
    "janam janam": "https://www.youtube.com/results?search_query=janam+janam+song",
    "kal ho naa ho": "https://www.youtube.com/results?search_query=kal+ho+naa+ho+song",
    "kuch kuch hota hai": "https://www.youtube.com/results?search_query=kuch+kuch+hota+hai+song",
    "kabhi kabhi aditi": "https://www.youtube.com/results?search_query=kabhi+kabhi+aditi+song",
    "yeh dooriyan": "https://www.youtube.com/results?search_query=yeh+dooriyan+song",
    "tum tak": "https://www.youtube.com/results?search_query=tum+tak+song",
    "nadaan parindey": "https://www.youtube.com/results?search_query=nadaan+parindey+song",
    "sadda haq": "https://www.youtube.com/results?search_query=sadda+haq+song",
    "choo lo": "https://www.youtube.com/results?search_query=choo+lo+song",
    "dil dhadakne do": "https://www.youtube.com/results?search_query=dil+dhadakne+do+song",
    "patakha guddi": "https://www.youtube.com/results?search_query=patakha+guddi+song",
    "love you zindagi": "https://www.youtube.com/results?search_query=love+you+zindagi+song",
    "kaise hua": "https://www.youtube.com/results?search_query=kaise+hua+song",
    "tum ho toh": "https://www.youtube.com/results?search_query=tum+ho+toh+song",
}


# ============================================================
# 4) APP LIBRARY
# ============================================================
APPS = {
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "firefox": "firefox", "brave": "brave",
    "vscode": "code", "vs code": "code", "visual studio code": "code",
    "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "cmd": "cmd", "command prompt": "cmd",
    "powershell": "powershell", "terminal": "wt",
    "task manager": "taskmgr", "explorer": "explorer",
    "file explorer": "explorer", "settings": "ms-settings:",
    "control panel": "control", "spotify": "spotify", "vlc": "vlc",
    "discord": "discord", "telegram": "telegram", "whatsapp": "whatsapp",
    "zoom": "zoom", "teams": "teams", "steam": "steam",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:", "clock": "ms-clock:",
    "calendar": "outlookcal:", "store": "ms-windows-store:",
}


# ============================================================
# 5) VOICE (Female) — with interrupt support
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

if not female_set:
    print("[Setup] No female voice found")

# Global flag for stop command
STOP_FLAG = threading.Event()


def speak(text, allow_stop=False):
    """Speak. If allow_stop=True, background listener can interrupt."""
    if not text:
        return
    print(f"[Sunday] {text}")

    if not allow_stop:
        # Simple blocking speak (no interrupt)
        try:
            speaker.Speak(text)
        except Exception as ex:
            print(f"[TTS Error] {ex}")
        return

    # Interruptible speak
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
        """Background listener — checks for stop command."""
        try:
            stop_recognizer = sr.Recognizer()
            stop_mic = sr.Microphone()
            with stop_mic as source:
                stop_recognizer.adjust_for_ambient_noise(source, duration=0.2)
                while not speech_done.is_set():
                    try:
                        audio = stop_recognizer.listen(
                            source, timeout=2, phrase_time_limit=3
                        )
                        try:
                            text_heard = stop_recognizer.recognize_google(
                                audio, language="en-IN"
                            ).lower()
                            print(f"[Stop-listener] Heard: '{text_heard}'")
                            if is_stop_command(text_heard):
                                print("[Sunday] Stop command detected!")
                                STOP_FLAG.set()
                                try:
                                    speaker.Speak("", 3)  # SVSFPurgeBeforeSpeak
                                except Exception:
                                    pass
                                break
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError:
                            continue
                    except sr.WaitTimeoutError:
                        continue
        except Exception as e:
            print(f"[Stop-listener] Error: {e}")

    t_speak = threading.Thread(target=_speak_thread, daemon=True)
    t_listener = threading.Thread(target=_listener_thread, daemon=True)
    t_speak.start()
    t_listener.start()

    # Wait for speech to finish (or stop flag)
    t_speak.join(timeout=30)
    speech_done.set()

    if STOP_FLAG.is_set():
        print("[Sunday] (speech interrupted)")


# ============================================================
# 6) VOLUME CONTROL
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
    if not vol:
        return "Volume control not available"
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new = min(1.0, current + step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume up to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_down(step=10):
    vol = get_volume_interface()
    if not vol:
        return "Volume control not available"
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new = max(0.0, current - step / 100)
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume down to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_set(percent):
    vol = get_volume_interface()
    if not vol:
        return "Volume control not available"
    try:
        new = max(0.0, min(1.0, percent / 100))
        vol.SetMasterVolumeLevelScalar(new, None)
        return f"Volume set to {int(new * 100)} percent"
    except Exception as e:
        return f"Volume error: {e}"


def volume_mute():
    vol = get_volume_interface()
    if not vol:
        return "Volume control not available"
    try:
        is_muted = vol.GetMute()
        vol.SetMute(not is_muted, None)
        return "Muted" if not is_muted else "Unmuted"
    except Exception as e:
        return f"Volume error: {e}"


# ============================================================
# 7) APP CONTROL
# ============================================================
def open_app(app_name):
    key = app_name.lower().strip()
    target = APPS.get(key, key)
    try:
        subprocess.Popen(f'start "" "{target}"', shell=True)
        return f"Opening {app_name}"
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
# 8) MEDIA CONTROL
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
# 9) SYSTEM CONTROL
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
                if not answer:
                    continue
                parts = [p.strip() for p in answer.split(".") if p.strip()]
                short = ". ".join(parts[:2])
                if not short.endswith("."):
                    short += "."
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

    # ---- STOP (say stop) ----
    if is_stop_command(c):
        speak("Okay, stopped.")
        return

    # ---- CANCEL SHUTDOWN (priority) ----
    if ("cancel" in c or "cancel karo" in c):
        if "shutdown" in c or "shut down" in c or "restart" in c or "shut" in c:
            speak(system_cancel_shutdown())
            return

    # ---- SHUTDOWN ----
    if "shutdown" in c or "shut down" in c or "shut computer" in c:
        delay = 30
        for w in words:
            if w.isdigit():
                delay = int(w)
                break
        speak(system_shutdown(delay))
        return

    # ---- RESTART ----
    if "restart" in c or "reboot" in c:
        delay = 30
        for w in words:
            if w.isdigit():
                delay = int(w)
                break
        speak(system_restart(delay))
        return

    # ---- SLEEP PC ----
    if ("sleep" in c and ("pc" in c or "computer" in c or "laptop" in c)):
        speak(system_sleep_pc())
        return

    # ---- LOCK ----
    if "lock" in c and ("screen" in c or "pc" in c or "computer" in c or "karo" in c):
        speak(system_lock())
        return

    # ---- SCREENSHOT ----
    screenshot_phrases = [
        "screenshot", "screen shot", "take a screenshot", "take screenshot",
        "capture screen", "capture the screen",
        "screenshot lo", "screenshot le",
    ]
    if any(p in c for p in screenshot_phrases):
        speak(system_screenshot())
        return

    # ---- VOLUME ----
    if any(w in c for w in ("volume", "awaaz", "aawaz", "sound", "vol")):
        if any(w in c for w in ("up", "increase", "badha", "badhao", "tez")):
            speak(volume_up())
            return
        if any(w in c for w in ("down", "decrease", "kam", "dheema")):
            speak(volume_down())
            return
        if "unmute" in c or "un-mute" in c:
            speak(volume_mute())
            return
        if "mute" in c or "chup" in c:
            speak(volume_mute())
            return
        for w in words:
            if w.isdigit():
                speak(volume_set(int(w)))
                return
        speak("Volume up, down, or mute?")
        return

    # ---- MEDIA ----
    if "next" in c and ("song" in c or "gaana" in c or "track" in c):
        speak(media_next())
        return
    if ("previous" in c or "prev" in c or "pichla" in c) and ("song" in c or "gaana" in c or "track" in c):
        speak(media_prev())
        return
    if "pause" in c or "roko" in c or "rok do" in c:
        speak(media_play_pause())
        return
    if "resume" in c or ("play" in c and "music" in c):
        speak(media_play_pause())
        return
    if "stop music" in c or "music band" in c:
        speak(media_stop())
        return

    # ---- CLOSE APP ----
    if any(w in c for w in ("close", "band karo", "band kar", "exit app")):
        for app_name in APPS:
            if app_name in c:
                speak(close_app(app_name))
                return
        speak("Which app to close?")
        return

    # ---- OPEN ----
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
                speak(response)
                webbrowser.open(url)
                return
        for app_name in APPS:
            if app_name in c:
                speak(open_app(app_name))
                return
        speak("Which app or website to open?")
        return

    # ---- MUSIC ----
    music_triggers = ("play", "baja", "sunao", "gaana", "gana", "song", "music")
    if any(t in c for t in music_triggers):
        for song_name, url in music.items():
            if song_name in c:
                speak(f"Playing {song_name}")
                webbrowser.open(url)
                return
        words_clean = [w for w in words if w not in music_triggers + ("the", "a", "song", "gaana", "music", "some")]
        for i in range(len(words_clean)):
            for j in range(len(words_clean), i, -1):
                candidate = " ".join(words_clean[i:j])
                if candidate in music:
                    speak(f"Playing {candidate}")
                    webbrowser.open(music[candidate])
                    return
        query = " ".join(words_clean)
        if query:
            speak(f"Searching {query} on YouTube")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
            return
        speak("Please say a song name")
        return

    # ---- TIME / DATE ----
    if "time" in c or "samay" in c:
        speak(datetime.now().strftime("It's %I:%M %p"))
        return
    if "date" in c or "tareekh" in c or "din" in c:
        speak(datetime.now().strftime("Today is %A, %B %d"))
        return

    # ---- UNKNOWN → GEMINI (interruptible) ----
    if gemini_client:
        speak("Let me think")
        answer = ask_gemini(c)
        # Allow stop command for long AI answers
        speak(answer, allow_stop=True)
    else:
        speak("I didn't understand that")


# ============================================================
# 12) MAIN LOOP
# ============================================================
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Sunday — Full PC Control Assistant (v12)")
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