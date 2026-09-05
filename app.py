"""
GS27QA Brightness Widget — system tray + floating slider.

Uses DDC/CI over HDMI/DisplayPort (no USB). Falls back to software gamma
dimming if the monitor rejects VCP brightness.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from brightness_backend import BrightnessController


APP_NAME = "GS27QA Brightness"
ACCENT = "#00A651"  # Gigabyte-ish green
BG = "#1a1a1a"
FG = "#f0f0f0"


def _make_tray_icon(level: int) -> Image.Image:
    """Simple sun/circle icon tinted by brightness level."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    brightness = max(40, min(255, int(80 + level * 1.75)))
    color = (0, brightness, int(brightness * 0.55), 255)
    margin = 10
    draw.ellipse([margin, margin, size - margin, size - margin], fill=color)
    # inner highlight
    draw.ellipse([22, 18, 38, 34], fill=(255, 255, 255, 90))
    return img


class BrightnessWindow(ctk.CTk):
    def __init__(self, controller: BrightnessController, on_close_to_tray) -> None:
        super().__init__()
        self.controller = controller
        self.on_close_to_tray = on_close_to_tray
        self._drag_offset = (0, 0)
        self._updating = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title(APP_NAME)
        self.geometry("320x170")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=BG)

        # Frameless-ish compact panel
        self.overrideredirect(False)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))

        self.title_label = ctk.CTkLabel(
            header,
            text="Monitor Brightness",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=FG,
        )
        self.title_label.pack(side="left")

        self.mode_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        self.mode_label.pack(side="right")

        self.monitor_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
            anchor="w",
        )
        self.monitor_label.pack(fill="x", padx=16, pady=(0, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16)

        self.value_label = ctk.CTkLabel(
            row,
            text="100%",
            width=52,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=ACCENT,
        )
        self.value_label.pack(side="right")

        self.slider = ctk.CTkSlider(
            row,
            from_=0,
            to=100,
            number_of_steps=100,
            command=self._on_slide,
            progress_color=ACCENT,
            button_color=ACCENT,
            button_hover_color="#00c45f",
            height=18,
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        presets = ctk.CTkFrame(self, fg_color="transparent")
        presets.pack(fill="x", padx=16, pady=(12, 8))

        for label, val in (("Night", 20), ("Desk", 50), ("Bright", 80), ("Max", 100)):
            btn = ctk.CTkButton(
                presets,
                text=label,
                width=68,
                height=28,
                fg_color="#2a2a2a",
                hover_color="#333333",
                text_color=FG,
                command=lambda v=val: self._set_value(v),
            )
            btn.pack(side="left", padx=(0, 6))

        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.bind("<Escape>", lambda _e: self._hide_to_tray())

        self.refresh()

    def refresh(self) -> None:
        mon = self.controller.get_target_monitor()
        if not mon:
            self.monitor_label.configure(text="No monitor detected")
            return
        self.monitor_label.configure(text=mon.name)
        mode = "Hardware (DDC/CI)" if mon.method == "vcp" else "Software dim"
        self.mode_label.configure(text=mode)
        self._updating = True
        self.slider.set(mon.brightness)
        self.value_label.configure(text=f"{mon.brightness}%")
        self._updating = False

    def _on_slide(self, value: float) -> None:
        if self._updating:
            return
        level = int(round(value))
        self.value_label.configure(text=f"{level}%")
        self._apply(level)

    def _set_value(self, value: int) -> None:
        self._updating = True
        self.slider.set(value)
        self.value_label.configure(text=f"{value}%")
        self._updating = False
        self._apply(value)

    def _apply(self, value: int) -> None:
        ok, mode = self.controller.set_brightness(value)
        if ok:
            label = "Hardware (DDC/CI)" if mode == "vcp" else "Software dim"
            self.mode_label.configure(text=label)
        else:
            self.mode_label.configure(text=f"Failed: {mode}")

    def _hide_to_tray(self) -> None:
        self.withdraw()
        if self.on_close_to_tray:
            self.on_close_to_tray()

    def show_near_cursor(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.refresh()


class App:
    def __init__(self) -> None:
        self.controller = BrightnessController()
        self.window: BrightnessWindow | None = None
        self.icon: pystray.Icon | None = None
        self._root_ready = threading.Event()

    def run(self) -> None:
        # Tk must live on main thread on Windows
        self.window = BrightnessWindow(self.controller, on_close_to_tray=None)
        self.window.withdraw()

        level = self.controller.get_brightness()
        menu = pystray.Menu(
            pystray.MenuItem("Open brightness", self._show_window, default=True),
            pystray.MenuItem("Night 20%", lambda: self._preset(20)),
            pystray.MenuItem("Desk 50%", lambda: self._preset(50)),
            pystray.MenuItem("Bright 80%", lambda: self._preset(80)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        self.icon = pystray.Icon(
            APP_NAME,
            _make_tray_icon(level),
            APP_NAME,
            menu,
        )

        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        # Hotkeys: Ctrl+Shift+Up / Down
        self.window.bind_all("<Control-Shift-Up>", lambda _e: self._nudge(5))
        self.window.bind_all("<Control-Shift-Down>", lambda _e: self._nudge(-5))

        self.window.after(400, self._show_window)
        self.window.mainloop()

    def _show_window(self, _icon=None, _item=None) -> None:
        if self.window:
            self.window.after(0, self.window.show_near_cursor)

    def _preset(self, value: int) -> None:
        def apply():
            self.controller.set_brightness(value)
            if self.window:
                self.window.refresh()
            if self.icon:
                self.icon.icon = _make_tray_icon(value)

        if self.window:
            self.window.after(0, apply)

    def _nudge(self, delta: int) -> None:
        current = self.controller.get_brightness()
        self.controller.set_brightness(current + delta)
        if self.window:
            self.window.refresh()
        if self.icon:
            self.icon.icon = _make_tray_icon(self.controller.get_brightness())

    def _quit(self, _icon=None, _item=None) -> None:
        if self.icon:
            self.icon.stop()
        if self.window:
            self.window.after(0, self.window.destroy)


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
