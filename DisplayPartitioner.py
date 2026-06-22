# =============================================================================
# Display Partitioner - A Persistent Monitor Partitioning Utility
# Version: 3.1.0 (Four-Edge Partitioning)
#
# Description:
#   Partition any monitor from the left, right, top, or bottom edge. The app
#   uses a tray menu, customizable overlay, hotkey toggle, cursor clipping, and
#   Windows work-area resizing so maximized windows tile into the usable area.
# =============================================================================
import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import colorchooser, messagebox

import keyboard
import win32api
import win32con
import win32gui
from PIL import Image, ImageDraw
from pystray import Icon, Menu
from pystray import MenuItem as item


# --- INITIAL CONFIGURATION ---
INITIAL_BOUNDARY_PERCENT = 0.5
DEFAULT_HOTKEY = "win+alt+p"
DEFAULT_OVERLAY_COLOR = "#000000"
DEFAULT_OVERLAY_OPACITY = 100
DEFAULT_PARTITION_EDGE = "left"
APP_VERSION = "3.1.0"

# --- CONFIG FILE LOCATION ---
APPDATA_DIR = os.getenv("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(APPDATA_DIR, "DisplayPartitioner")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
WORK_AREA_STATE_FILE = os.path.join(CONFIG_DIR, "work_area_state.json")
VALID_PARTITION_EDGES = {"left", "right", "top", "bottom"}


class RECT(ctypes.Structure):
    """Windows RECT structure used by SystemParametersInfoW."""

    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class SettingsWindow(tk.Toplevel):
    """Settings window for monitor selection, partitioning, and appearance."""

    def __init__(self, master, app_instance):
        """Build the settings window and connect controls to app state."""
        super().__init__(master)

        self.app = app_instance
        self.title("Display Partitioner Settings")
        self.geometry("800x500")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.boundary_var = tk.StringVar(value=str(self.app.window_boundary_x))
        self.is_enabled_var = tk.BooleanVar(value=self.app.is_running)
        self.partition_edge_var = tk.StringVar(value=self.app.partition_edge)
        self.hotkey_var = tk.StringVar(value=self.app.hotkey)
        self.color_var = tk.StringVar(value=self.app.overlay_color)
        self.opacity_var = tk.IntVar(value=self.app.overlay_opacity)

        self.canvas_width = 780
        self.canvas_height = 100
        self.all_monitors = self.app.get_all_monitors()
        self.scale, self.offset_x, self.offset_y = self._calculate_scale()
        self.boundary_line_id = None
        self.shading_rect_id = None

        self._build_canvas()
        self._build_monitor_selection()
        self._build_settings_controls()
        self._build_action_controls()
        self.update_full_canvas()

    def _build_canvas(self):
        """Create the monitor preview canvas and boundary drag binding."""
        self.canvas = tk.Canvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#f0f0f0",
            relief="sunken",
            borderwidth=1,
        )
        self.canvas.pack(pady=10, padx=10)
        self.canvas.tag_bind("boundary_line", "<B1-Motion>", self.on_drag_line)

    def _build_monitor_selection(self):
        """Create monitor and edge selection controls."""
        selection_frame = tk.Frame(self)
        selection_frame.pack(pady=5, padx=10, fill="x")

        tk.Label(selection_frame, text="Target Monitor:").grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.monitor_names = []
        for i, monitor in enumerate(self.all_monitors):
            left, top, right, bottom = monitor["Rect"]
            self.monitor_names.append(f"Monitor {i} ({right - left}x{bottom - top})")

        self.monitor_var = tk.StringVar(
            value=self.monitor_names[self.app.target_monitor_index],
        )
        monitor_menu = tk.OptionMenu(
            selection_frame,
            self.monitor_var,
            *self.monitor_names,
            command=self.on_monitor_select,
        )
        monitor_menu.grid(row=0, column=1, padx=5, sticky="w")

        edge_frame = tk.Frame(selection_frame)
        edge_frame.grid(row=0, column=2, padx=20)

        for text, value in (
            ("Left", "left"),
            ("Right", "right"),
            ("Top", "top"),
            ("Bottom", "bottom"),
        ):
            tk.Radiobutton(
                edge_frame,
                text=text,
                variable=self.partition_edge_var,
                value=value,
                command=self.on_edge_select,
            ).pack(side="left", padx=3)

    def _build_settings_controls(self):
        """Create boundary, hotkey, color, and opacity controls."""
        settings_container = tk.Frame(self)
        settings_container.pack(pady=5, padx=10, fill="x")

        controls_frame = tk.LabelFrame(
            settings_container,
            text="Controls",
            padx=10,
            pady=10,
        )
        controls_frame.pack(side="left", fill="y", padx=(0, 5))

        tk.Label(controls_frame, text="Boundary Coordinate:").grid(
            row=0,
            column=0,
            pady=2,
            sticky="w",
        )

        self.entry_box = tk.Entry(
            controls_frame,
            textvariable=self.boundary_var,
            width=10,
        )
        self.entry_box.grid(row=0, column=1, padx=5, sticky="w")

        tk.Button(
            controls_frame,
            text="Set",
            command=self.apply_text_boundary,
            width=8,
        ).grid(row=0, column=2, sticky="w")

        tk.Label(controls_frame, text="Toggle Hotkey:").grid(
            row=1,
            column=0,
            pady=2,
            sticky="w",
        )

        hotkey_entry = tk.Entry(
            controls_frame,
            textvariable=self.hotkey_var,
            width=20,
        )
        hotkey_entry.grid(row=1, column=1, columnspan=2, padx=5, sticky="w")

        tk.Button(
            controls_frame,
            text="Set Hotkey",
            command=self.apply_hotkey,
        ).grid(row=2, column=1, columnspan=2, pady=(0, 5), sticky="w")

        appearance_frame = tk.LabelFrame(
            settings_container,
            text="Overlay Appearance",
            padx=10,
            pady=10,
        )
        appearance_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        tk.Label(appearance_frame, text="Color:").grid(row=0, column=0, sticky="w")

        self.color_preview = tk.Label(
            appearance_frame,
            text="      ",
            bg=self.app.overlay_color,
            relief="sunken",
            borderwidth=1,
        )
        self.color_preview.grid(row=0, column=1, padx=5, sticky="w")

        tk.Button(
            appearance_frame,
            text="Choose Color...",
            command=self.on_choose_color,
        ).grid(row=0, column=2, sticky="w")

        tk.Label(appearance_frame, text="Opacity:").grid(
            row=1,
            column=0,
            pady=5,
            sticky="w",
        )

        opacity_slider = tk.Scale(
            appearance_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.opacity_var,
            command=self.on_opacity_change,
            length=200,
            showvalue=0,
        )
        opacity_slider.grid(row=1, column=1, columnspan=2, sticky="we")

        self.opacity_label = tk.Label(
            appearance_frame,
            textvariable=self.opacity_var,
        )
        self.opacity_label.grid(row=1, column=3, padx=(5, 0))

        tk.Label(appearance_frame, text="%").grid(row=1, column=4, sticky="w")

    def _build_action_controls(self):
        """Create enable and close controls."""
        action_frame = tk.Frame(self)
        action_frame.pack(pady=15)

        enable_check = tk.Checkbutton(
            action_frame,
            text="Enable Partitioning",
            variable=self.is_enabled_var,
            command=self.toggle_partition,
            font=("Segoe UI", 10, "bold"),
        )
        enable_check.pack(side="left", padx=10)

        tk.Button(
            action_frame,
            text="Close",
            width=12,
            command=self.on_close,
        ).pack(side="left", padx=10)

    def on_choose_color(self):
        """Open the color picker and apply the selected overlay color."""
        color_code = colorchooser.askcolor(
            title="Choose overlay color",
            initialcolor=self.app.overlay_color,
        )

        if color_code and color_code[1]:
            hex_color = color_code[1]
            self.color_var.set(hex_color)
            self.color_preview.config(bg=hex_color)
            self.app.set_overlay_color(hex_color)

    def on_opacity_change(self, value):
        """Apply the selected opacity percentage to the overlay."""
        self.app.set_overlay_opacity(int(value))

    def _calculate_scale(self):
        """Calculate a canvas scale that fits the full virtual monitor layout."""
        min_x = min(monitor["Rect"][0] for monitor in self.all_monitors)
        max_x = max(monitor["Rect"][2] for monitor in self.all_monitors)
        min_y = min(monitor["Rect"][1] for monitor in self.all_monitors)
        max_y = max(monitor["Rect"][3] for monitor in self.all_monitors)

        total_width = max_x - min_x
        total_height = max_y - min_y
        scale_x = self.canvas_width / total_width * 0.95 if total_width > 0 else 1
        scale_y = self.canvas_height / total_height * 0.85 if total_height > 0 else 1

        return min(scale_x, scale_y), -min_x, -min_y

    def _real_to_canvas_x(self, value):
        """Convert a real desktop X coordinate to a canvas X coordinate."""
        return (value + self.offset_x) * self.scale + self.canvas_width * 0.025

    def _real_to_canvas_y(self, value):
        """Convert a real desktop Y coordinate to a canvas Y coordinate."""
        return (value + self.offset_y) * self.scale + self.canvas_height * 0.075

    def _canvas_to_real_x(self, value):
        """Convert a canvas X coordinate to a real desktop X coordinate."""
        return int(((value - self.canvas_width * 0.025) / self.scale) - self.offset_x)

    def _canvas_to_real_y(self, value):
        """Convert a canvas Y coordinate to a real desktop Y coordinate."""
        return int(((value - self.canvas_height * 0.075) / self.scale) - self.offset_y)

    def _draw_monitors(self):
        """Draw detected monitors in the preview canvas."""
        self.canvas.delete("monitors")

        for i, monitor in enumerate(self.all_monitors):
            left, top, right, bottom = monitor["Rect"]
            canvas_left = self._real_to_canvas_x(left)
            canvas_top = self._real_to_canvas_y(top)
            canvas_right = self._real_to_canvas_x(right)
            canvas_bottom = self._real_to_canvas_y(bottom)
            fill_color = "#aaddaa" if i == self.app.target_monitor_index else "#cccccc"

            self.canvas.create_rectangle(
                canvas_left,
                canvas_top,
                canvas_right,
                canvas_bottom,
                fill=fill_color,
                outline="black",
                width=2,
                tags="monitors",
            )

            primary_text = " (Primary)" if monitor["is_primary"] else ""
            self.canvas.create_text(
                (canvas_left + canvas_right) / 2,
                (canvas_top + canvas_bottom) / 2,
                text=f"Monitor {i}{primary_text}",
                tags="monitors",
            )

    def _draw_partition_shading(self):
        """Draw shaded preview area showing the blocked partition."""
        target_monitor = self.all_monitors[self.app.target_monitor_index]
        left, top, right, bottom = target_monitor["Rect"]
        canvas_left = self._real_to_canvas_x(left)
        canvas_top = self._real_to_canvas_y(top)
        canvas_right = self._real_to_canvas_x(right)
        canvas_bottom = self._real_to_canvas_y(bottom)
        boundary_x = self._real_to_canvas_x(self.app.window_boundary_x)
        boundary_y = self._real_to_canvas_y(self.app.window_boundary_x)

        if self.app.partition_edge == "left":
            shade_coords = (canvas_left, canvas_top, boundary_x, canvas_bottom)
        elif self.app.partition_edge == "right":
            shade_coords = (boundary_x, canvas_top, canvas_right, canvas_bottom)
        elif self.app.partition_edge == "top":
            shade_coords = (canvas_left, canvas_top, canvas_right, boundary_y)
        else:
            shade_coords = (canvas_left, boundary_y, canvas_right, canvas_bottom)

        if self.shading_rect_id:
            self.canvas.coords(self.shading_rect_id, *shade_coords)
        else:
            self.shading_rect_id = self.canvas.create_rectangle(
                *shade_coords,
                fill="#333333",
                stipple="gray50",
                outline="",
                tags="shading",
            )

    def _draw_boundary_line(self):
        """Draw or move the draggable boundary line."""
        target_monitor = self.all_monitors[self.app.target_monitor_index]
        left, top, right, bottom = target_monitor["Rect"]
        boundary_x = self._real_to_canvas_x(self.app.window_boundary_x)
        boundary_y = self._real_to_canvas_y(self.app.window_boundary_x)

        if self.app.partition_edge in ("left", "right"):
            line_coords = (
                boundary_x,
                self._real_to_canvas_y(top),
                boundary_x,
                self._real_to_canvas_y(bottom),
            )
        else:
            line_coords = (
                self._real_to_canvas_x(left),
                boundary_y,
                self._real_to_canvas_x(right),
                boundary_y,
            )

        if self.boundary_line_id:
            self.canvas.coords(self.boundary_line_id, *line_coords)
        else:
            self.boundary_line_id = self.canvas.create_line(
                *line_coords,
                fill="red",
                width=3,
                tags="boundary_line",
            )

    def update_full_canvas(self):
        """Redraw the monitor preview, shaded partition, and boundary line."""
        self._draw_monitors()
        self._draw_partition_shading()
        self._draw_boundary_line()
        self.canvas.tag_raise(self.boundary_line_id)

    def on_drag_line(self, event):
        """Update the partition boundary while dragging the preview line."""
        target_monitor = self.all_monitors[self.app.target_monitor_index]
        left, top, right, bottom = target_monitor["Rect"]

        if self.app.partition_edge in ("left", "right"):
            canvas_left = self._real_to_canvas_x(left)
            canvas_right = self._real_to_canvas_x(right)
            canvas_x = max(canvas_left, min(event.x, canvas_right))
            real_value = self._canvas_to_real_x(canvas_x)
        else:
            canvas_top = self._real_to_canvas_y(top)
            canvas_bottom = self._real_to_canvas_y(bottom)
            canvas_y = max(canvas_top, min(event.y, canvas_bottom))
            real_value = self._canvas_to_real_y(canvas_y)

        self.boundary_var.set(str(real_value))
        self.app.update_boundary(real_value)
        self.update_full_canvas()

    def apply_text_boundary(self, event=None):
        """Apply a manually entered boundary coordinate."""
        try:
            self.app.update_boundary(int(self.boundary_var.get()))
            self.boundary_var.set(str(self.app.window_boundary_x))
            self.update_full_canvas()
        except ValueError:
            messagebox.showerror(
                "Invalid Input",
                "Please enter a valid integer.",
                parent=self,
            )
            self.boundary_var.set(str(self.app.window_boundary_x))

    def apply_hotkey(self):
        """Validate and apply a new global hotkey."""
        new_hotkey = self.hotkey_var.get().strip().lower()

        if not new_hotkey:
            messagebox.showerror("Invalid Input", "Hotkey cannot be empty.", parent=self)
            self.hotkey_var.set(self.app.hotkey)
            return

        if self.app.set_hotkey(new_hotkey):
            messagebox.showinfo(
                "Success",
                f"Hotkey successfully set to '{new_hotkey}'.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "Invalid Hotkey",
                "The entered hotkey string is not valid.",
                parent=self,
            )
            self.hotkey_var.set(self.app.hotkey)

    def on_monitor_select(self, selection):
        """Switch to the selected target monitor."""
        index = self.monitor_names.index(selection)
        self.app.set_target_monitor(index)
        self.boundary_var.set(str(self.app.window_boundary_x))
        self.update_full_canvas()

    def on_edge_select(self):
        """Switch the partition edge and reset the boundary for that edge."""
        self.app.set_partition_edge(self.partition_edge_var.get())
        self.boundary_var.set(str(self.app.window_boundary_x))
        self.update_full_canvas()

    def toggle_partition(self):
        """Toggle partitioning from the settings window."""
        self.app.toggle_partition()

    def update_ui_state(self):
        """Synchronize the enable checkbox with the app state."""
        self.is_enabled_var.set(self.app.is_running)

    def on_close(self):
        """Close the settings window and clear the app reference to it."""
        self.app.settings_window = None
        self.destroy()


def hex_to_rgb(hex_color):
    """Convert a '#rrggbb' color string to an RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class DisplayPartitioner:
    """Core controller for overlay, tiling, cursor clipping, and settings."""

    def __init__(self, root):
        """Initialize state, load configuration, create overlay, and bind hotkey."""
        self.tk_root = root
        self.is_running = False
        self.enforcement_thread = None
        self.overlay_hwnd = None
        self.settings_window = None
        self.original_work_area = None
        self.state_lock = threading.RLock()

        self.partition_on_left = True
        self.partition_edge = DEFAULT_PARTITION_EDGE
        self.hotkey = DEFAULT_HOTKEY
        self.overlay_color = DEFAULT_OVERLAY_COLOR
        self.overlay_opacity = DEFAULT_OVERLAY_OPACITY

        self.all_monitors = self.get_all_monitors()
        self._recover_stale_work_area()
        self.load_config()

        self._recalculate_geometry()
        self._create_native_overlay()
        self.register_initial_hotkey()

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        """Handle native overlay paint messages."""
        if msg == win32con.WM_ERASEBKGND:
            hdc = wParam
            rect = win32gui.GetClientRect(hwnd)
            rgb = hex_to_rgb(self.overlay_color)
            brush = win32gui.CreateSolidBrush(win32api.RGB(*rgb))

            win32gui.FillRect(hdc, rect, brush)
            win32gui.DeleteObject(brush)

            return 1

        return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)

    def set_overlay_color(self, hex_color):
        """Set the overlay color and repaint the overlay window."""
        with self.state_lock:
            self.overlay_color = self._validated_hex_color(hex_color)

            if self.overlay_hwnd:
                win32gui.InvalidateRect(self.overlay_hwnd, None, True)

    def _create_native_overlay(self):
        """Create the transparent, click-through native overlay window."""
        h_instance = win32api.GetModuleHandle()
        class_name = "DPOverlay"

        wnd_class = win32gui.WNDCLASS()
        wnd_class.lpfnWndProc = self._wnd_proc
        wnd_class.hInstance = h_instance
        wnd_class.hbrBackground = 0
        wnd_class.lpszClassName = class_name

        try:
            win32gui.RegisterClass(wnd_class)
        except win32gui.error as error:
            if error.winerror != 1410:
                raise

        ex_style = (
            win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_LAYERED
        )

        self.overlay_hwnd = win32gui.CreateWindowEx(
            ex_style,
            class_name,
            "DPO",
            win32con.WS_POPUP,
            self.overlay_rect["x"],
            self.overlay_rect["y"],
            self.overlay_rect["w"],
            self.overlay_rect["h"],
            None,
            None,
            h_instance,
            None,
        )

        self.set_overlay_opacity(self.overlay_opacity)

    def set_overlay_opacity(self, opacity_percent):
        """Set overlay opacity from a 0-100 percentage."""
        with self.state_lock:
            self.overlay_opacity = self._clamp_percent(opacity_percent)
            alpha_value = int(self.overlay_opacity / 100 * 255)

            win32gui.SetLayeredWindowAttributes(
                self.overlay_hwnd,
                0,
                alpha_value,
                win32con.LWA_ALPHA,
            )

    def load_config(self):
        """Load saved settings and fall back to defaults when needed."""
        try:
            with open(CONFIG_FILE, "r") as file:
                config = json.load(file)

            self.hotkey = config.get("hotkey", DEFAULT_HOTKEY)
            self.partition_on_left = config.get("partition_on_left", True)
            self.partition_edge = config.get(
                "partition_edge",
                "left" if self.partition_on_left else "right",
            )
            self.partition_edge = self._validated_partition_edge(self.partition_edge)
            self.overlay_color = self._validated_hex_color(
                config.get("overlay_color", DEFAULT_OVERLAY_COLOR),
            )
            self.overlay_opacity = self._clamp_percent(
                config.get("overlay_opacity", DEFAULT_OVERLAY_OPACITY),
            )

            saved_monitor_index = config.get("target_monitor_index", 0)
            saved_monitor_index = self._safe_int(saved_monitor_index, 0)

            if saved_monitor_index >= len(self.all_monitors):
                self.target_monitor_index = 0
            else:
                self.target_monitor_index = max(0, saved_monitor_index)

            initial_monitor = self.all_monitors[self.target_monitor_index]
            saved_boundary = config.get(
                "window_boundary_x",
                self._default_boundary_for_monitor(initial_monitor),
            )
            self.window_boundary_x = self._safe_int(
                saved_boundary,
                self._default_boundary_for_monitor(initial_monitor),
            )
            self.window_boundary_x = self._clamp_boundary(self.window_boundary_x)

            print("Configuration loaded successfully.")
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            print("No valid config file found. Using default settings.")
            self.target_monitor_index = self._find_initial_target_monitor()
            initial_monitor = self.all_monitors[self.target_monitor_index]
            self.partition_edge = DEFAULT_PARTITION_EDGE
            self.window_boundary_x = self._default_boundary_for_monitor(initial_monitor)

    def _safe_int(self, value, default):
        """Return value as an int, or default when conversion fails."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _clamp_percent(self, value):
        """Clamp a saved percentage value to the 0-100 range."""
        return max(0, min(self._safe_int(value, DEFAULT_OVERLAY_OPACITY), 100))

    def _validated_partition_edge(self, edge):
        """Return a known partition edge, falling back to the default."""
        if edge in VALID_PARTITION_EDGES:
            return edge

        return DEFAULT_PARTITION_EDGE

    def _validated_hex_color(self, hex_color):
        """Return a safe '#rrggbb' color string."""
        if not isinstance(hex_color, str):
            return DEFAULT_OVERLAY_COLOR

        candidate = hex_color.strip()

        if len(candidate) != 7 or not candidate.startswith("#"):
            return DEFAULT_OVERLAY_COLOR

        try:
            int(candidate[1:], 16)
        except ValueError:
            return DEFAULT_OVERLAY_COLOR

        return candidate

    def save_config(self):
        """Save current settings to the app config file."""
        config = {
            "target_monitor_index": self.target_monitor_index,
            "window_boundary_x": self.window_boundary_x,
            "partition_on_left": self.partition_on_left,
            "partition_edge": self.partition_edge,
            "hotkey": self.hotkey,
            "overlay_color": self.overlay_color,
            "overlay_opacity": self.overlay_opacity,
        }

        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)

            with open(CONFIG_FILE, "w") as file:
                json.dump(config, file, indent=4)

            print(f"Configuration saved to {CONFIG_FILE}")
        except Exception as error:
            print(f"Error saving configuration: {error}")

    def get_all_monitors(self):
        """Return monitor metadata from the Windows display API."""
        monitors = []

        for handle, _, rect in win32api.EnumDisplayMonitors():
            monitor_info = win32api.GetMonitorInfo(handle)
            monitors.append(
                {
                    "Handle": handle,
                    "Rect": rect,
                    "is_primary": monitor_info.get("Flags") == 1,
                    "Device": monitor_info.get("Device"),
                }
            )

        return monitors

    def _find_initial_target_monitor(self):
        """Choose a non-primary monitor by default when possible."""
        for i, monitor in enumerate(self.all_monitors):
            if not monitor["is_primary"]:
                return i

        return 0

    def _default_boundary_for_monitor(self, monitor):
        """Calculate a centered default boundary for the current edge."""
        left, top, right, bottom = monitor["Rect"]

        if self.partition_edge in ("top", "bottom"):
            return int(top + (bottom - top) * INITIAL_BOUNDARY_PERCENT)

        return int(left + (right - left) * INITIAL_BOUNDARY_PERCENT)

    def _clamp_boundary(self, value):
        """Keep the boundary coordinate inside the selected monitor."""
        left, top, right, bottom = self.all_monitors[self.target_monitor_index]["Rect"]

        if self.partition_edge in ("top", "bottom"):
            return max(top, min(int(value), bottom))

        return max(left, min(int(value), right))

    def _recalculate_geometry(self):
        """Recalculate overlay, usable area, and cursor clipping geometry."""
        target_monitor = self.all_monitors[self.target_monitor_index]
        target_left, target_top, target_right, target_bottom = target_monitor["Rect"]
        primary_monitor = next(
            (monitor for monitor in self.all_monitors if monitor["is_primary"]),
            self.all_monitors[0],
        )

        self.window_boundary_x = self._clamp_boundary(self.window_boundary_x)

        if self.partition_edge == "left":
            usable_part = (
                self.window_boundary_x,
                target_top,
                target_right,
                target_bottom,
            )
            self.overlay_rect = {
                "x": target_left,
                "y": target_top,
                "w": self.window_boundary_x - target_left,
                "h": target_bottom - target_top,
            }
        elif self.partition_edge == "right":
            usable_part = (
                target_left,
                target_top,
                self.window_boundary_x,
                target_bottom,
            )
            self.overlay_rect = {
                "x": self.window_boundary_x,
                "y": target_top,
                "w": target_right - self.window_boundary_x,
                "h": target_bottom - target_top,
            }
        elif self.partition_edge == "top":
            usable_part = (
                target_left,
                self.window_boundary_x,
                target_right,
                target_bottom,
            )
            self.overlay_rect = {
                "x": target_left,
                "y": target_top,
                "w": target_right - target_left,
                "h": self.window_boundary_x - target_top,
            }
        else:
            usable_part = (
                target_left,
                target_top,
                target_right,
                self.window_boundary_x,
            )
            self.overlay_rect = {
                "x": target_left,
                "y": self.window_boundary_x,
                "w": target_right - target_left,
                "h": target_bottom - self.window_boundary_x,
            }

        self.usable_part = usable_part

        if self.target_monitor_index != self.all_monitors.index(primary_monitor):
            primary_rect = primary_monitor["Rect"]
        else:
            primary_rect = usable_part

        self.cursor_clip_rect = (
            min(primary_rect[0], usable_part[0]),
            min(primary_rect[1], usable_part[1]),
            max(primary_rect[2], usable_part[2]),
            max(primary_rect[3], usable_part[3]),
        )

    def _set_work_area(self, rect):
        """Set the Windows work area used by maximized windows."""
        work_rect = RECT(*rect)
        success = ctypes.windll.user32.SystemParametersInfoW(
            win32con.SPI_SETWORKAREA,
            0,
            ctypes.byref(work_rect),
            win32con.SPIF_SENDCHANGE,
        )

        if not success:
            raise ctypes.WinError()

    def _save_work_area_state(self):
        """Persist the original work area so it can be restored after a bad exit."""
        if self.original_work_area is None:
            return

        state = {"original_work_area": list(self.original_work_area)}

        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)

            with open(WORK_AREA_STATE_FILE, "w") as file:
                json.dump(state, file, indent=4)
        except Exception as error:
            print(f"Warning: could not save work-area recovery state: {error}")

    def _clear_work_area_state(self):
        """Remove the saved recovery marker after work-area restoration."""
        try:
            if os.path.exists(WORK_AREA_STATE_FILE):
                os.remove(WORK_AREA_STATE_FILE)
        except Exception as error:
            print(f"Warning: could not clear work-area recovery state: {error}")

    def _recover_stale_work_area(self):
        """Restore the work area saved by a previous run that did not exit cleanly."""
        try:
            with open(WORK_AREA_STATE_FILE, "r") as file:
                state = json.load(file)

            original_work_area = state.get("original_work_area")

            if not self._is_valid_rect(original_work_area):
                self._clear_work_area_state()
                return

            self._set_work_area(tuple(original_work_area))
            self._clear_work_area_state()
            print("Recovered work area from previous unclean exit.")
        except FileNotFoundError:
            return
        except Exception as error:
            print(f"Warning: stale work-area recovery failed: {error}")

    def _is_valid_rect(self, rect):
        """Return True when rect looks like a usable Windows rectangle."""
        if not isinstance(rect, list) or len(rect) != 4:
            return False

        try:
            left, top, right, bottom = (int(value) for value in rect)
        except (TypeError, ValueError):
            return False

        return left < right and top < bottom

    def _get_work_area(self):
        """Return the current Windows work area."""
        work_rect = RECT()
        success = ctypes.windll.user32.SystemParametersInfoW(
            win32con.SPI_GETWORKAREA,
            0,
            ctypes.byref(work_rect),
            0,
        )

        if not success:
            raise ctypes.WinError()

        return (
            work_rect.left,
            work_rect.top,
            work_rect.right,
            work_rect.bottom,
        )

    def _apply_work_area(self):
        """Resize the primary monitor work area to keep windows in usable space."""
        target_monitor = self.all_monitors[self.target_monitor_index]

        if not target_monitor["is_primary"]:
            print(
                "Work-area resize skipped: "
                "SPI_SETWORKAREA only applies reliably to the primary monitor."
            )
            self._restore_work_area()
            return

        if self.original_work_area is None:
            self.original_work_area = self._get_work_area()
            self._save_work_area_state()

        work_area = (
            max(self.original_work_area[0], self.usable_part[0]),
            max(self.original_work_area[1], self.usable_part[1]),
            min(self.original_work_area[2], self.usable_part[2]),
            min(self.original_work_area[3], self.usable_part[3]),
        )

        if work_area[0] >= work_area[2] or work_area[1] >= work_area[3]:
            print("Work-area resize skipped: partition leaves no usable desktop area.")
            return

        self._set_work_area(work_area)

    def _restore_work_area(self):
        """Restore the Windows work area captured before partitioning."""
        if self.original_work_area is None:
            return

        try:
            self._set_work_area(self.original_work_area)
        finally:
            self.original_work_area = None
            self._clear_work_area_state()

    def _update_overlay_window(self):
        """Move, resize, and repaint the overlay window."""
        if not self.overlay_hwnd:
            return

        x = self.overlay_rect["x"]
        y = self.overlay_rect["y"]
        width = max(1, self.overlay_rect["w"])
        height = max(1, self.overlay_rect["h"])

        win32gui.SetWindowPos(
            self.overlay_hwnd,
            None,
            x,
            y,
            width,
            height,
            win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
        )
        win32gui.InvalidateRect(self.overlay_hwnd, None, True)

    def update_boundary(self, new_boundary_x):
        """Set a new boundary coordinate and update dependent geometry."""
        with self.state_lock:
            self.window_boundary_x = self._clamp_boundary(new_boundary_x)
            self._recalculate_geometry()
            self._update_overlay_window()

            if self.is_running:
                try:
                    self._apply_work_area()
                except Exception as error:
                    print(f"Work-area update failed: {error}")

    def set_target_monitor(self, index):
        """Switch the target monitor and reset the boundary for that monitor."""
        with self.state_lock:
            self.target_monitor_index = index
            target_monitor = self.all_monitors[index]
            self.update_boundary(self._default_boundary_for_monitor(target_monitor))

    def set_partition_side(self, partition_on_left):
        """Set the legacy left/right partition option."""
        with self.state_lock:
            self.partition_on_left = partition_on_left
            self.partition_edge = "left" if partition_on_left else "right"
            self.update_boundary(self.window_boundary_x)

    def set_partition_edge(self, edge):
        """Set the partition edge and reset the boundary for that edge."""
        with self.state_lock:
            self.partition_edge = self._validated_partition_edge(edge)
            self.partition_on_left = self.partition_edge == "left"
            target_monitor = self.all_monitors[self.target_monitor_index]
            self.update_boundary(self._default_boundary_for_monitor(target_monitor))

    def register_initial_hotkey(self):
        """Register the startup global hotkey."""
        try:
            keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True)
            print(f"Global hotkey '{self.hotkey}' registered to toggle partitioning.")
        except Exception as error:
            print(f"Error registering initial hotkey: {error}")
            messagebox.showwarning(
                "Hotkey Error",
                (
                    f"Could not register the hotkey '{self.hotkey}'.\n"
                    "Please set a different one in the settings."
                ),
            )

    def set_hotkey(self, new_hotkey):
        """Replace the current global hotkey with a new hotkey."""
        with self.state_lock:
            try:
                keyboard.remove_hotkey(self.hotkey)
            except Exception:
                pass

            try:
                keyboard.add_hotkey(new_hotkey, self.toggle_partition, suppress=True)
                self.hotkey = new_hotkey
                print(f"Hotkey updated to '{self.hotkey}'")
                return True
            except Exception as error:
                print(f"Failed to set new hotkey '{new_hotkey}': {error}")

                try:
                    keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True)
                except Exception:
                    pass

                return False

    def _enforcement_loop(self):
        """Continuously enforce cursor clipping while partitioning is enabled."""
        while self.is_running:
            try:
                with self.state_lock:
                    cursor_clip_rect = self.cursor_clip_rect

                win32api.ClipCursor(cursor_clip_rect)
            except Exception:
                pass

            time.sleep(0.25)

    def toggle_partition(self):
        """Enable partitioning if stopped, or disable it if running."""
        with self.state_lock:
            should_stop = self.is_running

        if should_stop:
            self.stop()
            return

        self.start()

    def start(self):
        """Enable overlay, work-area tiling, and cursor clipping."""
        with self.state_lock:
            if self.is_running:
                return

            self.is_running = True

            try:
                self._apply_work_area()
            except Exception as error:
                print(f"Work-area resize failed: {error}")

            try:
                win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
                self.enforcement_thread = threading.Thread(
                    target=self._enforcement_loop,
                    daemon=True,
                )
                self.enforcement_thread.start()
            except Exception:
                self.is_running = False
                self.enforcement_thread = None
                self._restore_work_area()
                raise

        print("Partition ENABLED.")

        if self.settings_window:
            self.settings_window.update_ui_state()

    def stop(self):
        """Disable partitioning and restore cursor and work-area state."""
        with self.state_lock:
            if not self.is_running:
                return

            self.is_running = False
            enforcement_thread = self.enforcement_thread
            self.enforcement_thread = None

        if enforcement_thread:
            enforcement_thread.join(timeout=1.0)

        with self.state_lock:
            try:
                win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_HIDE)
            except Exception as error:
                print(f"Overlay hide failed: {error}")

            try:
                self._restore_work_area()
            except Exception as error:
                print(f"Work-area restore failed: {error}")

            try:
                virtual_screen_rect = (
                    win32api.GetSystemMetrics(76),
                    win32api.GetSystemMetrics(77),
                    win32api.GetSystemMetrics(78),
                    win32api.GetSystemMetrics(79),
                )
                left, top, width, height = virtual_screen_rect
                win32api.ClipCursor((left, top, left + width, top + height))
            except Exception:
                pass

        print("Partition DISABLED.")

        if self.settings_window:
            self.settings_window.update_ui_state()

    def cleanup(self):
        """Stop the app, restore work area, unregister hotkeys, and save config."""
        cleanup_errors = []

        try:
            self.stop()
        except Exception as error:
            cleanup_errors.append(f"stop failed: {error}")

        try:
            with self.state_lock:
                self._restore_work_area()
        except Exception as error:
            cleanup_errors.append(f"work-area restore failed: {error}")

        try:
            keyboard.unhook_all()
        except Exception as error:
            cleanup_errors.append(f"hotkey cleanup failed: {error}")

        try:
            self.save_config()
        except Exception as error:
            cleanup_errors.append(f"config save failed: {error}")

        for cleanup_error in cleanup_errors:
            print(f"Cleanup warning: {cleanup_error}")


def resource_path(relative_path):
    """Return the correct resource path for source and PyInstaller builds."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def create_tray_icon():
    """Load the tray icon, or create a fallback icon if icon.ico is missing."""
    icon_path = resource_path("icon.ico")

    try:
        image = Image.open(icon_path)
    except FileNotFoundError:
        width = 64
        height = 64
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, width // 2, height), fill="black")

    return image


def main():
    """Start the hidden Tk root, tray icon, and event loop."""
    tk_root = tk.Tk()
    tk_root.withdraw()
    app = DisplayPartitioner(tk_root)

    def show_settings_window(icon=None, item=None):
        """Open or focus the settings window from the tray."""
        if not app.settings_window or not app.settings_window.winfo_exists():
            app.settings_window = SettingsWindow(tk_root, app)
        else:
            app.settings_window.deiconify()
            app.settings_window.focus_force()

    def on_quit(icon):
        """Cleanly shut down the tray app."""
        try:
            app.cleanup()
        finally:
            icon.stop()
            tk_root.after(100, tk_root.destroy)

    def get_enable_text(menu_item):
        """Return the dynamic enable menu label with the current hotkey."""
        return f"Enable Partition ({app.hotkey})"

    menu = Menu(
        item("Settings...", show_settings_window),
        item(
            get_enable_text,
            lambda: app.toggle_partition(),
            checked=lambda menu_item: app.is_running,
        ),
        Menu.SEPARATOR,
        item("Quit", on_quit),
    )

    icon = Icon(
        "DisplayPartitioner",
        create_tray_icon(),
        "Display Partitioner",
        menu,
    )
    icon.default_action = show_settings_window

    threading.Thread(target=icon.run, daemon=True).start()

    print(f"Display Partitioner v{APP_VERSION} is running.")
    tk_root.mainloop()


if __name__ == "__main__":
    main()
