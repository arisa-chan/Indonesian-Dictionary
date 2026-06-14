#!/usr/bin/env python3
"""Indonesian Dictionary — PySide6 GUI application.

An offline Indonesian dictionary with three modes:
  - Indonesian → English
  - English → Indonesian
  - Indonesian → Indonesian

Usage: python -m src.main
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from src.dictionary import DictionaryManager
from src.collection import CollectionManager
from src.srs import SrsManager
from src.ui.main_window import MainWindow
from src.paths import resource_dir


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Indonesian Dictionary")
    app.setOrganizationName("IndonesianDict")

    # Check for data files
    data_path = resource_dir()
    required = ["id_id.json", "id_en.json", "en_id.json", "frequency.json"]
    missing = [f for f in required if not (data_path / f).exists()]

    if missing:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Missing Data")
        msg.setText(
            "Dictionary data files not found.\n\n"
            f"Missing: {', '.join(missing)}\n\n"
            "Please run 'python build_data.py' first to build the dictionary data."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        # Still launch — some modes may work partially

    # Load dictionary data
    dict_manager = DictionaryManager()
    dict_manager.load()

    # Load collections and SRS
    collection_mgr = CollectionManager()
    srs_mgr = SrsManager()

    # Set application and window icon
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        icon_path = Path(sys._MEIPASS) / "icon.ico"
    else:
        icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
    icon = None
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    # Show main window
    window = MainWindow(dict_manager, collection_mgr, srs_mgr)
    if icon and not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
