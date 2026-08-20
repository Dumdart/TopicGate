from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class McpSetupDialog(QDialog):
    """Show a copyable, deliberately read-only MCP client configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mcpSetupDialog")
        self.setWindowTitle("Configure TopicGate MCP")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        introduction = QLabel(
            "Add this server to your MCP host, then restart that host. "
            "Read-only mode is the safe default; use control mode only for a trusted host."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        self._configuration = QPlainTextEdit(
            '{\n'
            '  "mcpServers": {\n'
            '    "topicgate": {\n'
            '      "command": "topicgate",\n'
            '      "args": ["--mode", "read-only"]\n'
            '    }\n'
            '  }\n'
            '}'
        )
        self._configuration.setObjectName("mcpSetupConfiguration")
        self._configuration.setReadOnly(True)
        self._configuration.setAccessibleName("TopicGate MCP configuration")
        layout.addWidget(self._configuration)
        copy_button = QPushButton("Copy configuration")
        copy_button.setObjectName("copyMcpConfigurationButton")
        copy_button.setAccessibleName("Copy TopicGate MCP configuration")
        copy_button.clicked.connect(self._copy_configuration)
        layout.addWidget(copy_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def _copy_configuration(self) -> None:
        QGuiApplication.clipboard().setText(self._configuration.toPlainText())

