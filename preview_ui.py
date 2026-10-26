"""
preview_ui.py — Standalone visual runner for the redesigned AGENT UI.
Allows interactive inspection of all panels, quick drawer, overlays, and color wheel retheming.
"""
import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ProAssist.AGENT001.1")
    except Exception:
        pass

from PyQt6.QtWidgets import QApplication
from core.app_icon import get_app_icon
import ui


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())
    win = ui.MainWindow(face_path="")

    # Add sample log entries for immediate visual context
    win._log.append_log("SYS: MARK-LIV Quantum Core initialized.")
    win._log.append_log("AGENT: Audio pipeline and voice authentication ready.")
    win._log.append_log("SYS: Visual redesign loaded (Dark Cyberpunk / Minimalist).")

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
