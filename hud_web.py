"""
Sunday Web HUD — Cosmos Orb HTML + state API.
Flask server + pywebview fullscreen window.
Supports palettes: amber, cyan, violet, red (hunter mode).
Starts hidden; shows on wake word only.
"""

import threading
import time
from pathlib import Path
from flask import Flask, send_from_directory, jsonify

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

# Root is the project folder
ROOT_DIR = Path(__file__).parent.resolve()
TEMP_DIR = ROOT_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

STATE_FILE = TEMP_DIR / "hud_fullscreen_state.txt"
TEXT_FILE = TEMP_DIR / "hud_fullscreen_text.txt"
PALETTE_FILE = TEMP_DIR / "hud_palette.txt"
LEVEL_FILE = TEMP_DIR / "hud_level.txt"
VISIBLE_FILE = TEMP_DIR / "hud_visible.txt"

# Valid palettes
VALID_PALETTES = ("amber", "cyan", "violet", "red")

app = Flask(__name__, static_folder=str(ROOT_DIR))


@app.route("/")
def index():
    return send_from_directory(str(ROOT_DIR), "sunday_hud.html")


@app.route("/state")
def get_state():
    state = "idle"
    palette = "amber"
    level = None
    text = ""

    try:
        if STATE_FILE.exists():
            s = STATE_FILE.read_text(encoding="utf-8").strip()
            if s in ("idle", "listening", "speaking"):
                state = s

        if PALETTE_FILE.exists():
            p = PALETTE_FILE.read_text(encoding="utf-8").strip()
            if p in VALID_PALETTES:
                palette = p

        if LEVEL_FILE.exists():
            try:
                level = float(LEVEL_FILE.read_text(encoding="utf-8").strip())
                level = max(0.0, min(1.0, level))
            except Exception:
                level = None

        if TEXT_FILE.exists():
            text = TEXT_FILE.read_text(encoding="utf-8").strip()[:200]
    except Exception:
        pass

    # System stats
    cpu = 0
    ram = 0
    if PSUTIL_OK:
        try:
            cpu = int(psutil.cpu_percent(interval=None))
            ram = int(psutil.virtual_memory().percent)
        except Exception:
            cpu = 0
            ram = 0

    return jsonify({
        "state": state,
        "palette": palette,
        "level": level,
        "text": text,
        "cpu": cpu,
        "ram": ram,
    })


def run_server():
    """Run Flask server quietly on port 5050."""
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(
        host="127.0.0.1",
        port=5050,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def run_hud_window():
    """Open pywebview window. Start small + offscreen, go fullscreen when told."""
    import webview

    # Wait for Flask to boot
    time.sleep(1.5)

    window = None
    try:
        window = webview.create_window(
            "Sunday HUD",
            "http://127.0.0.1:5050",
            width=400,
            height=300,
            x=-3000,
            y=-3000,
            frameless=True,
            on_top=True,
            fullscreen=False,
            easy_drag=False,
            hidden=True,
        )
    except Exception as e:
        print(f"[HUD] create_window failed: {e}")
        return

    # Watcher thread — polls hud_visible.txt to show/hide
    def watcher():
        last = "hide"
        while True:
            try:
                if VISIBLE_FILE.exists():
                    v = VISIBLE_FILE.read_text(encoding="utf-8").strip()
                    if v != last:
                        last = v
                        if v == "show":
                            try:
                                window.show()
                                time.sleep(0.15)
                                window.toggle_fullscreen()
                                print("[HUD] Fullscreen shown")
                            except Exception as e:
                                print(f"[HUD] show failed: {e}")
                        elif v == "hide":
                            try:
                                window.toggle_fullscreen()
                                time.sleep(0.1)
                                window.hide()
                                print("[HUD] Fullscreen hidden")
                            except Exception as e:
                                print(f"[HUD] hide failed: {e}")
            except Exception as e:
                print(f"[HUD watcher] {e}")
            time.sleep(0.2)

    threading.Thread(target=watcher, daemon=True).start()

    try:
        webview.start()
    except Exception as e:
        print(f"[HUD] webview.start failed: {e}")


if __name__ == "__main__":
    print("[HUD] Starting Sunday Cosmos Orb...")
    threading.Thread(target=run_server, daemon=True).start()
    run_hud_window()