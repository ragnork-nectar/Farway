"""
HUD Controller — runs Sunday HUD in a SEPARATE PROCESS.
Uses file-based IPC to communicate state.
Avoids Tkinter threading issues completely.
"""

import multiprocessing
import os
from pathlib import Path


def _hud_process():
    """Entry point for the HUD subprocess."""
    try:
        from hud import SundayHUD
        hud = SundayHUD(size=220, position="bottom-right")
        hud.run()
    except Exception as e:
        print(f"[HUD Process] Fatal: {e}")


class HUDController:
    """Manages HUD subprocess + state file."""

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.process = None

        root_dir = Path(__file__).parent.resolve()
        temp_dir = root_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        self.state_file = temp_dir / "hud_state.txt"

        if not enabled:
            print("[HUD] Disabled")
            return

        try:
            # Initial state
            self._write_state("idle")

            # Start HUD process
            self.process = multiprocessing.Process(
                target=_hud_process,
                daemon=True,
            )
            self.process.start()
            print("[HUD] Started in separate process")

        except Exception as e:
            print(f"[HUD] Failed to start: {e}")
            self.enabled = False

    def _write_state(self, state):
        try:
            self.state_file.write_text(state)
        except Exception:
            pass

    def set_state(self, state):
        if not self.enabled:
            return
        self._write_state(state)

    def set_mic_level(self, level):
        pass

    def stop(self):
        if self.process and self.process.is_alive():
            try:
                self.process.terminate()
                self.process.join(timeout=2)
            except Exception:
                pass


hud = None


def init_hud(enabled=True):
    global hud
    hud = HUDController(enabled=enabled)
    return hud