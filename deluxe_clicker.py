"""
Deluxe Clicker
==============
A customizable auto clicker with an Alpha-Clicker-style layout and a
Discord/Nitro-inspired theme customizer.

Tech: CustomTkinter (modern rounded widgets), pynput (clicking + global
hotkey), Pillow (color-picker gradients).

Run:    python deluxe_clicker.py
Build:  see BUILD.md
"""

import colorsys
import json
import os
import random
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk
from PIL import Image, ImageTk
from pynput import mouse, keyboard

ICON_PNG = "deluxe_clicker_icon_v2.png"
SETTINGS_FILE = "deluxe_settings.json"

# --------------------------------------------------------------------------- #
#  Path helpers (work both from source and from a PyInstaller bundle)
# --------------------------------------------------------------------------- #

def app_dir():
    """Directory the .exe (or script) lives in â where settings are written."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """Locate a read-only bundled asset (handles PyInstaller's _MEIPASS)."""
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, name)


def settings_path():
    return os.path.join(app_dir(), SETTINGS_FILE)


# --------------------------------------------------------------------------- #
#  Color helpers
# --------------------------------------------------------------------------- #

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def hex_to_hsv(h):
    r, g, b = (c / 255 for c in hex_to_rgb(h))
    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return rgb_to_hex(r * 255, g * 255, b * 255)


def shade(hex_color, factor):
    """Darken (factor<1) or lighten (factor>1) a hex color for hover states."""
    r, g, b = hex_to_rgb(hex_color)
    if factor < 1:
        r, g, b = (c * factor for c in (r, g, b))
    else:
        r, g, b = (c + (255 - c) * (factor - 1) for c in (r, g, b))
    return rgb_to_hex(min(255, r), min(255, g), min(255, b))


def vertical_gradient(c1, c2, w, h):
    """A top-to-bottom gradient PIL image from c1 to c2."""
    w, h = max(1, int(w)), max(1, int(h))
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / (h - 1) if h > 1 else 0
        px[0, y] = (int(r1 + (r2 - r1) * t),
                    int(g1 + (g2 - g1) * t),
                    int(b1 + (b2 - b1) * t))
    return strip.resize((w, h))


# --------------------------------------------------------------------------- #
#  Click engine (runs on its own thread)
# --------------------------------------------------------------------------- #

class ClickEngine:
    def __init__(self):
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
        self._thread = None
        self._stop = threading.Event()
        self.running = False
        self.count = 0           # live click counter (read by the status bar)

    def start(self, cfg, on_finish):
        if self.running:
            return
        self.running = True
        self.count = 0
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(cfg, on_finish), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _sleep(self, seconds):
        """Interruptible sleep so Stop is responsive."""
        end = time.perf_counter() + seconds
        while not self._stop.is_set() and time.perf_counter() < end:
            time.sleep(min(0.01, end - time.perf_counter()))

    def _do_click(self, cfg, clicks):
        if cfg["button_kind"] == "mouse":
            self.mouse.click(cfg["button_obj"], clicks)
        else:                                   # keyboard key
            key = cfg["button_obj"]
            for _ in range(clicks):
                self.keyboard.press(key)
                self.keyboard.release(key)

    def _run(self, cfg, on_finish):
        clicks = 2 if cfg["click_type"] == "Double" else 1
        try:
            while not self._stop.is_set():
                if cfg["fixed_pos"] and cfg["button_kind"] == "mouse":
                    self.mouse.position = (cfg["x"], cfg["y"])
                self._do_click(cfg, clicks)
                self.count += 1

                if not cfg["repeat_forever"] and self.count >= cfg["repeat_times"]:
                    break

                if cfg["random_interval"]:
                    lo, hi = cfg["rand_lo"], cfg["rand_hi"]
                    interval = random.uniform(min(lo, hi), max(lo, hi))
                else:
                    interval = cfg["interval"]
                self._sleep(max(0.0, interval))
        finally:
            self.running = False
            on_finish()


# --------------------------------------------------------------------------- #
#  Reusable HSV colour picker (SV gradient + hue slider + hex entry)
# --------------------------------------------------------------------------- #

class ColorPicker(ctk.CTkFrame):
    SV_W, SV_H = 224, 120
    HUE_H = 14

    def __init__(self, master, initial, on_change=None, label=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.on_change = on_change
        self.h, self.s, self.v = hex_to_hsv(initial)
        self._sv_img = self._hue_img = None       # keep refs from GC

        if label:
            ctk.CTkLabel(self, text=label, text_color="#b5bac1"
                         ).pack(anchor="w", pady=(2, 2))

        self.sv = tk.Canvas(self, width=self.SV_W, height=self.SV_H,
                            highlightthickness=0, bd=0, cursor="crosshair")
        self.sv.pack()
        self.sv.bind("<Button-1>", self._sv_drag)
        self.sv.bind("<B1-Motion>", self._sv_drag)

        self.hue = tk.Canvas(self, width=self.SV_W, height=self.HUE_H,
                             highlightthickness=0, bd=0,
                             cursor="sb_h_double_arrow")
        self.hue.pack(pady=(6, 6))
        self.hue.bind("<Button-1>", self._hue_drag)
        self.hue.bind("<B1-Motion>", self._hue_drag)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        self.swatch = ctk.CTkLabel(row, text="", width=26, corner_radius=6)
        self.swatch.pack(side="left")
        self.hex_var = tk.StringVar()
        self.hex_entry = ctk.CTkEntry(row, textvariable=self.hex_var)
        self.hex_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.hex_entry.bind("<Return>", self._hex_typed)

        self._redraw_hue()
        self._redraw_sv()

    # -- public -------------------------------------------------------------- #
    def get(self):
        return hsv_to_hex(self.h, self.s, self.v)

    def set_hex(self, hx):
        try:
            self.h, self.s, self.v = hex_to_hsv(hx)
            self._redraw_hue()
            self._redraw_sv()
        except Exception:
            pass

    # -- gradient rendering -------------------------------------------------- #
    def _redraw_sv(self):
        small = (60, 36)                          # render small, upscale smooth
        img = Image.new("RGB", small)
        px = img.load()
        sw, sh = small
        for j in range(sh):
            v = 1 - j / (sh - 1)
            for i in range(sw):
                s = i / (sw - 1)
                r, g, b = colorsys.hsv_to_rgb(self.h, s, v)
                px[i, j] = (int(r * 255), int(g * 255), int(b * 255))
        img = img.resize((self.SV_W, self.SV_H), Image.BILINEAR)
        self._sv_img = ImageTk.PhotoImage(img)
        self.sv.delete("all")
        self.sv.create_image(0, 0, anchor="nw", image=self._sv_img)
        cx, cy = self.s * self.SV_W, (1 - self.v) * self.SV_H
        outline = "#000" if self.v > 0.5 else "#fff"
        self.sv.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                            outline=outline, width=2)
        self._refresh_hex()

    def _redraw_hue(self):
        img = Image.new("RGB", (self.SV_W, self.HUE_H))
        px = img.load()
        for i in range(self.SV_W):
            r, g, b = colorsys.hsv_to_rgb(i / (self.SV_W - 1), 1, 1)
            for j in range(self.HUE_H):
                px[i, j] = (int(r * 255), int(g * 255), int(b * 255))
        self._hue_img = ImageTk.PhotoImage(img)
        self.hue.delete("all")
        self.hue.create_image(0, 0, anchor="nw", image=self._hue_img)
        hx = self.h * self.SV_W
        self.hue.create_rectangle(hx - 2, 0, hx + 2, self.HUE_H,
                                  outline="#fff", width=2)

    # -- interactions -------------------------------------------------------- #
    def _sv_drag(self, e):
        self.s = min(max(e.x / self.SV_W, 0), 1)
        self.v = 1 - min(max(e.y / self.SV_H, 0), 1)
        self._redraw_sv()

    def _hue_drag(self, e):
        self.h = min(max(e.x / self.SV_W, 0), 1)
        self._redraw_hue()
        self._redraw_sv()

    def _hex_typed(self, _):
        try:
            self.h, self.s, self.v = hex_to_hsv(self.hex_var.get().strip())
            self._redraw_hue()
            self._redraw_sv()
        except Exception:
            pass

    def _refresh_hex(self):
        hx = hsv_to_hex(self.h, self.s, self.v)
        self.hex_var.set(hx)
        self.swatch.configure(fg_color=hx)
        if self.on_change:
            self.on_change(hx)


# --------------------------------------------------------------------------- #
#  Theme customizer (Toplevel) â appearance + backgrounds + accent
# --------------------------------------------------------------------------- #

class ThemePicker(ctk.CTkToplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("Customise your theme")
        self.geometry("330x600")
        self.minsize(330, 460)
        self.configure(fg_color="#232428")

        ctk.CTkLabel(self, text="Customise your theme",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=18, pady=(16, 4))

        # Appearance: Dark / Light / Custom ----------------------------------- #
        ctk.CTkLabel(self, text="Appearance", text_color="#b5bac1"
                     ).pack(anchor="w", padx=18, pady=(8, 2))
        self.mode = ctk.CTkSegmentedButton(
            self, values=["Dark", "Light", "Custom"], command=self._mode_change)
        self.mode.set(app.appearance_mode.capitalize())
        self.mode.pack(fill="x", padx=18, pady=(0, 10))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        # Custom backgrounds (shown only in Custom mode) ---------------------- #
        self.bg_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.bg1 = ColorPicker(self.bg_frame, app.bg_color1, label="Background 1")
        self.bg1.pack(fill="x", pady=(0, 10))
        self.bg2 = ColorPicker(self.bg_frame, app.bg_color2, label="Background 2")
        self.bg2.pack(fill="x", pady=(0, 10))
        # Wire live updates only after both pickers exist.
        self.bg1.on_change = lambda c: self.app.apply_background(c, self.bg2.get())
        self.bg2.on_change = lambda c: self.app.apply_background(self.bg1.get(), c)

        # Accent ------------------------------------------------------------- #
        self.accent_label = ctk.CTkLabel(body, text="Accent Colour",
                                         text_color="#b5bac1")
        self.accent_label.pack(anchor="w", pady=(4, 2))
        self.accent_picker = ColorPicker(body, app.accent)
        self.accent_picker.pack(fill="x")

        # Buttons ------------------------------------------------------------- #
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=14, side="bottom")
        ctk.CTkButton(btns, text="Apply Accent",
                      command=self._apply_accent).pack(fill="x")
        ctk.CTkButton(btns, text="Back to Settings", fg_color="#3a3c42",
                      hover_color="#46474d",
                      command=self.destroy).pack(fill="x", pady=(8, 0))

        self._mode_change(self.mode.get())
        self.after(200, self.lift)

    def _mode_change(self, m):
        if m == "Custom":
            self.bg_frame.pack(fill="x", before=self.accent_label)
            self.app.set_appearance("custom")
            self.app.apply_background(self.bg1.get(), self.bg2.get())
        else:
            self.bg_frame.pack_forget()
            self.app.set_appearance(m.lower())

    def _apply_accent(self):
        self.app._apply_accent(self.accent_picker.get())


# --------------------------------------------------------------------------- #
#  Custom "Button" input widget (display box + dropdown + capture modal)
# --------------------------------------------------------------------------- #

class ButtonPicker(ctk.CTkFrame):
    MOUSE_NAMES = {"left": "Left Mouse", "right": "Right Mouse",
                   "middle": "Middle Mouse", "x1": "X1 Mouse", "x2": "X2 Mouse"}

    def __init__(self, master, width=128, command=None):
        super().__init__(master, fg_color="transparent")
        self.command = command
        self.value_kind = "mouse"          # "mouse" or "key"
        self.value = mouse.Button.left
        self.display_text = "Left Mouse"
        self._accent = "#5865F2"
        self._hover = shade(self._accent, 0.85)
        self._menu = None
        self._cap = None
        self._kl = self._ml = None
        self._captured = False

        self.box = ctk.CTkButton(self, text=self.display_text, width=width - 28,
                                 fg_color="#3a3c42", hover_color="#46474d",
                                 anchor="w", command=self._open_menu)
        self.box.pack(side="left")
        self.arrow = ctk.CTkButton(self, text="▼", width=26,
                                   fg_color=self._accent, hover_color=self._hover,
                                   command=self._open_menu)
        self.arrow.pack(side="left", padx=(3, 0))

    # -- accent recolouring (only the dropdown arrow uses the accent) -------- #
    def set_accent(self, color, hover):
        self._accent, self._hover = color, hover
        self.arrow.configure(fg_color=color, hover_color=hover)

    # -- selection state ----------------------------------------------------- #
    def _set(self, kind, value, text, emit=True):
        self.value_kind, self.value, self.display_text = kind, value, text
        self.box.configure(text=text)
        if emit and self.command:
            self.command()

    # -- dropdown menu ------------------------------------------------------- #
    def _open_menu(self):
        if self._menu is not None and self._menu.winfo_exists():
            self._close_menu()
            return
        self._menu = ctk.CTkToplevel(self)
        self._menu.overrideredirect(True)
        self._menu.configure(fg_color="#2b2d31")
        x = self.box.winfo_rootx()
        y = self.box.winfo_rooty() + self.box.winfo_height() + 2
        self._menu.geometry(f"+{x}+{y}")
        items = [
            ("Left Mouse", lambda: self._pick_mouse(mouse.Button.left, "Left Mouse")),
            ("Right Mouse", lambda: self._pick_mouse(mouse.Button.right, "Right Mouse")),
            ("Custom…", self._start_capture),
        ]
        for text, fn in items:
            ctk.CTkButton(self._menu, text=text, fg_color="transparent",
                          hover_color="#3a3c42", anchor="w", corner_radius=0,
                          command=fn).pack(fill="x", padx=2, pady=1)
        self._menu.after(10, self._menu.focus_set)
        self._menu.bind("<FocusOut>",
                        lambda e: self._menu.after(120, self._close_menu))

    def _close_menu(self):
        if self._menu is not None and self._menu.winfo_exists():
            self._menu.destroy()
        self._menu = None

    def _pick_mouse(self, button, text):
        self._close_menu()
        self._set("mouse", button, text)

    # -- "Customâ¦" capture modal -------------------------------------------- #
    def _start_capture(self):
        self._close_menu()
        self._captured = False
        self._cap = ctk.CTkToplevel(self)
        self._cap.title("Capture input")
        self._cap.geometry("280x110")
        self._cap.resizable(False, False)
        self._cap.configure(fg_color="#232428")
        ctk.CTkLabel(self._cap, text="Press any key or mouse button…",
                     font=ctk.CTkFont(size=13)).pack(expand=True, pady=24)
        self._cap.protocol("WM_DELETE_WINDOW", self._cancel_capture)
        self._cap.grab_set()
        self._cap.focus_force()
        # Start global listeners slightly later so the click that opened this
        # modal isn't itself captured.
        self._cap.after(220, self._begin_listening)

    def _begin_listening(self):
        if self._cap is None or not self._cap.winfo_exists():
            return
        self._kl = keyboard.Listener(on_press=self._cap_key)
        self._ml = mouse.Listener(on_click=self._cap_click)
        self._kl.start()
        self._ml.start()

    def _cap_key(self, key):
        if self._captured:
            return False
        self._captured = True
        try:
            ch = key.char
            if not ch:
                raise AttributeError
            name = ch.upper()
        except AttributeError:
            name = str(key).replace("Key.", "").replace("_", " ").title()
        self.after(0, lambda: self._finish_capture("key", key, name))
        return False

    def _cap_click(self, x, y, button, pressed):
        if not pressed or self._captured:
            return
        self._captured = True
        name = self.MOUSE_NAMES.get(button.name, button.name.title() + " Mouse")
        self.after(0, lambda: self._finish_capture("mouse", button, name))
        return False

    def _finish_capture(self, kind, value, name):
        self._stop_listeners()
        if self._cap is not None and self._cap.winfo_exists():
            self._cap.grab_release()
            self._cap.destroy()
        self._cap = None
        self._set(kind, value, name)

    def _cancel_capture(self):
        self._captured = True
        self._stop_listeners()
        if self._cap is not None and self._cap.winfo_exists():
            self._cap.grab_release()
            self._cap.destroy()
        self._cap = None

    def _stop_listeners(self):
        for lst in (self._kl, self._ml):
            try:
                if lst is not None:
                    lst.stop()
            except Exception:
                pass
        self._kl = self._ml = None

    # -- persistence --------------------------------------------------------- #
    def to_dict(self):
        if self.value_kind == "mouse":
            serial = self.value.name
        else:
            char = getattr(self.value, "char", None)
            serial = "char:" + char if char else "key:" + self.value.name
        return {"kind": self.value_kind, "name": self.display_text,
                "serial": serial}

    def from_dict(self, d):
        kind = d.get("kind", "mouse")
        name = d.get("name", "Left Mouse")
        serial = d.get("serial", "left")
        if kind == "mouse":
            value = getattr(mouse.Button, serial, mouse.Button.left)
        elif serial.startswith("char:"):
            value = keyboard.KeyCode.from_char(serial[5:])
        elif serial.startswith("key:"):
            value = getattr(keyboard.Key, serial[4:], None) \
                or keyboard.KeyCode.from_char(" ")
        else:
            value = keyboard.KeyCode.from_char(serial[:1] or " ")
        self._set(kind, value, name, emit=False)


# --------------------------------------------------------------------------- #
#  Outlined text label (fakes transparency over the custom gradient)
# --------------------------------------------------------------------------- #

class OutlinedLabel(tk.Canvas):
    """A canvas-based label.

    In Custom appearance it fakes transparency against the vertical gradient
    (a vertical gradient is uniform across any given row, so a solid fill of
    the row's colour is indistinguishable from the gradient) and draws
    comic-style outlined text â the glyphs are stamped in black in the eight
    surrounding directions, then the main colour on top. In Dark/Light it
    renders a plain label whose background matches the window, so it looks the
    same as the original CTkLabel.
    """

    def __init__(self, master, app, text="", text_color="#dce4ee",
                 outline="#000000", anchor="w", font=("Segoe UI", 11), **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw)
        self.app = app
        self._text = text
        self._color = text_color
        self._outline = outline
        self._anchor = anchor
        self._font = font
        app._outlined.append(self)
        self.render()

    def set(self, text=None, color=None):
        if text is not None:
            self._text = text
        if color is not None:
            self._color = color
        self.render()

    def render(self):
        self.delete("all")
        # Use one concrete Font object for BOTH measuring and drawing, so the
        # canvas is never sized narrower than the glyphs Tk actually paints
        # (a font-name tuple can resolve differently between the two paths).
        f = tkfont.Font(font=self._font)
        tw, th = f.measure(self._text), f.metrics("linespace")
        # Keep the width overhead to just what the outline needs, so rows stay
        # as compact as the original CTk labels and don't overflow the window.
        ow = 2 if abs(f.actual("size")) >= 16 else 1
        pad = ow
        w = tw + pad * 2
        h = th + pad * 2
        self.config(width=w, height=h)
        custom = (self.app.appearance_mode == "custom")
        self.config(bg=(self.app._grad_color_at(self) if custom
                        else self.app._window_bg))
        if self._anchor == "center":
            x, anc = w / 2, "center"
        else:
            x, anc = pad, "w"
        y = h / 2
        if custom:
            for dx in range(-ow, ow + 1):
                for dy in range(-ow, ow + 1):
                    if dx or dy:
                        self.create_text(x + dx, y + dy, text=self._text,
                                         fill=self._outline, font=f, anchor=anc)
        self.create_text(x, y, text=self._text, fill=self._color,
                         font=f, anchor=anc)


# --------------------------------------------------------------------------- #
#  Toggle-style radio button
# --------------------------------------------------------------------------- #

class ToggleRadio(ctk.CTkRadioButton):
    """A CTkRadioButton used as an independent toggle.

    The UI treats radios as loose toggles with manual mutual-exclusion logic
    and reads their state via ``.get()`` â a method CTkRadioButton does not
    provide. This subclass backs each radio with its own variable so that
    ``.get()`` / ``.select()`` / ``.deselect()`` work as the app expects.
    """

    def __init__(self, master, **kwargs):
        kwargs.pop("value", None)            # state is driven by our own var
        # A StringVar is used because CTkRadioButton.deselect() clears the
        # variable with "", which an IntVar cannot hold. Selected == "1".
        self._toggle_var = tk.StringVar(value="")
        super().__init__(master, variable=self._toggle_var, value="1", **kwargs)

    def get(self):
        return self._toggle_var.get() == "1"


# --------------------------------------------------------------------------- #
#  Main application
# --------------------------------------------------------------------------- #

class DeluxeClicker(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Deluxe Clicker")
        self.geometry("500x440")
        self.minsize(500, 440)
        self.configure(fg_color="#1e1f22")

        self.engine = ClickEngine()
        self.accent = "#5865F2"            # Discord blurple default
        self.accent_widgets = []           # widgets recolored on theme change
        self.hotkey = keyboard.Key.f6
        self.hotkey_name = "F6"
        self.captured_pos = (0, 0)

        # appearance / custom background state
        self.appearance_mode = "dark"      # "dark" | "light" | "custom"
        self._window_bg = "#1e1f22"
        self.bg_color1 = "#5865F2"
        self.bg_color2 = "#1e1f22"
        self._bg_canvas = None
        self._bg_img = None
        self._counter_job = None

        # Widgets whose opaque background must track the gradient in Custom
        # mode (otherwise CTk paints a solid "box" of the window colour).
        self._grad_ctk_frames = []   # CTkFrame  -> fg_color
        self._grad_tk_frames = []    # tk.Frame  -> bg
        self._grad_radios = []       # CTkRadioButton -> bg_color
        self._outlined = []          # OutlinedLabel  -> render()

        self._load_icon()
        self._build_ui()
        self._load_settings()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- window icon ------------------------------------------------------- #
    def _load_icon(self):
        try:
            self._icon_img = ImageTk.PhotoImage(
                Image.open(resource_path(ICON_PNG)))
            self.wm_iconphoto(True, self._icon_img)
        except Exception:
            pass

    # -- UI ---------------------------------------------------------------- #
    def _build_ui(self):
        pad = {"padx": 14, "pady": 6}

        OutlinedLabel(self, self, text="Deluxe Clicker", text_color="#f2f3f5",
                      anchor="center", font=("Segoe UI", 18, "bold")
                      ).grid(row=0, column=0, columnspan=4, pady=(12, 6))

        # --- interval row (Hours / Mins / Secs / Millis) ------------------ #
        self.fixed_radio = ToggleRadio(self, text="", width=20,
                                               value=False, command=self._sync)
        self.fixed_radio.grid(row=1, column=0, sticky="w", padx=(14, 0))
        self.fixed_radio.select()
        self.accent_widgets.append(self.fixed_radio)
        self._grad_radios.append(self.fixed_radio)

        irow = ctk.CTkFrame(self, fg_color="transparent")
        irow.grid(row=1, column=1, columnspan=3, sticky="w")
        self._grad_ctk_frames.append(irow)
        self.e_h = self._num(irow, "0", "Hours")
        self.e_m = self._num(irow, "0", "Mins")
        self.e_s = self._num(irow, "0", "Secs")
        self.e_ms = self._num(irow, "100", "Millis")

        # --- random interval row ----------------------------------------- #
        self.rand_radio = self._labeled_radio(
            "Random Click Interval Between", row=2, column=0, columnspan=2,
            sticky="w", padx=(14, 0), pady=6)
        rrow = ctk.CTkFrame(self, fg_color="transparent")
        rrow.grid(row=2, column=2, columnspan=2, sticky="w")
        self._grad_ctk_frames.append(rrow)
        self.e_lo = self._num(rrow, "0.1", "Secs", w=46)
        self.e_hi = self._num(rrow, "0.2", "Secs", w=46)

        # --- button / repeat count --------------------------------------- #
        OutlinedLabel(self, self, text="Button", anchor="w"
                      ).grid(row=3, column=0, sticky="w", **pad)
        self.btn_picker = ButtonPicker(self, width=128)
        self.btn_picker.grid(row=3, column=1, sticky="w")
        self.accent_widgets.append(self.btn_picker)
        self._grad_ctk_frames.append(self.btn_picker)

        self.repeat_n_radio = self._labeled_radio(
            "Repeat", row=3, column=2, sticky="w")
        self.e_times = self._num(self, "1", "Times", row=3, col=3, w=50)

        # --- click type / repeat forever --------------------------------- #
        OutlinedLabel(self, self, text="Click Type", anchor="w"
                      ).grid(row=4, column=0, sticky="w", **pad)
        self.opt_click = ctk.CTkOptionMenu(self, values=["Single", "Double"],
                                           width=90)
        self.opt_click.grid(row=4, column=1, sticky="w")
        self.accent_widgets.append(self.opt_click)

        self.repeat_forever_radio = self._labeled_radio(
            "Repeat Until Stopped", row=4, column=2, columnspan=2,
            sticky="w", pady=6)
        self.repeat_forever_radio.select()

        # --- location ----------------------------------------------------- #
        self.cur_loc_radio = self._labeled_radio(
            "Current Location", row=5, column=0, columnspan=2,
            sticky="w", padx=(14, 0))
        self.cur_loc_radio.select()

        self.pick_radio = ToggleRadio(self, text="", width=20,
                                             command=self._sync)
        self.pick_radio.grid(row=5, column=2, sticky="e")
        self.accent_widgets.append(self.pick_radio)
        self._grad_radios.append(self.pick_radio)
        prow = ctk.CTkFrame(self, fg_color="transparent")
        prow.grid(row=5, column=3, sticky="w")
        self._grad_ctk_frames.append(prow)
        self.btn_get = ctk.CTkButton(prow, text="Get", width=40,
                                     command=self._capture_pos)
        self.btn_get.pack(side="left", padx=(0, 2))
        self.accent_widgets.append(self.btn_get)
        self.e_x = self._num(prow, "0", "X", w=46)
        self.e_y = self._num(prow, "0", "Y", w=46)

        # --- start / stop ------------------------------------------------- #
        self.btn_start = ctk.CTkButton(self, text=f"Start ({self.hotkey_name})",
                                       fg_color="#3ba55d", hover_color="#2d8049",
                                       height=42, command=self.start)
        self.btn_start.grid(row=6, column=0, columnspan=2,
                            sticky="ew", padx=14, pady=(14, 4))
        self.btn_stop = ctk.CTkButton(self, text=f"Stop ({self.hotkey_name})",
                                      fg_color="#ed4245", hover_color="#c23538",
                                      height=42, command=self.stop)
        self.btn_stop.grid(row=6, column=2, columnspan=2,
                           sticky="ew", padx=14, pady=(14, 4))

        # --- hotkey / theme ---------------------------------------------- #
        ctk.CTkButton(self, text="Change Hotkey", fg_color="#3a3c42",
                      hover_color="#46474d", command=self._change_hotkey
                      ).grid(row=7, column=0, columnspan=2,
                             sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkButton(self, text="Customise Theme", fg_color="#3a3c42",
                      hover_color="#46474d", command=self._open_theme
                      ).grid(row=7, column=2, columnspan=2,
                             sticky="ew", padx=14, pady=(0, 12))

        self.status = OutlinedLabel(self, self, text="Idle",
                                    text_color="#b5bac1", anchor="center")
        self.status.grid(row=8, column=0, columnspan=4, pady=(0, 6))

        for c in range(4):
            self.grid_columnconfigure(c, weight=1)
        self._apply_accent(self.accent)
        self._sync()

    # -- small widget factory ---------------------------------------------- #
    def _num(self, parent, default, label, row=None, col=None, w=46):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        if row is not None:
            frame.grid(row=row, column=col, sticky="w")
        else:
            frame.pack(side="left", padx=2)
        self._grad_ctk_frames.append(frame)
        entry = ctk.CTkEntry(frame, width=w, justify="center")
        entry.insert(0, default)
        entry.pack(side="left")
        OutlinedLabel(frame, self, text=label, text_color="#b5bac1",
                      anchor="w").pack(side="left", padx=(3, 4))
        return entry

    # -- radio + outlined label, wrapped so both blend with the gradient --- #
    def _labeled_radio(self, text, **grid_kw):
        frame = tk.Frame(self, bg=self._window_bg, highlightthickness=0, bd=0)
        frame.grid(**grid_kw)
        radio = ToggleRadio(frame, text="", width=20, command=self._sync)
        radio.pack(side="left")
        OutlinedLabel(frame, self, text=text, text_color="#dce4ee",
                      anchor="w").pack(side="left")
        self.accent_widgets.append(radio)
        self._grad_radios.append(radio)
        self._grad_tk_frames.append(frame)
        return radio

    # -- accent theming ---------------------------------------------------- #
    def _apply_accent(self, color):
        self.accent = color
        hover = shade(color, 0.85)
        for w in self.accent_widgets:
            try:
                if isinstance(w, ButtonPicker):
                    w.set_accent(color, hover)
                elif isinstance(w, ctk.CTkOptionMenu):
                    w.configure(fg_color=color, button_color=color,
                                button_hover_color=hover)
                else:
                    w.configure(fg_color=color, hover_color=hover)
            except Exception:
                pass
        self.status.set(text=f"Accent set to {color}")

    def _open_theme(self):
        ThemePicker(self, self)

    # -- appearance / custom gradient background --------------------------- #
    def set_appearance(self, mode):
        self.appearance_mode = mode
        if mode in ("dark", "light"):
            ctk.set_appearance_mode(mode)
            if self._bg_canvas is not None:
                self._bg_canvas.place_forget()
            self._update_gradient_widgets()
        else:                                       # custom gradient
            ctk.set_appearance_mode("dark")
            self._ensure_bg_canvas()
            self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self._lower_bg_canvas()
            self._redraw_bg()

    # -- per-row gradient colour (vertical gradient is uniform across a row) - #
    def _grad_color_at(self, widget):
        try:
            y = (widget.winfo_rooty() - self.winfo_rooty()
                 + widget.winfo_height() / 2)
        except Exception:
            y = 0
        t = min(max(y / max(1, self.winfo_height()), 0.0), 1.0)
        r1, g1, b1 = hex_to_rgb(self.bg_color1)
        r2, g2, b2 = hex_to_rgb(self.bg_color2)
        return rgb_to_hex(r1 + (r2 - r1) * t,
                          g1 + (g2 - g1) * t,
                          b1 + (b2 - b1) * t)

    def _update_gradient_widgets(self):
        """Recolour every box-prone widget so it blends with the gradient
        (Custom), or revert it to the normal flat look (Dark/Light)."""
        custom = self.appearance_mode == "custom"
        for f in self._grad_ctk_frames:
            try:
                f.configure(fg_color=(self._grad_color_at(f) if custom
                                      else "transparent"))
            except Exception:
                pass
        for f in self._grad_tk_frames:
            try:
                f.configure(bg=(self._grad_color_at(f) if custom
                                else self._window_bg))
            except Exception:
                pass
        for r in self._grad_radios:
            try:
                r.configure(bg_color=(self._grad_color_at(r) if custom
                                      else "transparent"))
            except Exception:
                pass
        for lbl in self._outlined:
            try:
                lbl.render()
            except Exception:
                pass

    def _lower_bg_canvas(self):
        """Lower the canvas *widget* in the window stacking order.

        ``tk.Canvas.lower`` is overridden to lower a canvas *item* (and needs
        a tagOrId), so call the Tk widget-stacking command directly to push the
        whole canvas behind its sibling widgets.
        """
        if self._bg_canvas is not None:
            self._bg_canvas.tk.call("lower", self._bg_canvas._w)

    def _ensure_bg_canvas(self):
        if self._bg_canvas is None:
            self._bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
            self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self._lower_bg_canvas()
            self.bind("<Configure>", lambda e: self._redraw_bg())

    def apply_background(self, c1, c2):
        self.bg_color1, self.bg_color2 = c1, c2
        self.appearance_mode = "custom"
        self._ensure_bg_canvas()
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._lower_bg_canvas()
        self._redraw_bg()

    def _redraw_bg(self):
        if self._bg_canvas is None or self.appearance_mode != "custom":
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2:
            return
        img = vertical_gradient(self.bg_color1, self.bg_color2, w, h)
        self._bg_img = ImageTk.PhotoImage(img)
        self._bg_canvas.delete("all")
        self._bg_canvas.create_image(0, 0, anchor="nw", image=self._bg_img)
        self._lower_bg_canvas()
        self._update_gradient_widgets()

    # -- radio sync (mutually exclusive groups, since CTk radios are loose) - #
    def _sync(self, *_):
        # interval mode
        if self.rand_radio.get():
            self.fixed_radio.deselect()
        if self.fixed_radio.get():
            self.rand_radio.deselect()
        # repeat mode
        if self.repeat_forever_radio.get():
            self.repeat_n_radio.deselect()
        if self.repeat_n_radio.get():
            self.repeat_forever_radio.deselect()
        # location mode
        if self.pick_radio.get():
            self.cur_loc_radio.deselect()
        if self.cur_loc_radio.get():
            self.pick_radio.deselect()

    def _capture_pos(self):
        self.captured_pos = mouse.Controller().position
        x, y = (int(c) for c in self.captured_pos)
        for entry, val in ((self.e_x, x), (self.e_y, y)):
            entry.delete(0, "end")
            entry.insert(0, str(val))
        self.pick_radio.select()
        self._sync()

    # -- config gathering -------------------------------------------------- #
    @staticmethod
    def _f(entry, default=0.0):
        try:
            return float(entry.get())
        except ValueError:
            return default

    def _gather(self):
        interval = (self._f(self.e_h) * 3600 + self._f(self.e_m) * 60
                    + self._f(self.e_s) + self._f(self.e_ms) / 1000.0)
        return {
            "interval": interval,
            "random_interval": bool(self.rand_radio.get()),
            "rand_lo": self._f(self.e_lo, 0.1),
            "rand_hi": self._f(self.e_hi, 0.2),
            "button_kind": self.btn_picker.value_kind,
            "button_obj": self.btn_picker.value,
            "button_name": self.btn_picker.display_text,
            "click_type": self.opt_click.get(),
            "repeat_forever": bool(self.repeat_forever_radio.get()),
            "repeat_times": max(1, int(self._f(self.e_times, 1))),
            "fixed_pos": bool(self.pick_radio.get()),
            "x": int(self._f(self.e_x)),
            "y": int(self._f(self.e_y)),
        }

    # -- start / stop ------------------------------------------------------ #
    def start(self):
        if self.engine.running:
            return
        self.engine.start(self._gather(),
                          on_finish=lambda: self.after(0, self._on_finish))
        self._tick_counter()

    def stop(self):
        self.engine.stop()

    def _tick_counter(self):
        if self.engine.running:
            self.status.set(
                text=f"Clicking… ({self.engine.count} clicks)",
                color="#3ba55d")
            self._counter_job = self.after(100, self._tick_counter)

    def _on_finish(self):
        if self._counter_job is not None:
            self.after_cancel(self._counter_job)
            self._counter_job = None
        self.status.set(text="Idle", color="#b5bac1")

    def toggle(self):
        self.stop() if self.engine.running else self.start()

    # -- global hotkey ----------------------------------------------------- #
    def _start_hotkey_listener(self):
        self._listener = keyboard.Listener(on_press=self._on_key)
        self._listener.daemon = True
        self._listener.start()

    def _on_key(self, key):
        if self._capturing:
            self._set_hotkey(key)
            return
        if key == self.hotkey:
            self.after(0, self.toggle)

    _capturing = False

    def _change_hotkey(self):
        self._capturing = True
        self.status.set(text="Press any key…", color="#faa61a")

    def _set_hotkey(self, key):
        self._capturing = False
        self.hotkey = key
        try:
            self.hotkey_name = key.char.upper()
        except AttributeError:
            self.hotkey_name = str(key).replace("Key.", "").upper()
        self.after(0, lambda: (
            self.btn_start.configure(text=f"Start ({self.hotkey_name})"),
            self.btn_stop.configure(text=f"Stop ({self.hotkey_name})"),
            self.status.set(text=f"Hotkey set to {self.hotkey_name}",
                            color="#b5bac1")))

    # -- settings persistence ---------------------------------------------- #
    def _collect_settings(self):
        return {
            "e_h": self.e_h.get(), "e_m": self.e_m.get(),
            "e_s": self.e_s.get(), "e_ms": self.e_ms.get(),
            "e_lo": self.e_lo.get(), "e_hi": self.e_hi.get(),
            "e_times": self.e_times.get(),
            "e_x": self.e_x.get(), "e_y": self.e_y.get(),
            "button": self.btn_picker.to_dict(),
            "click_type": self.opt_click.get(),
            "interval_mode": "random" if self.rand_radio.get() else "fixed",
            "repeat_mode": "forever" if self.repeat_forever_radio.get() else "times",
            "location_mode": "pick" if self.pick_radio.get() else "current",
            "accent": self.accent,
            "appearance": self.appearance_mode,
            "bg1": self.bg_color1, "bg2": self.bg_color2,
        }

    def _save_settings(self):
        try:
            with open(settings_path(), "w", encoding="utf-8") as fh:
                json.dump(self._collect_settings(), fh, indent=2)
        except Exception:
            pass

    @staticmethod
    def _set_entry(entry, val):
        entry.delete(0, "end")
        entry.insert(0, str(val))

    def _load_settings(self):
        try:
            with open(settings_path(), "r", encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            return

        for name in ("e_h", "e_m", "e_s", "e_ms", "e_lo", "e_hi",
                     "e_times", "e_x", "e_y"):
            if name in d:
                self._set_entry(getattr(self, name), d[name])

        if "button" in d:
            self.btn_picker.from_dict(d["button"])
        if d.get("click_type") in ("Single", "Double"):
            self.opt_click.set(d["click_type"])

        if d.get("interval_mode") == "random":
            self.rand_radio.select(); self.fixed_radio.deselect()
        else:
            self.fixed_radio.select(); self.rand_radio.deselect()

        if d.get("repeat_mode") == "times":
            self.repeat_n_radio.select(); self.repeat_forever_radio.deselect()
        else:
            self.repeat_forever_radio.select(); self.repeat_n_radio.deselect()

        if d.get("location_mode") == "pick":
            self.pick_radio.select(); self.cur_loc_radio.deselect()
        else:
            self.cur_loc_radio.select(); self.pick_radio.deselect()
        self._sync()

        self.bg_color1 = d.get("bg1", self.bg_color1)
        self.bg_color2 = d.get("bg2", self.bg_color2)
        if "accent" in d:
            self._apply_accent(d["accent"])
        self.set_appearance(d.get("appearance", "dark"))
        if self.appearance_mode == "custom":
            self.apply_background(self.bg_color1, self.bg_color2)

        self.status.set(text="Idle", color="#b5bac1")

    def _on_close(self):
        self._save_settings()
        self.engine.stop()
        try:
            self._listener.stop()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    DeluxeClicker().mainloop()
