"""Utility functions for text normalization and POS formatting."""

def pos_label(pos: str | None) -> str:
    """Return a human-readable POS label."""
    if not pos:
        return ""
    labels = {
        "noun": "noun",
        "verb": "verb",
        "adjective": "adj",
        "adverb": "adv",
        "pronoun": "pron",
        "numeral": "num",
        "particle": "part",
        "partikel": "part",
        "adjektiva": "adj",
        "adverbia": "adv",
        "nomina": "noun",
        "verba": "verb",
        "pronomina": "pron",
        "numeralia": "num",
    }
    return labels.get(pos.lower(), pos.lower())


def normalize_text(text: str) -> str:
    """Normalize text for search: lowercase, strip whitespace."""
    return text.strip().lower()


def highlight_matches(text: str, query: str) -> str:
    """Wrap matching substrings in <b> tags for HTML display.

    Escapes HTML in the text first, then wraps matches.
    """
    import html
    escaped = html.escape(text)
    if not query:
        return escaped
    q = html.escape(query.lower())
    # Case-insensitive replacement
    result = []
    pos = 0
    lower = escaped.lower()
    while True:
        idx = lower.find(q, pos)
        if idx == -1:
            result.append(escaped[pos:])
            break
        result.append(escaped[pos:idx])
        result.append(f"<b>{escaped[idx:idx + len(q)]}</b>")
        pos = idx + len(q)
    return "".join(result)
