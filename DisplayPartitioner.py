# =============================================================================
# Display Partitioner - A Persistent Monitor Partitioning Utility
# Version: 2.0.0 
#
# Description:
#   This utility allows users to partition any monitor via a user-friendly GUI.
#   It now saves all user settings (target monitor, boundary, side, hotkey)
#   and automatically loads them on the next startup.
# =============================================================================
import sys
import win32api
import win32gui
import win32con
import tkinter as tk
from tkinter import messagebox
import threading
import time
from pystray import MenuItem as item, Icon, Menu
from PIL import Image, ImageDraw
import keyboard
import json
import os

# --- INITIAL CONFIGURATION ---
INITIAL_BOUNDARY_PERCENT = 0.5
DEFAULT_HOTKEY = "win+alt+p"
# --- CONFIG FILE LOCATION ---
# Standard location for application data on Windows
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'DisplayPartitioner')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')
# -------------------------

class SettingsWindow(tk.Toplevel):
    """The GUI window for configuring the partition boundary and settings."""
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.app = app_instance
        self.title("Display Partitioner Settings")
        self.geometry("800x400")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Tkinter variables to link UI elements to the app state
        self.boundary_var = tk.StringVar(value=str(self.app.window_boundary_x))
        self.is_enabled_var = tk.BooleanVar(value=self.app.is_running)
        self.partition_on_left_var = tk.BooleanVar(value=self.app.partition_on_left)
        self.hotkey_var = tk.StringVar(value=self.app.hotkey)

        self.canvas_width, self.canvas_height = 780, 100
        self.all_monitors = self.app.get_all_monitors()
        self.scale, self.offset_x, self.offset_y = self._calculate_scale()
        self.boundary_line_id = None
        self.shading_rect_id = None
        
        # --- GUI Elements (Code is identical to v3.2, no changes needed here) ---
        self.canvas = tk.Canvas(self, width=self.canvas_width, height=self.canvas_height, bg="#f0f0f0", relief="sunken", borderwidth=1)
        self.canvas.pack(pady=10, padx=10)
        self.canvas.tag_bind("boundary_line", "<B1-Motion>", self.on_drag_line)
        selection_frame = tk.Frame(self); selection_frame.pack(pady=5, padx=10, fill='x')
        tk.Label(selection_frame, text="Target Monitor:").grid(row=0, column=0, sticky='w')
        self.monitor_names = [f"Monitor {i} ({mon['Rect'][2]-mon['Rect'][0]}x{mon['Rect'][3]-mon['Rect'][1]})" for i, mon in enumerate(self.all_monitors)]
        self.monitor_var = tk.StringVar(value=self.monitor_names[self.app.target_monitor_index])
        monitor_menu = tk.OptionMenu(selection_frame, self.monitor_var, *self.monitor_names, command=self.on_monitor_select)
        monitor_menu.grid(row=0, column=1, padx=5, sticky='w')
        side_frame = tk.Frame(selection_frame)
        side_frame.grid(row=0, column=2, padx=20)
        tk.Radiobutton(side_frame, text="Partition Left Side", variable=self.partition_on_left_var, value=True, command=self.on_side_select).pack(anchor='w')
        tk.Radiobutton(side_frame, text="Partition Right Side", variable=self.partition_on_left_var, value=False, command=self.on_side_select).pack(anchor='w')
        control_frame = tk.Frame(self); control_frame.pack(pady=5, padx=10, fill='x')
        tk.Label(control_frame, text="Boundary Coordinate:").grid(row=0, column=0, padx=5, sticky='w')
        self.entry_box = tk.Entry(control_frame, textvariable=self.boundary_var, width=10)
        self.entry_box.grid(row=0, column=1, padx=5)
        set_button = tk.Button(control_frame, text="Set", command=self.apply_text_boundary)
        set_button.grid(row=0, column=2, padx=5)
        hotkey_frame = tk.Frame(self); hotkey_frame.pack(pady=10, padx=10, fill='x')
        tk.Label(hotkey_frame, text="Toggle Hotkey:").grid(row=0, column=0, padx=5, sticky='w')
        hotkey_entry = tk.Entry(hotkey_frame, textvariable=self.hotkey_var, width=20)
        hotkey_entry.grid(row=0, column=1, padx=5)
        set_hotkey_button = tk.Button(hotkey_frame, text="Set Hotkey", command=self.apply_hotkey)
        set_hotkey_button.grid(row=0, column=2, padx=5)
        tk.Label(hotkey_frame, text="(e.g., 'ctrl+alt+p', 'win+shift+x')", fg="grey").grid(row=0, column=3, padx=10, sticky='w')
        action_frame = tk.Frame(self); action_frame.pack(pady=15)
        enable_check = tk.Checkbutton(action_frame, text="Enable Partitioning", variable=self.is_enabled_var, command=self.toggle_partition, font=("Segoe UI", 10, "bold"))
        enable_check.pack(side='left', padx=10)
        close_button = tk.Button(action_frame, text="Close", width=12, command=self.on_close)
        close_button.pack(side='left', padx=10)
        self.update_full_canvas()
        
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
        l, t, r, b = target_mon['Rect']; h = b-t
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
        self._draw_monitors(); self._draw_partition_shading(); self._draw_boundary_line()
        self.canvas.tag_raise(self.boundary_line_id)
    def on_drag_line(self, event):
        target_mon = self.all_monitors[self.app.target_monitor_index]
        l, _, r, _ = target_mon['Rect']
        canvas_l = (l + self.offset_x) * self.scale; canvas_r = (r + self.offset_x) * self.scale
        canvas_x = max(canvas_l, min(event.x, canvas_r))
        real_x = int((canvas_x / self.scale) - self.offset_x)
        self.boundary_var.set(str(real_x)); self.app.update_boundary(real_x); self.update_full_canvas()
    def apply_text_boundary(self, event=None):
        try: self.app.update_boundary(int(self.boundary_var.get())); self.update_full_canvas()
        except ValueError: messagebox.showerror("Invalid Input", "Please enter a valid integer.", parent=self); self.boundary_var.set(str(self.app.window_boundary_x))
    def apply_hotkey(self):
        new_hotkey = self.hotkey_var.get().strip().lower()
        if not new_hotkey: messagebox.showerror("Invalid Input", "Hotkey cannot be empty.", parent=self); self.hotkey_var.set(self.app.hotkey); return
        if self.app.set_hotkey(new_hotkey): messagebox.showinfo("Success", f"Hotkey successfully set to '{new_hotkey}'.", parent=self)
        else: messagebox.showerror("Invalid Hotkey", "The entered hotkey string is not valid.", parent=self); self.hotkey_var.set(self.app.hotkey)
    def on_monitor_select(self, selection):
        index = self.monitor_names.index(selection); self.app.set_target_monitor(index)
        self.boundary_var.set(str(self.app.window_boundary_x)); self.update_full_canvas()
    def on_side_select(self):
        self.app.set_partition_side(self.partition_on_left_var.get())
        self.boundary_var.set(str(self.app.window_boundary_x)); self.update_full_canvas()
    def toggle_partition(self): self.app.toggle_partition()
    def update_ui_state(self): self.is_enabled_var.set(self.app.is_running)
    def on_close(self): self.app.settings_window = None; self.destroy()

class DisplayPartitioner:
    def __init__(self, root):
        self.tk_root = root
        self.is_running, self.enforcement_thread, self.overlay_hwnd, self.settings_window = False, None, None, None
        
        # Set defaults first
        self.partition_on_left = True
        self.hotkey = DEFAULT_HOTKEY
        
        # Load current system state
        self.all_monitors = self.get_all_monitors()

        # Load config or set initial values
        self.load_config() # This will override defaults if a config file exists
        
        self._recalculate_geometry()
        self._create_native_overlay()
        self.register_initial_hotkey()

    def load_config(self):
        """Loads settings from the config file. If it fails, uses defaults."""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # --- Load values with validation and fallbacks ---
            self.hotkey = config.get('hotkey', DEFAULT_HOTKEY)
            self.partition_on_left = config.get('partition_on_left', True)
            
            # Validate monitor index - crucial if monitor setup has changed
            saved_monitor_index = config.get('target_monitor_index', 0)
            if saved_monitor_index >= len(self.all_monitors):
                print(f"Warning: Saved monitor index ({saved_monitor_index}) is invalid. Falling back to monitor 0.")
                self.target_monitor_index = 0
            else:
                self.target_monitor_index = saved_monitor_index

            # If boundary is not saved, calculate it. Otherwise, use saved value.
            initial_mon = self.all_monitors[self.target_monitor_index]
            default_boundary = int(initial_mon['Rect'][0] + (initial_mon['Rect'][2] - initial_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)
            self.window_boundary_x = config.get('window_boundary_x', default_boundary)

            print("Configuration loaded successfully.")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"No valid config file found ({e}). Using default settings.")
            # Set initial values for a fresh start
            self.target_monitor_index = self._find_initial_target_monitor()
            initial_mon = self.all_monitors[self.target_monitor_index]
            self.window_boundary_x = int(initial_mon['Rect'][0] + (initial_mon['Rect'][2] - initial_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)

    def save_config(self):
        """Saves current settings to the config file."""
        config = {
            'target_monitor_index': self.target_monitor_index,
            'window_boundary_x': self.window_boundary_x,
            'partition_on_left': self.partition_on_left,
            'hotkey': self.hotkey
        }
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True) # Ensure directory exists
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get_all_monitors(self):
        monitors = []; [monitors.append({'Handle':h, 'Rect':r, 'is_primary':win32api.GetMonitorInfo(h).get('Flags')==1, 'Device': win32api.GetMonitorInfo(h).get('Device')}) for h,_,r in win32api.EnumDisplayMonitors()]
        return monitors
    
    def _find_initial_target_monitor(self):
        for i, mon in enumerate(self.all_monitors):
            if not mon['is_primary']: return i
        return 0

    def _recalculate_geometry(self):
        target_mon = self.all_monitors[self.target_monitor_index]
        target_l, target_t, target_r, target_b = target_mon['Rect']
        primary_mon = next((m for m in self.all_monitors if m['is_primary']), self.all_monitors[0])
        if self.partition_on_left:
            usable_part = (self.window_boundary_x, target_t, target_r, target_b)
            self.overlay_rect = {'x': target_l, 'y': target_t, 'w': self.window_boundary_x - target_l, 'h': target_b - target_t}
        else:
            usable_part = (target_l, target_t, self.window_boundary_x, target_b)
            self.overlay_rect = {'x': self.window_boundary_x, 'y': target_t, 'w': target_r - self.window_boundary_x, 'h': target_b - target_t}
        primary_rect = primary_mon['Rect'] if self.target_monitor_index != self.all_monitors.index(primary_mon) else usable_part
        self.cursor_clip_rect = (min(primary_rect[0], usable_part[0]), min(primary_rect[1], usable_part[1]),
                                 max(primary_rect[2], usable_part[2]), max(primary_rect[3], usable_part[3]))
        # print(f"Geometry updated. Boundary: x={self.window_boundary_x}, Side: {'Left' if self.partition_on_left else 'Right'}")

    def update_boundary(self, new_boundary_x):
        self.window_boundary_x = new_boundary_x
        self._recalculate_geometry()
        win32gui.SetWindowPos(self.overlay_hwnd, None, self.overlay_rect['x'], self.overlay_rect['y'], self.overlay_rect['w'], self.overlay_rect['h'], win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
        
    def set_target_monitor(self, index):
        self.target_monitor_index = index
        target_mon = self.all_monitors[index]
        new_boundary = int(target_mon['Rect'][0] + (target_mon['Rect'][2] - target_mon['Rect'][0]) * INITIAL_BOUNDARY_PERCENT)
        self.update_boundary(new_boundary)

    def set_partition_side(self, partition_on_left):
        self.partition_on_left = partition_on_left
        self.update_boundary(self.window_boundary_x)

    def register_initial_hotkey(self):
        try:
            keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True)
            print(f"Global hotkey '{self.hotkey}' registered to toggle partitioning.")
        except Exception as e:
            print(f"Error registering initial hotkey: {e}")
            messagebox.showwarning("Hotkey Error", f"Could not register the hotkey '{self.hotkey}'.\nPlease set a different one in the settings.")

    def set_hotkey(self, new_hotkey):
        try: keyboard.remove_hotkey(self.hotkey)
        except (KeyError, AttributeError): pass
        try:
            keyboard.add_hotkey(new_hotkey, self.toggle_partition, suppress=True)
            self.hotkey = new_hotkey
            print(f"Hotkey updated to '{self.hotkey}'")
            return True
        except Exception as e:
            print(f"Failed to set new hotkey '{new_hotkey}': {e}")
            try: keyboard.add_hotkey(self.hotkey, self.toggle_partition, suppress=True)
            except Exception: pass
            return False

    def _create_native_overlay(self):
        h_instance = win32api.GetModuleHandle(); class_name = "DPOverlay"
        wnd_class = win32gui.WNDCLASS(); wnd_class.lpfnWndProc = lambda h,m,w,l: win32gui.DefWindowProc(h,m,w,l)
        wnd_class.hInstance, wnd_class.hbrBackground, wnd_class.lpszClassName = h_instance, win32gui.GetStockObject(4), class_name
        try: win32gui.RegisterClass(wnd_class)
        except win32gui.error: pass
        self.overlay_hwnd = win32gui.CreateWindowEx(win32con.WS_EX_TOPMOST|win32con.WS_EX_TOOLWINDOW|win32con.WS_EX_TRANSPARENT, class_name, "DPO", win32con.WS_POPUP,
                                                   self.overlay_rect['x'], self.overlay_rect['y'], self.overlay_rect['w'], self.overlay_rect['h'], None, None, h_instance, None)
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
        
    def cleanup(self):
        self.stop()
        keyboard.unhook_all()
        self.save_config() # <-- SAVE CONFIGURATION ON CLEAN EXIT


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)



def create_tray_icon():
    """Creates the tray icon image, handling the path for bundled executables."""
    icon_path = resource_path("icon.ico")
    try:
        image = Image.open(icon_path)
    except FileNotFoundError:
        # Fallback if icon is missing
        w, h = 64, 64
        i = Image.new('RGB', (w, h), 'white')
        d = ImageDraw.Draw(i)
        d.rectangle((0, 0, w // 2, h), fill='black')
        return i
    return image

def main():
    tk_root = tk.Tk(); tk_root.withdraw()
    app = DisplayPartitioner(tk_root)
    def show_settings_window(icon=None,item=None):
        if not app.settings_window or not app.settings_window.winfo_exists(): app.settings_window=SettingsWindow(tk_root,app)
        else: app.settings_window.deiconify();app.settings_window.focus_force()
    def on_quit(icon): app.cleanup();icon.stop();tk_root.after(100, tk_root.destroy)
    
    def get_enable_text(item): return f"Enable Partition ({app.hotkey})"
        
    menu = Menu(item('Settings...', show_settings_window), 
                item(get_enable_text, lambda:app.toggle_partition(), checked=lambda item:app.is_running),
                Menu.SEPARATOR, item('Quit', on_quit))

    icon = Icon("DisplayPartitioner", create_tray_icon(), "Display Partitioner", menu)
    icon.default_action = show_settings_window
    threading.Thread(target=icon.run, daemon=True).start()
    
    print("Display Partitioner (Persistence Version) is running.")
    tk_root.mainloop()

if __name__ == "__main__":
    main()