# GS27QA Brightness Widget

Windows tray app to control **Gigabyte GS27QA** brightness without using the monitor buttons or Gigabyte Control Center.

## Why this works without USB

Your GS27QA has no USB port. Brightness is sent with **DDC/CI** over the **HDMI or DisplayPort** cable (same path Gigabyte OSD Sidekick uses). This was verified on your PC: the monitor appears as `Gigabyte Generic Monitor` and accepts VCP brightness.

## Run

```powershell
cd C:\Users\saibhatkar\Desktop\Project-Test\britness-controller-monitor
pip install -r requirements.txt
python app.py
```

Or double-click `run.bat`.

## Features

- System tray icon — click **Open brightness** for the slider
- Presets: Night 20%, Desk 50%, Bright 80%, Max 100%
- Keyboard while the window is focused: `Ctrl+Shift+Up` / `Ctrl+Shift+Down`
- Prefers the Gigabyte display if multiple monitors are connected
- Falls back to software gamma dimming if DDC/CI fails (e.g. HDR lock)

## Tips

- Use a direct HDMI/DP cable (not a dock that strips DDC)
- If brightness does not change, turn **HDR** off temporarily and retry
- Keep Gigabyte Control Center closed if it fights for control of the same settings
