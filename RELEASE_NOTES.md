# Indonesian Dictionary v1.0.0

An offline Indonesian dictionary desktop application with spaced repetition (SRS) flashcards, built with Python + PySide6. Learn Indonesian vocabulary with Anki-style flashcard review across three dictionary modes.

---

## Features

### Dictionary Search
- **Three lookup modes:** Indonesian → English (~50K entries), English → Indonesian (~23K entries), Indonesian → Indonesian (~116K entries from KBBI)
- **Live debounced search** with three matching strategies: exact match → prefix match → substring match
- **Results ranked by frequency** (common words first), with an LRU query cache (max 500 entries)

### Rich Word Details
Each dictionary entry includes:
- Part of speech (Indonesian/English POS labels)
- Translations and definitions (with glosses)
- Synonyms and related phrases
- Example sentences (from Tatoeba, Indonesian–English pairs)
- Usage frequency rank (Very Common → Very Rare)

### Word Collections
- Create and manage named collections
- Save words from any dictionary mode to a collection
- Duplicate word detection
- Persisted to `data/collections.json`

### SM-2 Spaced Repetition Flashcards
- Full Anki-style SM-2 algorithm with four ratings: Again, Hard, Good, Easy
- Ease factor adjustment, interval scheduling, and review history tracking
- SRS visual indicators — color-coded dots (red=overdue, orange=due today, yellow=soon, green=medium, blue=far out, gray=new) with days-until-review labels
- Modal flashcard review dialog with click-to-flip cards
- Color-coded rating buttons that preview the next interval (e.g., "Good (7d)")
- Per-word SRS data reset
- Persisted to `data/srs_data.json`

### Keyboard Shortcuts
- `Ctrl+F` — focus search bar
- `Ctrl+1` — Indonesian → English mode
- `Ctrl+2` — English → Indonesian mode
- `Ctrl+3` — Indonesian → Indonesian mode

### Build & Distribution
- PyInstaller build producing a standalone Windows `.exe` (~57 MB)
- Application icon embedded for Windows Explorer/taskbar and window title bar

### Data Sources
- KBBI (official Indonesian dictionary) — Indonesian → Indonesian
- WordNet Bahasa — Indonesian → English
- FreeDict TEI XML — English → Indonesian
- Tatoeba — Indonesian–English example sentences
- Frequency data — word usage ranking

---

## Requirements
- Python 3.9+
- PySide6 ≥ 6.7.0
- `lxml` ≥ 5.0.0 (build time only; excluded from PyInstaller bundle)

---

## Getting Started

**Run in development mode:**
```
python -m src.main
```

**Build standalone executable:**
```
pip install pyinstaller
pyinstaller IndonesianDictionary.spec
```

**Rebuild dictionary data (if needed):**
```
python build_data.py
```
