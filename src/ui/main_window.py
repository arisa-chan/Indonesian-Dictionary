"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QStatusBar, QWidget, QVBoxLayout, QTabWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from .search_panel import SearchPanel
from .results_list import ResultsList
from .detail_panel import DetailPanel
from .collection_panel import CollectionPanel
from .flashcard_window import FlashcardWindow
from src.dictionary import DictionaryManager
from src.collection import CollectionManager
from src.srs import SrsManager
from src.models import DictionaryEntry


class MainWindow(QMainWindow):
    """Indonesian Dictionary main window."""

    def __init__(self, dict_manager: DictionaryManager, collection_mgr: CollectionManager, srs_mgr: SrsManager):
        super().__init__()
        self._dict = dict_manager
        self._collections = collection_mgr
        self._srs = srs_mgr
        self._current_mode = "id_en"
        self._current_query = ""

        self.setWindowTitle("Indonesian Dictionary")
        self.resize(1100, 680)
        self.setMinimumSize(900, 500)

        self._build_ui()
        self._setup_shortcuts()
        self._apply_stylesheet()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        self._search_panel = SearchPanel()

        # Left panel: tabbed (results + collections)
        self._left_tabs = QTabWidget()
        self._left_tabs.setTabPosition(QTabWidget.North)
        self._left_tabs.setMinimumWidth(260)

        self._results_list = ResultsList()
        self._left_tabs.addTab(self._results_list, "Results")

        self._collection_panel = CollectionPanel(self._collections, srs_mgr=self._srs)
        self._left_tabs.addTab(self._collection_panel, "Collections")

        self._detail_panel = DetailPanel(srs_mgr=self._srs)
        self._detail_panel.save_requested.connect(self._on_save_to_collection)

        # Horizontal splitter: tabs | detail
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self._left_tabs)
        h_splitter.addWidget(self._detail_panel)
        h_splitter.setStretchFactor(0, 2)
        h_splitter.setStretchFactor(1, 3)
        h_splitter.setSizes([320, 780])

        # Main layout: search on top, splitter below
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._search_panel)
        main_layout.addWidget(h_splitter, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, self._search_panel.focus_search)
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._switch_mode("id_en"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._switch_mode("en_id"))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._switch_mode("id_id"))

    def _switch_mode(self, mode: str):
        self._search_panel.set_mode(mode)

    def _connect_signals(self):
        self._search_panel.search_requested.connect(self._on_search)
        self._results_list.entry_selected.connect(self._on_entry_selected)
        self._collection_panel.word_selected.connect(self._on_collection_word_selected)
        self._collection_panel.review_requested.connect(self._on_start_review)

    def _on_search(self, query: str, mode: str):
        if query == self._current_query and mode == self._current_mode:
            return
        self._current_query = query
        self._current_mode = mode

        results = self._dict.search(query, mode)
        self._results_list.set_results(results)

        count = len(results)
        if query.strip():
            self._status_bar.showMessage(
                f"Found {count:,} result{'s' if count != 1 else ''} for \"{query}\""
            )
        else:
            self._status_bar.showMessage(f"{count:,} words loaded")

    def _on_entry_selected(self, entry: DictionaryEntry):
        self._detail_panel.show_entry(
            entry, query=self._current_query, mode=self._current_mode
        )

    def _on_save_to_collection(self, entry: DictionaryEntry):
        """Handle save-to-collection request from detail panel."""
        added = self._collection_panel.add_current_word(entry)
        if added:
            self._status_bar.showMessage(
                f'Saved "{entry.word}" to collection', 3000
            )
            self._left_tabs.setCurrentWidget(self._collection_panel)
        else:
            self._status_bar.showMessage(
                f'"{entry.word}" is already in the collection or no collection selected', 3000
            )

    def _on_collection_word_selected(self, entry: DictionaryEntry, collection: str = ""):
        """When a word is clicked in the collection panel, show it in the detail panel."""
        self._detail_panel.show_entry(
            entry, query="", mode="id_en", collection=collection
        )
        self._left_tabs.setCurrentWidget(self._results_list)

    def _on_start_review(self, collection_name: str):
        """Launch flashcard review for the given collection."""
        words = self._collections.get_words(collection_name)
        if not words:
            self._status_bar.showMessage("No words in this collection", 3000)
            return

        due_cards = self._srs.get_due_cards(collection_name, words)
        if not due_cards:
            self._status_bar.showMessage("No cards due for review!", 3000)
            return

        dialog = FlashcardWindow(self._srs, collection_name, due_cards, self)
        dialog.finished_review.connect(self._on_review_finished)
        dialog.exec()

    def _on_review_finished(self, collection_name: str, total_reviewed: int):
        self._status_bar.showMessage(
            f"Review complete — {total_reviewed} cards reviewed in \"{collection_name}\"", 5000
        )
        self._collection_panel.refresh_current()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }

            QSplitter::handle {
                background-color: #e0e0e0;
                width: 1px;
            }

            QStatusBar {
                background-color: #f8f8f8;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
                color: #666;
                padding: 2px 8px;
            }

            QLineEdit {
                padding: 4px 8px;
                border: 2px solid #ddd;
                border-radius: 6px;
                background: #fafafa;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #ce1126;
                background: #ffffff;
            }

            QComboBox {
                padding: 4px 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                background: #fafafa;
                font-size: 13px;
                min-width: 200px;
            }
            QComboBox:focus {
                border-color: #ce1126;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }

            QListView {
                border: none;
                background: #fdfdfd;
                font-size: 14px;
                padding: 4px;
            }
            QListView::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QListView::item:selected {
                background: #fde8e8;
                color: #ce1126;
            }
            QListView::item:hover:!selected {
                background: #f5f5f5;
            }

            QTextBrowser {
                border: none;
                background: #ffffff;
                padding: 8px;
            }
        """)
