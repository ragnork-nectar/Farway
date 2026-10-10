"""
HUD Controller — Manages small (Tkinter) + fullscreen (Web) HUDs.
Supports hunter mode (red palette).
"""

import sys
import multiprocessing
import traceback
from pathlib import Path


# ============================================================
# PATHS
# ============================================================
ROOT_DIR = Path(__file__).parent.resolve()


# ============================================================
# SMALL HUD PROCESS
# ============================================================
def _small_hud_process():
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from hud import SundayHUD
        hud = SundayHUD(size=220, position="bottom-right")
        hud.run()
    except Exception as e:
        print(f"[Small HUD] Fatal: {e}")
        traceback.print_exc()


# ============================================================
# FULLSCREEN HUD PROCESS
# ============================================================
def _fullscreen_hud_process():
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        import threading
        from hud_web import run_server, run_hud_window

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        run_hud_window()
    except Exception as e:
        print(f"[Fullscreen HUD] Fatal: {e}")
        traceback.print_exc()


# ============================================================
# HUD CONTROLLER
# ============================================================
class HUDController:
    """Manages both small + fullscreen HUDs via separate processes."""

    def __init__(self, enabled=True, fullscreen=True):
        self.enabled = enabled
        self.fullscreen_enabled = fullscreen
        self.small_process = None
        self.big_process = None

        # Temp folder in project root
        self.temp_dir = ROOT_DIR / "temp"
        self.temp_dir.mkdir(exist_ok=True)

        # State files
        self.state_file = self.temp_dir / "hud_state.txt"
        self.full_state_file = self.temp_dir / "hud_fullscreen_state.txt"
        self.full_text_file = self.temp_dir / "hud_fullscreen_text.txt"
        self.playing_file = self.temp_dir / "hud_now_playing.txt"
        self.visible_file = self.temp_dir / "hud_visible.txt"
        self.palette_file = self.temp_dir / "hud_palette.txt"
        self.level_file = self.temp_dir / "hud_level.txt"

        if not enabled:
            print("[HUD] Disabled")
            return

        try:
            # Initial states
            self._write(self.state_file, "idle")
            self._write(self.full_state_file, "idle")
            self._write(self.full_text_file, "")
            self._write(self.playing_file, "")
            self._write(self.visible_file, "hide")
            self._write(self.palette_file, "cyan")

            # Start small HUD
            self.small_process = multiprocessing.Process(
                target=_small_hud_process,
                daemon=True,
                name="SundaySmallHUD",
            )
            self.small_process.start()
            print("[HUD] Small arc reactor started (bottom-right)")

            # Start fullscreen HUD
            if self.fullscreen_enabled:
                self.big_process = multiprocessing.Process(
                    target=_fullscreen_hud_process,
                    daemon=True,
                    name="SundayFullscreenHUD",
                )
                self.big_process.start()
                print("[HUD] Fullscreen Cosmos Orb started (hidden)")

        except Exception as e:
            print(f"[HUD] Failed to start: {e}")
            traceback.print_exc()
            self.enabled = False

    # ---------- INTERNAL ----------
    def _write(self, path, content):
        try:
            Path(path).write_text(str(content), encoding="utf-8")
        except Exception as e:
            print(f"[HUD] Write failed ({path}): {e}")

    # ---------- STATE ----------
    def set_state(self, state):
        if not self.enabled:
            return
        self._write(self.state_file, state)

        # Map to fullscreen HUD states (only idle/listening/speaking)
        if state == "thinking":
            self._write(self.full_state_file, "listening")
        elif state == "hunter":
            self._write(self.full_state_file, "listening")
        else:
            self._write(self.full_state_file, state)

    def set_text(self, text):
        if not self.enabled:
            return
        try:
            truncated = (text or "")[:200]
            self._write(self.full_text_file, truncated)
        except Exception:
            pass

    def set_now_playing(self, text):
        if not self.enabled:
            return
        try:
            truncated = (text or "")[:60]
            self._write(self.playing_file, truncated)
        except Exception:
            pass

    def set_mic_level(self, level):
        if not self.enabled:
            return
        try:
            v = max(0.0, min(1.0, float(level)))
            self._write(self.level_file, str(v))
        except Exception:
            pass

    def set_palette(self, palette):
        if not self.enabled:
            return
        if palette not in ("amber", "cyan", "violet", "red"):
            return
        self._write(self.palette_file, palette)

    # ---------- HUNTER MODE ----------
    def enter_hunter(self):
        """Switch HUD to hunter mode (red palette + hunter state)."""
        if not self.enabled:
            return
        self._write(self.state_file, "hunter")
        self._write(self.full_state_file, "listening")
        self._write(self.palette_file, "red")

    def exit_hunter(self):
        """Switch HUD back to normal mode (cyan palette)."""
        if not self.enabled:
            return
        self._write(self.palette_file, "cyan")
        self._write(self.state_file, "idle")
        self._write(self.full_state_file, "idle")

    # ---------- VISIBILITY ----------
    def show_fullscreen(self):
        self._write(self.visible_file, "show")

    def hide_fullscreen(self):
        self._write(self.visible_file, "hide")

    # ---------- SHUTDOWN ----------
    def stop(self):
        for p in (self.small_process, self.big_process):
            if p and p.is_alive():
                try:
                    p.terminate()
                    p.join(timeout=2)
                except Exception:
                    pass


# ============================================================
# GLOBAL SINGLETON
# ============================================================
hud = None


def init_hud(enabled=True, fullscreen=True):
    global hud
    hud = HUDController(enabled=enabled, fullscreen=fullscreen)
    return hud