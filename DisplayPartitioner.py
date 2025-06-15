# =============================================================================
# Display Zone Manager
# Version: 3.0.0 (Stable - Tkinter Overlay Architecture)
#
# Description:
#   A comprehensive, stable window management utility. This version migrates
#   the overlay from a native Win32 window to a more stable Tkinter-based
#   architecture, resolving all startup and handle-invalidation errors.
# =============================================================================
import sys, os, json, time, threading, math, tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from pystray import MenuItem as item, Icon, Menu
from PIL import Image, ImageDraw, ImageTk
import win32api, win32gui, win32con, keyboard, pythoncom, ctypes
from ctypes import wintypes

# --- CONFIGURATION & CONSTANTS ---
APP_NAME = "DisplayZoneManager"
CONFIG_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')
DEFAULT_HOTKEY = "win+alt+z"
DEFAULT_OVERLAY_COLOR = "#000000"
DEFAULT_OVERLAY_OPACITY = 50
# NATIVE_OVERLAY_CLASS no longer needed

# --- HELPER CLASSES AND FUNCTIONS ---
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# --- FINAL DYNAMIC LAYOUT LOGIC ---

class DynamicProportionalLayout:
    """
    An intelligent layout that adapts to the number of windows and the
    aspect ratio of the tiling zone, following specific user rules.
    """
    def calculate(self, windows, rect):
        positions = {}
        x, y, w, h = rect
        num_windows = len(windows)

        if not num_windows:
            return positions

        # --- Rule for 1 window ---
        if num_windows == 1:
            positions[windows[0]] = (x, y, w, h)
            return positions

        # Determine if the tiling zone is wider than it is tall.
        is_horizontal = w > h

        # --- Rule for 2 windows ---
        if num_windows == 2:
            if is_horizontal: # Split vertically
                positions[windows[0]] = (x, y, w // 2, h)
                positions[windows[1]] = (x + w // 2, y, w - (w // 2), h)
            else: # Split horizontally
                positions[windows[0]] = (x, y, w, h // 2)
                positions[windows[1]] = (x, y + h // 2, w, h - (h // 2))
            return positions

        # --- Rule for 3 windows (Master/Stack layout) ---
        if num_windows == 3:
            if is_horizontal: # Master on the side
                positions[windows[0]] = (x, y, w // 2, h) # Master
                positions[windows[1]] = (x + w // 2, y, w - (w // 2), h // 2) # Stack 1
                positions[windows[2]] = (x + w // 2, y + h // 2, w - (w // 2), h - (h // 2)) # Stack 2
            else: # Master on top
                positions[windows[0]] = (x, y, w, h // 2) # Master
                positions[windows[1]] = (x, y + h // 2, w // 2, h - (h // 2)) # Stack 1
                positions[windows[2]] = (x + w // 2, y + h // 2, w - (w // 2), h - (h // 2)) # Stack 2
            return positions

        # --- Fallback Rule for 4+ windows (Smart Grid) ---
        if num_windows >= 4:
            cols = math.ceil(math.sqrt(num_windows))
            rows = math.ceil(num_windows / cols)
            
            cell_height = h // rows
            window_index = 0
            for r in range(int(rows)):
                remaining_windows = num_windows - window_index
                windows_in_this_row = min(int(cols), remaining_windows)
                if windows_in_this_row == 0: break
                
                cell_width = w // windows_in_this_row
                for c in range(windows_in_this_row):
                    hwnd = windows[window_index]
                    pos_x = x + c * cell_width
                    pos_y = y + r * cell_height
                    
                    pos_w = w - (c * cell_width) if c == windows_in_this_row - 1 else cell_width
                    pos_h = h - (r * cell_height) if r == rows - 1 else cell_height
                    
                    positions[hwnd] = (pos_x, pos_y, pos_w, pos_h)
                    window_index += 1
            return positions
        
        return positions


class LayoutManager:
    """Manages which layout algorithm to use."""
    def __init__(self):
        # We now use our new, intelligent dynamic layout class.
        self.layout = DynamicProportionalLayout()

    def tile(self, windows, rect):
        return self.layout.calculate(windows, rect) if windows and rect else None

# --- UI CLASS ---

# ==============================================================================
#  Replace your ENTIRE SettingsWindow class with this one
# ==============================================================================
class SettingsWindow(tk.Toplevel):
    def __init__(self, master, app_instance):
        super().__init__(master); self.app = app_instance; self.title(f"{APP_NAME} Settings")

        try:
            self.iconbitmap('icon.ico')
        except tk.TclError:
            pass # The warning will be printed once from main()

        self.resizable(True, True)  # Allow the window to be resized
        self.minsize(820, 500)      # Set a reasonable minimum size
        self.protocol("WM_DELETE_WINDOW", self.on_close); self.dragged_item = None

        self._link_variables(); self._create_styles(); self._create_widgets(); self.update_all_ui_sections()

    def _link_variables(self):
        self.is_overlay_enabled_var = tk.BooleanVar(value=self.app.is_overlay_enabled)
        self.is_tiling_enabled_var = tk.BooleanVar(value=self.app.is_tiling_enabled)
        self.is_cursor_lock_enabled_var = tk.BooleanVar(value=self.app.is_cursor_lock_enabled)
        self.overlay_boundary_var = tk.IntVar(value=self.app.overlay_boundary_x)
        self.tiling_start_var = tk.IntVar(value=self.app.tiling_start_x)
        self.tiling_end_var = tk.IntVar(value=self.app.tiling_end_x)
        self.cursor_lock_boundary_var = tk.IntVar(value=self.app.cursor_lock_x)
        self.hotkey_var = tk.StringVar(value=self.app.hotkey); self.color_var = tk.StringVar(value=self.app.overlay_color)
        self.opacity_var = tk.IntVar(value=self.app.overlay_opacity); self.tiling_mode_var = tk.StringVar(value=self.app.tiling_mode)
        self.cursor_lock_mode_var = tk.StringVar(value=self.app.cursor_lock_mode)
        self.all_monitors = self.app.all_monitors; self.monitor_names = [f"Monitor {i} ({mon['Rect'][2]-mon['Rect'][0]}x{mon['Rect'][3]-mon['Rect'][1]}) {'(Primary)' if mon['is_primary'] else ''}" for i, mon in enumerate(self.all_monitors)]
        self.monitor_var = tk.StringVar(value=self.monitor_names[self.app.target_monitor_index])

    def _create_styles(self): s=ttk.Style(self);s.configure('Section.TFrame',background='#fafafa',borderwidth=1,relief='groove');s.configure('Sub.TFrame',background='#fafafa')

    # Replace this entire method in the SettingsWindow class
    def _create_widgets(self):
        # Main frame setup is fine
        main_frame = tk.Frame(self,padx=10,pady=10); main_frame.pack(fill='both',expand=True)
        
        # Top frame setup is fine
        top_frame = tk.Frame(main_frame); top_frame.pack(fill='x',pady=(0,10))
        tk.Label(top_frame,text="Target Monitor:").grid(row=0,column=0,sticky='w');tk.OptionMenu(top_frame,self.monitor_var,*self.monitor_names,command=self.on_monitor_select).grid(row=0,column=1,padx=5,sticky='w');tk.Label(top_frame,text="Global Hotkey:").grid(row=0,column=2,padx=(20,0));tk.Entry(top_frame,textvariable=self.hotkey_var,width=20).grid(row=0,column=3,padx=5);tk.Button(top_frame,text="Set",command=self.apply_hotkey).grid(row=0,column=4)
        
        # --- CHANGE 1: Configure the Canvas ---
        # The canvas should only fill horizontally, not vertically.
        self.canvas = tk.Canvas(main_frame,width=800,height=100,bg="#e0e0e0",relief="sunken",borderwidth=1)
        self.canvas.pack(pady=5,padx=5, fill='x') # Changed from just pack(...)
        self.canvas.bind("<ButtonPress-1>",self._on_drag_start);self.canvas.bind("<B1-Motion>",self._on_drag_line);self.canvas.bind("<ButtonRelease-1>",self._on_drag_end)

        # --- CHANGE 2: Configure the Features Container ---
        # This container holds the three main sections and should expand both ways.
        features_container = tk.Frame(main_frame)
        features_container.pack(fill='both',expand=True,pady=10)

        # These two lines are CRITICAL for making the sections resize
        features_container.grid_columnconfigure((0,1,2),weight=1) # Makes columns expand horizontally
        features_container.grid_rowconfigure(0,weight=1)          # Makes the row expand vertically
        
        # The rest of the creation logic is the same, but it will now be responsive
        self.overlay_frame = self._create_section_frame(features_container," Overlay Zone ","Enable Overlay",self.is_overlay_enabled_var,self.toggle_overlay_feature)
        self.tiling_frame = self._create_section_frame(features_container," Tiling Zone ","Enable Tiling",self.is_tiling_enabled_var,self.toggle_tiling_feature)
        self.cursor_frame = self._create_section_frame(features_container," Cursor Lock ","Enable Cursor Lock",self.is_cursor_lock_enabled_var,self.toggle_cursor_lock_feature)
        
        # Use 'nsew' sticky to make the frames fill their grid cell completely
        self.overlay_frame.grid(row=0,column=0,sticky='nsew',padx=5)
        self.tiling_frame.grid(row=0,column=1,sticky='nsew',padx=5)
        self.cursor_frame.grid(row=0,column=2,sticky='nsew',padx=5)   
    
    
    def _create_section_frame(self, p,t,cb,v,c): f=ttk.Labelframe(p,text=t,padding=10);tk.Checkbutton(f,text=cb,variable=v,command=c).pack(anchor='w',pady=(0,5));cf=ttk.Frame(f,style='Section.TFrame',padding=5);cf.pack(fill='both',expand=True);setattr(self,t.strip().lower().replace(" ","_")+"_controls",cf);return f
    def _create_bound_entry(self, p,l,v,cmd): tk.Label(p,text=l).grid(row=0,column=0,sticky='w');e=tk.Entry(p,textvariable=v,width=8);e.grid(row=0,column=1,padx=5);b=tk.Button(p,text="Set",width=5,command=lambda:cmd(v.get()));b.grid(row=0,column=2);e.bind("<Return>",lambda e:cmd(v.get()))
    # Replace this entire method in the SettingsWindow class
    def update_all_ui_sections(self):
        # First, clear the detailed controls from all three sections.
        # This prepares them for a fresh build.
        for f in [self.overlay_zone_controls, self.tiling_zone_controls, self.cursor_lock_controls]:
            for c in f.winfo_children():
                c.destroy()
                
        # --- THIS IS THE FIX ---
        # Unconditionally call all build methods. The methods themselves contain the
        # logic to decide whether to show detailed controls based on the feature's status.
        self._build_overlay_controls()
        self._build_tiling_controls()
        self._build_cursor_controls()
        
        # Recalculate geometry and update the top canvas after the UI is rebuilt.
        self.app.recalculate_geometry()
        self.update_canvas()


    def _open_color_picker(self):
        """Opens the OS color picker and applies the selected color."""
        # The initialcolor parameter pre-selects the current color in the dialog.
        # The title sets the dialog window's title.
        # The parent ensures the dialog appears on top of the settings window.
        result_color = colorchooser.askcolor(initialcolor=self.app.overlay_color,
                                            title="Select Overlay Color",
                                            parent=self)
        
        # askcolor returns a tuple: ((r,g,b), '#hexcode') or (None, None) if canceled.
        if result_color and result_color[1]:
            hex_code = result_color[1]
            self.color_var.set(hex_code) # Update the Entry box variable
            self.app.set_overlay_color(hex_code) # Apply the color to the app
            
    # Now, replace the build method
    def _build_overlay_controls(self):
        f = self.overlay_zone_controls
        f.grid_columnconfigure(0, weight=1) # Allow contents to expand horizontally

        # --- THIS IS THE FIX for Request #1 ---
        # Create an inner frame for all controls EXCEPT the main "Enable" checkbox.
        inner_controls_frame = ttk.Frame(f)
        inner_controls_frame.pack(fill='both', expand=True)

        ef = ttk.Frame(inner_controls_frame, style='Sub.TFrame')
        ef.grid(row=0, column=0, sticky='ew', pady=(0, 5))
        self._create_bound_entry(ef, "Boundary X:", self.overlay_boundary_var, self.app.set_overlay_boundary)
        
        tk.Label(inner_controls_frame, text="Color:").grid(row=1, column=0, sticky='w')
        cf = ttk.Frame(inner_controls_frame, style='Sub.TFrame')
        cf.grid(row=2, column=0, sticky='ew', pady=(0, 5))
        self.color_preview = tk.Label(cf, text="    ", bg=self.app.overlay_color, relief='sunken', borderwidth=1)
        self.color_preview.grid(row=0, column=0, padx=(0, 5))
        self.color_entry = tk.Entry(cf, textvariable=self.color_var, width=10)
        self.color_entry.grid(row=0, column=1)
        self.color_entry.bind("<Return>", self.apply_hex_color)
        tk.Button(cf, text="Set", command=self.apply_hex_color, width=5).grid(row=0, column=2, padx=5)
        
        # The command for the "Picker..." button is now our new helper method.
        tk.Button(cf, text="Picker...", command=self._open_color_picker, width=8).grid(row=0, column=3, padx=(10, 0))

        tk.Label(inner_controls_frame, text="Opacity:").grid(row=3, column=0, sticky='w', pady=(5, 0))
        of = ttk.Frame(inner_controls_frame, style='Sub.TFrame')
        of.grid(row=4, column=0, sticky='ew')
        tk.Scale(of, from_=0, to=100, orient='h', variable=self.opacity_var, command=lambda v: self.app.set_overlay_opacity(int(v)), showvalue=0).pack(side='left', fill='x', expand=True)
        tk.Label(of, textvariable=self.opacity_var).pack(side='left', padx=(5, 0))
        
        self._create_description_label(inner_controls_frame, "Creates a semi-transparent colored bar on the screen to visually separate monitor space.")

        # Call our helper to set the initial state of the controls.
        self._set_child_widgets_state(inner_controls_frame, 'normal' if self.app.is_overlay_enabled else 'disabled')


    def _build_tiling_controls(self):
        self._create_check_images()
        f = self.tiling_zone_controls

        # --- THIS IS THE FIX for Request #1 ---
        # Create an inner frame for all controls EXCEPT the main "Enable" checkbox.
        # This allows us to disable/enable everything at once.
        inner_controls_frame = ttk.Frame(f)
        inner_controls_frame.pack(fill='both', expand=True)
        
        inner_controls_frame.grid_columnconfigure(0, weight=1)
        inner_controls_frame.grid_rowconfigure(3, weight=1)

        # 1. Tiling Zone Definition
        mode_frame = ttk.Frame(inner_controls_frame)
        mode_frame.grid(row=0, column=0, sticky='ew')
        tk.Label(mode_frame, text="Tiling Zone:").pack(side='left', anchor='w')
        tk.Radiobutton(mode_frame, text="Full Partition", variable=self.tiling_mode_var, value="full", command=self.on_tiling_mode_change).pack(side='left', padx=5)
        tk.Radiobutton(mode_frame, text="Custom Zone", variable=self.tiling_mode_var, value="custom", command=self.on_tiling_mode_change).pack(side='left', padx=5)

        # 2. Custom Zone Inputs
        self.custom_options_frame = ttk.Frame(inner_controls_frame, style='Section.TFrame', padding=5)
        start_frame = ttk.Frame(self.custom_options_frame, style='Sub.TFrame'); start_frame.pack(fill='x', pady=(0, 2))
        end_frame = ttk.Frame(self.custom_options_frame, style='Sub.TFrame'); end_frame.pack(fill='x')
        self._create_bound_entry(start_frame, "Start X:", self.tiling_start_var, self.app.set_tiling_start)
        self._create_bound_entry(end_frame, "End X:  ", self.tiling_end_var, self.app.set_tiling_end)
        self.custom_options_frame.grid(row=1, column=0, sticky='ew', pady=5)
        
        # 3. Separator
        ttk.Separator(inner_controls_frame, orient='horizontal').grid(row=2, column=0, sticky='ew', pady=5)

        # 4. Manual Window Selection UI
        list_frame = ttk.Frame(inner_controls_frame)
        list_frame.grid(row=3, column=0, sticky='nsew')
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        tk.Button(list_frame, text="Refresh Window List", command=self._refresh_window_list).grid(row=0, column=0, sticky='ew', pady=(0, 5))
        self.tree = ttk.Treeview(list_frame, show='tree', height=8)
        self.tree.grid(row=1, column=0, sticky='nsew')
        self.tree.column("#0", width=350, stretch=tk.YES, anchor='w')
        self.tree.heading("#0", text="Window Title", anchor='w')
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure('checked', image=self.check_images['checked'])
        self.tree.tag_configure('unchecked', image=self.check_images['unchecked'])
        self.tree.bind("<Button-1>", self._on_toggle_check)
        self.listbox_windows_map = {}

        # 5. Description
        self._create_description_label(inner_controls_frame, "Automatically arranges selected windows into a grid within the defined Tiling Zone. Windows can be selected from the list above.")

        # Call our helper to set the initial state of the controls.
        if not self.app.is_tiling_enabled:
            self._set_child_widgets_state(inner_controls_frame, state='disabled')

        self.on_tiling_mode_change() 
        self._refresh_window_list()


    def _create_check_images(self):
        if hasattr(self, 'check_images'): return
        unchecked = Image.new('RGBA', (16, 16), (0,0,0,0))
        draw = ImageDraw.Draw(unchecked)
        draw.rectangle((2, 2, 13, 13), outline='gray', width=1)
        checked = unchecked.copy()
        draw = ImageDraw.Draw(checked)
        draw.line((4, 8, 7, 11, 12, 4), fill='blue', width=2)
        self.check_images = {'checked': ImageTk.PhotoImage(checked), 'unchecked': ImageTk.PhotoImage(unchecked)}
        

    def _refresh_window_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        eligible_windows = self.app.get_all_eligible_windows()
        self.listbox_windows_map = {hwnd: title for hwnd, title in eligible_windows}
        
        selected_hwnds = set(self.app.managed_windows)
        
        for hwnd, title in eligible_windows:
            app_icon = self.app.get_icon_for_hwnd(hwnd)
            is_checked = hwnd in selected_hwnds
            tag_to_apply = 'checked' if is_checked else 'unchecked'
            
            # --- THE FINAL, ROBUST 2-STEP LOGIC ---
            
            # Step 1: Insert the item with the absolute bare minimum.
            # We only provide the iid and the text. This call is reliable.
            self.tree.insert('', 'end', iid=hwnd, text=title)
            
            # Step 2: Configure ALL other options (image, tags) using the reliable
            # .item() method in a separate, secondary call.
            if app_icon: # Only apply the image if it exists
                self.tree.item(hwnd, image=app_icon, tags=(tag_to_apply,))
            else: # Fallback for windows without icons
                self.tree.item(hwnd, tags=(tag_to_apply,))

    def _on_toggle_check(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id: return
            
        hwnd = int(row_id)
        current_tags = self.tree.item(hwnd, "tags")
        
        if 'checked' in current_tags:
            self.tree.item(hwnd, tags=('unchecked',))
        else:
            self.tree.item(hwnd, tags=('checked',))
            
        self._update_tiling_from_tree_state()

    def _update_tiling_from_tree_state(self):
        selected_hwnds = []
        for hwnd_str in self.tree.get_children():
            tags = self.tree.item(hwnd_str, "tags")
            if 'checked' in tags:
                selected_hwnds.append(int(hwnd_str))
        
        self.app.managed_windows = selected_hwnds
        self.app.retile_zone()
    # ---- END OF CORRECTED TILING UI METHODS ----

    # Replace this entire method in the SettingsWindow class
    def _build_cursor_controls(self):
        f = self.cursor_lock_controls

        # --- THIS IS THE FIX ---
        # Create an inner frame to hold all controls except the main "Enable" checkbox.
        inner_controls_frame = ttk.Frame(f)
        inner_controls_frame.pack(fill='both', expand=True)
        inner_controls_frame.grid_columnconfigure(0, weight=1) # Allow contents to expand horizontally

        # --- Manage all items with Grid inside the inner frame ---
        tk.Label(inner_controls_frame, text="Lock Mode:").grid(row=0, column=0, sticky='w')
        
        rb1 = tk.Radiobutton(inner_controls_frame, text="To Overlay Edge", variable=self.cursor_lock_mode_var, value="overlay", command=self.on_cursor_mode_change)
        rb1.grid(row=1, column=0, sticky='w')
        # The 'disabled' state of this specific radio button depends on the OVERLAY's status.
        rb1.config(state='normal' if self.app.is_overlay_enabled else 'disabled') 

        tk.Radiobutton(inner_controls_frame, text="Custom Position", variable=self.cursor_lock_mode_var, value="custom", command=self.on_cursor_mode_change).grid(row=2, column=0, sticky='w')

        self.custom_cursor_frame = ttk.Frame(inner_controls_frame, style='Sub.TFrame')
        self.custom_cursor_frame.grid(row=3, column=0, sticky='ew', pady=5)
        self._create_bound_entry(self.custom_cursor_frame, "Wall X:", self.cursor_lock_boundary_var, self.app.set_cursor_lock_boundary)
        
        self.on_cursor_mode_change() 
        
        self._create_description_label(inner_controls_frame, "Restricts the mouse cursor, preventing it from moving past the defined line on the target monitor.")

        # Call our helper to set the initial state of the controls.
        if not self.app.is_cursor_lock_enabled:
            self._set_child_widgets_state(inner_controls_frame, state='disabled')

    def update_canvas(self):
        self.canvas.delete("all");self._scale,self.offset_x,self.offset_y=self._calculate_scale();
        for i,mon in enumerate(self.all_monitors):
            l,t,r,b=mon['Rect'];h=b-t;cl=self._real_to_canvas_x(l);cr=self._real_to_canvas_x(r);ct=self.offset_y-(h*self._scale*0.4);cb=self.offset_y+(h*self._scale*0.4);fill_color="#ddffdd" if i==self.app.target_monitor_index else"#cccccc";self.canvas.create_rectangle(cl,ct,cr,cb,fill=fill_color,outline="black");self.canvas.create_text((cl+cr)/2,self.offset_y,text=f"M{i}{'P' if mon['is_primary'] else ''}",anchor='center')
        tm=self.all_monitors[self.app.target_monitor_index];l,t,r,b=tm['Rect'];h=b-t;ct=self.offset_y-(h*self._scale*0.4);cb=self.offset_y+(h*self._scale*0.4)
        if self.app.overlay_rect:x,_,w,_=self.app.overlay_rect;self.canvas.create_rectangle(self._real_to_canvas_x(x),ct,self._real_to_canvas_x(x+w),cb,fill="#ffaaaa",stipple="gray50",outline="")

        if self.app.tiling_rect and self.app.is_tiling_enabled:
            x,_,w,_=self.app.tiling_rect
            self.canvas.create_rectangle(self._real_to_canvas_x(x),ct,self._real_to_canvas_x(x+w),cb,fill="#aaffaa",stipple="gray25",outline="")

        if self.app.is_overlay_enabled:self._draw_draggable_line(self.app.overlay_boundary_x,'red','overlay_line')
        if self.app.is_tiling_enabled and self.app.tiling_mode=="custom":self._draw_draggable_line(self.app.tiling_start_x,'green','tiling_start_line');self._draw_draggable_line(self.app.tiling_end_x,'green','tiling_end_line')
        if self.app.is_cursor_lock_enabled and self.app.cursor_lock_mode=="custom":self._draw_draggable_line(self.app.cursor_lock_x,'blue','cursor_line',(4,4))
    
    def _calculate_scale(self):min_x=min(m['Rect'][0]for m in self.all_monitors);max_x=max(m['Rect'][2]for m in self.all_monitors);w=max_x-min_x;return(800*0.95)/w if w>0 else 1,-min_x,50
    def _real_to_canvas_x(self,x):return 20+(x+self.offset_x)*self._scale
    def _canvas_to_real_x(self,x):return int(((x-20)/self._scale)-self.offset_x)
    def _draw_draggable_line(self,x,c,t,d=None):cx=self._real_to_canvas_x(x);self.canvas.create_line(cx,0,cx,100,fill=c,width=3,tags=(t,"draggable"),dash=d)
    def _on_drag_start(self,e):i=self.canvas.find_closest(e.x,e.y,halo=5);self.dragged_item=self.canvas.gettags(i[0])[0]if i and"draggable"in self.canvas.gettags(i[0])else None
    def _on_drag_end(self,e):self.dragged_item=None
    # Replace this entire method in the SettingsWindow class
    def _on_drag_line(self, e):
        if not self.dragged_item:
            return

        # Get the boundaries of the target monitor on the canvas
        target_mon = self.all_monitors[self.app.target_monitor_index]['Rect']
        l, _, r, _ = target_mon
        canvas_left_bound = self._real_to_canvas_x(l)
        canvas_right_bound = self._real_to_canvas_x(r)
        
        # Constrain the mouse's X position to within the monitor's representation on the canvas
        constrained_x = max(canvas_left_bound, min(e.x, canvas_right_bound))
        real_x_value = self._canvas_to_real_x(constrained_x)

        # --- THIS IS THE KEY ---
        # The dictionary that maps a dragged line's tag to its action.
        # We are adding the tiling and cursor lines here.
        drag_actions = {
            "overlay_line":      (self.overlay_boundary_var, self.app.set_overlay_boundary),
            "tiling_start_line": (self.tiling_start_var, self.app.set_tiling_start),
            "tiling_end_line":   (self.tiling_end_var, self.app.set_tiling_end),
            "cursor_line":       (self.cursor_lock_boundary_var, self.app.set_cursor_lock_boundary)
        }
        
        # Check if the item we are dragging has a defined action
        if self.dragged_item in drag_actions:
            variable_to_update, setter_function = drag_actions[self.dragged_item]
            
            # Update the Tkinter variable, which instantly changes the value in the Entry box
            variable_to_update.set(real_x_value)
            
            # Call the main application's function to apply the new value. This will also
            # trigger a retile or recalculation of geometry automatically.
            setter_function(real_x_value)
    
    def on_monitor_select(self,s):self.app.set_target_monitor(self.monitor_names.index(s))

    def on_tiling_mode_change(self):
        mode = self.tiling_mode_var.get()
        self.app.set_tiling_mode(mode)
        
        # --- THIS IS THE FIX for Request #1 ---
        # Explicitly redraw the canvas after mode has changed.
        self.app._redraw_canvas_only()

        if hasattr(self, 'custom_options_frame'):
            if mode == "custom":
                self.custom_options_frame.grid()
            else:
                self.custom_options_frame.grid_remove()


    # Replace this method in SettingsWindow
    def on_cursor_mode_change(self):
        mode = self.cursor_lock_mode_var.get()
        self.app.set_cursor_lock_mode(mode)
        
        # Use grid()/grid_remove() to show/hide the custom control frame
        if hasattr(self, 'custom_cursor_frame'):
            if mode == "custom":
                self.custom_cursor_frame.grid()
            else:
                self.custom_cursor_frame.grid_remove()

    def toggle_overlay_feature(self):self.app.set_feature_enabled('overlay',self.is_overlay_enabled_var.get())
    def toggle_tiling_feature(self):self.app.set_feature_enabled('tiling',self.is_tiling_enabled_var.get())
    def toggle_cursor_lock_feature(self):self.app.set_feature_enabled('cursor',self.is_cursor_lock_enabled_var.get())



    def _set_child_widgets_state(self, parent_widget, state='normal'):
        """Recursively set the state of all child widgets."""
        for child in parent_widget.winfo_children():
            # Some widgets like Labels don't have a 'state' option.
            try:
                # Exclude scrollbars from being disabled, as it looks bad.
                if 'scrollbar' not in child.winfo_class():
                    child.configure(state=state)
            except tk.TclError:
                pass # Widget does not have a 'state' property.
            self._set_child_widgets_state(child, state=state)



    
    def apply_hotkey(self):
        if not self.app.set_hotkey(self.hotkey_var.get()):messagebox.showerror("Invalid Hotkey","Invalid hotkey.",parent=self);self.hotkey_var.set(self.app.hotkey)
    def apply_hex_color(self,e=None):
        c=self.color_var.get();
        try:self.color_entry.winfo_rgb(c);self.app.set_overlay_color(c)
        except tk.TclError:messagebox.showerror("Invalid Color",f"'{c}' is not a valid color code.",parent=self);self.color_var.set(self.app.overlay_color)
    

    # Add this new helper method to the SettingsWindow class
# Replace this entire helper method in the SettingsWindow class
    def _create_description_label(self, parent, text):
        """Creates a formatted description label using the grid manager."""
        desc = ttk.Label(parent, text=text, wraplength=230, justify='left', style='Sub.TFrame')
        
        # --- THIS IS THE FIX ---
        # Use grid() instead of pack() to be compatible with other layouts.
        # We place it in the next available row at the bottom of the parent frame.
        next_row = parent.grid_size()[1]
        desc.grid(row=next_row, column=0, sticky='ew', pady=(10, 0))


    def on_close(self):self.app.settings_window=None;self.destroy()



class DisplayZoneManager:

    EVENT_SYSTEM_MOVESIZE_END = 0x000B
    
    
    def __init__(self, root):
        self.tk_root = root; self.settings_window = None; self.tiling_event_hook_thread = None
        self.enforcement_thread = None; self.managed_windows = []; self.overlay_window = None
        self.WinEventProc = ctypes.WINFUNCTYPE(None,wintypes.HANDLE,wintypes.DWORD,wintypes.HWND,wintypes.LONG,wintypes.LONG,wintypes.DWORD,wintypes.DWORD)
        self.tiling_event_proc = self.WinEventProc(self._tiling_event_callback)
        self.layout_manager = LayoutManager(); self.overlay_rect=self.tiling_rect=self.cursor_clip_rect=None

        self._load_config()
        self._create_tkinter_overlay() # Use Tkinter-based overlay

        if self.is_tiling_enabled: self._start_tiling_hooks()
        self._start_enforcement_loop()
        self.tk_root.after_idle(self.recalculate_geometry) # Defer initial calculation
        self._register_initial_hotkey()

    def _load_config(self):
        self.all_monitors=self.get_all_monitors(); self.target_monitor_index=0
        try:
            with open(CONFIG_FILE,'r')as f: cfg=json.load(f)
            for k,v in cfg.items(): setattr(self,k,v)
        except (FileNotFoundError,json.JSONDecodeError): self._set_default_config()

    def _set_default_config(self):
        mon=self.all_monitors[self.target_monitor_index]['Rect']; l,_,r,_=mon; w=r-l
        self.is_overlay_enabled,self.is_tiling_enabled,self.is_cursor_lock_enabled=False,False,False
        self.tiling_mode,self.cursor_lock_mode='full','overlay'
        self.overlay_boundary_x,self.tiling_start_x,self.tiling_end_x,self.cursor_lock_x=l+w//4,l+w//4,l+w*3//4,l+w//2
        self.hotkey,self.overlay_color,self.overlay_opacity=DEFAULT_HOTKEY,DEFAULT_OVERLAY_COLOR,DEFAULT_OVERLAY_OPACITY

    def save_config(self):
        cfg={k:v for k,v in self.__dict__.items() if isinstance(v,(bool,str,int,float)) and k!='all_monitors'}
        os.makedirs(CONFIG_DIR,exist_ok=True);open(CONFIG_FILE,'w').write(json.dumps(cfg,indent=4))

    def _trigger_full_ui_update(self):
        if self.settings_window and self.settings_window.winfo_exists():self.settings_window.update_all_ui_sections()
    def _redraw_canvas_only(self):
        if self.settings_window and self.settings_window.winfo_exists():self.settings_window.update_canvas()

    def set_feature_enabled(self, feature, enabled):
        if feature == 'overlay':
            self.is_overlay_enabled = enabled
        elif feature == 'tiling':
            self.is_tiling_enabled = enabled
            if not enabled: # If tiling is disabled, clear the managed windows
                self.managed_windows.clear()
        elif feature == 'cursor':
            self.is_cursor_lock_enabled = enabled
        
        self.recalculate_geometry()
        self.retile_zone()
        
        # --- THIS IS THE FIX for Request #2 ---
        # Explicitly redraw the canvas to show/hide tiling zones immediately.
        self._redraw_canvas_only()
        
        self._trigger_full_ui_update()

    def set_overlay_boundary(self,v):self.overlay_boundary_x=int(v);self.recalculate_geometry();self.retile_zone();self._redraw_canvas_only()

    # Replace this method
    def set_tiling_start(self,v):
        self.tiling_start_x = int(v)
        self.recalculate_geometry_and_retile()
        self._redraw_canvas_only() # <-- ADD THIS LINE

    # Replace this method
    def set_tiling_end(self,v):
        self.tiling_end_x = int(v)
        self.recalculate_geometry_and_retile()
        self._redraw_canvas_only() # <-- ADD THIS LINE
    
    def set_cursor_lock_boundary(self,v):self.cursor_lock_x=int(v);self.recalculate_geometry();self._redraw_canvas_only()

    # NEW, CORRECTED METHOD
    def set_tiling_mode(self, m):
        self.tiling_mode = m
        self.recalculate_geometry_and_retile()
        # We no longer call self._trigger_full_ui_update() here.
    
    # NEW, CORRECTED METHOD
    def set_cursor_lock_mode(self, m):
        self.cursor_lock_mode = m
        self.recalculate_geometry()
        # DO NOT trigger a full UI update here. The SettingsWindow will handle its own state.
        self._redraw_canvas_only() # Just redraw the canvas, which is safe.


    def set_target_monitor(self,i):
        if self.settings_window:self.settings_window.destroy();self.settings_window=None
        self.target_monitor_index=i;self._set_default_config()
        self.recalculate_geometry_and_retile();self.show_settings_window()

    def set_overlay_color(self,c):self.overlay_color=c;self._update_overlay_visuals();self._trigger_full_ui_update()
    def set_overlay_opacity(self,o):self.overlay_opacity=o;self._update_overlay_visuals()

    def recalculate_geometry(self):
        mon=self.all_monitors[self.target_monitor_index]['Rect'];l,t,r,b=mon;h=b-t
        self.overlay_rect,self.tiling_rect = None,None
        if self.is_overlay_enabled:self.overlay_rect = (l, t, self.overlay_boundary_x - l, h)
        if self.is_tiling_enabled:
            s_x,e_x=(self.overlay_boundary_x,r)if self.tiling_mode=='full'and self.is_overlay_enabled else(l,r)if self.tiling_mode=='full'else(min(self.tiling_start_x,self.tiling_end_x),max(self.tiling_start_x,self.tiling_end_x))
            self.tiling_rect=(s_x, t, e_x - s_x, h)
        self._update_overlay_visuals();self._update_cursor_clip()
    def recalculate_geometry_and_retile(self):self.recalculate_geometry();self.retile_zone()

    def _start_enforcement_loop(self):
        if not self.enforcement_thread or not self.enforcement_thread.is_alive():
            self.enforcement_thread=threading.Thread(target=self._enforcement_loop,daemon=True)
            self.enforcement_thread.start()

    def _enforcement_loop(self):
        while True:
            if self.is_cursor_lock_enabled and self.cursor_clip_rect:
                try:win32api.ClipCursor(self.cursor_clip_rect)
                except win32api.error:pass
            time.sleep(0.25)

    def _unclip_cursor(self):
        try:
            full=(win32api.GetSystemMetrics(76),win32api.GetSystemMetrics(77),win32api.GetSystemMetrics(78),win32api.GetSystemMetrics(79))
            win32api.ClipCursor((full[0],full[1],full[0]+full[2],full[1]+full[3]))
        except win32api.error:pass

    def _update_cursor_clip(self):
        if not self.is_cursor_lock_enabled:self._unclip_cursor();self.cursor_clip_rect=None;return
        target_mon = self.all_monitors[self.target_monitor_index]; primary_handle=next((m['Handle']for m in self.all_monitors if m['is_primary']), target_mon['Handle'])
        wall_x = self.overlay_boundary_x if self.cursor_lock_mode=='overlay' and self.is_overlay_enabled else self.cursor_lock_x
        usable_area = (wall_x, target_mon['Rect'][1], target_mon['Rect'][2], target_mon['Rect'][3])
        if primary_handle==target_mon['Handle']:self.cursor_clip_rect=usable_area
        else:
            primary_rect = win32api.GetMonitorInfo(primary_handle)['Monitor']
            self.cursor_clip_rect=(min(primary_rect[0], usable_area[0]),min(primary_rect[1],usable_area[1]),max(primary_rect[2],usable_area[2]),max(primary_rect[3],usable_area[3]))



    def get_all_eligible_windows(self):
        """Enumerates all top-level windows and returns a list of (hwnd, title)
        tuples for those that are manageable."""
        eligible_windows = []
        def enum_callback(hwnd, lParam):
            if self.is_window_manageable(hwnd):
                title = win32gui.GetWindowText(hwnd)
                eligible_windows.append((hwnd, title))
            return True # Continue enumeration
        
        win32gui.EnumWindows(enum_callback, None)
        return sorted(eligible_windows, key=lambda item: item[1].lower())



    def _start_tiling_hooks(self):
        if not self.tiling_event_hook_thread or not self.tiling_event_hook_thread.is_alive():self.tiling_event_hook_thread=threading.Thread(target=self._tiling_event_loop,daemon=True);self.tiling_event_hook_thread.start()
    def _stop_tiling_hooks(self):
        if self.tiling_event_hook_thread:self.is_tiling_enabled=False;self.tiling_event_hook_thread.join(timeout=1.5);self.managed_windows.clear()

    def _tiling_event_loop(self):
        pythoncom.CoInitialize()
        user32 = ctypes.windll.user32
        
        # More reliable and specific event hooks
        events_to_hook = [
            win32con.EVENT_OBJECT_SHOW,
            win32con.EVENT_OBJECT_HIDE,
            win32con.EVENT_OBJECT_DESTROY,
            self.EVENT_SYSTEM_MOVESIZE_END, # <-- CORRECTED
        ]

        hooks = []
        for event in events_to_hook:
            # Note: The event range in SetWinEventHook is [event, event] (inclusive)
            hook = user32.SetWinEventHook(event, event, 0, self.tiling_event_proc, 0, 0, 0)
            if hook:
                hooks.append(hook)
        
        print(f"Tiling hooks installed: {len(hooks)} active.")
        
        while self.is_tiling_enabled:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)

        for h in hooks:
            if h:
                user32.UnhookWinEvent(h)
        pythoncom.CoUninitialize()
        print("Tiling hooks uninstalled.")

    def _tiling_event_callback(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        # ... (the first part of the function is unchanged) ...

        was_managed = hwnd in self.managed_windows
        is_in_zone = self.is_window_in_tiling_zone(hwnd)
        needs_retile = False

        # --- Tiling Logic ---
        if event in (win32con.EVENT_OBJECT_HIDE, win32con.EVENT_OBJECT_DESTROY):
            # A window was hidden or closed, remove it if we were managing it.
            if was_managed:
                self.managed_windows.remove(hwnd)
                needs_retile = True
        
        elif event in (win32con.EVENT_OBJECT_SHOW, self.EVENT_SYSTEM_MOVESIZE_END): # <-- CORRECTED
            # A window appeared or finished moving.
            if is_in_zone and not was_managed:
                # It's IN the zone and we WEREN'T managing it: add it.
                self.managed_windows.append(hwnd)
                needs_retile = True
            elif not is_in_zone and was_managed:
                # It's OUT of the zone and we WERE managing it: remove it.
                self.managed_windows.remove(hwnd)
                needs_retile = True

        if needs_retile:
            self.retile_zone()

    def retile_zone(self):
        # We now use self.managed_windows directly. The layout manager will
        # get all selected windows, even if they are minimized.
        windows_to_tile = self.managed_windows
        
        if not self.is_tiling_enabled or not self.tiling_rect or not windows_to_tile:
            return

        # The sorting order of `windows_to_tile` (from user selection) is preserved.
        positions = self.layout_manager.tile(windows_to_tile, self.tiling_rect)
        
        if positions:
            user32 = ctypes.windll.user32
            # The Begin/EndDeferWindowPos combo prevents flicker by applying all changes at once.
            hDWP = user32.BeginDeferWindowPos(len(positions))
            flags = win32con.SWP_NOZORDER | win32con.SWP_NOOWNERZORDER | win32con.SWP_NOACTIVATE

            if hDWP:
                for hwnd, (x, y, w, h) in positions.items():
                    # SW_RESTORE (9) will un-minimize the window if needed.
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    user32.DeferWindowPos(hDWP, hwnd, 0, x, y, w, h, flags)
                user32.EndDeferWindowPos(hDWP)






    # Add this method inside the DisplayZoneManager class
    def get_icon_for_hwnd(self, hwnd):
        # We'll cache icons to improve performance and avoid memory issues
        if not hasattr(self, 'icon_cache'):
            self.icon_cache = {}
        if hwnd in self.icon_cache:
            return self.icon_cache[hwnd]

        # Constants for icon retrieval
        ICON_SMALL = 0
        ICON_BIG = 1
        GCL_HICONSM = -34
        WM_GETICON = 0x007F

        hIcon = None
        try:
            # Send a message to the window to get its icon handle
            result = ctypes.windll.user32.SendMessageTimeoutW(hwnd, WM_GETICON, ICON_SMALL, 0, 2, 500, ctypes.pointer(ctypes.c_size_t()))
            if result: hIcon = result
            
            if not hIcon: # Fallback 1: Try big icon
                result = ctypes.windll.user32.SendMessageTimeoutW(hwnd, WM_GETICON, ICON_BIG, 0, 2, 500, ctypes.pointer(ctypes.c_size_t()))
                if result: hIcon = result

            if not hIcon: # Fallback 2: Get icon from the window class
                hIcon = ctypes.windll.user32.GetClassLongPtrW(hwnd, GCL_HICONSM)

            if not hIcon: # If we still have no icon, we can't proceed
                self.icon_cache[hwnd] = None
                return None
                
            # --- Convert HICON to Tk PhotoImage ---
            icon_info = win32gui.GetIconInfo(hIcon)
            if not icon_info: return None
            
            hdc = win32gui.GetDC(0)
            mem_dc = win32gui.CreateCompatibleDC(hdc)
            bmp = win32gui.CreateCompatibleBitmap(hdc, 16, 16)
            win32gui.SelectObject(mem_dc, bmp)
            
            # Draw the icon onto the memory bitmap
            ctypes.windll.user32.DrawIconEx(mem_dc, 0, 0, hIcon, 16, 16, 0, 0, 3) # DI_NORMAL

            # Create a Pillow image from the raw bitmap data
            bitmap_bits = win32gui.GetBitmapBits(bmp, True)
            img = Image.frombuffer('RGBA', (16, 16), bitmap_bits, 'raw', 'BGRA', 0, 1)

            # Convert to PhotoImage and cache it
            photo_img = ImageTk.PhotoImage(image=img)
            self.icon_cache[hwnd] = photo_img

            # CRITICAL: Clean up GDI objects
            win32gui.DeleteObject(bmp)
            win32gui.DeleteDC(mem_dc)
            win32gui.ReleaseDC(0, hdc)
            win32gui.DestroyIcon(icon_info[0])
            win32gui.DestroyIcon(icon_info[1])

            return photo_img

        except Exception as e:
            # print(f"Icon error for {hwnd}: {e}") # for debugging
            self.icon_cache[hwnd] = None
            return None









    def is_window_manageable(self,hwnd):
        if not hwnd or not win32gui.IsWindowVisible(hwnd) or win32gui.GetParent(hwnd)!=0 or not win32gui.GetWindowText(hwnd):return False
        if not(win32gui.GetWindowLong(hwnd,-16)&12582912):return False
        try:mon_h=win32api.MonitorFromWindow(hwnd,1);mon_r=win32api.GetMonitorInfo(mon_h)['Monitor'];return win32gui.GetWindowRect(hwnd)!=mon_r
        except:return False
    def is_window_in_tiling_zone(self,hwnd):
        if not self.tiling_rect or not win32gui.IsWindowVisible(hwnd):return False
        try:l,_,r,_=win32gui.GetWindowRect(hwnd);cx=l+(r-l)//2
        except:return False
        tz_x,_,tz_w,_=self.tiling_rect;return tz_x<=cx<=(tz_x+tz_w)

    def _create_tkinter_overlay(self):
        if self.overlay_window and self.overlay_window.winfo_exists(): return
        self.overlay_window = tk.Toplevel(self.tk_root)
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.attributes("-disabled", True) # Make window click-through
        self.overlay_window.withdraw()

    def _destroy_tkinter_overlay(self):
        if self.overlay_window and self.overlay_window.winfo_exists():
            self.overlay_window.destroy()
        self.overlay_window = None

    def _update_overlay_visuals(self):
        if not self.overlay_window or not self.overlay_window.winfo_exists(): return
        if self.overlay_rect and self.is_overlay_enabled:
            x, y, w, h = self.overlay_rect
            w, h = max(1, w), max(1, h)
            self.overlay_window.geometry(f"{w}x{h}+{x}+{y}")
            self.overlay_window.configure(bg=self.overlay_color)
            self.overlay_window.attributes("-alpha", self.overlay_opacity / 100.0)
            self.overlay_window.deiconify()
        else:
            self.overlay_window.withdraw()

    def get_all_monitors(self):return[{'Handle':h,'Rect':r,'is_primary':win32api.GetMonitorInfo(h).get('Flags')==1} for h,_,r in win32api.EnumDisplayMonitors()]
    def _register_initial_hotkey(self):
        try:keyboard.add_hotkey(self.hotkey,self.show_settings_window,suppress=True)
        except Exception as e:messagebox.showwarning("Hotkey Error",f"Could not register '{self.hotkey}': {e}")

    def set_hotkey(self,new):
        try:keyboard.remove_hotkey(self.hotkey)
        except:pass
        try:keyboard.add_hotkey(new,self.show_settings_window,suppress=True);self.hotkey=new;return True
        except:
            try:keyboard.add_hotkey(self.hotkey,self.show_settings_window,suppress=True)
            except:pass
            return False

    def cleanup(self):
        print("Cleaning up...");self.is_cursor_lock_enabled=False;self.is_tiling_enabled=False
        self._unclip_cursor();self._stop_tiling_hooks()
        if self.enforcement_thread and self.enforcement_thread.is_alive(): self.enforcement_thread.join(timeout=0.5)
        self.tk_root.after(1, self._destroy_tkinter_overlay)
        keyboard.unhook_all();self.save_config();print("Cleanup complete.")

    def show_settings_window(self):
        if not self.settings_window or not self.settings_window.winfo_exists():self.settings_window=SettingsWindow(self.tk_root,self)
        else:self.settings_window.deiconify();self.settings_window.focus_force()

# --- MAIN EXECUTION ---
# Replace the entire main() function at the end of the script

def main():
    # Set DPI awareness for sharp UI rendering
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass # Not available on older Windows versions

    root = tk.Tk()
    root.withdraw()
    app = DisplayZoneManager(root)

    # Set the icon for the root Tk window. This ensures any dialogs
    # (like messageboxes) or future windows will inherit the icon.
    # It also helps set the taskbar icon when the settings window is open.
    try:
        # Assumes 'icon.ico' is in the same directory as the script
        root.iconbitmap('icon.ico')
    except tk.TclError:
        print("Warning: 'icon.ico' not found. Using default icon.")


    def on_quit(icon, item):
        app.cleanup()
        icon.stop()

    def create_tray_icon(app_instance):
        # --- THIS IS THE FIX (PART 2) ---
        # Replace the procedurally generated image with your .ico file
        try:
            image = Image.open("icon.ico")
        except FileNotFoundError:
            # Fallback to the old image if icon.ico is not found
            print("Warning: 'icon.ico' not found. Using default tray icon.")
            image = Image.new('RGB', (64, 64), 'black')
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 44, 44), outline='white', width=4)
            draw.line((32, 0, 32, 64), fill='white', width=2)
        
        tooltip_text = f"{APP_NAME} | Hotkey: {app_instance.hotkey}"

        menu = Menu(
            item('Settings...', app_instance.show_settings_window, default=True),
            Menu.SEPARATOR,
            item('Quit', on_quit)
        )
        
        icon = Icon(APP_NAME, image, tooltip_text, menu)
        icon.run()

    threading.Thread(target=create_tray_icon, args=(app,), daemon=True).start()
    print(f"{APP_NAME} is running.")
    root.mainloop()
    print(f"{APP_NAME} has shut down.")

if __name__ == "__main__":
    main()