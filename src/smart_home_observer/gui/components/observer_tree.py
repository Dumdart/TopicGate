from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QStyle,
    QToolButton,
    QTreeView,
)

from smart_home_observer.gui.components.workspace_pane import WorkspacePane

TOPIC_ROLE = Qt.ItemDataRole.UserRole + 1


class ObserverTreePane(WorkspacePane):
    """Searchable tree of configured and dynamically observed MQTT topics."""

    topic_selected = Signal(str)
    add_filter_requested = Signal()

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

        expand_button = QToolButton()
        expand_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        expand_button.setToolTip("Expand all topics")
        expand_button.setAccessibleName("Expand all topics")
        expand_button.clicked.connect(self.expand_all)
        controls.addWidget(expand_button)

        collapse_button = QToolButton()
        collapse_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        )
        collapse_button.setToolTip("Collapse all topics")
        collapse_button.setAccessibleName("Collapse all topics")
        collapse_button.clicked.connect(self.collapse_all)
        controls.addWidget(collapse_button)
        self.content_layout.addLayout(controls)

        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["Topic"])
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
        self._tree.selectionModel().currentChanged.connect(
            self._selection_changed
        )
        self._search_edit.textChanged.connect(self._proxy.setFilterFixedString)
        self.content_layout.addWidget(self._tree, 1)

    def render(self, topic_paths: list[str], selected_topic: str) -> None:
        expanded_paths = {
            path
            for path, item in self._items.items()
            if self._tree.isExpanded(self._proxy.mapFromSource(item.index()))
        }
        self._model.removeRows(0, self._model.rowCount())
        self._items.clear()

        for topic in topic_paths:
            self._add_topic(topic)

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
                parent.appendRow(item)
                self._items[path] = item
            parent = item

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
