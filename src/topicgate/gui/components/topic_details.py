from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from topicgate.gui.main_view_model import MainViewModel
from topicgate.gui.components.workspace_pane import WorkspacePane
from topicgate.gui.components.topic_metadata import TopicMetadataPane


class TopicDetailsPane(WorkspacePane):
    """Read-only details and statistics for the selected live topic."""

    topic_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__("Details / Stats")

        self._filter_summary = QWidget()
        self._filter_summary.setObjectName("subscriptionFilterSummary")
        filter_layout = QVBoxLayout(self._filter_summary)
        filter_layout.setContentsMargins(0, 0, 0, 0)

        self._filter_notice = QLabel()
        self._filter_notice.setObjectName("subscriptionFilterNotice")
        self._filter_notice.setTextFormat(Qt.TextFormat.PlainText)
        self._filter_notice.setWordWrap(True)
        filter_layout.addWidget(self._filter_notice)

        filter_form = QFormLayout()
        self._filter_labels = {
            name: self._plain_label(object_name)
            for name, object_name in (
                ("topics", "filterMatchingTopicCount"),
                ("messages", "filterMessageCount"),
                ("states", "filterStateCounts"),
                ("retained", "filterRetainedCount"),
            )
        }
        filter_form.addRow("Matching topics", self._filter_labels["topics"])
        filter_form.addRow("Messages observed", self._filter_labels["messages"])
        filter_form.addRow("Current states", self._filter_labels["states"])
        filter_form.addRow("Retained topics", self._filter_labels["retained"])
        filter_layout.addLayout(filter_form)

        self._filter_topics = QTableWidget(0, 2)
        self._filter_topics.setObjectName("filterMatchingTopics")
        self._filter_topics.setHorizontalHeaderLabels(
            ["Topic", "Last received"]
        )
        self._filter_topics.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._filter_topics.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._filter_topics.setAlternatingRowColors(True)
        self._filter_topics.verticalHeader().setVisible(False)
        header = self._filter_topics.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self._filter_topics.cellClicked.connect(self._select_filter_topic)
        filter_layout.addWidget(self._filter_topics, 1)

        self._filter_scope = QLabel(
            "Current snapshot only. Topics omitted by snapshot filters, age, "
            "or result limits are not included."
        )
        self._filter_scope.setObjectName("filterSummaryScope")
        self._filter_scope.setTextFormat(Qt.TextFormat.PlainText)
        self._filter_scope.setWordWrap(True)
        filter_layout.addWidget(self._filter_scope)
        self._filter_summary.setHidden(True)
        self.content_layout.addWidget(self._filter_summary, 1)

        self._metadata = TopicMetadataPane()
        self.content_layout.addWidget(self._metadata)

        self._decoded_label = self._section_label("Decoded payload")
        self.content_layout.addWidget(self._decoded_label)
        self._decoded_payload = QPlainTextEdit()
        self._decoded_payload.setObjectName("decodedPayload")
        self._decoded_payload.setReadOnly(True)
        self._decoded_payload.setPlaceholderText(
            "Select a topic to inspect its payload"
        )
        self.content_layout.addWidget(self._decoded_payload, 3)

        self._raw_label = self._section_label("Raw payload (hex)")
        self.content_layout.addWidget(self._raw_label)
        self._raw_payload = QPlainTextEdit()
        self._raw_payload.setObjectName("rawPayload")
        self._raw_payload.setReadOnly(True)
        self._raw_payload.setMaximumHeight(110)
        self.content_layout.addWidget(self._raw_payload, 1)

    def render(self, view_model: MainViewModel) -> None:
        summary = view_model.selected_wildcard_filter_summary
        showing_filter = summary is not None
        self._filter_summary.setVisible(showing_filter)
        self._filter_notice.setVisible(showing_filter)
        for widget in (
            self._metadata,
            self._decoded_label,
            self._decoded_payload,
            self._raw_label,
            self._raw_payload,
        ):
            widget.setVisible(not showing_filter)
        if summary is not None:
            self._filter_notice.setText(
                f"Subscription filter: {summary.topic_filter}\n"
                "Aggregate statistics for matching concrete topic paths."
            )
            self._filter_labels["topics"].setText(
                str(summary.matching_topic_count)
            )
            self._filter_labels["messages"].setText(str(summary.message_count))
            self._filter_labels["states"].setText(
                f"Live {summary.live_count} · Cached {summary.cached_count} · "
                f"Stale {summary.stale_count}"
            )
            self._filter_labels["retained"].setText(str(summary.retained_count))
            self._filter_topics.setRowCount(len(summary.topics))
            for row, topic in enumerate(summary.topics):
                values = (
                    topic.topic,
                    topic.received_at,
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, topic.topic)
                    self._filter_topics.setItem(row, column, item)
            return

        detail = view_model.topic_detail
        self._metadata.render(detail)
        self._decoded_payload.setPlainText(detail.decoded_payload)
        self._raw_payload.setPlainText(detail.raw_payload)

    def focus_payload(self) -> None:
        self._decoded_payload.setFocus(Qt.FocusReason.OtherFocusReason)

    def _select_filter_topic(self, row: int, _column: int) -> None:
        item = self._filter_topics.item(row, 0)
        if item is not None:
            self.topic_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label

    @staticmethod
    def _plain_label(name: str) -> QLabel:
        label = QLabel("0")
        label.setObjectName(name)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        return label


# Backward-compatible name while the pane acts as the primary content component.
TopicContentPane = TopicDetailsPane
