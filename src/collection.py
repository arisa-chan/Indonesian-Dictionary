"""Collection manager for saving words into user-defined collections."""

import json
from dataclasses import asdict

from .models import DictionaryEntry
from .paths import user_data_dir

DATA_DIR = user_data_dir()
COLLECTIONS_FILE = DATA_DIR / "collections.json"


class CollectionManager:
    """Manages named word collections backed by a JSON file."""

    def __init__(self):
        self._collections: dict[str, list[dict]] = {}
        self._load()

    def _load(self):
        if COLLECTIONS_FILE.exists():
            with open(COLLECTIONS_FILE, 'r', encoding='utf-8') as f:
                self._collections = json.load(f)
        else:
            self._collections = {}

    def _save(self):
        COLLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COLLECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._collections, f, ensure_ascii=False, indent=2)

    def list_collections(self) -> list[str]:
        return sorted(self._collections.keys())

    def create_collection(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        if name not in self._collections:
            self._collections[name] = []
            self._save()

    def delete_collection(self, name: str) -> None:
        if name in self._collections:
            del self._collections[name]
            self._save()

    def get_words(self, collection_name: str) -> list[dict]:
        return self._collections.get(collection_name, [])

    def add_word(self, collection_name: str, entry: DictionaryEntry) -> None:
        if collection_name not in self._collections:
            self._collections[collection_name] = []

        entry_dict = {
            "word": entry.word,
            "pos": entry.pos,
            "meanings": entry.meanings[:3],
            "translations": entry.translations[:5],
            "glosses": entry.glosses[:3],
            "synonyms": entry.synonyms[:10],
            "phrases": entry.phrases[:5],
            "examples": entry.examples[:3],
            "frequency_rank": entry.frequency_rank,
        }

        # Avoid duplicates
        if not any(w.get("word") == entry.word for w in self._collections[collection_name]):
            self._collections[collection_name].append(entry_dict)
            self._save()

    def remove_word(self, collection_name: str, word: str) -> None:
        if collection_name in self._collections:
            self._collections[collection_name] = [
                w for w in self._collections[collection_name]
                if w.get("word") != word
            ]
            self._save()

    def is_saved(self, collection_name: str, word: str) -> bool:
        if collection_name not in self._collections:
            return False
        return any(w.get("word") == word for w in self._collections[collection_name])

    def entry_to_dict(self, entry: DictionaryEntry) -> dict:
        return {
            "word": entry.word,
            "pos": entry.pos,
            "meanings": entry.meanings[:3],
            "translations": entry.translations[:5],
            "glosses": entry.glosses[:3],
            "synonyms": entry.synonyms[:10],
            "phrases": entry.phrases[:5],
            "examples": entry.examples[:3],
            "frequency_rank": entry.frequency_rank,
        }

    @staticmethod
    def dict_to_entry(data: dict) -> DictionaryEntry:
        return DictionaryEntry(
            word=data.get("word", ""),
            pos=data.get("pos"),
            meanings=data.get("meanings", []),
            translations=data.get("translations", []),
            glosses=data.get("glosses", []),
            synonyms=data.get("synonyms", []),
            phrases=data.get("phrases", []),
            examples=data.get("examples", []),
            frequency_rank=data.get("frequency_rank"),
        )
