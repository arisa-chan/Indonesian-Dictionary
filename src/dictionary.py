"""Dictionary data manager: loads JSON, runs searches."""

import json
import bisect
from pathlib import Path
from .models import DictionaryEntry
from .utils import normalize_text
from .paths import resource_dir

DATA_DIR = resource_dir()
MAX_CACHE_SIZE = 500


class DictionaryManager:
    """Loads and queries all dictionary databases."""

    def __init__(self):
        self.id_id_entries: list[DictionaryEntry] = []
        self.id_en_entries: list[DictionaryEntry] = []
        self.en_id_entries: list[DictionaryEntry] = []

        # Sorted word lists for binary search (prefix matching)
        self._id_id_words: list[str] = []
        self._id_en_words: list[str] = []
        self._en_id_words: list[str] = []

        # Word → indices lookup for exact matches
        self._id_id_index: dict[str, list[int]] = {}
        self._id_en_index: dict[str, list[int]] = {}
        self._en_id_index: dict[str, list[int]] = {}

        # Pre-sorted lists (returned for empty query — no copy/sort needed)
        self._id_id_sorted: list[DictionaryEntry] = []
        self._id_en_sorted: list[DictionaryEntry] = []
        self._en_id_sorted: list[DictionaryEntry] = []

        # Query result cache: (query, mode) -> list[DictionaryEntry]
        self._cache: dict[tuple[str, str], list[DictionaryEntry]] = {}

    def load(self) -> None:
        """Load all dictionary files from data/."""
        self.id_id_entries = self._load_entries(DATA_DIR / "id_id.json")
        self.id_en_entries = self._load_entries(DATA_DIR / "id_en.json")
        self.en_id_entries = self._load_entries(DATA_DIR / "en_id.json")

        self._build_index(self.id_id_entries, "_id_id")
        self._build_index(self.id_en_entries, "_id_en")
        self._build_index(self.en_id_entries, "_en_id")

    def _load_entries(self, path: Path) -> list[DictionaryEntry]:
        """Load entries from a JSON file."""
        if not path.exists():
            print(f"Warning: {path.name} not found — skipping")
            return []

        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        entries = []
        for item in raw:
            entry = DictionaryEntry(
                word=item.get("word", ""),
                pos=item.get("pos"),
                meanings=item.get("meanings", []),
                glosses=item.get("glosses", []),
                translations=item.get("translations", []),
                synonyms=item.get("synonyms", []),
                phrases=item.get("phrases", []),
                examples=item.get("examples", []),
                frequency_rank=item.get("frequency_rank"),
            )
            entries.append(entry)
        return entries

    def _build_index(self, entries: list[DictionaryEntry], prefix: str) -> None:
        """Build sorted word list, exact-match index, and pre-sorted entries."""
        word_list: list[str] = []
        index: dict[str, list[int]] = {}

        for i, entry in enumerate(entries):
            key = normalize_text(entry.word)
            word_list.append(key)
            if key not in index:
                index[key] = []
            index[key].append(i)

        setattr(self, f"{prefix}_words", word_list)
        setattr(self, f"{prefix}_index", index)

        # Pre-sort entries by frequency (common first), then alphabetically
        sorted_entries = sorted(
            entries,
            key=lambda e: (
                e.frequency_rank if e.frequency_rank is not None else 999999,
                normalize_text(e.word),
            )
        )
        setattr(self, f"{prefix}_sorted", sorted_entries)

    # ── Search ──────────────────────────────────────────────────────────

    def search(
        self, query: str, dict_mode: str
    ) -> list[DictionaryEntry]:
        """Search dictionary entries matching the query.

        Args:
            query: The search string.
            dict_mode: One of "id_id", "id_en", "en_id".

        Returns:
            List of matching entries sorted by frequency (common first).
        """
        if dict_mode == "id_id":
            entries = self.id_id_entries
            words = self._id_id_words
            index = self._id_id_index
            sorted_entries = self._id_id_sorted
        elif dict_mode == "id_en":
            entries = self.id_en_entries
            words = self._id_en_words
            index = self._id_en_index
            sorted_entries = self._id_en_sorted
        else:
            entries = self.en_id_entries
            words = self._en_id_words
            index = self._en_id_index
            sorted_entries = self._en_id_sorted

        if not query.strip():
            return sorted_entries

        q = normalize_text(query)

        # Check cache
        cache_key = (q, dict_mode)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try exact match first
        matched_indices = list(index.get(q, []))

        # Then prefix match using binary search
        if not matched_indices:
            matched_indices = self._prefix_search(words, q)

        # If still no results, fall back to substring match
        if not matched_indices:
            matched_indices = self._substring_search(words, q)

        # Deduplicate and get results
        seen = set()
        results = []
        for idx in matched_indices:
            if idx not in seen:
                seen.add(idx)
                results.append(entries[idx])

        results = self._sort_by_frequency(results)

        # Store in cache (evict oldest if full)
        if len(self._cache) >= MAX_CACHE_SIZE:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[cache_key] = results

        return results

    @staticmethod
    def _sort_by_frequency(entries: list[DictionaryEntry]) -> list[DictionaryEntry]:
        """Sort entries by frequency rank (common first), then alphabetically."""
        entries.sort(
            key=lambda e: (
                e.frequency_rank if e.frequency_rank is not None else 999999,
                normalize_text(e.word),
            )
        )
        return entries

    @staticmethod
    def _prefix_search(words: list[str], query: str) -> list[int]:
        """Find entries where word starts with query using binary search."""
        left = bisect.bisect_left(words, query)
        results = []
        for i in range(left, len(words)):
            if words[i].startswith(query):
                results.append(i)
            else:
                break
        return results

    @staticmethod
    def _substring_search(words: list[str], query: str) -> list[int]:
        """Linear scan for substring matches."""
        results = []
        for i, word in enumerate(words):
            if query in word:
                results.append(i)
        return results
