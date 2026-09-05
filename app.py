"""
GS27QA Desktop Widget — floating Windows-style brightness widget.

Compact frameless panel you can place on the desktop (not the Win+W board).
Uses DDC/CI over HDMI/DP — no USB required.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from brightness_backend import BrightnessController

APP_NAME = "Brightness Widget"
ACCENT = "#3DDC84"
BG = "#12141a"
CARD = "#1c1f28"
FG = "#f2f4f8"
MUTED = "#8b93a7"
STATE_FILE = Path(__file__).with_name("widget_state.json")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(data: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _tray_icon(level: int) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    g = max(60, min(255, int(70 + level * 1.8)))
    draw.ellipse([8, 8, 56, 56], fill=(40, g, 100, 255))
    draw.ellipse([22, 18, 38, 34], fill=(255, 255, 255, 100))
    return img


class DesktopWidget(ctk.CTk):
    """Frameless floating widget — drag to move, snap-friendly size."""

    WIDTH = 280
    HEIGHT = 148

    def __init__(self, controller: BrightnessController) -> None:
        super().__init__()
        self.controller = controller
        self._updating = False
        self._drag = {"x": 0, "y": 0}
        self._always_on_top = True
        self.icon: pystray.Icon | None = None

        ctk.set_appearance_mode("dark")

        self.title(APP_NAME)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.overrideredirect(True)  # frameless = widget look
        self.attributes("-topmost", True)
        self.configure(fg_color=BG)
        self.attributes("-alpha", 0.96)

        # Rounded outer card
        self.card = ctk.CTkFrame(
            self,
            fg_color=CARD,
            corner_radius=18,
            border_width=1,
            border_color="#2a2f3a",
        )
        self.card.pack(fill="both", expand=True, padx=4, pady=4)

        # Drag handle / title row
        header = ctk.CTkFrame(self.card, fg_color="transparent", height=28)
        header.pack(fill="x", padx=14, pady=(12, 0))
        header.pack_propagate(False)

        self.title_lbl = ctk.CTkLabel(
            header,
            text="Brightness",
            font=ctk.CTkFont(family="Segoe UI Semibold", size=14),
            text_color=FG,
            anchor="w",
        )
        self.title_lbl.pack(side="left")

        self.pin_btn = ctk.CTkButton(
            header,
            text="Pin",
            width=36,
            height=24,
            fg_color="transparent",
            hover_color="#2a2f3a",
            text_color=ACCENT,
            font=ctk.CTkFont(size=11),
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side="right", padx=(4, 0))

        self.close_btn = ctk.CTkButton(
            header,
            text="Hide",
            width=40,
            height=24,
            fg_color="transparent",
            hover_color="#3a2030",
            text_color=MUTED,
            font=ctk.CTkFont(size=11),
            command=self._hide_to_tray,
        )
        self.close_btn.pack(side="right")

        for w in (header, self.title_lbl):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        self.monitor_lbl = ctk.CTkLabel(
            self.card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=MUTED,
            anchor="w",
        )
        self.monitor_lbl.pack(fill="x", padx=14, pady=(2, 6))

        mid = ctk.CTkFrame(self.card, fg_color="transparent")
        mid.pack(fill="x", padx=14)

        self.value_lbl = ctk.CTkLabel(
            mid,
            text="100%",
            width=54,
            font=ctk.CTkFont(family="Segoe UI Semibold", size=20),
            text_color=ACCENT,
        )
        self.value_lbl.pack(side="right")

        self.slider = ctk.CTkSlider(
            mid,
            from_=0,
            to=100,
            number_of_steps=100,
            command=self._on_slide,
            progress_color=ACCENT,
            button_color=ACCENT,
            button_hover_color="#5aef9a",
            fg_color="#2a2f3a",
            height=16,
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=(0, 8))

        presets = ctk.CTkFrame(self.card, fg_color="transparent")
        presets.pack(fill="x", padx=12, pady=(10, 10))

        for text, val in (("20", 20), ("50", 50), ("80", 80), ("100", 100)):
            b = ctk.CTkButton(
                presets,
                text=text,
                width=56,
                height=26,
                corner_radius=8,
                fg_color="#262b36",
                hover_color="#323846",
                text_color=FG,
                font=ctk.CTkFont(size=12),
                command=lambda v=val: self._set_value(v),
            )
            b.pack(side="left", padx=3, expand=True)

        self.bind("<Escape>", lambda _e: self._hide_to_tray())
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self._restore_position()
        self.refresh()
        self.after(2000, self._poll_refresh)

    def _start_drag(self, event) -> None:
        self._drag["x"] = event.x_root - self.winfo_x()
        self._drag["y"] = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        x = event.x_root - self._drag["x"]
        y = event.y_root - self._drag["y"]
        self.geometry(f"+{x}+{y}")

    def _toggle_pin(self) -> None:
        self._always_on_top = not self._always_on_top
        self.attributes("-topmost", self._always_on_top)
        self.pin_btn.configure(text_color=ACCENT if self._always_on_top else MUTED)

    def _restore_position(self) -> None:
        state = _load_state()
        x, y = state.get("x"), state.get("y")
        if isinstance(x, int) and isinstance(y, int):
            self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        else:
            # Bottom-right-ish default
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(
                f"{self.WIDTH}x{self.HEIGHT}+{sw - self.WIDTH - 40}+{sh - self.HEIGHT - 80}"
            )

    def _persist_position(self) -> None:
        _save_state({"x": self.winfo_x(), "y": self.winfo_y()})

    def refresh(self) -> None:
        mon = self.controller.get_target_monitor()
        if not mon:
            self.monitor_lbl.configure(text="No monitor found")
            return
        short = mon.name
        if len(short) > 34:
            short = short[:31] + "…"
        mode = "DDC/CI" if mon.method == "vcp" else "Software"
        self.monitor_lbl.configure(text=f"{short}  ·  {mode}")
        self._updating = True
        self.slider.set(mon.brightness)
        self.value_lbl.configure(text=f"{mon.brightness}%")
        self._updating = False
        if self.icon:
            self.icon.icon = _tray_icon(mon.brightness)

    def _poll_refresh(self) -> None:
        # Keep in sync if GCC / OSD changes brightness
        try:
            self.refresh()
        finally:
            self.after(3000, self._poll_refresh)

    def _on_slide(self, value: float) -> None:
        if self._updating:
            return
        level = int(round(value))
        self.value_lbl.configure(text=f"{level}%")
        self._apply(level)

    def _set_value(self, value: int) -> None:
        self._updating = True
        self.slider.set(value)
        self.value_lbl.configure(text=f"{value}%")
        self._updating = False
        self._apply(value)

    def _apply(self, value: int) -> None:
        ok, mode = self.controller.set_brightness(value)
        if ok:
            mon = self.controller.get_target_monitor()
            name = mon.name if mon else "Monitor"
            if len(name) > 34:
                name = name[:31] + "…"
            label = "DDC/CI" if mode == "vcp" else "Software"
            self.monitor_lbl.configure(text=f"{name}  ·  {label}")
        if self.icon:
            self.icon.icon = _tray_icon(value)

    def _hide_to_tray(self) -> None:
        self._persist_position()
        self.withdraw()

    def show_widget(self) -> None:
        self.deiconify()
        self.lift()
        if self._always_on_top:
            self.attributes("-topmost", True)
        self.refresh()


class App:
    def __init__(self) -> None:
        self.controller = BrightnessController()
        self.widget = DesktopWidget(self.controller)

    def run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Show widget", self._show, default=True),
            pystray.MenuItem("Night 20%", lambda: self._preset(20)),
            pystray.MenuItem("Desk 50%", lambda: self._preset(50)),
            pystray.MenuItem("Bright 80%", lambda: self._preset(80)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        level = self.controller.get_brightness()
        icon = pystray.Icon(APP_NAME, _tray_icon(level), APP_NAME, menu)
        self.widget.icon = icon

        threading.Thread(target=icon.run, daemon=True).start()
        self.widget.mainloop()

    def _show(self, _icon=None, _item=None) -> None:
        self.widget.after(0, self.widget.show_widget)

    def _preset(self, value: int) -> None:
        def go():
            self.controller.set_brightness(value)
            self.widget.refresh()

        self.widget.after(0, go)

    def _quit(self, _icon=None, _item=None) -> None:
        self.widget._persist_position()
        if self.widget.icon:
            self.widget.icon.stop()
        self.widget.after(0, self.widget.destroy)


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
