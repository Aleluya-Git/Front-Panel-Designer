"""Temas claro y oscuro (paleta Qt + hoja de estilos + colores del lienzo)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEMES = {
    "oscuro": {
        "window": "#1f2227", "base": "#17191d", "alt": "#23272d", "panel": "#262a31", "text": "#e3e6ea",
        "muted": "#9aa3ad", "border": "#353b44", "accent": "#3d8bfd", "accent_text": "#ffffff",
        "canvas": "#14161a", "grid_minor": "#20242a", "grid_major": "#2b3038", "ruler": "#1b1e23",
        "ruler_text": "#8b95a1", "hole": "#14161a", "sel": "#3d8bfd", "snap": "#ffb020", "hover": "#2d333b",
        "issue": "#ff4d4f",
    },
    "claro": {
        "window": "#f3f4f6", "base": "#ffffff", "alt": "#f7f8fa", "panel": "#ffffff", "text": "#1d2229",
        "muted": "#66707b", "border": "#d6dae0", "accent": "#1f6feb", "accent_text": "#ffffff",
        "canvas": "#e9ecef", "grid_minor": "#dde1e6", "grid_major": "#c9cfd6", "ruler": "#f7f8fa",
        "ruler_text": "#5b6570", "hole": "#e9ecef", "sel": "#1f6feb", "snap": "#e07b00", "hover": "#eef1f4",
        "issue": "#d92d20",
    },
}


def colors(name: str) -> dict:
    return THEMES.get(name, THEMES["oscuro"])


def apply_theme(app: QApplication, name: str) -> dict:
    c = colors(name)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(c["window"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(c["base"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(c["alt"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(c["panel"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(c["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(c["accent_text"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["panel"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["muted"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
    app.setPalette(pal)
    app.setStyleSheet(f"""
        QMainWindow, QDialog {{ background: {c['window']}; }}
        QToolBar {{ background: {c['window']}; border: none; spacing: 2px; padding: 3px; }}
        QToolBar::separator {{ background: {c['border']}; width: 1px; margin: 4px 4px; }}
        QToolButton {{ border: 1px solid transparent; border-radius: 6px; padding: 4px; }}
        QToolButton:hover {{ background: {c['hover']}; border-color: {c['border']}; }}
        QToolButton:checked {{ background: {c['accent']}; color: {c['accent_text']}; }}
        QDockWidget {{ titlebar-close-icon: none; font-weight: 600; }}
        QDockWidget::title {{ background: {c['window']}; padding: 6px 8px; border-bottom: 1px solid {c['border']}; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QFontComboBox {{
            background: {c['base']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 3px 6px; }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
            color: {c['text']}; selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
        /* Lista desplegable de los QComboBox: la opción resaltada debe verse siempre */
        QComboBox QAbstractItemView {{
            background: {c['base']}; color: {c['text']}; border: 1px solid {c['border']}; outline: 0;
            selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
        QComboBox QAbstractItemView::item {{ min-height: 22px; padding: 2px 6px; color: {c['text']}; }}
        QComboBox QAbstractItemView::item:selected, QComboBox QAbstractItemView::item:hover {{
            background: {c['accent']}; color: {c['accent_text']}; }}
        QTreeView, QListView, QTableView {{
            selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
        QLineEdit[error="true"] {{ border-color: {c['issue']}; }}
        QPushButton {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 5px 12px; }}
        QPushButton:hover {{ border-color: {c['accent']}; }}
        QPushButton:default {{ background: {c['accent']}; color: {c['accent_text']}; border-color: {c['accent']}; }}
        QTreeWidget, QListWidget, QTableWidget {{ background: {c['base']}; border: 1px solid {c['border']};
            border-radius: 6px; }}
        QHeaderView::section {{ background: {c['alt']}; border: none; border-bottom: 1px solid {c['border']}; padding: 4px; }}
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ padding: 5px 10px; border: none; color: {c['muted']}; }}
        QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
        QStatusBar {{ background: {c['window']}; border-top: 1px solid {c['border']}; }}
        QGroupBox {{ border: 1px solid {c['border']}; border-radius: 6px; margin-top: 12px; padding-top: 6px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {c['muted']}; }}
        QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; }}
        QMenu::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
        QLabel[role="hint"] {{ color: {c['muted']}; }}
        QLabel[role="title"] {{ font-weight: 600; font-size: 13px; }}
    """)
    return c
