# =============================================================================
# Display Partitioner - A Persistent Monitor Partitioning Utility
#
# Author: Built by AI and you, the user!
# Version: 1.1 (Stable - Renamed)
#
# Description:
#   This utility is designed for users with a dual-monitor setup where one
#   monitor needs to be partially disabled. It creates a persistent "hard wall"
#   for the mouse cursor and a visual black overlay, effectively partitioning
#   a physical screen without any performance lag.
#
# =============================================================================

import win32api
import win32gui
import win32con
import threading
import time
from pystray import MenuItem as item, Icon
from PIL import Image, ImageDraw

# --- USER CONFIGURATION ---
# This is the only number you need to change.
# Set this to the absolute X-coordinate where your usable screen should begin.
BOUNDARY_X_COORDINATE = -967
# -------------------------

class DisplayPartitioner:
    """
    Manages the core logic for screen partitioning, including the visual
    overlay and the persistent cursor confinement.
    """
    def __init__(self):
        """Initializes the application state and calculates required geometry."""
        self.is_running = False
        self.enforcement_thread = None
        self.overlay_hwnd = None  # The handle for our native overlay window

        # --- Hardcoded Geometry ---
        MONITOR_START_X = -1920
        PRIMARY_MONITOR_END_X = 1920
        MONITOR_HEIGHT = 1080

        self.cursor_clip_rect = (BOUNDARY_X_COORDINATE, 0, PRIMARY_MONITOR_END_X, MONITOR_HEIGHT)
        overlay_width = BOUNDARY_X_COORDINATE - MONITOR_START_X
        self.overlay_rect = {'x': MONITOR_START_X, 'y': 0, 'w': overlay_width, 'h': MONITOR_HEIGHT}

        self._create_native_overlay()
        print(f"Ready. Hard boundary and overlay set to x={BOUNDARY_X_COORDINATE}")

    def _create_native_overlay(self):
        """Creates a simple, borderless black window using pure Win32 API calls."""
        h_instance = win32api.GetModuleHandle()
        class_name = "SimpleBlackOverlay"
        wnd_class = win32gui.WNDCLASS()
        wnd_class.lpfnWndProc = lambda hwnd, msg, wparam, lparam: win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        wnd_class.hInstance = h_instance
        wnd_class.hbrBackground = win32gui.GetStockObject(win32con.BLACK_BRUSH)
        wnd_class.lpszClassName = class_name
        
        try:
            win32gui.RegisterClass(wnd_class)
        except win32gui.error:
            pass 

        self.overlay_hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT,
            class_name, "DisplayPartitionerOverlay", win32con.WS_POPUP,
            self.overlay_rect['x'], self.overlay_rect['y'],
            self.overlay_rect['w'], self.overlay_rect['h'],
            None, None, h_instance, None
        )

    def _enforcement_loop(self):
        """
        The "watchdog" loop. Its only job is to re-apply the cursor clip
        constantly, ensuring it is never lost due to system actions.
        """
        while self.is_running:
            try:
                win32api.ClipCursor(self.cursor_clip_rect)
            except Exception:
                pass 
            time.sleep(0.25)

    def start(self):
        """Activates the overlay and the enforcement loop."""
        if self.is_running: return
        print("Starting... Activating overlay and hard cursor confinement.")
        self.is_running = True
        
        win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
        
        self.enforcement_thread = threading.Thread(target=self._enforcement_loop, daemon=True)
        self.enforcement_thread.start()
        
    def stop(self):
        """Deactivates the overlay and enforcement loop, releasing the cursor."""
        if not self.is_running: return
        print("Stopping... Deactivating.")
        self.is_running = False

        if self.enforcement_thread:
            self.enforcement_thread.join(timeout=1.0)
        
        win32gui.ShowWindow(self.overlay_hwnd, win32con.SW_HIDE)
        
        try:
            x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            win32api.ClipCursor((x, y, x + w, y + h))
            print("Cursor clip released.")
        except Exception:
            pass

def create_tray_icon():
    """
    Creates the image for the system tray icon. It first tries to load a
    local 'icon.ico' file. If that fails, it generates a default
    placeholder image.
    """
    try:
        image = Image.open("icon.ico")
    except FileNotFoundError:
        print("Warning: 'icon.ico' not found. Creating a default icon.")
        width, height = 64, 64
        image = Image.new('RGB', (width, height), 'white')
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, width // 2, height), fill='black')
    return image

def main():
    """The main entry point for the application."""
    app = DisplayPartitioner()

    def on_quit(tray_icon):
        app.stop()
        tray_icon.stop()

    def on_toggle_enable(tray_icon, menu_item):
        if not app.is_running:
            app.start()
        else:
            app.stop()

    menu = (
        item('Enable Partition', on_toggle_enable, checked=lambda item: app.is_running),
        item('Quit', on_quit)
    )

    icon = Icon("DisplayPartitioner", create_tray_icon(), "Display Partitioner", menu)
    
    print("Display Partitioner is running in the system tray.")
    
    icon.run()

if __name__ == "__main__":
    main()