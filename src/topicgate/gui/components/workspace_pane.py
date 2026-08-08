from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout


class WorkspacePane(QFrame):
    """Common framed pane used inside the workspace splitter."""

    def __init__(
        self,
        title: str,
        minimum_hint_width: int = 240,
    ) -> None:
        super().__init__()
        self._minimum_hint_width = minimum_hint_width
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.content_layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.content_layout.addWidget(heading)

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        hint.setWidth(self._minimum_hint_width)
        return hint
