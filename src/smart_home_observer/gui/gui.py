import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from smart_home_observer.gui.main_view_model import MainViewModel


class MainWindow(QMainWindow):
    def __init__(self, view_model: MainViewModel) -> None:
        super().__init__()
        self.setWindowTitle(view_model.title)
        self.setCentralWidget(QLabel(view_model.message))
        self.resize(360, 120)
