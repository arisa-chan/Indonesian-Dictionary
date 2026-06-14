"""Search panel with search bar and dictionary mode selector."""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QComboBox, QLabel, QFrame
)
from PySide6.QtCore import Signal, QTimer



class SearchPanel(QWidget):
    """Top panel: search bar + dictionary mode combo box."""

    search_requested = Signal(str, str)  # query, dict_mode

    MODES = [
        ("id_en", "Indonesian → English"),
        ("en_id", "English → Indonesian"),
        ("id_id", "Indonesian → Indonesian"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._emit_search)

        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(32)
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._emit_search_now)
        layout.addWidget(self._search_input, 1)

        self._mode_combo = QComboBox()
        self._mode_combo.setMinimumHeight(32)
        for value, label in self.MODES:
            self._mode_combo.addItem(label, value)
        self._mode_combo.currentIndexChanged.connect(self._emit_search_now)
        layout.addWidget(self._mode_combo)

    def _on_text_changed(self):
        """Debounce search on typing."""
        self._debounce_timer.start()

    def _emit_search(self):
        """Emit the search signal."""
        query = self._search_input.text()
        mode = self._mode_combo.currentData()
        self.search_requested.emit(query, mode)

    def _emit_search_now(self):
        """Emit immediately (Enter pressed or mode changed)."""
        self._debounce_timer.stop()
        self._emit_search()

    def focus_search(self):
        """Set focus to the search input."""
        self._search_input.setFocus()
        self._search_input.selectAll()

    @property
    def current_mode(self) -> str:
        return self._mode_combo.currentData()

    def set_mode(self, mode: str):
        """Set the dictionary mode programmatically."""
        for i in range(self._mode_combo.count()):
            if self._mode_combo.itemData(i) == mode:
                self._mode_combo.setCurrentIndex(i)
                break
