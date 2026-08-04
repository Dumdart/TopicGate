from PySide6.QtWidgets import QFormLayout, QLabel, QMainWindow, QWidget

from smart_home_observer.gui.main_view_model import MainViewModel


class MainWindow(QMainWindow):
    """Displays the latest state for the selected observer topic."""

    def __init__(self, view_model: MainViewModel) -> None:
        super().__init__()
        self._view_model = view_model
        self.setWindowTitle(view_model.title)

        self._topic_label = QLabel()
        self._value_label = QLabel()
        self._received_at_label = QLabel()
        self._quality_of_service_label = QLabel()
        self._retained_label = QLabel()

        content = QWidget()
        layout = QFormLayout(content)
        layout.addRow("Topic", self._topic_label)
        layout.addRow("Latest value", self._value_label)
        layout.addRow("Received", self._received_at_label)
        layout.addRow("QoS", self._quality_of_service_label)
        layout.addRow("Retained", self._retained_label)
        self.setCentralWidget(content)
        self.resize(520, 180)

        self._view_model.state_changed.connect(self._render)
        self._render()

    def _render(self) -> None:
        self._topic_label.setText(self._view_model.topic)
        self._value_label.setText(self._view_model.value)
        self._received_at_label.setText(self._view_model.received_at)
        self._quality_of_service_label.setText(self._view_model.quality_of_service)
        self._retained_label.setText(self._view_model.retained)
