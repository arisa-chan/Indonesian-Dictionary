"""Collection panel for managing word collections."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QAbstractItemView,
    QPushButton, QComboBox, QLabel, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QModelIndex, QAbstractListModel
from PySide6.QtGui import QFont, QColor

from src.models import DictionaryEntry
from src.collection import CollectionManager
from src.srs import SrsManager


def _srs_color(days: int | None) -> QColor:
    """Return a color for an SRS status dot."""
    if days is None:
        return QColor("#999999")  # gray — never reviewed
    if days < 0:
        return QColor("#d32f2f")  # red — overdue
    if days == 0:
        return QColor("#f57c00")  # orange — due today
    if days <= 3:
        return QColor("#fbc02d")  # yellow — soon
    if days <= 7:
        return QColor("#388e3c")  # green — medium
    return QColor("#1976d2")  # blue — far out


def _srs_label(days: int | None) -> str:
    """Return a short SRS status label for list display."""
    if days is None:
        return ""
    if days < 0:
        return f"overdue {-days}d"
    if days == 0:
        return "due today"
    return f"in {days}d"


def _srs_summary(days: int | None, card) -> str:
    """Return a multi-line SRS summary for tooltips."""
    if days is None or card is None:
        return "Not yet reviewed"
    if days < 0:
        parts = [f"Overdue by {-days} days"]
    elif days == 0:
        parts = ["Due today"]
    else:
        parts = [f"Due in {days} days"]
    parts.append(f"Interval: {card.interval}d — Ease: {card.ease_factor:.1f}")
    if card.reps > 0:
        ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(card.reps, f"{card.reps}th")
        parts.append(f"{ordinal} review")
    else:
        parts.append("New card")
    return "\n".join(parts)


class CollectionListModel(QAbstractListModel):
    """List model for collection words with SRS indicators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._words: list[dict] = []
        self._srs: SrsManager | None = None
        self._collection: str = ""

    def set_srs_context(self, srs: SrsManager | None, collection: str):
        self._srs = srs
        self._collection = collection

    def rowCount(self, parent=QModelIndex()):
        return len(self._words)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        word_dict = self._words[index.row()]
        word = word_dict.get("word", "")
        days = self._srs_days(word)

        if role == Qt.DisplayRole:
            label = _srs_label(days)
            if label:
                return f"{word}  \u00b7 {label}"
            return word

        if role == Qt.DecorationRole:
            return _srs_color(days)

        if role == Qt.UserRole:
            return word_dict

        if role == Qt.ToolTipRole:
            lines = []
            card = self._srs_card(word)
            lines.append(_srs_summary(days, card))

            trans = word_dict.get("translations", [])
            if trans:
                lines.append(", ".join(trans[:3]))
            else:
                meanings = word_dict.get("meanings", [])
                if meanings:
                    lines.append(meanings[0][:120])
            return "\n\n".join(lines)

        return None

    def _srs_card(self, word: str):
        if not self._srs or not self._collection:
            return None
        return self._srs.get_card(self._collection, word)

    def _srs_days(self, word: str) -> int | None:
        card = self._srs_card(word)
        if card is None:
            return None
        return self._srs.days_from_today(card.due_date)

    def set_words(self, words: list[dict]):
        self.beginResetModel()
        self._words = words
        self.endResetModel()

    def get_word_dict(self, index: QModelIndex) -> dict | None:
        if index.isValid() and 0 <= index.row() < len(self._words):
            return self._words[index.row()]
        return None


class CollectionPanel(QWidget):
    """Panel for viewing and managing saved word collections."""

    word_selected = Signal(DictionaryEntry, str)  # entry, collection_name
    review_requested = Signal(str)  # collection_name

    def __init__(self, collection_mgr: CollectionManager,
                 srs_mgr: SrsManager | None = None, parent=None):
        super().__init__(parent)
        self._mgr = collection_mgr
        self._srs = srs_mgr
        self._current_collection = ""
        self._build_ui()
        self._refresh_collections()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Collection selector row
        selector_row = QHBoxLayout()
        selector_row.setSpacing(4)

        self._collection_combo = QComboBox()
        self._collection_combo.setMinimumHeight(28)
        self._collection_combo.currentTextChanged.connect(self._on_collection_changed)
        selector_row.addWidget(self._collection_combo, 1)

        new_btn = QPushButton("+")
        new_btn.setFixedSize(28, 28)
        new_btn.setToolTip("Create a new collection")
        new_btn.clicked.connect(self._create_collection)
        selector_row.addWidget(new_btn)

        del_btn = QPushButton("X")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("Delete this collection")
        del_btn.clicked.connect(self._delete_collection)
        selector_row.addWidget(del_btn)

        layout.addLayout(selector_row)

        # Word list
        self._list_model = CollectionListModel(self)
        self._list_view = QListView()
        self._list_view.setModel(self._list_model)
        self._list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list_view.setAlternatingRowColors(True)
        self._list_view.clicked.connect(self._on_word_clicked)
        self._list_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        font = QFont("Segoe UI", 11)
        self._list_view.setFont(font)
        layout.addWidget(self._list_view, 1)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        # Review button
        self._review_btn = QPushButton("Review Flashcards")
        self._review_btn.setMinimumHeight(30)
        self._review_btn.clicked.connect(self._request_review)
        self._review_btn.setStyleSheet("""
            QPushButton {
                background: #4caf50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #43a047;
            }
        """)
        btn_row.addWidget(self._review_btn)

        # Reset SRS button
        self._reset_srs_btn = QPushButton("Reset SRS")
        self._reset_srs_btn.setMinimumHeight(30)
        self._reset_srs_btn.setToolTip("Clear SRS data for the selected word")
        self._reset_srs_btn.clicked.connect(self._reset_srs)
        self._reset_srs_btn.setEnabled(False)
        btn_row.addWidget(self._reset_srs_btn)

        btn_row.addStretch()

        self._remove_btn = QPushButton("Remove from Collection")
        self._remove_btn.setMinimumHeight(30)
        self._remove_btn.clicked.connect(self._remove_word)
        self._remove_btn.setEnabled(False)
        btn_row.addWidget(self._remove_btn)

        layout.addLayout(btn_row)

        # Style
        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: #fafafa;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #f0f0f0;
                border-color: #aaa;
            }
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                background: #fafafa;
                padding: 2px 8px;
                font-size: 12px;
            }
            QListView {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: #fdfdfd;
                padding: 2px;
            }
            QListView::item {
                padding: 4px 8px;
                border-radius: 2px;
            }
            QListView::item:selected {
                background: #fde8e8;
                color: #ce1126;
            }
        """)

    def _refresh_collections(self):
        collections = self._mgr.list_collections()
        self._collection_combo.blockSignals(True)
        self._collection_combo.clear()
        if collections:
            for name in collections:
                self._collection_combo.addItem(name)
        else:
            self._collection_combo.addItem("(no collections)")
        self._collection_combo.blockSignals(False)

        if collections:
            self._current_collection = collections[0]
            self._collection_combo.setCurrentText(self._current_collection)
            self._on_collection_changed(self._current_collection)
        else:
            self._current_collection = ""
            self._list_model.set_words([])

    def _on_collection_changed(self, name: str):
        if name == "(no collections)":
            return
        self._current_collection = name
        self._list_model.set_srs_context(self._srs, name)
        words = self._mgr.get_words(name)
        self._list_model.set_words(words)

    def _request_review(self):
        collection = self._collection_combo.currentText()
        if collection and collection != "(no collections)":
            self.review_requested.emit(collection)

    def _create_collection(self):
        name, ok = QInputDialog.getText(
            self, "New Collection", "Collection name:"
        )
        if ok and name.strip():
            self._mgr.create_collection(name.strip())
            self._refresh_collections()

    def _delete_collection(self):
        if not self._current_collection:
            return
        reply = QMessageBox.question(
            self,
            "Delete Collection",
            f'Delete collection "{self._current_collection}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._mgr.delete_collection(self._current_collection)
            self._refresh_collections()

    def _on_word_clicked(self, index: QModelIndex):
        data = self._list_model.get_word_dict(index)
        if data:
            entry = self._mgr.dict_to_entry(data)
            self.word_selected.emit(entry, self._current_collection)

    def _on_selection_changed(self):
        has_selection = self._list_view.selectionModel().hasSelection()
        self._remove_btn.setEnabled(has_selection)
        self._reset_srs_btn.setEnabled(has_selection)

    def _remove_word(self):
        indexes = self._list_view.selectedIndexes()
        collection = self._collection_combo.currentText()
        if not indexes or not collection or collection == "(no collections)":
            return
        data = self._list_model.get_word_dict(indexes[0])
        if data:
            word = data.get("word", "")
            self._mgr.remove_word(collection, word)
            words = self._mgr.get_words(collection)
            self._list_model.set_words(words)

    def _reset_srs(self):
        indexes = self._list_view.selectedIndexes()
        collection = self._collection_combo.currentText()
        if not self._srs or not indexes or not collection or collection == "(no collections)":
            return
        data = self._list_model.get_word_dict(indexes[0])
        if data:
            word = data.get("word", "")
            self._srs.reset_card(collection, word)
            # Refresh display to update SRS indicators
            self._list_model.set_words(self._mgr.get_words(collection))

    def refresh_current(self):
        """Refresh the current collection's word list (e.g., after a review)."""
        if self._current_collection and self._current_collection != "(no collections)":
            words = self._mgr.get_words(self._current_collection)
            self._list_model.set_words(words)

    def add_current_word(self, entry: DictionaryEntry) -> bool:
        """Add an entry to the current collection. Returns True if added."""
        collection = self._collection_combo.currentText()
        if not collection or collection == "(no collections)":
            return False
        if self._mgr.is_saved(collection, entry.word):
            return False
        self._mgr.add_word(collection, entry)
        words = self._mgr.get_words(collection)
        self._list_model.set_words(words)
        return True
