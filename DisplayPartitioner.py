# =============================================================================
# Display Partitioner - A Persistent Monitor Partitioning Utility
# Version: 4.1.0 (Stable Hybrid Locking Model)
#
# Description:
#   This utility uses a hybrid model for window locking:
#   1. An efficient event hook for lag-free handling of dragged windows.
#   2. A slow polling thread to correct system-initiated moves like Maximizing
#      and Aero Snap, preventing infinite loops.
#   A lock ensures both systems work together without race conditions.
# =============================================================================
import sys
import os
import json
import time
import threading

# GUI and System Tray
import tkinter as tk
from tkinter import messagebox, colorchooser
from pystray import MenuItem as item, Icon, Menu
from PIL import Image, ImageDraw

# Windows API and Keyboard Hooks
import win32api
import win32gui
import win32con
import keyboard
import pythoncom
import ctypes
from ctypes import wintypes


# --- CONFIGURATION ---
INITIAL_BOUNDARY_PERCENT = 0.5
DEFAULT_HOTKEY = "win+alt+p"
DEFAULT_OVERLAY_COLOR = "#000000"
DEFAULT_OVERLAY_OPACITY = 100
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'DisplayPartitioner')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')
# -------------------------

class SettingsWindow(tk.Toplevel):
    """The GUI window for configuring all application settings."""
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.app = app_instance
        self.title("Display Partitioner Settings")
        self.geometry("800x490")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Tkinter variables linked to the app state
        self.boundary_var = tk.StringVar(value=str(self.app.window_boundary_x))
        self.is_enabled_var = tk.BooleanVar(value=self.app.is_running)
        self.partition_on_left_var = tk.BooleanVar(value=self.app.partition_on_left)
        self.is_window_locking_var = tk.BooleanVar(value=self.app.is_window_locking_enabled)
        self.hotkey_var = tk.StringVar(value=self.app.hotkey)
        self.color_var = tk.StringVar(value=self.app.overlay_color)
        self.opacity_var = tk.IntVar(value=self.app.overlay_opacity)
        self.color_var.trace_add("write", self.update_color_from_var)

        # --- GUI Elements ---
        self.canvas_width, self.canvas_height = 780, 100
        self.all_monitors = self.app.get_all_monitors()
        self.scale, self.offset_x, self.offset_y = self._calculate_scale()
        self.boundary_line_id, self.shading_rect_id = None, None
        
        self.canvas = tk.Canvas(self, width=self.canvas_width, height=self.canvas_height, bg="#f0f0f0", relief="sunken", borderwidth=1)
        self.canvas.pack(pady=10, padx=10)
        self.canvas.tag_bind("boundary_line", "<B1-Motion>", self.on_drag_line)
        
        selection_frame = tk.Frame(self); selection_frame.pack(pady=5, padx=10, fill='x')
        tk.Label(selection_frame, text="Target Monitor:").grid(row=0, column=0, sticky='w')
        self.monitor_names = [f"Monitor {i} ({mon['Rect'][2]-mon['Rect'][0]}x{mon['Rect'][3]-mon['Rect'][1]})" for i, mon in enumerate(self.all_monitors)]
        self.monitor_var = tk.StringVar(value=self.monitor_names[self.app.target_monitor_index])
        monitor_menu = tk.OptionMenu(selection_frame, self.monitor_var, *self.monitor_names, command=self.on_monitor_select)
        monitor_menu.grid(row=0, column=1, padx=5, sticky='w')
        side_frame = tk.Frame(selection_frame); side_frame.grid(row=0, column=2, padx=20)
        tk.Radiobutton(side_frame, text="Partition Left Side", variable=self.partition_on_left_var, value=True, command=self.on_side_select).pack(anchor='w')
        tk.Radiobutton(side_frame, text="Partition Right Side", variable=self.partition_on_left_var, value=False, command=self.on_side_select).pack(anchor='w')
        
        settings_container = tk.Frame(self); settings_container.pack(pady=5, padx=10, fill='x')
        
        left_frame = tk.LabelFrame(settings_container, text="Controls", padx=10, pady=10); left_frame.pack(side='left', fill='y', padx=(0,5))
        tk.Label(left_frame, text="Boundary Coordinate:").grid(row=0, column=0, pady=2, sticky='w')
        self.entry_box = tk.Entry(left_frame, textvariable=self.boundary_var, width=10)
        self.entry_box.grid(row=0, column=1, padx=5, sticky='w')
        tk.Button(left_frame, text="Set", command=self.apply_text_boundary, width=8).grid(row=0, column=2, sticky='w')
        tk.Label(left_frame, text="Toggle Hotkey:").grid(row=1, column=0, pady=2, sticky='w')
        hotkey_entry = tk.Entry(left_frame, textvariable=self.hotkey_var, width=20)
        hotkey_entry.grid(row=1, column=1, columnspan=2, padx=5, sticky='w')
        tk.Button(left_frame, text="Set Hotkey", command=self.apply_hotkey).grid(row=2, column=1, columnspan=2, pady=(0, 5), sticky='w')
        tk.Checkbutton(left_frame, text="Lock windows within partition", variable=self.is_window_locking_var, command=self.app.toggle_window_locking).grid(row=3, column=0, columnspan=3, pady=(5,0), sticky='w')
        
        right_frame = tk.LabelFrame(settings_container, text="Overlay Appearance", padx=10, pady=10); right_frame.pack(side='left', fill='both', expand=True, padx=(5,0))
        tk.Label(right_frame, text="Color:").grid(row=0, column=0, sticky='nw', pady=2)
        color_input_frame = tk.Frame(right_frame); color_input_frame.grid(row=0, column=1, sticky='w', columnspan=3)
        self.color_preview = tk.Label(color_input_frame, text="    ", bg=self.app.overlay_color, relief='sunken', borderwidth=1)
        self.color_preview.pack(side='left', padx=(0, 5))
        self.color_entry = tk.Entry(color_input_frame, textvariable=self.color_var, width=10)
        self.color_entry.pack(side='left')
        self.color_entry.bind("<Return>", self.apply_hex_color_from_entry)
        tk.Button(right_frame, text="Choose Color...", command=self.on_choose_color).grid(row=0, column=4, sticky='w', padx=10)
        tk.Label(right_frame, text="Opacity:").grid(row=1, column=0, pady=5, sticky='w')
        opacity_slider = tk.Scale(right_frame, from_=0, to=100, orient='horizontal', variable=self.opacity_var, command=self.on_opacity_change, length=200, showvalue=0)
        opacity_slider.grid(row=1, column=1, columnspan=2, sticky='we')
        self.opacity_label = tk.Label(right_frame, textvariable=self.opacity_var)
        self.opacity_label.grid(row=1, column=3, padx=(5,0))
        tk.Label(right_frame, text="%").grid(row=1, column=4, sticky='w')

        action_frame = tk.Frame(self); action_frame.pack(pady=15)
        enable_check = tk.Checkbutton(action_frame, text="Enable Partitioning", variable=self.is_enabled_var, command=self.toggle_partition, font=("Segoe UI", 10, "bold"))
        enable_check.pack(side='left', padx=10)
        close_button = tk.Button(action_frame, text="Close", width=12, command=self.on_close)
        close_button.pack(side='left', padx=10)
        self.update_full_canvas()

    def on_choose_color(self):
        color_code = colorchooser.askcolor(title="Choose overlay color", initialcolor=self.app.overlay_color)
        if color_code and color_code[1]: self.color_var.set(color_code[1])

    def apply_hex_color_from_entry(self, event=None):
        hex_color = self.color_var.get()
        try:
            self.color_entry.winfo_rgb(hex_color) # Validate color
            self.app.set_overlay_color(hex_color)
        except tk.TclError:
            messagebox.showerror("Invalid Color", f"'{hex_color}' is not a valid color code.", parent=self)
            self.color_var.set(self.app.overlay_color)
    
    def update_color_from_var(self, *args):
        new_color = self.color_var.get()
        try:
            self.color_preview.config(bg=new_color)
            self.app.set_overlay_color(new_color)
        except tk.TclError: pass # Ignore intermediate invalid values while typing

    def on_opacity_change(self, value):
        self.app.set_overlay_opacity(int(value))

    def _calculate_scale(self):
        min_x = min(mon['Rect'][0] for mon in self.all_monitors)
        max_x = max(mon['Rect'][2] for mon in self.all_monitors)
        scale = self.canvas_width / (max_x - min_x) * 0.95 if max_x > min_x else 1
        return scale, -min_x, self.canvas_height / 2

    def _draw_monitors(self):
        self.canvas.delete("monitors")
        for i, mon in enumerate(self.all_monitors):
            l, t, r, b = mon['Rect']; h = b - t
            cl, cr = (l + self.offset_x) * self.scale, (r + self.offset_x) * self.scale
            ct, cb = self.offset_y - (h * self.scale / 2), self.offset_y + (h * self.scale / 2)
            fill_color = "#cccccc" if i != self.app.target_monitor_index else "#aaddaa"
            self.canvas.create_rectangle(cl, ct, cr, cb, fill=fill_color, outline="black", width=2, tags="monitors")
            p_str = " (Primary)" if mon['is_primary'] else ""
            self.canvas.create_text((cl + cr) / 2, self.offset_y, text=f"Monitor {i}{p_str}", tags="monitors")

    def _draw_partition_shading(self):
        target_mon = self.all_monitors[self.app.target_monitor_index]
        l, t, r, b = target_mon['Rect']
        h = b-t
        ct, cb = self.offset_y - (h * self.scale / 2), self.offset_y + (h * self.scale / 2)
        boundary_canvas_x = (self.app.window_boundary_x + self.offset_x) * self.scale
        if self.app.partition_on_left: sl, sr = (l + self.offset_x) * self.scale, boundary_canvas_x
        else: sl, sr = boundary_canvas_x, (r + self.offset_x) * self.scale
        if self.shading_rect_id: self.canvas.coords(self.shading_rect_id, sl, ct, sr, cb)
        else: self.shading_rect_id = self.canvas.create_rectangle(sl, ct, sr, cb, fill="#333333", stipple="gray50", outline="", tags="shading")

    def _draw_boundary_line(self):
        canvas_x = (self.app.window_boundary_x + self.offset_x) * self.scale
        if self.boundary_line_id: self.canvas.coords(self.boundary_line_id, canvas_x, 0, canvas_x, self.canvas_height)
        else: self.boundary_line_id = self.canvas.create_line(canvas_x, 0, canvas_x, self.canvas_height, fill="red", width=3, tags="boundary_line")

    def update_full_canvas(self):
        self._draw_monitors(); self._draw_partition_shading(); self._draw_boundary_line(); self.canvas.tag_raise(self.boundary_line_id)

    def on_drag_line(self, event):
        target_mon = self.all_monitors[self.app.target_monitor_index]
        l, _, r, _ = target_mon['Rect']
        canvas_l, canvas_r = (l + self.offset_x) * self.scale, (r + self.offset_x) * self.scale
        canvas_x = max(canvas_l, min(event.x, canvas_r))
        real_x = int((canvas_x / self.scale) - self.offset_x)
        self.boundary_var.set(str(real_x))
        self.app.update_boundary(real_x)
        self.update_full_canvas()

    def apply_text_boundary(self, event=None):
        try:
            self.app.update_boundary(int(self.boundary_var.get()))
            self.update_full_canvas()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid integer.", parent=self)
            self.boundary_var.set(str(self.app.window_boundary_x))

    def apply_hotkey(self):
        new_hotkey = self.hotkey_var.get().strip().lower()
        if not new_hotkey:
            messagebox.showerror("Invalid Input", "Hotkey cannot be empty.", parent=self)
            self.hotkey_var.set(self.app.hotkey)
            return
        if self.app.set_hotkey(new_hotkey):
            messagebox.showinfo("Success", f"Hotkey successfully set to '{new_hotkey}'.", parent=self)
        else:
            messagebox.showerror("Invalid Hotkey", "The entered hotkey string is not valid.", parent=self)
            self.hotkey_var.set(self.app.hotkey)

    def on_monitor_select(self, selection):
        index = self.monitor_names.index(selection)
        self.app.set_target_monitor(index)
        self.boundary_var.set(str(self.app.window_boundary_x))
        self.update_full_canvas()

    def on_side_select(self):
        self.app.set_partition_side(self.partition_on_left_var.get())
        self.boundary_var.set(str(self.app.window_boundary_x))
        self.update_full_canvas()

    def toggle_partition(self): self.app.toggle_partition()
    def update_ui_state(self): self.is_enabled_var.set(self.app.is_running)
    def on_close(self): self.app.settings_window = None; self.destroy()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

class DisplayPartitioner:
    def __init__(self, root):
        self.tk_root = root
        self.is_running, self.enforcement_thread, self.overlay_hwnd, self.settings_window = False, None, None, None
        
        self.is_window_locking_enabled = False
        self.window_drag_hook_thread = None
        self.periodic_check_thread = None
        self.window_fix_lock = threading.Lock()

        self.partition_on_left = True
        self.hotkey = DEFAULT_HOTKEY
        self.overlay_color = DEFAULT_OVERLAY_COLOR
        self.overlay_opacity = DEFAULT_OVERLAY_OPACITY
        
        self.user32 = ctypes.windll.user32
        self.WinEventProcType = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
        )
        self.drag_event_proc = self.WinEventProcType(self._drag_event_callback)

        self.all_monitors = self.get_all_monitors()
        self.load_config()
        self._recalculate_geometry()
        self._create_native_overlay()
        self.register_initial_hotkey()
        if self.is_window_locking_enabled:
            self.start_window_locking()

    def toggle_window_locking(self):
        self.is_window_locking_enabled = not self.is_window_locking_enabled
        print(f"Window locking {'ENABLED' if self.is_window_locking_enabled else 'DISABLED'}.")
        if self.is_window_locking_enabled: self.start_window_locking()
        else: self.stop_window_locking()

    def start_window_locking(self):
        if not self.is_window_locking_enabled: self.is_window_locking_enabled = True
        if not self.window_drag_hook_thread or not self.window_drag_hook_thread.is_alive():
            self.window_drag_hook_thread = threading.Thread(target=self._window_drag_hook_loop, daemon=True)
            self.window_drag_hook_thread.start()
        if not self.periodic_check_thread or not self.periodic_check_thread.is_alive():
            self.periodic_check_thread = threading.Thread(target=self._periodic_check_loop, daemon=True)
            self.periodic_check_thread.start()

    def stop_window_locking(self):
        self.is_window_locking_enabled = False
        if self.window_drag_hook_thread: self.window_drag_hook_thread.join(timeout=0.5)
        if self.periodic_check_thread: self.periodic_check_thread.join(timeout=0.5)

    def _window_drag_hook_loop(self):
        pythoncom.CoInitialize()
        h_hook = self.user32.SetWinEventHook(
            win32con.EVENT_SYSTEM_MOVESIZEEND, win32con.EVENT_SYSTEM_MOVESIZEEND,
            0, self.drag_event_proc, 0, 0,
            win32con.WINEVENT_OUTOFCONTEXT | win32con.WINEVENT_SKIPOWNPROCESS)
        if not h_hook: print("Error: Could not set drag event hook."); pythoncom.CoUninitialize(); return
        print("Window drag event hook installed.")
        
        while self.is_window_locking_enabled:
            pythoncom.PumpWaitingMessages(); time.sleep(0.05)
            
        self.user32.UnhookWinEvent(h_hook); pythoncom.CoUninitialize()
        print("Window drag event hook uninstalled.")

    def _periodic_check_loop(self):
        print("Periodic maximization checker started.")
        while self.is_window_locking_enabled:
            if self.is_running:
                hwnd = win32gui.GetForegroundWindow()
                self._check_and_fix_window(hwnd, check_for_maximize=True)
            time.sleep(0.75)
        print("Periodic maximization checker stopped.")

    def _drag_event_callback(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        if idObject == win32con.OBJID_WINDOW:
            self._check_and_fix_window(hwnd, check_for_maximize=False)

    def _check_and_fix_window(self, hwnd, check_for_maximize):
        if not self.window_fix_lock.acquire(blocking=False): return
        try:
            if not self.is_running or not self.is_window_locking_enabled: return
            if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd): return

            window_monitor_h = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            target_monitor_h = self.all_monitors[self.target_monitor_index]['Handle']
            if window_monitor_h != target_monitor_h: return

            ux, uy, uw, uh = self.get_target_monitor_usable_rect()
            placement = win32gui.GetWindowPlacement(hwnd)
            is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED

            if check_for_maximize and is_maximized:
                current_rect = win32gui.GetWindowRect(hwnd)
                if current_rect != (ux, uy, ux + uw, uy + uh):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.MoveWindow(hwnd, ux, uy, uw, uh, True)
            
            elif not is_maximized:
                l_win, t_win, r_win, b_win = win32gui.GetWindowRect(hwnd)
                w_win, h_win = r_win - l_win, b_win - t_win
                new_x, new_y = l_win, t_win
                
                if l_win < ux: new_x = ux
                if r_win > ux + uw: new_x = ux + uw - w_win
                if t_win < uy: new_y = uy
                if b_win > uy + uh: new_y = uy + uh - h_win

                if int(new_x) != l_win or int(new_y) != t_win:
                     win32gui.MoveWindow(hwnd, int(new_x), int(new_y), w_win, h_win, True)
        except win32gui.error: pass
        finally:
            self.window_fix_lock.release()

    def get_target_monitor_usable_rect(self):
        tm_rect = self.all_monitors[self.target_monitor_index]['Rect']
        tm_l, tm_t, tm_r, tm_b = tm_rect
        if self.partition_on_left:
            x, y = self.window_boundary_x, tm_t; w, h = tm_r - self.window_boundary_x, tm_b - tm_t
        else:
            x, y = tm_l, tm_t; w, h = self.window_boundary_x - tm_l, tm_b - tm_t
        return (x, y, w, h)
        
    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
            self.hotkey = config.get('hotkey', DEFAULT_HOTKEY)
            self.partition_on_left = config.get('partition_on_left', True)
            self.is_window_locking_enabled = config.get('is_window_locking_enabled', False)
            self.overlay_color = config.get('overlay_color', DEFAULT_OVERLAY_COLOR)
            self.overlay_opacity = config.get('overlay_opacity', DEFAULT_OVERLAY_OPACITY)
            saved_monitor_index = config.get('target_monitor_index', 0)
            if saved_monitor_index >= len(self.all_monitors): self.target_monitor_index = 0
            else: self.target_monitor_index = saved_monitor_index
            initial_mon = self.all_monitors[self.target_monitor_index]
            default_boundary = int(initial_mon['Rect'][0] + (initial_mon['Rect'][2] - initial_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)
            self.window_boundary_x = config.get('window_boundary_x', default_boundary)
            print("Configuration loaded successfully.")
        except (FileNotFoundError, json.JSONDecodeError):
            print("No valid config file found. Using default settings.")
            self.target_monitor_index = self._find_initial_target_monitor()
            initial_mon = self.all_monitors[self.target_monitor_index]
            self.window_boundary_x = int(initial_mon['Rect'][0] + (initial_mon['Rect'][2] - initial_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)

    def save_config(self):
        config = {
            'target_monitor_index': self.target_monitor_index, 'window_boundary_x': self.window_boundary_x,
            'partition_on_left': self.partition_on_left, 'hotkey': self.hotkey,
            'is_window_locking_enabled': self.is_window_locking_enabled,
            'overlay_color': self.overlay_color, 'overlay_opacity': self.overlay_opacity
        }
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
            print(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e: print(f"Error saving configuration: {e}")

    def get_all_monitors(self):
        monitors = []
        [monitors.append({'Handle':h, 'Rect':r, 'is_primary':win32api.GetMonitorInfo(h).get('Flags')==1, 'Device': win32api.GetMonitorInfo(h).get('Device')}) 
         for h,_,r in win32api.EnumDisplayMonitors()]
        return monitors
    
    def _find_initial_target_monitor(self):
        for i, mon in enumerate(self.all_monitors):
            if not mon['is_primary']: return i
        return 0

    def _recalculate_geometry(self):
        target_mon = self.all_monitors[self.target_monitor_index]
        tm_l, tm_t, tm_r, tm_b = target_mon['Rect']
        if self.partition_on_left:
            self.overlay_rect = {'x': tm_l, 'y': tm_t, 'w': self.window_boundary_x - tm_l, 'h': tm_b - tm_t}
        else:
            self.overlay_rect = {'x': self.window_boundary_x, 'y': tm_t, 'w': tm_r - self.window_boundary_x, 'h': tm_b - tm_t}
        primary_mon = next((m for m in self.all_monitors if m['is_primary']), self.all_monitors[0])
        target_usable_x, target_usable_y, target_usable_w, target_usable_h = self.get_target_monitor_usable_rect()
        target_usable_part = (target_usable_x, target_usable_y, target_usable_x + target_usable_w, target_usable_y + target_usable_h)
        primary_rect = primary_mon['Rect'] if self.all_monitors.index(primary_mon) != self.target_monitor_index else target_usable_part
        self.cursor_clip_rect = (min(primary_rect[0], target_usable_part[0]), min(primary_rect[1], target_usable_part[1]),
                                 max(primary_rect[2], target_usable_part[2]), max(primary_rect[3], target_usable_part[3]))

    def cleanup(self):
        self.stop(); self.stop_window_locking(); keyboard.unhook_all(); self.save_config()

    def _wnd_proc(self, hwnd, msg, wParam, lParam):
        if msg == win32con.WM_ERASEBKGND:
            hdc, rect = wParam, win32gui.GetClientRect(hwnd)
            rgb = hex_to_rgb(self.overlay_color); brush = win32gui.CreateSolidBrush(win32api.RGB(*rgb))
            win32gui.FillRect(hdc, rect, brush); win32gui.DeleteObject(brush)
            return 1
        return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)
        
    def set_overlay_color(self, hex_color):
        self.overlay_color = hex_color
        if self.overlay_hwnd: win32gui.InvalidateRect(self.overlay_hwnd, None, True)
        
    def set_overlay_opacity(self, opacity_percent):
        self.overlay_opacity = opacity_percent; alpha_value = int(opacity_percent / 100 * 255)
        win32gui.SetLayeredWindowAttributes(self.overlay_hwnd, 0, alpha_value, win32con.LWA_ALPHA)
        
    def _create_native_overlay(self):
        h_instance = win32api.GetModuleHandle(); class_name = "DPOverlay"; wnd_class = win32gui.WNDCLASS()
        wnd_class.lpfnWndProc = self._wnd_proc; wnd_class.hInstance = h_instance; wnd_class.hbrBackground = 0; wnd_class.lpszClassName = class_name
        try: win32gui.RegisterClass(wnd_class)
        except win32gui.error as err:
            if err.winerror != 1410: raise
        ex_style = win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
        self.overlay_hwnd = win32gui.CreateWindowEx(ex_style, class_name, "DPO", win32con.WS_POPUP, self.overlay_rect['x'], self.overlay_rect['y'], self.overlay_rect['w'], self.overlay_rect['h'], None, None, h_instance, None)
        self.set_overlay_opacity(self.overlay_opacity)
        
    def update_boundary(self, new_boundary_x):
        self.window_boundary_x = new_boundary_x; self._recalculate_geometry()
        win32gui.SetWindowPos(self.overlay_hwnd, None, self.overlay_rect['x'], self.overlay_rect['y'], self.overlay_rect['w'], self.overlay_rect['h'], win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
        
    def set_target_monitor(self, index):
        self.target_monitor_index = index; self._recalculate_geometry()
        target_mon = self.all_monitors[index]; new_boundary = int(target_mon['Rect'][0] + (target_mon['Rect'][2] - target_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)
        self.update_boundary(new_boundary)
        
    def set_partition_side(self, partition_on_left):
        self.partition_on_left = partition_on_left; self._recalculate_geometry(); self.update_boundary(self.window_boundary_x)
        
    def register_initial_hotkey(self):
        try: keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True); print(f"Global hotkey '{self.hotkey}' registered to toggle partitioning.")
        except Exception as e: print(f"Error registering initial hotkey: {e}"); messagebox.showwarning("Hotkey Error", f"Could not register the hotkey '{self.hotkey}'.\nPlease set a different one in the settings.")
        
    def set_hotkey(self, new_hotkey):
        try: keyboard.remove_hotkey(self.hotkey)
        except (KeyError, AttributeError): pass
        try: keyboard.add_hotkey(new_hotkey, self.toggle_partition, suppress=True); self.hotkey = new_hotkey; print(f"Hotkey updated to '{self.hotkey}'"); return True
        except Exception as e:
            print(f"Failed to set new hotkey '{new_hotkey}': {e}");
            try: keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True)
            except Exception: pass
            return False
            
    def _enforcement_loop(self):
        while self.is_running:
            try: win32api.ClipCursor(self.cursor_clip_rect)
            except Exception: pass
            time.sleep(0.25)
            
    def toggle_partition(self): self.start() if not self.is_running else self.stop()
    
    def start(self):
        if self.is_running: return
        self.is_running = True; win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
        self.enforcement_thread = threading.Thread(target=self._enforcement_loop, daemon=True)
        self.enforcement_thread.start(); print("Partition ENABLED.")
        if self.settings_window: self.settings_window.update_ui_state()
        
    def stop(self):
        if not self.is_running: return
        self.is_running = False
        if self.enforcement_thread: self.enforcement_thread.join(timeout=1.0)
        win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_HIDE)
        try:
            r=(win32api.GetSystemMetrics(76),win32api.GetSystemMetrics(77),win32api.GetSystemMetrics(78),win32api.GetSystemMetrics(79))
            win32api.ClipCursor((r[0], r[1], r[0]+r[2], r[1]+r[3]))
        except Exception: pass
        print("Partition DISABLED.");
        if self.settings_window: self.settings_window.update_ui_state()

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def create_tray_icon():
    icon_path = resource_path("icon.ico")
    try: image = Image.open(icon_path)
    except FileNotFoundError:
        w, h = 64, 64; i = Image.new('RGB', (w, h), 'white')
        d = ImageDraw.Draw(i); d.rectangle((0, 0, w // 2, h), fill='black')
        return i
    return image

def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception as e:
        print(f"Could not set DPI awareness (requires Win8.1+): {e}")

    tk_root = tk.Tk(); tk_root.withdraw()
    app = DisplayPartitioner(tk_root)
    def show_settings_window(icon=None,item=None):
        if not app.settings_window or not app.settings_window.winfo_exists():
            app.settings_window=SettingsWindow(tk_root,app)
        else: app.settings_window.deiconify(); app.settings_window.focus_force()
    def on_quit(icon): app.cleanup(); icon.stop(); tk_root.after(100, tk_root.destroy)
    def get_enable_text(item): return f"Enable Partition ({app.hotkey})"
    menu = Menu(
        item('Settings...', show_settings_window), 
        item(get_enable_text, lambda:app.toggle_partition(), checked=lambda item:app.is_running),
        Menu.SEPARATOR, item('Quit', on_quit))
    icon = Icon("DisplayPartitioner", create_tray_icon(), "Display Partitioner", menu)
    icon.default_action = show_settings_window
    threading.Thread(target=icon.run, daemon=True).start()
    print("Display Partitioner (Stable) is running.")
    tk_root.mainloop()

if __name__ == "__main__":
    main()