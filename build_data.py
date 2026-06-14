#!/usr/bin/env python3
"""
build_data.py -- Download and parse open-source Indonesian dictionary databases.

Produces four JSON files in data/:
  - id_id.json    (Indonesian definitions from KBBI)
  - id_en.json    (Indonesian->English from WordNet)
  - en_id.json    (English->Indonesian from FreeDict)
  - frequency.json (Indonesian word frequency ranks)

MIT-licensed data sources:
  KBBI:      dyazincahya/KBBI-SQL-database  (MIT)
  WordNet:   open-language/id-wordnet        (MIT)
  FreeDict:  freedict/fd-dictionaries        (GPL-2.0)
  Frequency: ardwort/freq-dist-id            (open data)

Usage: python build_data.py
"""

import json
import re
import csv
import io
import os
import sys
import bz2
import html as html_mod
import tarfile
import tempfile
import gzip
from pathlib import Path
from collections import defaultdict
from urllib.request import urlopen, urlretrieve

try:
    from lxml import etree
except ImportError:
    print("Error: lxml is required. Install with: pip install lxml")
    sys.exit(1)

# -- Config ------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_DIR = DATA_DIR / ".cache"

KBBI_JSON_URL = "https://raw.githubusercontent.com/dyazincahya/KBBI-SQL-database/main/dictionary_JSON.json"
WN_TAB_URL = "https://raw.githubusercontent.com/open-language/id-wordnet/master/database/1.2/wn-msa-all.tab"
WN_DB_URL = "https://wordnetcode.princeton.edu/3.0/WNdb-3.0.tar.gz"
FREQ_CSV_URL = "https://raw.githubusercontent.com/ardwort/freq-dist-id/master/data/idwiki.csv"
FREEDICT_SRC_URL = "https://download.freedict.org/dictionaries/eng-ind/2025.11.23/freedict-eng-ind-2025.11.23.src.tar.xz"
TATOEBA_SENTENCES_URL = "https://downloads.tatoeba.org/exports/sentences.tar.bz2"
TATOEBA_LINKS_URL = "https://downloads.tatoeba.org/exports/links.tar.bz2"

# -- Helpers -----------------------------------------------------------------

POS_MAP = {
    "n": "noun", "nomina": "noun",
    "v": "verb", "verba": "verb",
    "adj": "adjective", "adjektiva": "adjective",
    "adv": "adverb", "adverbia": "adverb",
    "pron": "pronoun", "pronomina": "pronoun",
    "num": "numeral", "numeralia": "numeral",
    "p": "particle", "partikel": "particle",
    "a": "adjective",
    "r": "adverb",
    "s": "adjective",
}

def normalize_pos(raw: str) -> str:
    """Normalize POS tag to a standard English label.

    Handles compound tags like "Mk p" -> "particle".
    """
    raw = raw.strip().lower()
    # Try multi-word lookup first, then single-word
    candidate = raw.replace("  ", " ")
    if candidate in POS_MAP:
        return POS_MAP[candidate]
    # Try the last word (handles "Mk p" -> "p", "Jw n" -> "n")
    parts = candidate.split()
    for part in reversed(parts):
        if part in POS_MAP:
            return POS_MAP[part]
    return candidate

def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, preserving structure."""
    # First decode HTML entities (&lt; -> <, &amp; -> &, etc.)
    text = html_mod.unescape(text)
    # Replace <br> and <br/> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def download(url: str, dest: Path) -> None:
    """Download a file with progress indication."""
    print(f"  Downloading {url[:80]}...")
    urlretrieve(url, dest)

def extract_tar_xz(path: Path, dest_dir: Path) -> Path:
    """Extract a .tar.xz file, return the extraction directory."""
    import lzma
    with lzma.open(path, 'rb') as f:
        with tarfile.open(fileobj=f, mode='r:') as tar:
            tar.extractall(dest_dir)
    return dest_dir

# -- Supplemental ID->EN Dictionary (common words WordNet misses) ---------

# These are high-frequency Indonesian words that the WordNet Bahasa dataset
# either misses entirely or maps to wrong synsets due to sparse coverage
# of pronouns, particles, conjunctions, and other function words.
SUPPLEMENTAL_ID_EN: list[dict] = [
    # Pronouns
    {"word": "saya", "pos": "pronoun", "translations": ["I", "me", "my", "mine"],
     "glosses": ["first person singular pronoun (formal)"], "phrases": [], "examples": []},
    {"word": "aku", "pos": "pronoun", "translations": ["I", "me", "my", "mine"],
     "glosses": ["first person singular pronoun (informal/intimate)"], "phrases": [], "examples": []},
    {"word": "kamu", "pos": "pronoun", "translations": ["you", "your", "yours"],
     "glosses": ["second person singular pronoun (informal)"], "phrases": [], "examples": []},
    {"word": "anda", "pos": "pronoun", "translations": ["you", "your", "yours"],
     "glosses": ["second person singular/plural pronoun (formal)"], "phrases": [], "examples": []},
    {"word": "dia", "pos": "pronoun", "translations": ["he", "she", "him", "her"],
     "glosses": ["third person singular pronoun"], "phrases": [], "examples": []},
    {"word": "ia", "pos": "pronoun", "translations": ["he", "she", "it"],
     "glosses": ["third person singular pronoun"], "phrases": [], "examples": []},
    {"word": "mereka", "pos": "pronoun", "translations": ["they", "them", "their"],
     "glosses": ["third person plural pronoun"], "phrases": [], "examples": []},
    {"word": "kami", "pos": "pronoun", "translations": ["we", "us", "our"],
     "glosses": ["first person plural exclusive (excluding the listener)"], "phrases": [], "examples": []},
    {"word": "kita", "pos": "pronoun", "translations": ["we", "us", "our"],
     "glosses": ["first person plural inclusive (including the listener)"], "phrases": [], "examples": []},
    {"word": "ini", "pos": "pronoun", "translations": ["this", "these"],
     "glosses": ["demonstrative pronoun for something near the speaker"], "phrases": [], "examples": []},
    {"word": "itu", "pos": "pronoun", "translations": ["that", "those"],
     "glosses": ["demonstrative pronoun for something distant"], "phrases": [], "examples": []},
    {"word": "siapa", "pos": "pronoun", "translations": ["who", "whom"],
     "glosses": ["interrogative pronoun asking about a person"], "phrases": [], "examples": []},
    {"word": "apa", "pos": "pronoun", "translations": ["what"],
     "glosses": ["interrogative pronoun asking about a thing or concept"], "phrases": [], "examples": []},
    {"word": "mana", "pos": "pronoun", "translations": ["which", "where"],
     "glosses": ["interrogative pronoun asking about location or choice"], "phrases": ["di mana — where", "yang mana — which one"], "examples": []},
    {"word": "kapan", "pos": "adverb", "translations": ["when"],
     "glosses": ["interrogative adverb asking about time"], "phrases": [], "examples": []},
    {"word": "bagaimana", "pos": "adverb", "translations": ["how"],
     "glosses": ["interrogative adverb asking about manner or condition"], "phrases": [], "examples": []},
    {"word": "mengapa", "pos": "adverb", "translations": ["why"],
     "glosses": ["interrogative adverb asking about reason"], "phrases": [], "examples": []},
    {"word": "kenapa", "pos": "adverb", "translations": ["why"],
     "glosses": ["interrogative adverb asking about reason (informal)"], "phrases": [], "examples": []},
    {"word": "berapa", "pos": "pronoun", "translations": ["how many", "how much"],
     "glosses": ["interrogative pronoun asking about quantity"], "phrases": [], "examples": []},

    # Conjunctions & particles
    {"word": "dan", "pos": "particle", "translations": ["and"],
     "glosses": ["coordinating conjunction linking words or clauses"], "phrases": [], "examples": []},
    {"word": "atau", "pos": "particle", "translations": ["or"],
     "glosses": ["disjunctive conjunction"], "phrases": [], "examples": []},
    {"word": "tetapi", "pos": "particle", "translations": ["but", "however"],
     "glosses": ["adversative conjunction"], "phrases": [], "examples": []},
    {"word": "tapi", "pos": "particle", "translations": ["but"],
     "glosses": ["adversative conjunction (informal)"], "phrases": [], "examples": []},
    {"word": "karena", "pos": "particle", "translations": ["because", "since"],
     "glosses": ["causal conjunction"], "phrases": ["karena itu — therefore"], "examples": []},
    {"word": "jika", "pos": "particle", "translations": ["if"],
     "glosses": ["conditional conjunction"], "phrases": [], "examples": []},
    {"word": "kalau", "pos": "particle", "translations": ["if", "when"],
     "glosses": ["conditional conjunction (informal)"], "phrases": [], "examples": []},
    {"word": "bahwa", "pos": "particle", "translations": ["that"],
     "glosses": ["subordinating conjunction introducing a clause"], "phrases": [], "examples": []},
    {"word": "agar", "pos": "particle", "translations": ["so that", "in order to"],
     "glosses": ["purpose conjunction"], "phrases": [], "examples": []},
    {"word": "supaya", "pos": "particle", "translations": ["so that", "in order that"],
     "glosses": ["purpose conjunction"], "phrases": [], "examples": []},
    {"word": "meskipun", "pos": "particle", "translations": ["although", "even though"],
     "glosses": ["concessive conjunction"], "phrases": [], "examples": []},
    {"word": "walaupun", "pos": "particle", "translations": ["although", "even though"],
     "glosses": ["concessive conjunction"], "phrases": [], "examples": []},
    {"word": "sehingga", "pos": "particle", "translations": ["so that", "resulting in"],
     "glosses": ["resultative conjunction"], "phrases": [], "examples": []},
    {"word": "dengan", "pos": "particle", "translations": ["with", "by", "using"],
     "glosses": ["instrumental/manner preposition"], "phrases": [], "examples": []},
    {"word": "untuk", "pos": "particle", "translations": ["for", "to", "in order to"],
     "glosses": ["purpose/benefactive preposition"], "phrases": [], "examples": []},
    {"word": "dari", "pos": "particle", "translations": ["from", "of"],
     "glosses": ["origin/source preposition"], "phrases": ["dari mana — from where"], "examples": []},
    {"word": "ke", "pos": "particle", "translations": ["to", "toward"],
     "glosses": ["direction preposition"], "phrases": ["ke mana — to where"], "examples": []},
    {"word": "di", "pos": "particle", "translations": ["at", "in", "on"],
     "glosses": ["location preposition"], "phrases": ["di sini — here", "di sana — there"], "examples": []},
    {"word": "pada", "pos": "particle", "translations": ["at", "on", "upon", "to"],
     "glosses": ["locative/temporal preposition (formal)"], "phrases": [], "examples": []},
    {"word": "yang", "pos": "particle", "translations": ["which", "that", "who"],
     "glosses": ["relativizer/definer particle"], "phrases": [], "examples": []},
    {"word": "juga", "pos": "adverb", "translations": ["also", "too", "as well"],
     "glosses": ["additive adverb"], "phrases": [], "examples": []},
    {"word": "saja", "pos": "adverb", "translations": ["just", "only", "simply"],
     "glosses": ["limiting/exclusive adverb"], "phrases": [], "examples": []},
    {"word": "sangat", "pos": "adverb", "translations": ["very", "extremely"],
     "glosses": ["intensifying adverb"], "phrases": [], "examples": []},
    {"word": "selalu", "pos": "adverb", "translations": ["always"],
     "glosses": ["frequency adverb"], "phrases": [], "examples": []},
    {"word": "pernah", "pos": "adverb", "translations": ["ever", "once"],
     "glosses": ["experiential aspect marker"], "phrases": [], "examples": []},
    {"word": "sudah", "pos": "adverb", "translations": ["already", "done"],
     "glosses": ["perfective aspect marker"], "phrases": [], "examples": []},
    {"word": "belum", "pos": "adverb", "translations": ["not yet"],
     "glosses": ["negative perfective aspect marker"], "phrases": [], "examples": []},
    {"word": "akan", "pos": "adverb", "translations": ["will", "shall", "going to"],
     "glosses": ["future tense marker"], "phrases": [], "examples": []},
    {"word": "sedang", "pos": "adverb", "translations": ["currently", "in the process of"],
     "glosses": ["progressive aspect marker"], "phrases": [], "examples": []},
    {"word": "tidak", "pos": "adverb", "translations": ["not", "no"],
     "glosses": ["negation marker (for verbs/adjectives)"], "phrases": [], "examples": []},
    {"word": "bukan", "pos": "adverb", "translations": ["not", "no"],
     "glosses": ["negation marker (for nouns)"], "phrases": [], "examples": []},
    {"word": "masih", "pos": "adverb", "translations": ["still", "yet"],
     "glosses": ["continuative aspect marker"], "phrases": [], "examples": []},
    {"word": "lagi", "pos": "adverb", "translations": ["again", "more", "else"],
     "glosses": ["iterative/additional adverb"], "phrases": [], "examples": []},
    {"word": "hanya", "pos": "adverb", "translations": ["only", "just"],
     "glosses": ["limiting adverb (formal)"], "phrases": [], "examples": []},
    {"word": "baru", "pos": "adverb", "translations": ["just now", "recently"],
     "glosses": ["recent-past temporal marker"], "phrases": [], "examples": []},
    {"word": "ada", "pos": "verb", "translations": ["there is", "there are", "exist", "have"],
     "glosses": ["existential verb"], "phrases": [], "examples": []},
    {"word": "bisa", "pos": "verb", "translations": ["can", "able to"],
     "glosses": ["ability/possibility modal"], "phrases": [], "examples": []},
    {"word": "dapat", "pos": "verb", "translations": ["can", "able to", "obtain"],
     "glosses": ["ability/possibility modal (formal)"], "phrases": [], "examples": []},
    {"word": "boleh", "pos": "verb", "translations": ["may", "allowed to"],
     "glosses": ["permission modal"], "phrases": [], "examples": []},
    {"word": "harus", "pos": "verb", "translations": ["must", "have to"],
     "glosses": ["obligation modal"], "phrases": [], "examples": []},
    {"word": "mau", "pos": "verb", "translations": ["want", "would like to"],
     "glosses": ["volition modal"], "phrases": [], "examples": []},
    {"word": "ingin", "pos": "verb", "translations": ["want", "desire"],
     "glosses": ["volition verb (formal)"], "phrases": [], "examples": []},
    {"word": "perlu", "pos": "verb", "translations": ["need", "needed"],
     "glosses": ["necessity modal"], "phrases": [], "examples": []},
    {"word": "suka", "pos": "verb", "translations": ["like", "enjoy"],
     "glosses": ["preference verb"], "phrases": [], "examples": []},
    {"word": "punya", "pos": "verb", "translations": ["have", "own", "possess"],
     "glosses": ["possessive verb (informal)"], "phrases": [], "examples": []},
    {"word": "memiliki", "pos": "verb", "translations": ["have", "own", "possess"],
     "glosses": ["possessive verb (formal)"], "phrases": [], "examples": []},

    # Common adjectives
    {"word": "baik", "pos": "adjective", "translations": ["good", "kind", "well"],
     "glosses": ["positive quality adjective"], "phrases": [], "examples": []},
    {"word": "buruk", "pos": "adjective", "translations": ["bad", "poor"],
     "glosses": ["negative quality adjective"], "phrases": [], "examples": []},
    {"word": "indah", "pos": "adjective", "translations": ["beautiful", "lovely"],
     "glosses": ["aesthetic quality adjective"], "phrases": [], "examples": []},
    {"word": "cantik", "pos": "adjective", "translations": ["pretty", "beautiful"],
     "glosses": ["aesthetic quality adjective (for people/objects)"], "phrases": [], "examples": []},
    {"word": "tampan", "pos": "adjective", "translations": ["handsome"],
     "glosses": ["aesthetic quality adjective (for men)"], "phrases": [], "examples": []},
    {"word": "penting", "pos": "adjective", "translations": ["important"],
     "glosses": ["significance adjective"], "phrases": [], "examples": []},
    {"word": "mudah", "pos": "adjective", "translations": ["easy", "simple"],
     "glosses": ["difficulty adjective"], "phrases": [], "examples": []},
    {"word": "sulit", "pos": "adjective", "translations": ["difficult", "hard"],
     "glosses": ["difficulty adjective"], "phrases": [], "examples": []},
    {"word": "dekat", "pos": "adjective", "translations": ["near", "close"],
     "glosses": ["proximity adjective"], "phrases": [], "examples": []},
    {"word": "jauh", "pos": "adjective", "translations": ["far", "distant"],
     "glosses": ["proximity adjective"], "phrases": [], "examples": []},
    {"word": "panjang", "pos": "adjective", "translations": ["long"],
     "glosses": ["length adjective"], "phrases": [], "examples": []},
    {"word": "pendek", "pos": "adjective", "translations": ["short"],
     "glosses": ["length/height adjective"], "phrases": [], "examples": []},
    {"word": "tinggi", "pos": "adjective", "translations": ["tall", "high"],
     "glosses": ["height adjective"], "phrases": [], "examples": []},
    {"word": "rendah", "pos": "adjective", "translations": ["low", "short"],
     "glosses": ["height adjective"], "phrases": [], "examples": []},
    {"word": "mahal", "pos": "adjective", "translations": ["expensive"],
     "glosses": ["cost adjective"], "phrases": [], "examples": []},
    {"word": "murah", "pos": "adjective", "translations": ["cheap", "inexpensive"],
     "glosses": ["cost adjective"], "phrases": [], "examples": []},
    {"word": "cepat", "pos": "adjective", "translations": ["fast", "quick"],
     "glosses": ["speed adjective"], "phrases": [], "examples": []},
    {"word": "lambat", "pos": "adjective", "translations": ["slow"],
     "glosses": ["speed adjective"], "phrases": [], "examples": []},

    # Common nouns
    {"word": "orang", "pos": "noun", "translations": ["person", "people", "human"],
     "glosses": ["human being"], "phrases": [], "examples": []},
    {"word": "teman", "pos": "noun", "translations": ["friend", "companion"],
     "glosses": ["personal relationship"], "phrases": [], "examples": []},
    {"word": "keluarga", "pos": "noun", "translations": ["family"],
     "glosses": ["kinship group"], "phrases": [], "examples": []},
    {"word": "anak", "pos": "noun", "translations": ["child", "kid"],
     "glosses": ["young human"], "phrases": ["anak laki-laki — boy", "anak perempuan — girl"], "examples": []},
    {"word": "ibu", "pos": "noun", "translations": ["mother", "mom", "Mrs"],
     "glosses": ["female parent"], "phrases": [], "examples": []},
    {"word": "bapak", "pos": "noun", "translations": ["father", "dad", "Mr"],
     "glosses": ["male parent"], "phrases": [], "examples": []},
    {"word": "hari", "pos": "noun", "translations": ["day"],
     "glosses": ["24-hour period"], "phrases": ["hari ini — today", "hari esok — tomorrow"], "examples": []},
    {"word": "waktu", "pos": "noun", "translations": ["time"],
     "glosses": ["temporal concept"], "phrases": [], "examples": []},
    {"word": "tahun", "pos": "noun", "translations": ["year"],
     "glosses": ["12-month period"], "phrases": [], "examples": []},
    {"word": "tempat", "pos": "noun", "translations": ["place", "location"],
     "glosses": ["spatial location"], "phrases": [], "examples": []},
    {"word": "kota", "pos": "noun", "translations": ["city", "town"],
     "glosses": ["urban settlement"], "phrases": [], "examples": []},
    {"word": "negara", "pos": "noun", "translations": ["country", "state", "nation"],
     "glosses": ["political entity"], "phrases": [], "examples": []},
    {"word": "dunia", "pos": "noun", "translations": ["world"],
     "glosses": ["the Earth, global realm"], "phrases": [], "examples": []},
    {"word": "nama", "pos": "noun", "translations": ["name"],
     "glosses": ["identifier for a person or thing"], "phrases": [], "examples": []},
    {"word": "kata", "pos": "noun", "translations": ["word"],
     "glosses": ["unit of language"], "phrases": [], "examples": []},
    {"word": "cerita", "pos": "noun", "translations": ["story", "tale"],
     "glosses": ["narrative"], "phrases": [], "examples": []},
    {"word": "masalah", "pos": "noun", "translations": ["problem", "issue"],
     "glosses": ["difficulty or challenge"], "phrases": [], "examples": []},
    {"word": "hal", "pos": "noun", "translations": ["thing", "matter", "affair"],
     "glosses": ["general noun for abstract concepts"], "phrases": [], "examples": []},

    # Common verbs
    {"word": "bilang", "pos": "verb", "translations": ["say", "tell"],
     "glosses": ["communication verb (informal)"], "phrases": [], "examples": []},
    {"word": "berkata", "pos": "verb", "translations": ["say", "speak"],
     "glosses": ["communication verb (formal)"], "phrases": [], "examples": []},
    {"word": "melihat", "pos": "verb", "translations": ["see", "look at", "watch"],
     "glosses": ["visual perception verb"], "phrases": [], "examples": []},
    {"word": "mendengar", "pos": "verb", "translations": ["hear", "listen"],
     "glosses": ["auditory perception verb"], "phrases": [], "examples": []},
    {"word": "datang", "pos": "verb", "translations": ["come", "arrive"],
     "glosses": ["motion-toward verb"], "phrases": [], "examples": []},
    {"word": "pergi", "pos": "verb", "translations": ["go", "leave"],
     "glosses": ["motion-away verb"], "phrases": [], "examples": []},
    {"word": "pulang", "pos": "verb", "translations": ["go home", "return home"],
     "glosses": ["motion-home verb"], "phrases": [], "examples": []},
    {"word": "tinggal", "pos": "verb", "translations": ["live", "stay", "reside"],
     "glosses": ["residence/location verb"], "phrases": [], "examples": []},
    {"word": "bawa", "pos": "verb", "translations": ["bring", "carry", "take"],
     "glosses": ["transport verb"], "phrases": [], "examples": []},
    {"word": "beri", "pos": "verb", "translations": ["give"],
     "glosses": ["transfer verb"], "phrases": [], "examples": []},
    {"word": "ambil", "pos": "verb", "translations": ["take", "get", "fetch"],
     "glosses": ["acquisition verb"], "phrases": [], "examples": []},
    {"word": "buka", "pos": "verb", "translations": ["open"],
     "glosses": ["opening action verb"], "phrases": [], "examples": []},
    {"word": "tutup", "pos": "verb", "translations": ["close", "shut"],
     "glosses": ["closing action verb"], "phrases": [], "examples": []},
    {"word": "bicara", "pos": "verb", "translations": ["speak", "talk"],
     "glosses": ["verbal communication verb"], "phrases": [], "examples": []},
    {"word": "tanya", "pos": "verb", "translations": ["ask", "inquire"],
     "glosses": ["question verb"], "phrases": [], "examples": []},
    {"word": "jawab", "pos": "verb", "translations": ["answer", "reply"],
     "glosses": ["response verb"], "phrases": [], "examples": []},
    {"word": "tahu", "pos": "verb", "translations": ["know", "aware"],
     "glosses": ["knowledge verb"], "phrases": [], "examples": []},
    {"word": "pikir", "pos": "verb", "translations": ["think"],
     "glosses": ["cognitive verb"], "phrases": [], "examples": []},
    {"word": "rasa", "pos": "verb", "translations": ["feel", "sense"],
     "glosses": ["sensation/emotion verb"], "phrases": [], "examples": []},
    {"word": "cinta", "pos": "verb", "translations": ["love"],
     "glosses": ["deep affection verb"], "phrases": [], "examples": []},
    {"word": "kerja", "pos": "verb", "translations": ["work"],
     "glosses": ["labor/occupation verb"], "phrases": [], "examples": []},
    {"word": "main", "pos": "verb", "translations": ["play"],
     "glosses": ["recreation verb"], "phrases": [], "examples": []},
    {"word": "tidur", "pos": "verb", "translations": ["sleep"],
     "glosses": ["rest verb"], "phrases": [], "examples": []},
    {"word": "bangun", "pos": "verb", "translations": ["wake up", "get up", "build"],
     "glosses": ["waking/construction verb"], "phrases": [], "examples": []},
    {"word": "beli", "pos": "verb", "translations": ["buy", "purchase"],
     "glosses": ["commerce verb"], "phrases": [], "examples": []},
    {"word": "jual", "pos": "verb", "translations": ["sell"],
     "glosses": ["commerce verb"], "phrases": [], "examples": []},
    {"word": "bayar", "pos": "verb", "translations": ["pay"],
     "glosses": ["commerce verb"], "phrases": [], "examples": []},
    {"word": "pakai", "pos": "verb", "translations": ["use", "wear"],
     "glosses": ["utilization verb"], "phrases": [], "examples": []},
    {"word": "tulis", "pos": "verb", "translations": ["write"],
     "glosses": ["writing verb"], "phrases": [], "examples": []},
    {"word": "baca", "pos": "verb", "translations": ["read"],
     "glosses": ["reading verb"], "phrases": [], "examples": []},
    {"word": "dengar", "pos": "verb", "translations": ["hear", "listen"],
     "glosses": ["auditory perception verb"], "phrases": [], "examples": []},
    {"word": "lupa", "pos": "verb", "translations": ["forget"],
     "glosses": ["memory-failure verb"], "phrases": [], "examples": []},
    {"word": "ingat", "pos": "verb", "translations": ["remember", "recall"],
     "glosses": ["memory verb"], "phrases": [], "examples": []},
    {"word": "coba", "pos": "verb", "translations": ["try", "attempt"],
     "glosses": ["attempt verb"], "phrases": [], "examples": []},
    {"word": "minta", "pos": "verb", "translations": ["ask for", "request"],
     "glosses": ["request verb"], "phrases": [], "examples": []},
    {"word": "tolong", "pos": "verb", "translations": ["help", "please"],
     "glosses": ["assistance verb/politeness marker"], "phrases": ["tolong bantu — please help"], "examples": []},
]


def merge_supplemental(wordnet_entries: list[dict]) -> list[dict]:
    """Merge supplemental dictionary entries into WordNet output.

    Supplemental entries replace any WordNet entry for the same word,
    regardless of POS. Entries for words not in WordNet are prepended.
    """
    # Build index: word -> list of indices
    word_index: dict[str, list[int]] = {}
    for i, e in enumerate(wordnet_entries):
        key = e["word"].lower()
        if key not in word_index:
            word_index[key] = []
        word_index[key].append(i)

    added = 0
    replaced = 0

    for supp in SUPPLEMENTAL_ID_EN:
        word_key = supp["word"].lower()
        entry = {
            "word": supp["word"],
            "pos": supp.get("pos"),
            "glosses": supp.get("glosses", []),
            "translations": supp.get("translations", []),
            "synonyms": [],
            "phrases": supp.get("phrases", []),
            "examples": supp.get("examples", []),
        }
        if word_key in word_index:
            # Replace the first (usually only) bad WordNet entry for this word
            first_idx = word_index[word_key][0]
            wordnet_entries[first_idx] = entry
            replaced += 1
        else:
            wordnet_entries.append(entry)
            added += 1

    print(f"  Supplemental: {added} added, {replaced} replaced in ID->EN dictionary")
    return wordnet_entries

# -- KBBI Parser (ID -> ID) ------------------------------------------------

def parse_kbbi(raw_json_path: Path) -> list[dict]:
    """Parse KBBI JSON into clean dictionary entries.

    Each word+POS pair gets its own entry. Homographs with different
    parts of speech (e.g., makan/v and makan/n) produce separate entries.
    """
    print("Parsing KBBI JSON...")
    with open(raw_json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # KBBI JSON is wrapped in {"dictionary": [...]}
    items = raw.get("dictionary", raw) if isinstance(raw, dict) else raw

    # (word, pos) -> list of meanings
    entries_by_key: dict[tuple[str, str | None], list[str]] = defaultdict(list)

    POS_LINE_RE = re.compile(
        r'^(Nomina|Verba|Adjektiva|Adverbia|Pronomina|Numeralia|Partikel'
        r'|Kata Benda|Kata Kerja|Kata Sifat|Kata Keterangan'
        r'|Kata Depan|Kata Sambung|Kata Seru|Kata Ganti'
        r'|Kata Bilangan|Kata Sandang|Kata Tanya'
        r'|Lambang|Singkatan|Akronim|Adjektival)',
        re.IGNORECASE
    )

    for item in items:
        word = item.get("word", "").strip()
        arti = item.get("arti", "")
        item_type = item.get("type", 1)

        if not word:
            continue

        word_lower = word.lower()
        pos = None

        if item_type == 1:
            # HTML format (entity-escaped: &lt;i&gt;n&lt;/i&gt;)
            arti_unescaped = html_mod.unescape(arti)
            pos_match = re.search(r'<i>([^<]+)</i>', arti_unescaped)
            raw_pos = pos_match.group(1) if pos_match else None
            pos = normalize_pos(raw_pos) if raw_pos else None
            meaning = strip_html(arti)
            # Strip the prefix: word + ordinal + POS tag
            # After strip_html: "2ma kan n tempat..." or "1ma kan 1 v memasukkan..."
            # Strategy: remove everything before and including the POS tag token
            if raw_pos:
                # Pattern: the raw POS as a standalone token (bounded by space/start)
                m = re.search(r'(?:^|(?<=\s))' + re.escape(raw_pos) + r'(?:\s|$)', meaning)
                if m:
                    meaning = meaning[m.end():].strip()
        else:
            # Type 2: plain text with POS on its own line
            lines = arti.split('\n')
            pos_line_idx = -1
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                # Skip word/syllabification line
                if word_lower.replace('.', '') == line.lower().replace('.', '').replace('-', ''):
                    continue
                pos_match = POS_LINE_RE.match(line)
                if pos_match:
                    pos = normalize_pos(pos_match.group(1))
                    pos_line_idx = i
                    break
            # Build meaning: everything after the POS line, stripping the POS prefix
            if pos_line_idx >= 0:
                # Strip the POS prefix from the POS line itself
                pos_line_raw = lines[pos_line_idx].strip()
                pos_label_found = POS_LINE_RE.match(pos_line_raw)
                if pos_label_found:
                    rest = pos_line_raw[pos_label_found.end():].strip()
                    lines[pos_line_idx] = rest
                meaning = ' '.join(ln.strip() for ln in lines[pos_line_idx:] if ln.strip())
            else:
                meaning = arti.replace('\n', ' ')

        meaning = re.sub(r'\s+', ' ', meaning).strip()
        # Strip parenthetical POS descriptions: "(kata benda)", "(kata kerja)", etc.
        meaning = re.sub(r'\s*\(kata\s+\w+\)\s*', ' ', meaning)
        meaning = re.sub(r'\s+', ' ', meaning).strip()
        if meaning:
            entries_by_key[(word_lower, pos)].append(meaning)

    # Build output entries
    output = []
    for (word, pos), meanings in sorted(entries_by_key.items(),
                                           key=lambda x: (x[0][0], x[0][1] or "")):
        seen = set()
        unique_meanings = []
        for m in meanings:
            if m not in seen:
                seen.add(m)
                unique_meanings.append(m)

        output.append({
            "word": word,
            "pos": pos,
            "meanings": unique_meanings,
            "phrases": [],
            "examples": [],
            "frequency_rank": None,
        })

    print(f"  Parsed {len(output):,} KBBI entries")
    return output

# -- WordNet Parser (ID -> EN) --------------------------------------------

def load_wordnet_glosses(wn_dir: Path) -> dict[tuple[int, str], str]:
    """Load Princeton WordNet 3.0 glosses from data files.

    Returns dict mapping (offset, pos) -> gloss string.
    """
    print("  Loading WordNet glosses...")
    glosses: dict[tuple[int, str], str] = {}

    pos_files = {
        'n': 'data.noun',
        'v': 'data.verb',
        'a': 'data.adj',
        'r': 'data.adv',
        's': 'data.adj',  # adjective satellites are in data.adj
    }

    dict_dir = wn_dir / "dict"

    for pos_code, filename in pos_files.items():
        filepath = dict_dir / filename
        if not filepath.exists():
            continue
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('  '):
                    continue
                if ' | ' not in line:
                    continue
                meta, gloss = line.split(' | ', 1)
                parts = meta.split()
                if len(parts) < 3:
                    continue
                try:
                    offset = int(parts[0])
                except ValueError:
                    continue
                ss_type = parts[2]
                if ss_type not in ('n', 'v', 'a', 'r', 's'):
                    continue
                glosses[(offset, ss_type)] = gloss.strip()

    print(f"    Loaded {len(glosses):,} WordNet glosses")
    return glosses

def parse_wordnet(tab_path: Path, glosses: dict) -> list[dict]:
    """Parse WordNet Bahasa tab file and merge with English glosses."""
    print("Parsing WordNet data...")

    entries_by_word: dict[str, dict] = defaultdict(lambda: {
        "word": "", "pos": None, "glosses": [], "translations": [],
        "synonyms": set()
    })

    with open(tab_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) < 4:
                continue

            synset_id = parts[0]
            goodness = parts[2]
            lemma = parts[3]

            if goodness not in ('Y', 'O'):
                continue
            if not synset_id or '-' not in synset_id:
                continue

            # Parse synset: "01234567-n" -> offset 1234567, pos 'n'
            offset_str, pos_wn = synset_id.split('-')
            try:
                offset = int(offset_str)
            except ValueError:
                continue

            # Map WordNet POS to standard
            pos_std = {'n': 'noun', 'v': 'verb', 'a': 'adjective', 'r': 'adverb', 's': 'adjective'}.get(pos_wn)

            # Get English gloss
            gloss = glosses.get((offset, pos_wn), "")

            # Split lemma into individual words
            words = [w.strip() for w in lemma.split(',') if w.strip()]

            # Merge all words from this synset as synonyms of each other
            for word in words:
                wl = word.lower().replace('_', ' ')
                key = wl
                if key not in entries_by_word:
                    entries_by_word[key]["word"] = wl
                    entries_by_word[key]["pos"] = pos_std
                if gloss:
                    entries_by_word[key]["glosses"].append(gloss)
                entries_by_word[key]["synonyms"].update(
                    w.lower().replace('_', ' ') for w in words if w.lower() != wl
                )

    output = []
    for word, data in sorted(entries_by_word.items()):
        # Deduplicate glosses
        seen_g = set()
        unique_glosses = []
        for g in data["glosses"]:
            if g not in seen_g:
                seen_g.add(g)
                unique_glosses.append(g)

        entry = {
            "word": data["word"],
            "pos": data["pos"],
            "glosses": unique_glosses,
            "translations": unique_glosses,
            "synonyms": sorted(data["synonyms"]),
            "phrases": [],
            "examples": [],
            "frequency_rank": None,
        }
        output.append(entry)

    print(f"  Parsed {len(output):,} WordNet (ID->EN) entries")
    return output

# -- FreeDict Parser (EN -> ID) -------------------------------------------

def parse_freedict(tei_path: Path) -> list[dict]:
    """Parse FreeDict TEI XML into English->Indonesian entries."""
    print("Parsing FreeDict TEI XML...")

    tree = etree.parse(str(tei_path))
    root = tree.getroot()

    # TEI namespace
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    # Try without namespace too
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0][1:]
        ns = {"tei": ns_uri}

    output = []

    for entry_el in root.iter(f"{{{ns['tei']}}}entry"):
        # Word (orth)
        orth_el = entry_el.find(f".//{{{ns['tei']}}}orth")
        if orth_el is None or orth_el.text is None:
            continue
        word = orth_el.text.strip().lower()
        if not word:
            continue

        # Part of speech
        pos = None
        pos_el = entry_el.find(f".//{{{ns['tei']}}}pos")
        if pos_el is not None and pos_el.text:
            pos = normalize_pos(pos_el.text.strip())

        # Translations from <sense> -> <cit type="trans"> -> <quote>
        translations = []
        phrases = []

        for sense_el in entry_el.findall(f".//{{{ns['tei']}}}sense"):
            for cit_el in sense_el.findall(f"{{{ns['tei']}}}cit"):
                cit_type = cit_el.get("type", "")
                quote_el = cit_el.find(f"{{{ns['tei']}}}quote")
                if quote_el is None or quote_el.text is None:
                    continue
                text = quote_el.text.strip()
                if cit_type == "trans":
                    translations.append(text)
                elif cit_type in ("example", "colloc"):
                    phrases.append(text)

        if not translations:
            continue

        entry = {
            "word": word,
            "pos": pos,
            "translations": translations,
            "phrases": phrases,
            "examples": [],
            "frequency_rank": None,
        }
        output.append(entry)

    print(f"  Parsed {len(output):,} FreeDict (EN->ID) entries")
    return output

# -- Tatoeba Example Sentences Parser ------------------------------------

def parse_tatoeba(sentences_path: Path, links_path: Path) -> dict[str, list[dict]]:
    """Parse Tatoeba sentences and links into word-indexed examples.

    Returns: {word: [{id: ind_sentence, en: eng_translation}]}
    """
    print("Parsing Tatoeba sentences...")

    # Load all sentences: id -> (lang, text)
    print("  Loading sentence IDs...")
    sentences: dict[int, tuple[str, str]] = {}
    with bz2.open(sentences_path, 'rt', encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t', 2)
            if len(parts) < 3:
                continue
            try:
                sid = int(parts[0])
            except ValueError:
                continue
            lang = parts[1].strip()
            text = parts[2].strip()
            if lang in ('ind', 'eng'):
                sentences[sid] = (lang, text)

    print(f"  Loaded {len(sentences):,} relevant sentences")

    # Load links: id -> [linked ids]
    print("  Loading translation links...")
    links: dict[int, list[int]] = {}
    with bz2.open(links_path, 'rt', encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 2:
                continue
            try:
                src = int(parts[0])
                dst = int(parts[1])
            except ValueError:
                continue
            if src not in links:
                links[src] = []
            links[src].append(dst)

    print(f"  Loaded {len(links):,} links")

    # Find Indonesian sentences with English translations
    print("  Matching Indonesian-English pairs...")
    word_examples: dict[str, list[dict]] = {}

    for sid, (lang, text) in sentences.items():
        if lang != 'ind':
            continue
        linked = links.get(sid, [])
        eng_texts = []
        for lid in linked:
            if lid in sentences and sentences[lid][0] == 'eng':
                eng_texts.append(sentences[lid][1])
        if not eng_texts:
            continue

        # Index each word in the Indonesian sentence
        words = set(w.strip().lower() for w in re.split(r'[\s,.;!?":/()\[\]{}]+', text) if w.strip())
        ex = {"id": text, "en": eng_texts[0]}
        for word in words:
            if len(word) < 2:
                continue
            if word not in word_examples:
                word_examples[word] = []
            if len(word_examples[word]) < 5:
                word_examples[word].append(ex)

    print(f"  Found examples for {len(word_examples):,} words")
    return word_examples


def embed_examples(entries: list[dict], word_examples: dict[str, list[dict]]) -> None:
    """Embed example sentences into dictionary entries."""
    count = 0
    for entry in entries:
        word = entry["word"].lower().replace("_", " ")
        exs = word_examples.get(word, [])
        if exs:
            entry["examples"] = exs
            count += 1
    print(f"  Added examples to {count:,} entries")

# -- Frequency Parser -----------------------------------------------------

def parse_frequency(csv_path: Path) -> dict[str, int]:
    """Parse frequency CSV into {word: rank} mapping.

    CSV format: word, count, percentage (rank = row index starting at 1)
    """
    print("Parsing frequency data...")
    freq: dict[str, int] = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rank = 0
        for row in reader:
            rank += 1
            if len(row) < 1:
                continue
            word = row[0].strip().lower()
            if word and word not in freq:
                freq[word] = rank

    print(f"  Loaded {len(freq):,} frequency entries")
    return freq

# -- Frequency Embedding --------------------------------------------------

def embed_frequency(entries: list[dict], freq: dict[str, int]) -> None:
    """Set frequency_rank on each entry from the frequency map."""
    count = 0
    for entry in entries:
        word = entry["word"].lower().replace("_", " ")
        rank = freq.get(word)
        if rank is not None:
            entry["frequency_rank"] = rank
            count += 1
    print(f"  Matched {count:,} entries with frequency data")

# -- Main Pipeline --------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Indonesian Dictionary -- Data Build Pipeline")
    print("=" * 60)

    # -- Step 1: KBBI (ID->ID) ----------------------------------------------
    print("\n[1/5] KBBI -- Indonesian Definitions")
    kbbi_path = CACHE_DIR / "kbbi_raw.json"
    if not kbbi_path.exists():
        download(KBBI_JSON_URL, kbbi_path)
    id_id_entries = parse_kbbi(kbbi_path)
    with open(DATA_DIR / "id_id.json", 'w', encoding='utf-8') as f:
        json.dump(id_id_entries, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {len(id_id_entries):,} entries -> data/id_id.json")

    # -- Step 2: WordNet (ID->EN) --------------------------------------------
    print("\n[2/5] WordNet -- Indonesian->English")
    wn_tab_path = CACHE_DIR / "wn-msa-all.tab"
    if not wn_tab_path.exists():
        download(WN_TAB_URL, wn_tab_path)

    wn_db_tar = CACHE_DIR / "WNdb-3.0.tar.gz"
    wn_extract_dir = CACHE_DIR / "WNdb-3.0"
    if not wn_extract_dir.exists():
        if not wn_db_tar.exists():
            download(WN_DB_URL, wn_db_tar)
        print("  Extracting WordNet database...")
        wn_extract_dir.mkdir(parents=True, exist_ok=True)
        with gzip.open(wn_db_tar, 'rb') as gz:
            with tarfile.open(fileobj=gz, mode='r:') as tar:
                tar.extractall(wn_extract_dir)
        # Files are in dict/ subdirectory inside the tar
        print("    Extracted successfully")

    glosses = load_wordnet_glosses(wn_extract_dir)
    id_en_entries = parse_wordnet(wn_tab_path, glosses)
    id_en_entries = merge_supplemental(id_en_entries)
    with open(DATA_DIR / "id_en.json", 'w', encoding='utf-8') as f:
        json.dump(id_en_entries, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {len(id_en_entries):,} entries -> data/id_en.json")

    # -- Step 3: FreeDict (EN->ID) -------------------------------------------
    print("\n[3/5] FreeDict -- English->Indonesian")
    fd_tar = CACHE_DIR / "freedict-eng-ind.src.tar.xz"
    fd_extract_dir = CACHE_DIR / "freedict-eng-ind"
    if not fd_extract_dir.exists():
        if not fd_tar.exists():
            download(FREEDICT_SRC_URL, fd_tar)
        print("  Extracting FreeDict source...")
        fd_extract_dir.mkdir(parents=True, exist_ok=True)
        extract_tar_xz(fd_tar, fd_extract_dir)

    # Find the TEI XML file
    tei_files = list(fd_extract_dir.glob("**/*.tei"))
    if not tei_files:
        tei_files = list(fd_extract_dir.glob("**/*.xml"))
    if not tei_files:
        print("  ERROR: No TEI/XML file found in FreeDict source")
        sys.exit(1)

    tei_file = tei_files[0]
    print(f"  Found source: {tei_file.name}")

    en_id_entries = parse_freedict(tei_file)
    with open(DATA_DIR / "en_id.json", 'w', encoding='utf-8') as f:
        json.dump(en_id_entries, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {len(en_id_entries):,} entries -> data/en_id.json")

    # -- Step 4: Tatoeba Example Sentences -----------------------------------
    print("\n[4/7] Tatoeba -- Example Sentences")
    tatoeba_sent = CACHE_DIR / "tatoeba_sentences.tar.bz2"
    tatoeba_links = CACHE_DIR / "tatoeba_links.tar.bz2"
    if not tatoeba_sent.exists():
        download(TATOEBA_SENTENCES_URL, tatoeba_sent)
    if not tatoeba_links.exists():
        download(TATOEBA_LINKS_URL, tatoeba_links)
    word_examples = parse_tatoeba(tatoeba_sent, tatoeba_links)
    with open(DATA_DIR / "examples.json", 'w', encoding='utf-8') as f:
        json.dump(word_examples, f, ensure_ascii=False, indent=2)
    print(f"  Wrote examples for {len(word_examples):,} words -> data/examples.json")

    # -- Step 5: Frequency -------------------------------------------------
    print("\n[5/7] Frequency Data")
    freq_csv_path = CACHE_DIR / "idwiki.csv"
    if not freq_csv_path.exists():
        download(FREQ_CSV_URL, freq_csv_path)
    frequency = parse_frequency(freq_csv_path)
    with open(DATA_DIR / "frequency.json", 'w', encoding='utf-8') as f:
        json.dump(frequency, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {len(frequency):,} entries -> data/frequency.json")

    # -- Step 6: Embed frequency -------------------------------------------
    print("\n[6/7] Embedding frequency...")
    for filename in ("id_id.json", "id_en.json", "en_id.json"):
        filepath = DATA_DIR / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        embed_frequency(entries, frequency)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f"  Updated {filename}")

    # -- Step 7: Embed examples into id_id and id_en dictionaries -----------
    print("\n[7/7] Embedding example sentences...")
    word_examples = json.load(open(DATA_DIR / "examples.json", 'r', encoding='utf-8'))
    for filename in ("id_id.json", "id_en.json"):
        filepath = DATA_DIR / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        embed_examples(entries, word_examples)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f"  Updated {filename}")

    print("\n" + "=" * 60)
    print("Build complete! Dictionary data is in data/")
    print(f"  id_id.json:  {(DATA_DIR/'id_id.json').stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  id_en.json:  {(DATA_DIR/'id_en.json').stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  en_id.json:  {(DATA_DIR/'en_id.json').stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  frequency.json: {(DATA_DIR/'frequency.json').stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 60)

if __name__ == "__main__":
    main()
