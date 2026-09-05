"""Hardware (DDC/CI) and software brightness control for external monitors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import screen_brightness_control as sbc


@dataclass
class MonitorInfo:
    index: int
    name: str
    brightness: int
    method: str  # "vcp" (hardware) or "software"


class BrightnessController:
    """Prefer DDC/CI (VCP 0x10 over HDMI/DP). Fall back to software dimming."""

    def __init__(self) -> None:
        self._software_level: dict[int, int] = {}
        self._prefer_display: Optional[str] = None
        self._pick_gigabyte_if_present()

    def _pick_gigabyte_if_present(self) -> None:
        for name in sbc.list_monitors():
            if "gigabyte" in name.lower():
                self._prefer_display = name
                return
        monitors = sbc.list_monitors()
        self._prefer_display = monitors[0] if monitors else None

    def list_monitors(self) -> list[MonitorInfo]:
        result: list[MonitorInfo] = []
        names = sbc.list_monitors()
        for i, name in enumerate(names):
            try:
                level = sbc.get_brightness(display=name)[0]
                method = "vcp"
            except Exception:
                level = self._software_level.get(i, 100)
                method = "software"
            result.append(MonitorInfo(index=i, name=name, brightness=level, method=method))
        return result

    def get_target_monitor(self) -> Optional[MonitorInfo]:
        monitors = self.list_monitors()
        if not monitors:
            return None
        if self._prefer_display:
            for m in monitors:
                if m.name == self._prefer_display:
                    return m
        for m in monitors:
            if "gigabyte" in m.name.lower():
                return m
        return monitors[0]

    def set_preferred(self, name: str) -> None:
        self._prefer_display = name

    def get_brightness(self, display: Optional[str] = None) -> int:
        name = display or self._prefer_display
        if not name:
            return 100
        try:
            return int(sbc.get_brightness(display=name)[0])
        except Exception:
            idx = self._index_for(name)
            return self._software_level.get(idx, 100)

    def set_brightness(self, value: int, display: Optional[str] = None) -> tuple[bool, str]:
        """Set brightness 0–100. Returns (ok, mode_used)."""
        value = max(0, min(100, int(value)))
        name = display or self._prefer_display
        if not name:
            return False, "no monitor"

        try:
            sbc.set_brightness(value, display=name)
            return True, "vcp"
        except Exception:
            pass

        # Software fallback: gamma ramp dimming via Windows
        try:
            self._set_software_brightness(name, value)
            return True, "software"
        except Exception as exc:
            return False, str(exc)

    def _index_for(self, name: str) -> int:
        try:
            return sbc.list_monitors().index(name)
        except ValueError:
            return 0

    def _set_software_brightness(self, name: str, value: int) -> None:
        """Approximate brightness by scaling the gamma ramp (not true backlight)."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        # Enumerate monitors and match by index order used by SBC when possible
        monitors: list[int] = []

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        def _callback(hmon, _hdc, _rect, _data):
            monitors.append(hmon)
            return True

        user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_callback), 0)
        idx = self._index_for(name)
        if idx >= len(monitors):
            idx = 0
        hmon = monitors[idx]

        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        hdc = user32.CreateDCW(info.szDevice, info.szDevice, None, None)
        if not hdc:
            raise RuntimeError("CreateDCW failed")

        try:
            # WORD ramp[3][256]
            Ramp = (wintypes.WORD * 256) * 3
            ramp = Ramp()
            scale = value / 100.0
            for i in range(256):
                v = min(65535, int(i * 256 * scale))
                ramp[0][i] = ramp[1][i] = ramp[2][i] = v
            if not gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)):
                raise RuntimeError("SetDeviceGammaRamp failed")
            self._software_level[idx] = value
        finally:
            user32.DeleteDC(hdc)
