from uuid import UUID

from PySide6.QtCore import QModelIndex, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QStyle,
    QToolButton,
    QTreeView,
    QWidget,
)

from smart_home_observer.core.models.broker_profile import BrokerProfile
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.components.workspace_pane import WorkspacePane

TOPIC_ROLE = Qt.ItemDataRole.UserRole + 1


class ObserverTreePane(WorkspacePane):
    """Searchable tree of configured and dynamically observed MQTT topics."""

    topic_selected = Signal(str)
    add_filter_requested = Signal()
    remove_filter_requested = Signal(object)
    broker_profile_selected = Signal(object)
    add_broker_profile_requested = Signal()
    edit_broker_profile_requested = Signal()
    delete_broker_profile_requested = Signal()

    def __init__(self) -> None:
        super().__init__("Observer Tree")
        self._items: dict[str, QStandardItem] = {}

        controls = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search topics...")
        self._search_edit.setClearButtonEnabled(True)
        controls.addWidget(self._search_edit, 1)

        add_button = QToolButton()
        add_button.setText("+ Filter")
        add_button.setToolTip("Add an MQTT subscription filter")
        add_button.clicked.connect(self.add_filter_requested)
        controls.addWidget(add_button)

        self._broker_profile_button = QToolButton()
        self._broker_profile_button.setObjectName("brokerProfileButton")
        self._broker_profile_button.setMinimumWidth(126)
        self._broker_profile_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self._broker_profile_menu = QMenu(self._broker_profile_button)
        self._broker_profile_button.setMenu(self._broker_profile_menu)
        controls.addWidget(self._broker_profile_button)
        self.content_layout.addLayout(controls)

        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["Topic", ""])
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setRecursiveFilteringEnabled(True)
        self._proxy.setFilterKeyColumn(0)

        self._tree = QTreeView()
        self._tree.setObjectName("observerTree")
        self._tree.setModel(self._proxy)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.header().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Fixed,
        )
        self._tree.header().resizeSection(1, 34)
        self._tree.selectionModel().currentChanged.connect(
            self._selection_changed
        )
        self._search_edit.textChanged.connect(self._proxy.setFilterFixedString)
        self.content_layout.addWidget(self._tree, 1)

    def render(
        self,
        topic_paths: list[str],
        selected_topic: str,
        subscriptions: tuple[Subscription, ...] = (),
    ) -> None:
        expanded_paths = {
            path
            for path, item in self._items.items()
            if self._tree.isExpanded(self._proxy.mapFromSource(item.index()))
        }
        self._model.removeRows(0, self._model.rowCount())
        self._items.clear()

        for topic in topic_paths:
            self._add_topic(topic)

        for subscription in subscriptions:
            self._add_remove_button(subscription)

        if expanded_paths:
            self._restore_expanded_paths(expanded_paths)
        else:
            self._tree.expandToDepth(1)
        self.select_topic(selected_topic)

    def select_topic(self, topic: str) -> None:
        item = self._items.get(topic)
        if item is None:
            return
        proxy_index = self._proxy.mapFromSource(item.index())
        if proxy_index.isValid():
            self._tree.setCurrentIndex(proxy_index)
            self._tree.scrollTo(proxy_index)

    def expand_all(self) -> None:
        self._tree.expandAll()

    def collapse_all(self) -> None:
        self._tree.collapseAll()

    def render_broker_profiles(
        self,
        profiles: tuple[BrokerProfile, ...],
        active_profile_id: UUID,
    ) -> None:
        """Render a quick-switch menu for the available broker profiles."""
        self._broker_profile_menu.clear()
        active_profile = next(
            profile for profile in profiles if profile.id == active_profile_id
        )
        self._broker_profile_button.setText(active_profile.name)
        self._broker_profile_button.setToolTip(
            f"Switch broker profile (current: {active_profile.name})"
        )
        self._broker_profile_button.setAccessibleName("Switch broker profile")
        for profile in profiles:
            action = self._broker_profile_menu.addAction(profile.name)
            action.setCheckable(True)
            action.setChecked(profile.id == active_profile_id)
            action.setEnabled(profile.id != active_profile_id)
            action.triggered.connect(
                lambda _checked=False, profile_id=profile.id: (
                    self.broker_profile_selected.emit(profile_id)
                )
            )
        self._broker_profile_menu.addSeparator()
        add_action = self._broker_profile_menu.addAction("Add profile...")
        add_action.setObjectName("addBrokerProfileAction")
        add_action.triggered.connect(self.add_broker_profile_requested.emit)
        edit_action = self._broker_profile_menu.addAction("Edit current profile...")
        edit_action.setObjectName("editBrokerProfileAction")
        edit_action.triggered.connect(self.edit_broker_profile_requested.emit)
        delete_action = self._broker_profile_menu.addAction(
            "Delete current profile..."
        )
        delete_action.setObjectName("deleteBrokerProfileAction")
        delete_action.setEnabled(len(profiles) > 1)
        delete_action.triggered.connect(self.delete_broker_profile_requested.emit)

    def set_profile_switching(self, switching: bool) -> None:
        """Prevent duplicate profile switches while the broker reconnects."""
        self._broker_profile_button.setEnabled(not switching)

    def _add_topic(self, topic: str) -> None:
        parent = self._model.invisibleRootItem()
        partial_path: list[str] = []
        for segment in topic.split("/"):
            partial_path.append(segment)
            path = "/".join(partial_path)
            item = self._items.get(path)
            if item is None:
                item = QStandardItem(segment or "/")
                item.setEditable(False)
                item.setData(path, TOPIC_ROLE)
                action_item = QStandardItem()
                action_item.setEditable(False)
                parent.appendRow([item, action_item])
                self._items[path] = item
            parent = item

    def _add_remove_button(self, subscription: Subscription) -> None:
        item = self._items.get(subscription.topic_filter)
        if item is None:
            return

        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(5, 0, 5, 0)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button = QToolButton(action_widget)
        button.setObjectName("removeSubscriptionButton")
        button.setFixedSize(24, 18)
        button.setIconSize(QSize(12, 12))
        button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        button.setStyleSheet(
            "QToolButton {"
            " background-color: #7f1d1d;"
            " border: 1px solid #b91c1c;"
            " border-radius: 4px;"
            " padding: 0;"
            "}"
            "QToolButton:hover {"
            " background-color: #b91c1c;"
            " border-color: #ef4444;"
            "}"
            "QToolButton:pressed {"
            " background-color: #450a0a;"
            " border-color: #991b1b;"
            "}"
        )
        button.setToolTip(f"Remove subscription {subscription.topic_filter}")
        button.setAccessibleName(
            f"Remove subscription {subscription.topic_filter}"
        )
        button.clicked.connect(
            lambda _checked=False, subscription=subscription: (
                self.remove_filter_requested.emit(subscription)
            )
        )
        action_layout.addWidget(button)
        action_index = item.index().siblingAtColumn(1)
        self._tree.setIndexWidget(
            self._proxy.mapFromSource(action_index),
            action_widget,
        )

    def _restore_expanded_paths(self, expanded_paths: set[str]) -> None:
        for path in expanded_paths:
            item = self._items.get(path)
            if item is not None:
                self._tree.setExpanded(
                    self._proxy.mapFromSource(item.index()),
                    True,
                )

    def _selection_changed(
        self,
        current: QModelIndex,
        _previous: QModelIndex,
    ) -> None:
        source_index = self._proxy.mapToSource(current)
        topic = self._model.data(source_index, TOPIC_ROLE) or ""
        self.topic_selected.emit(str(topic))
