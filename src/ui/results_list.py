"""Results list showing matching dictionary entries."""

from PySide6.QtWidgets import QListView, QAbstractItemView
from PySide6.QtCore import Qt, Signal, QAbstractListModel, QModelIndex
from PySide6.QtGui import QFont

from src.models import DictionaryEntry
from src.utils import pos_label


class ResultsModel(QAbstractListModel):
    """List model for dictionary entries."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[DictionaryEntry] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]

        if role == Qt.DisplayRole:
            pos = pos_label(entry.pos)
            if pos:
                return f"{entry.word}  ({pos})"
            return entry.word

        if role == Qt.UserRole:
            return entry

        if role == Qt.ToolTipRole:
            return self._tooltip(entry)

        return None

    def set_entries(self, entries: list[DictionaryEntry]):
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def get_entry(self, index: QModelIndex) -> DictionaryEntry | None:
        if index.isValid() and 0 <= index.row() < len(self._entries):
            return self._entries[index.row()]
        return None

    @staticmethod
    def _tooltip(entry: DictionaryEntry) -> str:
        lines = []
        if entry.meanings:
            lines.append(entry.meanings[0][:120])
        elif entry.translations:
            lines.append(", ".join(entry.translations[:3]))
        return "\n".join(lines)


class ResultsList(QListView):
    """List view for search results."""

    entry_selected = Signal(DictionaryEntry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ResultsModel(self)
        self.setModel(self._model)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        font = QFont("Segoe UI", 11)
        self.setFont(font)

        self.selectionModel().currentChanged.connect(self._on_selection_changed)

    def set_results(self, entries: list[DictionaryEntry]):
        """Update the list with new search results."""
        self._model.set_entries(entries)
        if entries:
            self.setCurrentIndex(self._model.index(0, 0))

    def _on_selection_changed(self, current, previous):
        entry = self._model.get_entry(current)
        if entry:
            self.entry_selected.emit(entry)
