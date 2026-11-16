"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: main.py
VERSAO: 1.0.0
DESCRICAO: - feat: Gravador grafico (PyQt6) do bootloader UART do PIC16F88
           - docs: Python 3.11+ - PyQt6 - pyserial. Modo terminal: scripts/pic16f88_boot.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from src.gui.main_window import MainWindow, APP_TITLE  # noqa: E402
from src.gui.theme import ThemeManager  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    theme = ThemeManager(app)
    win = MainWindow(theme)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
