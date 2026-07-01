# Deluxe Clicker — build guide

## 1. Run it first (to test before building)

```powershell
pip install -r requirements.txt
python deluxe_clicker.py
```

## 2. Build the .exe (Windows)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "Deluxe Clicker" --collect-all customtkinter --icon deluxe_clicker.ico --add-data "deluxe_clicker_icon_v2.png;." deluxe_clicker.py
```

The finished file lands in `dist\Deluxe Clicker.exe`.

Notes:
- `--collect-all customtkinter` is required — without it the .exe crashes on
  launch because CustomTkinter ships theme JSON/asset files it loads at runtime.
- `--windowed` hides the console window. Drop it if you want to see errors.
- `--icon deluxe_clicker.ico` embeds the app icon in the .exe. The `.ico` is
  generated from `deluxe_clicker_icon_v2.png` with Pillow (sizes 16/32/48/64/
  128/256):
  ```powershell
  python -c "from PIL import Image; Image.open('deluxe_clicker_icon_v2.png').convert('RGBA').save('deluxe_clicker.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
  ```
- `--add-data "deluxe_clicker_icon_v2.png;."` bundles the PNG so the running
  window can set its taskbar/title-bar icon via `wm_iconphoto`.
- Settings are saved to `deluxe_settings.json` next to the .exe on close and
  restored on launch.

## 3. Feature map (vs. your screenshots)

| Alpha Clicker control          | Deluxe Clicker             |
|--------------------------------|----------------------------|
| Hours / Mins / Secs / Millis   | ✅ fixed interval row       |
| Random Click Interval Between  | ✅ random radio + lo/hi     |
| Mouse Button (L/R/M)           | ✅ dropdown                 |
| Repeat N Times                 | ✅ radio + count            |
| Repeat Until Stopped           | ✅ radio                    |
| Click type Single/Double       | ✅ dropdown                 |
| Current Location / Get X,Y     | ✅ radios + Get button      |
| Start / Stop (F6)              | ✅ with global hotkey       |
| Change Hotkey                  | ✅ press-any-key capture    |
| Window Settings                | ✅ "Customise Theme"         |

The **Customise Theme** button opens the Discord/Nitro-style panel:
dark/light toggle, saturation-value gradient, hue slider, hex entry, and an
**Apply Accent** button that recolors every radio button live.

## 4. Things you may want Claude Code to add next
- Save/load the chosen accent + settings to a config file
- Multiple saved accent swatches (the "Add Colour" row in Discord)
- A small click counter in the status bar
- Tray icon so it keeps running minimized
