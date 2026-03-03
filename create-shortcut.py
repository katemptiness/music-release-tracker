"""Creates a desktop shortcut for Music Release Tracker.

- Windows: creates a .bat launcher on the Desktop
- Linux: creates a .desktop file on the Desktop
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
LAUNCHER = APP_DIR / "run.pyw"
ICON = APP_DIR / "static" / "icon.svg"

if sys.platform == "win32":
    desktop = Path.home() / "Desktop"
    shortcut = desktop / "Music Release Tracker.bat"
    shortcut.write_text(f'@echo off\nstart pythonw "{LAUNCHER}"\n')
    print(f"Shortcut created: {shortcut}")

else:
    python = sys.executable
    content = f"""[Desktop Entry]
Name=Music Release Tracker
Exec={python} "{LAUNCHER}"
Icon={ICON}
Type=Application
Terminal=false
Categories=AudioVideo;Music;
Comment=Track new album and EP releases
"""

    # Place in app menu
    app_menu = Path.home() / ".local" / "share" / "applications"
    app_menu.mkdir(parents=True, exist_ok=True)
    menu_shortcut = app_menu / "music-release-tracker.desktop"
    menu_shortcut.write_text(content)
    menu_shortcut.chmod(0o755)
    print(f"App menu shortcut: {menu_shortcut}")

    # Also place on Desktop if the folder exists
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        desktop_shortcut = desktop / "music-release-tracker.desktop"
        desktop_shortcut.write_text(content)
        desktop_shortcut.chmod(0o755)
        print(f"Desktop shortcut: {desktop_shortcut}")
    else:
        print("(No ~/Desktop folder found — shortcut added to app menu only)")

    print('\nYou can find "Music Release Tracker" in your application launcher.')
