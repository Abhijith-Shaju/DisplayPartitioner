# Display Partitioner - A Persistent Monitor Partitioning Utility

<p align="center">
  <img src="https://github.com/Abhijith-Shaju/DisplayPartitioner/blob/main/DisplayManagerAppIcon.png" alt="Application Icon" width="128"/>
</p>
<h3 align="center">A lightweight, powerful Windows utility for custom dual-monitor workspaces.</h3>

---

**Display Partitioner** is a "set it and forget it" tool designed for power users with specific dual-monitor needs. It allows you to effectively disable a portion of a monitor by creating a persistent "hard wall" for your mouse cursor and a clean visual overlay to hide the disabled area.

This app was born from the need to use only the right half of an external monitor while keeping full access to the primary monitor. It achieves this with **zero performance lag** by using native Windows APIs.

## Features

- ✅ **Lag-Free Cursor Confinement:** Uses the native `ClipCursor` API to lock the mouse to a defined "super-rectangle" covering multiple screens. This is a true OS-level boundary, not a laggy script-based correction.
- 🧱 **Persistent "Hard Wall":** A smart watchdog loop instantly re-applies the cursor confinement if it's ever cleared by a system action (like a UAC prompt or dragging a window), ensuring the boundary is always active.
- ⚫ **Clean Visual Overlay:** A dependency-free, pure `Win32` black overlay perfectly covers the "dead" portion of your screen, creating a clean visual edge that lines up with the cursor wall.
- 🚀 **Lightweight & Efficient:** Runs silently in the system tray with minimal CPU and memory usage. It has no complex UI—just a simple on/off toggle for when you need it.
- ⚙️ **Easily Configurable:** The active boundary is set by changing a single number in the source code, allowing for pixel-perfect customization.

## Who is this for?

This utility is perfect for anyone who:
- Uses an external monitor that is partially damaged, too large, or needs to be partitioned for a specific task.
- Wants to create a custom, focused workspace across multiple physical screens.
- Is a developer, streamer, or power user looking for more granular control over their desktop environment than standard Windows settings allow.

## Installation & Usage

### 1. For End-Users (Recommended)

The easiest way to get started. No programming knowledge required.

1.  Go to the [**Releases Page**](https://github.com/YOUR_USERNAME/YOUR_REPOSITORY/releases) of this repository.
2.  Download the latest `DisplayPartitioner.exe` file.
3.  Place the `.exe` file in a permanent folder on your computer (e.g., `C:\Tools\`).
4.  Double-click `DisplayPartitioner.exe` to run it. An icon will appear in your system tray. Right-click it to enable or disable the partition.

### 2. Auto-Start with Windows

To have the app run automatically every time you log in:

1.  Create a shortcut to `DisplayPartitioner.exe`.
2.  Press `Win + R` to open the Run dialog.
3.  Type `shell:startup` and press Enter. This opens your user Startup folder.
4.  Move the shortcut you created into this folder. Done!

### 3. For Developers

If you wish to modify or build the application yourself:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Abhijith-Shaju/DisplayPartitioner.git
    cd DisplayPartitioner
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the Script:**
    ```bash
    python DisplayPartitioner.py
    ```

---

## How it Works

The application's elegance lies in its simple and robust architecture:

1.  **Native Overlay:** A borderless, click-through, always-on-top window is created using pure `Win32 API` calls. This avoids heavy GUI toolkits like Tkinter and their associated event loop conflicts. This overlay provides the clean "visual wall".
2.  **Persistent Cursor Clip:** The core of the app is a background thread running a "watchdog" loop. Every 250 milliseconds, this loop re-issues the `ClipCursor` command. This ensures the boundary is always enforced, even if temporarily cleared by Windows for a system event. This is the "hard wall".

This two-pronged approach provides a perfect, seamless user experience without fighting the operating system or its applications.

## Customization & Building

The current script is hardcoded for a specific dual-monitor layout (a 1920x1080 external monitor positioned to the left of a 1920x1080 primary monitor). To adapt it to your own setup, simply edit the `BOUNDARY_X_COORDINATE` variable at the top of the Python script.

To build your own `.exe` after making changes:

1.  Make sure you have PyInstaller: `pip install pyinstaller`.
2.  Place your desired `.ico` file in the same directory (e.g., `icon.ico`).
3.  Run the build command, using the `-n` flag to name the output file:
    ```bash
    python -m PyInstaller --onefile --windowed --icon="icon.ico" -n "DisplayPartitioner" DisplayPartitioner.py
    ```
The final executable will be located in the `dist` folder.

## Dependencies

- **pywin32:** For all native Windows API interaction.
- **pystray:** For creating and managing the system tray icon.
- **Pillow:** An image library required by `pystray`.
