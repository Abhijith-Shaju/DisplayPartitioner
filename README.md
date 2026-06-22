# Display Partitioner

Version: `3.1.0`

Display Partitioner is a lightweight Windows tray utility for splitting a monitor into a usable area and a blocked partition area. It is useful when you want a monitor to behave like a smaller workspace, especially on large, ultrawide, or multi-monitor setups.

The main application file in this folder is:

```text
DisplayPartitioner_copy.py
```

## Features

- Runs quietly from the Windows system tray.
- Provides a settings window for monitor, boundary, hotkey, color, and opacity controls.
- Supports multi-monitor setups.
- Lets you partition a monitor from any edge:
  - left
  - right
  - top
  - bottom
- Shows a live monitor preview with a draggable red boundary line.
- Allows exact boundary input for pixel-level control.
- Draws a customizable overlay over the blocked partition area.
- Supports overlay color selection.
- Supports overlay opacity from `0%` to `100%`.
- Uses a global hotkey to enable or disable partitioning.
- Restricts cursor movement with the native Windows `ClipCursor` API while enabled.
- Uses Windows work-area resizing on the primary monitor so maximized windows tile into the usable area.
- Saves settings automatically on exit.
- Attempts to recover the Windows work area on next launch if the previous run exited unexpectedly.

## How It Works

When partitioning is enabled, the app does three things:

1. Shows a transparent, click-through overlay over the blocked side of the selected monitor.
2. Clips the cursor so it stays inside the usable desktop area.
3. On the primary monitor, updates the Windows work area so maximized windows avoid the blocked partition.

The app does not move or resize the Windows taskbar.

## Requirements

- Windows
- Python 3.9 or newer recommended
- Dependencies listed in `requirements.txt`

Install dependencies with:

```powershell
pip install -r requirements.txt
```

## Running From Source

From this folder, run:

```powershell
python DisplayPartitioner_copy.py
```

After launch, the app appears in the system tray. Open the settings window from the tray icon.

## Default Hotkey

The default toggle hotkey is:

```text
Win + Alt + P
```

You can change it from the settings window.

## Settings

Settings are saved to:

```text
%APPDATA%\DisplayPartitioner\settings.json
```

The app stores:

- target monitor
- boundary coordinate
- partition edge
- hotkey
- overlay color
- overlay opacity

## Work-Area Recovery

Because the app can change the Windows work area for tiling, it also saves a temporary recovery file before applying that change:

```text
%APPDATA%\DisplayPartitioner\work_area_state.json
```

On a normal quit, the app restores the original work area and removes this recovery file.

If the app is force-closed or crashes, the recovery file may remain. On the next launch, Display Partitioner attempts to restore the saved work area automatically.

## Building an Executable

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build:

```powershell
pyinstaller --onefile --windowed --icon "icon.ico" --add-data "icon.ico;." --name "DisplayPartitioner-3.1.0" DisplayPartitioner_copy.py
```

The executable will be created in the `dist` folder.

## Files In This Folder

```text
DisplayPartitioner_copy.py  Main application file
icon.ico                    Tray/application icon
requirements.txt            Python dependencies
README.md                   Project documentation
LICENSE                     License text
```

## Safety Notes

- The app changes desktop state while enabled: cursor clipping, overlay visibility, and optionally the Windows work area.
- Use the tray menu's `Quit` option when possible so the app can restore the work area and unregister hotkeys cleanly.
- If the work area ever appears stuck after a forced exit, launch the app again and quit normally.
- Work-area tiling applies reliably only to the primary monitor because of how Windows exposes `SPI_SETWORKAREA`.

## Dependencies

- `pywin32` for Windows API access
- `pystray` for the system tray icon
- `Pillow` for icon/image handling
- `keyboard` for the global hotkey

## License

This project is licensed under the GPLv3 License. See [LICENSE](LICENSE) for details.
