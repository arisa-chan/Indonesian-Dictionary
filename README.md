# Indonesian Dictionary

An offline Indonesian dictionary application with spaced repetition (SRS) flashcards,
built with Python and PySide6.

## Features

- **Three dictionary modes**: Indonesian → English, English → Indonesian, Indonesian → Indonesian
- **Live search** with prefix, exact, and substring matching
- **Word details**: part of speech, translations/definitions, synonyms, phrases, example sentences, and usage frequency
- **Word collections** — save words into named collections for study
- **Spaced repetition (SM-2)** — flashcard review with an Anki-style algorithm
- **SRS visual indicators** — color-coded dots and days-until-review in the collection list and detail panel
- **Reset SRS** — clear review history for individual words

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Build dictionary data (~5–10 min, ~150 MB download)
python build_data.py

# Run the application
python -m src.main
```

## Build Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Generate the icon
python build_icon.py

# Build the standalone .exe
pyinstaller IndonesianDictionary.spec
```

The executable is produced at `dist/IndonesianDictionary.exe` (~57 MB, self-contained).

User data (`collections.json`, `srs_data.json`) is stored in a `data/` directory next to the executable on first save.

## Keyboard Shortcuts

| Key        | Action                           |
|------------|----------------------------------|
| `Ctrl+F`   | Focus search bar                 |
| `Ctrl+1`   | Indonesian → English mode        |
| `Ctrl+2`   | English → Indonesian mode        |
| `Ctrl+3`   | Indonesian → Indonesian mode     |

## SRS Ratings

| Rating | Label  | Meaning                              |
|--------|--------|--------------------------------------|
| 0      | Again  | Complete blackout — card resets      |
| 1      | Hard   | Recalled with significant difficulty |
| 2      | Good   | Recalled with some effort            |
| 3      | Easy   | Perfect recall                       |

Buttons show the predicted next review interval (e.g., "Good (7d)").

## Data Sources

| Dictionary  | Source                                                                    | Entries | License  |
|-------------|---------------------------------------------------------------------------|--------:|----------|
| ID → ID     | [KBBI SQL Database](https://github.com/dyazincahya/KBBI-SQL-database)    | ~116K   | MIT      |
| ID → EN     | [Bahasa WordNet](https://github.com/open-language/id-wordnet)             | ~50K    | MIT      |
| EN → ID     | [FreeDict](https://freedict.org/)                                         | ~23K    | GPL-2.0  |
| Frequency   | [freq-dist-id](https://github.com/ardwort/freq-dist-id)                   | ~50K    | Open Data|
| Examples    | [Tatoeba](https://tatoeba.org/)                                           | varies  | CC-BY 2.0|

## Project Structure

```
indonesian-dictionary/
├── app.py                  # PyInstaller entry point
├── build_data.py           # One-time data pipeline
├── build_icon.py           # Icon generator (pure Python)
├── IndonesianDictionary.spec  # PyInstaller spec
├── icon.ico                # Application icon
├── data/                   # Bundled dictionary JSON files
├── src/
│   ├── main.py             # Application entry point
│   ├── models.py           # DictionaryEntry dataclass
│   ├── dictionary.py       # DictionaryManager (load/search)
│   ├── collection.py       # CollectionManager (CRUD)
│   ├── srs.py              # SrsManager (SM-2 algorithm)
│   ├── paths.py            # Path resolution (dev + frozen)
│   ├── utils.py            # Text normalization, HTML helpers
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py       # Main window + tab layout
│       ├── search_panel.py      # Search bar + mode selector
│       ├── results_list.py      # Search results list
│       ├── detail_panel.py      # Word detail (HTML)
│       ├── collection_panel.py  # Collections + word list
│       └── flashcard_window.py  # Flashcard review dialog
└── requirements.txt
```
