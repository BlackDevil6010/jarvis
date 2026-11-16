"""Main entry point for JARVIS Desktop Application."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from jarvis.config import APP_NAME
from jarvis.ui.main_window import MainWindow


def main():
    """Launch the JARVIS desktop GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
