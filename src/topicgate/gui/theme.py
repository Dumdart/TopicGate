from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


LIGHT_THEME = """
QWidget { color: #202124; font-size: 13px; }
QMainWindow, QDialog, QMessageBox, QWidget#applicationRoot { background: #f3f4f6; color: #202124; }
QMessageBox QLabel { background: transparent; color: #202124; }
QFrame[workspacePane="true"], QFrame#applicationHeader { background: #ffffff; border: 1px solid #c8ced6; border-radius: 8px; }
QFrame#observerEmptyState { background: #f8fafc; border: 1px solid #c8ced6; border-radius: 5px; }
QLabel#observerEmptyStateText { background: transparent; color: #4b5563; }
QWidget#snapshotPanel, QWidget#snapshotContent, QGroupBox#snapshotControls, QGroupBox#snapshotHealthPanel { background: #ffffff; }
QFrame#snapshotHeader { background: #fbfcfd; border: 1px solid #c8ced6; border-radius: 5px; }
QScrollArea#snapshotPanelScrollArea { background: #ffffff; }
QToolButton#snapshotToggleButton { border: 0; background: transparent; font-weight: 650; padding: 3px 5px; }
QToolButton#snapshotToggleButton:hover { background: #eef2f6; }
QGroupBox#snapshotControls, QGroupBox#snapshotHealthPanel { border: 1px solid #c8ced6; border-radius: 5px; margin-top: 8px; padding-top: 8px; }
QGroupBox#snapshotControls::title, QGroupBox#snapshotHealthPanel::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; color: #4b5563; font-weight: 650; }
QLabel#applicationTitle { font-size: 22px; font-weight: 650; }
QLabel#applicationSubtitle, QLabel#brokerEndpoint { color: #667085; }
QLabel#brokerEndpoint { font-size: 12px; }
QLabel#brokerSectionTitle { color: #475467; font-size: 11px; font-weight: 650; letter-spacing: 0.5px; }
QLabel#sectionTitle, QLabel#workspaceHeading { color: #4b5563; font-weight: 650; }
QLabel#sectionTitle { font-size: 11px; }
QLabel#workspaceHeading { font-size: 15px; }
QLineEdit, QPlainTextEdit, QComboBox, QTreeView { background: #ffffff; border: 1px solid #b8c0ca; border-radius: 5px; padding: 5px; selection-background-color: #dce9f7; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QTreeView:focus { border: 1px solid #4f6f91; }
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled { color: #737b85; background: #f1f3f5; border-color: #c8ced6; }
QPlainTextEdit#decodedPayload, QPlainTextEdit#rawPayload { background: #fbfcfd; }
QPlainTextEdit#decodedPayload:focus, QPlainTextEdit#rawPayload:focus { background: #ffffff; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #b8c0ca; border-radius: 5px; padding: 6px 11px; }
QPushButton:hover, QToolButton:hover { background: #f7f8fa; border-color: #89939f; }
QPushButton:pressed, QToolButton:pressed { background: #eceff3; }
QPushButton:disabled, QToolButton:disabled { color: #737b85; background: #f1f3f5; border-color: #c8ced6; }
QPushButton[primary="true"] { color: #ffffff; background: #405d7a; border-color: #405d7a; }
QPushButton[primary="true"]:hover { background: #334e68; border-color: #334e68; }
QPushButton[primary="true"]:pressed { background: #2b4259; border-color: #2b4259; }
QPushButton[primary="true"]:disabled { color: #737b85; background: #e5e7eb; border-color: #c8ced6; }
QPushButton[danger="true"] { color: #a53030; border-color: #d7a4a4; }
QPushButton[danger="true"]:hover { color: #8f2525; background: #fff5f5; border-color: #c77d7d; }
QMenuBar, QMenu, QDockWidget { background: #ffffff; }
QMenuBar { border-bottom: 1px solid #c8ced6; }
QHeaderView::section { color: #4b5563; background: #f3f5f7; border: 0; border-bottom: 1px solid #c8ced6; padding: 6px; font-weight: 600; }
QTreeView { alternate-background-color: #fafbfc; }
QTreeView::item { border-left: 3px solid transparent; padding: 3px 2px; }
QTreeView::item:hover { color: #202124; background: #eef2f6; border-left-color: #9aa8b6; }
QTreeView::item:selected { color: #202124; background: #dce9f7; border-left-color: #405d7a; }
QTreeView#observerTree::item { border-left: 0; }
QSplitter::handle:horizontal { background: #e4e7eb; border-left: 1px solid #c8ced6; border-right: 1px solid #c8ced6; width: 8px; }
QSplitter::handle:vertical { background: #e4e7eb; border-top: 1px solid #c8ced6; border-bottom: 1px solid #c8ced6; height: 8px; }
QDockWidget { border-top: 1px solid #c8ced6; }
"""


def apply_light_theme(application: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f3f4f6"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#fafbfc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#dce9f7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#737b85"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#202124"))
    application.setPalette(palette)
    application.setStyleSheet(LIGHT_THEME)
