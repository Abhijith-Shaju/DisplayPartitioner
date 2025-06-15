# Display Zone Manager

<p align="center">
  <img src="https://raw.githubusercontent.com/Abhijith-Shaju/DisplayPartitioner/main/icon.ico" alt="Application Icon" width="128"/>
</p>
<h1 align="center">Display Zone Manager</h1>
<p align="center">A lightweight, powerful, and persistent window management utility for Windows.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3">
</p>

---

**Display Zone Manager** is a "set it and forget it" tool for power users, developers, and anyone who needs precise control over their desktop real estate. It allows you to create custom workspaces on your monitor with an interactive, graphical interface.

Whether you need to visually partition a large monitor, lock your mouse to a specific area, or automatically arrange application windows into a perfect grid, this tool gives you the power to do so with ease and efficiency.

## ✨ Features

- ✅ **Full Graphical User Interface:** No more editing config files! A modern, responsive settings window gives you a real-time visual representation of your monitor and zones.
- 🎨 **Visual Overlay Zone:** Create a persistent, semi-transparent colored bar to visually divide your monitor space.
- 🖼️ **Intelligent Window Tiling:**
    - **Manual Selection:** Choose exactly which applications you want to manage from an auto-detected list, complete with app icons.
    - **Dynamic Grid Layout:** The app automatically arranges 1, 2, 3, or 4+ windows into a logical, aesthetically pleasing grid that adapts to your defined zone.
    - **Custom Tiling Areas:** Define a tiling zone across a full partition or specify a custom start and end coordinate.
- 🖱️ **Cursor Lock ("Hard Wall"):**
    - Lock your mouse cursor to a specific region of your monitor.
    - Uses the native `ClipCursor` API for a lag-free, OS-level boundary.
- ✏️ **Interactive & Precise Configuration:**
    - **Drag-and-Drop:** Simply drag a line on the screen canvas to set your boundaries.
    - **Manual Input:** Type in an exact coordinate for pixel-perfect control.
- ⌨️ **Customizable Global Hotkey:** Bring up the settings window from anywhere with a custom hotkey (defaults to a safe `Ctrl+Alt+P`).
- 💾 **Persistent Settings:** All your configurations—target monitor, zones, colors, opacity, hotkey, and tiled windows—are saved automatically and reloaded on next launch.
- 🚀 **Lightweight & Efficient:** Runs silently in the system tray with minimal CPU and memory usage.

## 📺 Demo

<p align="center">
    This is the Application interface</br>
  <img src="https://raw.githubusercontent.com/Abhijith-Shaju/DisplayPartitioner/main/images/one.png" alt="Appliaction Setting" width="256"/>
</p>

## Who is this for?

- **Developers** who want a tiling-like experience on one monitor while keeping another free.
- **Streamers** who need to section off parts of their screen for game, chat, and streaming software.
- **Power Users** looking for more granular control over their desktop than standard Windows settings allow.
- Anyone with an **ultrawide monitor** who wants to create more manageable, focused workspaces.

## 🚀 Installation & Usage

### For End-Users (Recommended)
No programming knowledge required.

1.  Go to the [**Releases Page**](https://github.com/Abhijith-Shaju/DisplayPartitioner/releases) of this repository.
2.  Download the latest `Display_Zone_Manager.exe` file.
3.  Place the `.exe` file in a permanent folder on your computer.
4.  Double-click to run. An icon will appear in your system tray.
5.  **Left-click the tray icon** (or right-click and choose "Settings") to open the configuration window and set up your zones.

### Auto-Start with Windows
To have the app run automatically every time you log in:

1.  Create a shortcut to `Display_Zone_Manager.exe`.
2.  Press `Win + R` to open the Run dialog.
3.  Type `shell:startup` and press Enter. This opens your user Startup folder.
4.  Move the shortcut you created into this folder. Done!

---

## 🛠️ Building from Source

If you wish to modify or build the application yourself:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Abhijith-Shaju/DisplayPartitioner.git
    cd DisplayPartitioner
    ```
2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # On Windows
    # source venv/bin/activate  # On macOS/Linux
    ```
3.  **Install Dependencies:**
    A `requirements.txt` file is included for convenience.
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the Script:**
    ```bash
    python your_script_name.py
    ```

### Building the Executable
To package the script into a single `.exe` file, [PyInstaller](https://pyinstaller.org/) is used.

1.  Make sure you have PyInstaller installed (`pip install pyinstaller`).
2.  Run the build command from the project root directory:
    ```bash
    pyinstaller --onefile --windowed --icon="icon.ico" --add-data "icon.ico;." --name="Display_Zone_Manager" your_script_name.py
    ```
    *Note: The `--add-data` flag is crucial for ensuring the `icon.ico` is bundled correctly into the final executable.*

The final `.exe` will be located in the `dist` folder.

## Dependencies

- **pywin32:** For all native Windows API interaction.
- **pystray:** For creating and managing the system tray icon.
- **Pillow:** An image library required by `pystray` and for icon handling.
- **keyboard:** For capturing the global hotkey.

---

## Author & Contact

**Abhijith Shaju**
- Email: [abhijithshaju2004@gmail.com](mailto:abhijithshaju2004@gmail.com)

*Note: AI was used as a tool to help create this project.*

## 📄 License
This project is licensed under the GPLv3 License. See the [LICENSE](LICENSE) file for details.