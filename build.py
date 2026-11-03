"""
Build SMP.exe with PyInstaller.

    pip install -r requirements.txt pyinstaller
    python build.py

The executable is written to dist/SMP.exe.
"""
import os
import sys
import PyInstaller.__main__
from PyQt6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT, "build")
ICON_PATH = os.path.join(BUILD_DIR, "icon.ico")


def make_icon():
    """Render the app logo to an .ico so the exe matches the app."""
    sys.path.insert(0, ROOT)
    import SMP
    app = QApplication.instance() or QApplication(sys.argv)
    os.makedirs(BUILD_DIR, exist_ok=True)
    SMP.make_app_icon().pixmap(256, 256).save(ICON_PATH, "ICO")


if __name__ == "__main__":
    make_icon()
    PyInstaller.__main__.run([
        os.path.join(ROOT, "SMP.py"),
        "--name", "SMP",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", ICON_PATH,
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", BUILD_DIR,
        "--specpath", BUILD_DIR,
    ])
