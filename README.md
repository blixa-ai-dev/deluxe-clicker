# Deluxe Clicker

> **Made entirely with AI.** Every part of this project — the code and the
> app icon — was created using AI (Claude).

A customizable auto clicker for Windows with an Alpha-Clicker-style layout and
a Discord/Nitro-inspired theme customizer. Alpha Autoclicker link: https://github.com/robiot/AlphaClicker

## Features

- Adjustable click interval (hours / mins / secs / millis) or a random interval
- Left / Right mouse, or a fully custom key / mouse button binding
- Single or double click, repeat N times or until stopped
- Click at the current cursor location or a fixed X/Y position
- Global hotkey to start/stop (customizable)
- Live click counter in the status bar
- Discord/Nitro-inspired theme customizer: Dark / Light / Custom modes, custom
  gradient backgrounds, and an adjustable accent color
- Settings are saved and restored automatically

## Download

Grab the latest pre-built `.exe` from the
[**Releases**](../../releases) page — no need to install Python.

## Build from Source

Requires Python 3.10+.

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run it
python deluxe_clicker.py

# 3. (Optional) Build a standalone .exe
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "Deluxe Clicker" --icon deluxe_clicker.ico --add-data "deluxe_clicker_icon_v2.png;." --collect-all customtkinter deluxe_clicker.py
```

The finished file lands in `dist\Deluxe Clicker.exe`. See [BUILD.md](BUILD.md)
for more detail.

## Disclaimer

Deluxe Clicker is intended for personal, legitimate use — accessibility,
automating your own repetitive tasks, and software testing. Always follow the
terms of service of whatever software you use it with.
