# Display Partitioner - A Persistent Monitor Partitioning Utility

<p align="center">
  <img src="https://github.com/Abhijith-Shaju/DisplayPartitioner/blob/main/DisplayManagerAppIcon.png" alt="Application Icon" width="128"/>
</p>
<h3 align="center">A lightweight, powerful Windows utility for creating custom monitor workspaces.</h3>

---

**Display Partitioner** is a "set it and forget it" tool for power users, developers, and anyone with unique multi-monitor needs. It allows you to partition any monitor by creating a persistent "hard wall" for your mouse cursor and a clean visual overlay to hide the disabled area, all managed through an intuitive graphical interface.

This app was born from the need to use only the right half of an external monitor, and has since evolved into a flexible utility that can partition any side of any display with **zero performance lag** by using native Windows APIs.

## ✨ Features

- ✅ **Full Graphical User Interface (GUI):** No more editing code! A settings window gives you a real-time, visual representation of your monitors.
- 🖱️ **Flexible & Interactive Partitioning:**
    - **Drag-and-Drop:** Simply drag a line on the screen canvas to set your boundary.
    - **Precise Input:** Type in an exact coordinate for pixel-perfect control.
    - **Side Selection:** Instantly choose whether to partition the left or right side of your monitor.
- ⌨️ **Customizable Global Hotkey:** Toggle the partition on or off from anywhere in Windows. Defaults to `Win+Alt+P` but can be changed to anything you like.
- 💾 **Persistent Settings:** The app remembers everything! Your target monitor, partition boundary, side selection, and custom hotkey are all saved automatically and reloaded on the next launch.
- 🚀 **Lightweight & Efficient:** Runs silently in the system tray with minimal CPU and memory usage. The settings window can be closed while the partitioning remains active.
- 🧱 **Lag-Free "Hard Wall":** Uses the native `ClipCursor` API to lock the mouse to your defined workspace, providing a true OS-level boundary that is instantly re-applied if ever cleared by a system event (like a UAC prompt).

## Who is this for?

This utility is perfect for anyone who:
- Uses an external monitor that is partially damaged, too large, or needs to be partitioned for a specific task.
- Wants to create a custom, focused workspace across multiple physical screens.
- Is a developer, streamer, or power user looking for more granular control over their desktop environment than standard Windows settings allow.

## 🚀 Installation & Usage

### For End-Users (Recommended)
The easiest way to get started. No programming knowledge required.

1.  Go to the [**Releases Page**](./releases) of this repository.
2.  Download the latest `Display_Partitioner.exe` file.
3.  Place the `.exe` file in a permanent folder on your computer.
4.  Double-click it to run. An icon will appear in your system tray.
5.  **Double-click the tray icon** (or right-click and choose "Settings") to open the configuration window and set up your partition.

### Auto-Start with Windows
To have the app run automatically every time you log in:

1.  Create a shortcut to `Display_Partitioner.exe`.
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
    .\venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    A `requirements.txt` file is included for convenience.
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the Script:**
    ```bash
    python display_partitioner.py
    ```

### Building the Executable
To package the script into a single `.exe` file, use PyInstaller.

1.  Make sure you have PyInstaller installed (`pip install pyinstaller`).
2.  Run the build command from the project root directory:
    ```bash
    pyinstaller --onefile --windowed --icon="icon.ico" --add-data "icon.ico;." --name="Display_Partitioner" display_partitioner.py
    ```
    *Note: The `--add-data` flag is crucial for ensuring the icon is bundled correctly into the final executable.*

The final `.exe` will be located in the `dist` folder.

## Dependencies

- **pywin32:** For all native Windows API interaction.
- **pystray:** For creating and managing the system tray icon.
- **Pillow:** An image library required by `pystray`.
- **keyboard:** For capturing the global hotkey.
- **Tkinter:** (Included with Python) For the GUI.
