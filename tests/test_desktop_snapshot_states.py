import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from topicgate.gui.components.observer_tree import ObserverTreePane
from topicgate.gui.components.snapshot_panel import SnapshotPanel
from topicgate.presentation.snapshot_presentation import (
    BrokerSnapshotHealth,
    TopicStateBadge,
)
from topicgate.presentation.topic_presentation import TopicTreeNode


def test_observer_tree_visually_distinguishes_all_snapshot_states() -> None:
    application = QApplication.instance() or QApplication([])
    pane = ObserverTreePane()
    nodes = tuple(
        TopicTreeNode(
            label=name,
            path=name,
            selectable=True,
            is_subscription=False,
            is_observed=True,
            children=(),
            badges=badges,
        )
        for name, badges in (
            ("live", (TopicStateBadge("live", "Live", "success"),)),
            (
                "cached",
                (
                    TopicStateBadge("cached", "Cached", "info"),
                    TopicStateBadge("stored", "Stored", "neutral"),
                ),
            ),
            (
                "stale",
                (
                    TopicStateBadge("stale", "Stale", "warning"),
                    TopicStateBadge("stored", "Stored", "neutral"),
                ),
            ),
        )
    )

    pane.render_tree(nodes, "")

    labels = [item.text() for item in pane.findChildren(QLabel, "topicStateBadge")]
    assert labels.count("Live") == 1
    assert labels.count("Cached") == 1
    assert labels.count("Stale") == 1
    assert labels.count("Stored") == 2
    pane.deleteLater()
    application.processEvents()


def test_snapshot_panel_renders_truncated_partial_and_empty_snapshots() -> None:
    application = QApplication.instance() or QApplication([])
    panel = SnapshotPanel()
    partial = BrokerSnapshotHealth(
        "captured",
        "connected",
        "observing",
        "2.0 seconds",
        1,
        3,
        2,
        1,
        4,
        "Limited",
        ("Topics were omitted by the result limit.",),
    )
    panel.render_health(partial)

    assert panel.findChild(QLabel, "snapshotTruncatedCount").text() == "1"
    assert panel.findChild(QLabel, "snapshotCompletenessStatus").text() == "Limited"
    assert "omitted" in panel.findChild(QLabel, "snapshotLimitations").text().lower()

    empty = BrokerSnapshotHealth(
        "captured",
        "Not started",
        "Not started",
        "Not observing",
        0,
        0,
        0,
        0,
        0,
        "Complete",
        (),
    )
    panel.render_health(empty)
    assert panel.findChild(QLabel, "snapshotReturnedCount").text() == "0"
    assert panel.findChild(QLabel, "snapshotCompletenessStatus").text() == "Complete"
    panel.deleteLater()
    application.processEvents()
