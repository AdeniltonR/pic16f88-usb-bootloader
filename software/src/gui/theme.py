"""
NOME: Adenilton Ribeiro
DATA: 14/11/2026
PROJETO: theme.py
VERSAO: 1.0.0
DESCRICAO: - feat: Tema claro/escuro seguindo o Windows (Configuracoes > Personalizacao > Cores)
           - feat: Troca automatica quando o usuario muda o tema com o programa aberto (Qt >= 6.5)
"""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

# ========================================================================================================
# ---CORES---

LIGHT = {
    "window": "#f3f3f3", "base": "#ffffff", "alt": "#f7f7f7", "text": "#1b1b1b",
    "button": "#fbfbfb", "highlight": "#0067c0", "hl_text": "#ffffff",
    "disabled": "#a0a0a0", "border": "#d0d0d0",
    "log_info": "#0067c0", "log_ok": "#107c10", "log_warn": "#9d5d00", "log_err": "#c42b1c", "log_app": "#1b1b1b",
    "log_tx": "#8a3ffc",
}
DARK = {
    "window": "#202020", "base": "#2b2b2b", "alt": "#323232", "text": "#f0f0f0",
    "button": "#2d2d2d", "highlight": "#4cc2ff", "hl_text": "#000000",
    "disabled": "#6e6e6e", "border": "#3d3d3d",
    "log_info": "#4cc2ff", "log_ok": "#6ccb5f", "log_warn": "#fce100", "log_err": "#ff99a4", "log_app": "#f0f0f0",
    "log_tx": "#d4a5ff",
}


# ========================================================================================================
# ---DETECCAO DO TEMA DO SISTEMA---

def _windows_registry_dark():
    """Fallback: le 'AppsUseLightTheme' do registro do Windows (0 = escuro)."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except OSError:
        return None


def system_is_dark(app):
    hints = app.styleHints()
    scheme = getattr(hints, "colorScheme", None)       # Qt >= 6.5
    if scheme is not None:
        cs = scheme()
        if cs == Qt.ColorScheme.Dark:
            return True
        if cs == Qt.ColorScheme.Light:
            return False
    reg = _windows_registry_dark()
    return bool(reg)


# ========================================================================================================
# ---APLICACAO DO TEMA---

def _palette(c):
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"],
        QPalette.ColorRole.AlternateBase: c["alt"],
        QPalette.ColorRole.ToolTipBase: c["base"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.PlaceholderText: c["disabled"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["button"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.BrightText: "#ff0000",
        QPalette.ColorRole.Highlight: c["highlight"],
        QPalette.ColorRole.HighlightedText: c["hl_text"],
        QPalette.ColorRole.Link: c["highlight"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    return p


def _stylesheet(c):
    return f"""
        QGroupBox {{ border: 1px solid {c['border']}; border-radius: 6px; margin-top: 10px; padding: 8px 8px 6px 8px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; font-weight: bold; }}
        QPushButton {{ padding: 5px 14px; border-radius: 4px; border: 1px solid {c['border']}; background: {c['button']}; }}
        QPushButton:hover {{ border-color: {c['highlight']}; }}
        QPushButton:disabled {{ color: {c['disabled']}; }}
        QPushButton#primary {{ background: {c['highlight']}; color: {c['hl_text']}; border-color: {c['highlight']}; font-weight: bold; }}
        QPushButton#primary:disabled {{ background: {c['button']}; color: {c['disabled']}; border-color: {c['border']}; }}
        QComboBox, QLineEdit {{ padding: 4px; border-radius: 4px; border: 1px solid {c['border']}; background: {c['base']}; }}
        QPlainTextEdit {{ border: 1px solid {c['border']}; border-radius: 4px; background: {c['base']}; }}
        QProgressBar {{ border: 1px solid {c['border']}; border-radius: 4px; text-align: center; background: {c['base']}; height: 18px; }}
        QProgressBar::chunk {{ background: {c['highlight']}; border-radius: 3px; }}
    """


class ThemeManager:
    """Aplica o tema do sistema e acompanha mudancas. on_change(colors) e chamado ao trocar."""

    def __init__(self, app, on_change=None):
        self.app = app
        self.on_change = on_change
        self.colors = LIGHT
        app.setStyle("Fusion")
        self.apply()
        hints = app.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.apply())

    @property
    def dark(self):
        return self.colors is DARK

    def apply(self):
        self.colors = DARK if system_is_dark(self.app) else LIGHT
        self.app.setPalette(_palette(self.colors))
        self.app.setStyleSheet(_stylesheet(self.colors))
        if self.on_change:
            self.on_change(self.colors)
