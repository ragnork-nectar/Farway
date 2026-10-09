"""
Sunday HUD v2 — Arc Reactor Overlay
Runs in its own process to avoid Tkinter threading issues.
Reads state from temp/hud_state.txt.
"""

import tkinter as tk
import math
import time
import os
from pathlib import Path


class SundayHUD:
    """Floating arc reactor HUD — Iron Man style."""

    def __init__(self, size=220, position="bottom-right"):
        self.size = size
        self.position = position

        self.root = tk.Tk()
        self.root.title("Sunday HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        self.root.attributes("-alpha", 0.95)

        # Position on screen
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        margin = 20

        if position == "bottom-right":
            x = screen_w - size - margin
            y = screen_h - size - margin - 50
        elif position == "bottom-left":
            x = margin
            y = screen_h - size - margin - 50
        elif position == "top-right":
            x = screen_w - size - margin
            y = margin
        elif position == "top-left":
            x = margin
            y = margin
        else:
            x = screen_w - size - margin
            y = screen_h - size - margin - 50

        self.root.geometry(f"{size}x{size}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root, width=size, height=size,
            bg="black", highlightthickness=0,
        )
        self.canvas.pack()

        # State
        self.state = "idle"
        self.running = True
        self.angle = 0
        self.pulse = 0
        self.mic_level = 0.3

        self.colors = {
            "idle":      "#ff8c00",
            "listening": "#ffa500",
            "thinking":  "#ff6600",
            "speaking":  "#ffcc00",
        }

        # State file path (for IPC)
        self.state_file = Path(__file__).parent / "temp" / "hud_state.txt"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Start animation
        self.root.after(40, self._animate)

    # ---------- PUBLIC API ----------
    def set_state(self, state):
        if state in self.colors:
            self.state = state

    def set_mic_level(self, level):
        self.mic_level = max(0.0, min(1.0, level))

    def destroy(self):
        self.running = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        """Blocking mainloop — call from main thread of its own process."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.destroy()
        except Exception as e:
            print(f"[HUD] Runtime error: {e}")

    # ---------- DRAWING ----------
    def _draw_reactor(self):
        self.canvas.delete("all")
        cx = self.size / 2
        cy = self.size / 2
        color = self.colors[self.state]

        # Base dim ring
        base_r = self.size * 0.42
        self.canvas.create_oval(
            cx - base_r, cy - base_r, cx + base_r, cy + base_r,
            outline="#3a1a00", width=2,
        )

        # Outer rotating rays (24 rays)
        num_rays = 24
        ray_len_outer = self.size * 0.46
        ray_len_inner = self.size * 0.34

        for i in range(num_rays):
            angle_rad = math.radians((self.angle + i * (360 / num_rays)))
            x1 = cx + ray_len_inner * math.cos(angle_rad)
            y1 = cy + ray_len_inner * math.sin(angle_rad)
            x2 = cx + ray_len_outer * math.cos(angle_rad)
            y2 = cy + ray_len_outer * math.sin(angle_rad)

            w = 3 if i % 2 == 0 else 1
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=w)

        # Inner rotating rays (12 rays, opposite direction)
        num_inner = 12
        ray_len_outer_in = self.size * 0.30
        ray_len_inner_in = self.size * 0.22

        for i in range(num_inner):
            angle_rad = math.radians((-self.angle * 1.5 + i * (360 / num_inner)))
            x1 = cx + ray_len_inner_in * math.cos(angle_rad)
            y1 = cy + ray_len_inner_in * math.sin(angle_rad)
            x2 = cx + ray_len_outer_in * math.cos(angle_rad)
            y2 = cy + ray_len_outer_in * math.sin(angle_rad)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=1)

        # Mid ring
        mid_r = self.size * 0.30
        self.canvas.create_oval(
            cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r,
            outline=color, width=1,
        )

        # Inner ring
        inner_r = self.size * 0.18
        self.canvas.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline=color, width=2,
        )

        # Glowing core (pulsing)
        core_r = self.size * 0.09 + self.pulse * self.size * 0.02

        # Outer glow (layered)
        for i in range(4, 0, -1):
            glow_r = core_r + i * 3
            fade = ["#ffe680", "#ffcc00", "#ffa500", "#ff8c00"][min(i - 1, 3)]
            self.canvas.create_oval(
                cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                fill=fade, outline="",
            )

        # White-hot center
        self.canvas.create_oval(
            cx - core_r, cy - core_r, cx + core_r, cy + core_r,
            fill="#ffffff", outline="",
        )

        # State-specific extras
        if self.state == "listening":
            pulse_r = self.size * 0.42 + self.mic_level * self.size * 0.06
            self.canvas.create_oval(
                cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r,
                outline=color, width=2,
            )

        elif self.state == "thinking":
            for i in range(6):
                dot_angle = math.radians(self.angle * 3 + i * 60)
                dot_r = self.size * 0.44
                dx = cx + dot_r * math.cos(dot_angle)
                dy = cy + dot_r * math.sin(dot_angle)
                self.canvas.create_oval(
                    dx - 3, dy - 3, dx + 3, dy + 3,
                    fill=color, outline="",
                )

        elif self.state == "speaking":
            for i in range(3):
                wave_r = self.size * 0.44 + i * 8 + self.pulse * 4
                if wave_r < self.size * 0.55:
                    self.canvas.create_oval(
                        cx - wave_r, cy - wave_r, cx + wave_r, cy + wave_r,
                        outline=color, width=1,
                    )

    # ---------- ANIMATION LOOP ----------
    def _read_state(self):
        """Read state from file (IPC)."""
        try:
            if self.state_file.exists():
                content = self.state_file.read_text().strip()
                if content and content in self.colors and content != self.state:
                    self.state = content
        except Exception:
            pass

    def _animate(self):
        if not self.running:
            return

        # Read latest state
        self._read_state()

        # Rotation speed
        speed_map = {
            "idle": 0.4,
            "listening": 1.5,
            "thinking": 4.0,
            "speaking": 2.5,
        }
        speed = speed_map.get(self.state, 0.4)
        self.angle = (self.angle + speed) % 360

        # Pulse
        now = time.time()
        if self.state == "idle":
            self.pulse = 0.5 + 0.3 * math.sin(now * 1.5)
        elif self.state == "listening":
            self.pulse = 0.4 + self.mic_level * 0.6
        elif self.state == "thinking":
            self.pulse = 0.6 + 0.4 * math.sin(now * 4)
        else:  # speaking
            self.pulse = 0.7 + 0.3 * math.sin(now * 6)

        self._draw_reactor()
        self.root.after(40, self._animate)


# ---------- STANDALONE TEST ----------
if __name__ == "__main__":
    print("[HUD] Starting standalone test...")
    print("[HUD] Cycle: idle → listening → thinking → speaking")
    print("[HUD] Close window to stop.\n")

    hud = SundayHUD(size=220, position="bottom-right")
    hud.run()