from PySide6.QtWidgets import QApplication


LIGHT_THEME = """
QWidget { color: #202124; font-size: 13px; }
QMainWindow, QWidget#applicationRoot { background: #f3f4f6; }
QFrame[workspacePane="true"], QFrame#applicationHeader { background: #ffffff; border: 1px solid #dfe3e8; border-radius: 8px; }
QLabel#applicationTitle { font-size: 22px; font-weight: 650; }
QLabel#sectionTitle { color: #5f6368; font-size: 11px; font-weight: 650; }
QLineEdit, QPlainTextEdit, QComboBox, QTreeView { background: #ffffff; border: 1px solid #cfd4da; border-radius: 5px; padding: 5px; selection-background-color: #dbeafe; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QTreeView:focus { border: 1px solid #4f6f91; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #c7cdd4; border-radius: 5px; padding: 6px 11px; }
QPushButton:hover, QToolButton:hover { background: #f7f8fa; border-color: #9aa3ad; }
QPushButton:pressed, QToolButton:pressed { background: #eceff3; }
QPushButton:disabled, QToolButton:disabled { color: #9aa0a6; background: #f4f5f6; }
QPushButton[primary="true"] { color: #ffffff; background: #405d7a; border-color: #405d7a; }
QMenuBar, QMenu, QDockWidget { background: #ffffff; }
QMenuBar { border-bottom: 1px solid #dfe3e8; }
QHeaderView::section { background: #f7f8fa; border: 0; border-bottom: 1px solid #dfe3e8; padding: 6px; }
QSplitter::handle { background: #f3f4f6; width: 8px; }
"""


def apply_light_theme(application: QApplication) -> None:
    application.setStyleSheet(LIGHT_THEME)
