"""Flashcard review window with spaced repetition (SM-2 algorithm).

Shows one side at a time. User taps to flip, then rates recall.
Cycles through all due cards in the selected collection.
"""

import html

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QFrame, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont

from src.srs import SrsManager


class FlashCard(QFrame):
    """A single flashcard that flips on click to reveal the answer."""

    flipped = Signal()

    FRONT_STYLE = """
        QFrame#flashcard {
            background: #ffffff;
            border: 2px solid #ce1126;
            border-radius: 12px;
        }
    """
    BACK_STYLE = """
        QFrame#flashcard {
            background: #fef8f8;
            border: 2px solid #ce1126;
            border-radius: 12px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("flashcard")
        self.setMinimumSize(320, 220)
        self.setCursor(Qt.PointingHandCursor)
        self._is_front = True
        self._build_ui()

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(8)

        self._word_label = QLabel()
        self._word_label.setAlignment(Qt.AlignCenter)
        self._word_label.setWordWrap(True)
        self._word_label.setFont(QFont("Segoe UI", 30, QFont.Bold))
        self._word_label.setStyleSheet("color: #ce1126;")
        self._layout.addWidget(self._word_label)

        self._sub_label = QLabel()
        self._sub_label.setAlignment(Qt.AlignCenter)
        self._sub_label.setWordWrap(True)
        self._sub_label.setFont(QFont("Segoe UI", 14))
        self._sub_label.setStyleSheet("color: #555;")
        self._layout.addWidget(self._sub_label)

        self._extra_label = QLabel()
        self._extra_label.setAlignment(Qt.AlignCenter)
        self._extra_label.setWordWrap(True)
        self._extra_label.setFont(QFont("Segoe UI", 11))
        self._extra_label.setStyleSheet("color: #888;")
        self._extra_label.setVisible(False)
        self._layout.addWidget(self._extra_label)

        self._layout.addStretch()

        self._hint = QLabel("Click to reveal")
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setFont(QFont("Segoe UI", 10))
        self._hint.setStyleSheet("color: #ccc;")
        self._layout.addWidget(self._hint)

    def mousePressEvent(self, event):
        self.flip()

    def set_front(self, word: str, pos: str | None = None):
        self._is_front = True
        self._word_label.setText(html.escape(word))
        if pos:
            self._sub_label.setText(html.escape(pos))
        else:
            self._sub_label.setText("")
        self._extra_label.setVisible(False)
        self._hint.setText("Click to reveal")
        self.setStyleSheet(self.FRONT_STYLE)

    def set_back(self, translations: list[str], meanings: list[str],
                 examples: list[str] | list[dict]):
        self._is_front = False
        parts = []

        if translations:
            self._sub_label.setText(" / ".join(
                html.escape(t) for t in translations[:5]
            ))
        elif meanings:
            self._sub_label.setText(html.escape(meanings[0][:200]))
        else:
            self._sub_label.setText("(no definition)")

        if examples:
            self._extra_label.setVisible(True)
            if isinstance(examples[0], dict):
                ex_text = examples[0].get("id", str(examples[0]))
                ex_en = examples[0].get("en", "")
                display = html.escape(ex_text)
                if ex_en:
                    display += f"\n{html.escape(ex_en)}"
                self._extra_label.setText(display)
            else:
                self._extra_label.setText(html.escape(str(examples[0])[:200]))
        else:
            self._extra_label.setVisible(False)

        self._hint.setText("")
        self.setStyleSheet(self.BACK_STYLE)

    def flip(self):
        if self._is_front:
            self.flipped.emit()


class FlashcardWindow(QDialog):
    """Modal dialog for reviewing flashcards with SRS."""

    finished_review = Signal(str, int)  # collection_name, total_reviewed

    RATING_BUTTONS = [
        (0, "Again", "#d32f2f", "Complete blackout — reset card"),
        (1, "Hard", "#f57c00", "Recalled with significant difficulty"),
        (2, "Good", "#388e3c", "Recalled with some effort"),
        (3, "Easy", "#1976d2", "Perfect recall"),
    ]

    def __init__(self, srs_mgr: SrsManager, collection: str,
                 cards: list[dict], parent=None):
        super().__init__(parent)
        self._srs = srs_mgr
        self._collection = collection
        self._cards = cards
        self._current_idx = 0
        self._is_showing_back = False
        self._total_reviewed = 0

        self.setWindowTitle(f"Flashcards — {collection}")
        self.resize(550, 500)
        self.setMinimumSize(420, 400)
        self.setModal(True)

        self._build_ui()
        self._show_card()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(len(self._cards))
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%v / %m")
        self._progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                font-size: 11px;
                height: 18px;
            }
            QProgressBar::chunk {
                background: #ce1126;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress)

        # Card counter
        self._counter = QLabel()
        self._counter.setAlignment(Qt.AlignCenter)
        self._counter.setFont(QFont("Segoe UI", 11))
        self._counter.setStyleSheet("color: #888;")
        layout.addWidget(self._counter)

        # Flashcard
        self._card = FlashCard()
        self._card.flipped.connect(self._on_card_flipped)
        layout.addWidget(self._card, 1)

        # Rating buttons (hidden until flipped)
        self._rating_widget = QWidget()
        rating_layout = QHBoxLayout(self._rating_widget)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        rating_layout.setSpacing(6)

        self._rating_btns: dict[int, QPushButton] = {}
        for rating, label, color, tooltip in self.RATING_BUTTONS:
            btn = QPushButton(label)
            btn.setMinimumHeight(40)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 12px;
                }}
                QPushButton:hover {{
                    opacity: 0.85;
                }}
                QPushButton:pressed {{
                    opacity: 0.7;
                }}
            """)
            btn.clicked.connect(lambda checked, r=rating: self._rate(r))
            self._rating_btns[rating] = btn
            rating_layout.addWidget(btn)

        self._rating_widget.setVisible(False)
        layout.addWidget(self._rating_widget)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)

        self._exit_btn = QPushButton("Exit Review")
        self._exit_btn.clicked.connect(self.close)
        self._exit_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        """)
        nav_layout.addWidget(self._exit_btn)

        nav_layout.addStretch()

        self._skip_btn = QPushButton("Skip →")
        self._skip_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        """)
        self._skip_btn.clicked.connect(self._next_card)
        nav_layout.addWidget(self._skip_btn)

        layout.addLayout(nav_layout)

        # Stylesheet for the window
        self.setStyleSheet("""
            QDialog {
                background: #fafafa;
            }
        """)

    def _show_card(self):
        if self._current_idx >= len(self._cards):
            self._finish()
            return

        self._is_showing_back = False
        self._rating_widget.setVisible(False)

        for rating, label, _, _ in self.RATING_BUTTONS:
            self._rating_btns[rating].setText(label)

        entry = self._cards[self._current_idx]
        word = entry.get("word", "")
        pos = entry.get("pos", "")

        self._card.set_front(word, pos)
        self._counter.setText(
            f"Card {self._current_idx + 1} of {len(self._cards)}"
        )
        self._progress.setValue(self._current_idx)

    def mousePressEvent(self, event):
        """Flip card on click anywhere in the window."""
        if not self._is_showing_back:
            self._reveal_answer()
            return
        super().mousePressEvent(event)

    def _on_card_flipped(self):
        self._reveal_answer()

    def _reveal_answer(self):
        self._is_showing_back = True
        entry = self._cards[self._current_idx]
        self._card.set_back(
            translations=entry.get("translations", []),
            meanings=entry.get("meanings", []),
            examples=entry.get("examples", []),
        )
        self._update_button_labels(entry)
        self._rating_widget.setVisible(True)

    def _update_button_labels(self, entry: dict):
        word = entry.get("word", "")
        for rating, label, _, _ in self.RATING_BUTTONS:
            days = self._srs.predict_next_interval(self._collection, word, rating)
            btn = self._rating_btns[rating]
            btn.setText(f"{label} ({days}d)")

    def _rate(self, rating: int):
        entry = self._cards[self._current_idx]
        word = entry.get("word", "")
        self._srs.review_card(self._collection, word, rating)
        self._total_reviewed += 1
        self._current_idx += 1
        self._show_card()

    def _next_card(self):
        if not self._is_showing_back:
            # Reveal first before allowing skip
            self._reveal_answer()
            return
        self._current_idx += 1
        self._show_card()

    def _finish(self):
        msg = QLabel(
            f"Review complete!\n\n{self._total_reviewed} cards reviewed.\n"
            "Come back tomorrow for the next batch."
        )
        msg.setAlignment(Qt.AlignCenter)
        msg.setFont(QFont("Segoe UI", 14))
        msg.setStyleSheet("color: #388e3c; padding: 20px;")

        # Replace card with completion message
        layout = self.layout()
        layout.replaceWidget(self._card, msg)
        self._card.hide()
        msg.show()

        self._rating_widget.hide()
        self._skip_btn.hide()
        self._counter.setText("Done!")
        self._progress.setValue(len(self._cards))

        self.finished_review.emit(self._collection, self._total_reviewed)
