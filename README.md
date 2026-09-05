# GS27QA Brightness Widget

Floating **desktop widget** to control **Gigabyte GS27QA** brightness (no monitor buttons / no USB).

> This is a desktop floating widget (always visible panel), not the Win+W Widgets Board.
> Official Win+W widgets need Visual Studio + C# WinAppSDK + MSIX packaging.

## Why no USB is needed

Brightness uses **DDC/CI** over **HDMI / DisplayPort**. Verified on this PC as `Gigabyte Generic Monitor`.

## Run

```powershell
cd C:\Users\saibhatkar\Desktop\Project-Test\britness-controller-monitor
pip install -r requirements.txt
python app.py
```

Or double-click `run.bat`.

## Widget controls

- **Drag** the title bar to move it on the desktop
- **Slider** + quick presets `20 / 50 / 80 / 100`
- **Pin** keeps it always on top
- **Hide** sends it to the system tray (right-click tray → Show widget / Quit)
- Remembers last position

## Tips

- Direct HDMI/DP cable works best
- If slider does nothing, turn **HDR** off and retry
