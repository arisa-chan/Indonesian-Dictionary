"""Spaced repetition system using the SM-2 algorithm.

Stores scheduling data alongside collection entries in SRS_DATA_FILE.
Each flashcard tracks: due_date, interval (days), ease_factor, reps,
and a history of review responses.
"""

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from .paths import user_data_dir

DATA_DIR = user_data_dir()
SRS_FILE = DATA_DIR / "srs_data.json"

# Anki-style grading scale
# 0 = Again (complete blackout)
# 1 = Hard (recalled with significant difficulty)
# 2 = Good (recalled with some effort)
# 3 = Easy (perfect recall)


@dataclass
class SrsCard:
    """Scheduling metadata for a single flashcard."""

    collection: str
    word: str
    due_date: str          # ISO date string "YYYY-MM-DD"
    interval: int = 0       # days until next review
    ease_factor: float = 2.5  # SM-2 ease factor (default 2.5)
    reps: int = 0           # number of successful consecutive reviews
    review_history: list[dict] = field(default_factory=list)  # [{date, rating}, ...]
    introduced: str = ""    # ISO date string when first seen


class SrsManager:
    """Manages SRS scheduling for words in collections."""

    def __init__(self):
        self._cards: dict[str, SrsCard] = {}  # key: "collection::word"
        self._load()

    def _load(self):
        if SRS_FILE.exists():
            with open(SRS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for key, data in raw.items():
                self._cards[key] = SrsCard(
                    collection=data.get("collection", ""),
                    word=data.get("word", ""),
                    due_date=data.get("due_date", ""),
                    interval=data.get("interval", 0),
                    ease_factor=data.get("ease_factor", 2.5),
                    reps=data.get("reps", 0),
                    review_history=data.get("review_history", []),
                    introduced=data.get("introduced", ""),
                )
        else:
            self._cards = {}

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        for key, card in self._cards.items():
            data[key] = {
                "collection": card.collection,
                "word": card.word,
                "due_date": card.due_date,
                "interval": card.interval,
                "ease_factor": card.ease_factor,
                "reps": card.reps,
                "review_history": card.review_history,
                "introduced": card.introduced,
            }
        with open(SRS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _key(self, collection: str, word: str) -> str:
        return f"{collection}::{word}"

    def today_str(self) -> str:
        return date.today().isoformat()

    def days_from_today(self, iso_date: str) -> int:
        """Return days between iso_date and today. Negative = overdue."""
        if not iso_date:
            return -9999
        d = date.fromisoformat(iso_date)
        return (d - date.today()).days

    def get_due_cards(self, collection: str, entry_dicts: list[dict]) -> list[dict]:
        """Return entry dicts for words that are due for review.

        Words never reviewed before are always due.
        """
        due = []
        today = self.today_str()

        for entry in entry_dicts:
            word = entry.get("word", "")
            key = self._key(collection, word)

            if key not in self._cards:
                # Never reviewed — due immediately
                due.append(entry)
            else:
                card = self._cards[key]
                if not card.due_date or card.due_date <= today:
                    due.append(entry)

        return due

    def get_due_count(self, collection: str, entry_dicts: list[dict]) -> int:
        """Count of due cards (fast, no intermediate list)."""
        count = 0
        today = self.today_str()

        for entry in entry_dicts:
            word = entry.get("word", "")
            key = self._key(collection, word)

            if key not in self._cards:
                count += 1
            else:
                card = self._cards[key]
                if not card.due_date or card.due_date <= today:
                    count += 1

        return count

    def review_card(self, collection: str, word: str, rating: int) -> None:
        """Record a review and update the card schedule using SM-2.

        Args:
            collection: The collection name.
            word: The word being reviewed.
            rating: 0=Again, 1=Hard, 2=Good, 3=Easy
        """
        key = self._key(collection, word)
        today = self.today_str()

        if key not in self._cards:
            card = SrsCard(
                collection=collection,
                word=word,
                due_date=today,
                introduced=today,
            )
            self._cards[key] = card
        else:
            card = self._cards[key]

        # Record review
        card.review_history.append({
            "date": today,
            "rating": rating,
        })

        # SM-2 algorithm
        if rating == 0:
            # Failed — reset
            card.interval = 1
            card.reps = 0
        else:
            # Successful review
            if card.reps == 0:
                card.interval = 1
            elif card.reps == 1:
                card.interval = 2
            else:
                card.interval = int(round(card.interval * card.ease_factor))

            card.reps += 1

            # Adjust ease factor based on rating
            # SM-2 formula: EF' = EF + (0.1 - (3 - q) * (0.08 + (3 - q) * 0.02))
            q = rating  # 1=Hard, 2=Good, 3=Easy
            card.ease_factor = max(
                1.3,
                card.ease_factor + (0.1 - (3 - q) * (0.08 + (3 - q) * 0.02))
            )

        # Set next due date
        next_due = date.today() + timedelta(days=card.interval)
        card.due_date = next_due.isoformat()

        self._save()

    def get_card(self, collection: str, word: str) -> SrsCard | None:
        """Get the SRS card for a word, or None if never reviewed."""
        key = self._key(collection, word)
        return self._cards.get(key)

    def get_stats(self, collection: str) -> dict:
        """Return statistics for a collection."""
        total = 0
        due_today = 0
        mature = 0  # interval >= 21 days

        today = self.today_str()

        for key, card in self._cards.items():
            if card.collection != collection:
                continue
            total += 1
            if not card.due_date or card.due_date <= today:
                due_today += 1
            if card.interval >= 21:
                mature += 1

        return {
            "total": total,
            "due_today": due_today,
            "mature": mature,
            "new": max(0, total - len([
                c for c in self._cards.values()
                if c.collection == collection and c.reps > 0
            ])),
        }

    def predict_next_interval(self, collection: str, word: str, rating: int) -> int:
        """Predict the next interval in days for a hypothetical rating, without saving.

        Args:
            collection: The collection name.
            word: The word.
            rating: 0=Again, 1=Hard, 2=Good, 3=Easy

        Returns:
            The interval in days that this rating would produce.
        """
        if rating == 0:
            return 1

        key = self._key(collection, word)
        if key in self._cards:
            card = self._cards[key]
            interval = card.interval
            reps = card.reps
            ease = card.ease_factor
        else:
            interval = 0
            reps = 0
            ease = 2.5

        if reps == 0:
            return 1
        elif reps == 1:
            return 2
        else:
            return int(round(interval * ease))

    def reset_card(self, collection: str, word: str) -> None:
        """Reset a card's SRS data (when removed from collection)."""
        key = self._key(collection, word)
        self._cards.pop(key, None)
        self._save()
