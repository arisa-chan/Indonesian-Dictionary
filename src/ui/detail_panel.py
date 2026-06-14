"""Detail panel showing rich information about a selected word."""

import html

from PySide6.QtWidgets import QTextBrowser
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.models import DictionaryEntry
from src.utils import pos_label, highlight_matches
from src.srs import SrsManager


def _srs_color_hex(days: int | None) -> str:
    """Return a hex color for the SRS status dot."""
    if days is None:
        return "#999999"
    if days < 0:
        return "#d32f2f"
    if days == 0:
        return "#f57c00"
    if days <= 3:
        return "#fbc02d"
    if days <= 7:
        return "#388e3c"
    return "#1976d2"


def _srs_status_html(srs: SrsManager, collection: str, word: str) -> str:
    """Build an SRS status section in HTML, or an empty string if no data."""
    card = srs.get_card(collection, word)
    if card is None:
        days = None
    else:
        days = srs.days_from_today(card.due_date)

    color = _srs_color_hex(days)

    if days is None or card is None:
        status = "New card \u2014 never reviewed"
    elif days < 0:
        status = f"Overdue by {-days} day{'s' if -days != 1 else ''}"
    elif days == 0:
        status = "Due today"
    else:
        status = f"Due in {days} day{'s' if days != 1 else ''}"

    detail = ""
    if card is not None:
        detail = f" \u2014 interval {card.interval}d, ease {card.ease_factor:.1f}"
        if card.reps > 0:
            ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(card.reps, f"{card.reps}th")
            detail += f", {ordinal} review"

    return (
        '<div class="srs-status">'
        f'<span class="srs-dot" style="background:{color};"></span>'
        f"<b>SRS:</b> {status}{detail}"
        "</div>"
    )


class DetailPanel(QTextBrowser):
    """Rich HTML display for dictionary entry details."""

    save_requested = Signal(object)  # emits DictionaryEntry

    HTML_HEADER = """\
<!DOCTYPE html>
<html>
<head>
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 13px; color: #1a1a1a; margin: 16px; }
h1 { font-size: 24px; font-weight: 600; color: #ce1126; margin: 0 0 4px 0; }
.pos { font-size: 14px; color: #666; font-style: italic; margin: 0 0 16px 0; }
h2 { font-size: 15px; font-weight: 600; color: #333; margin: 18px 0 8px 0; border-bottom: 1px solid #eee; padding-bottom: 4px; }
ul { margin: 4px 0 12px 0; padding-left: 20px; }
li { margin: 3px 0; line-height: 1.5; }
.syn { display: inline-block; background: #f0f0f0; border-radius: 4px; padding: 2px 8px; margin: 2px; font-size: 12px; }
.freq { font-size: 13px; color: #555; margin: 16px 0 0 0; padding: 8px; background: #f8f8f8; border-radius: 4px; }
.freq b { color: #ce1126; }
b.search-match { color: #ce1126; background: #fff3f3; padding: 1px 0; }
.empty { color: #999; font-style: italic; margin-top: 64px; text-align: center; font-size: 14px; }
.save-btn { display: inline-block; padding: 5px 14px; margin-top: 16px; background: #ce1126; color: #fff; border-radius: 4px; text-decoration: none; font-size: 13px; }
.save-btn:hover { background: #a50e1f; }
.srs-status { font-size: 13px; color: #555; margin: 12px 0; padding: 8px; background: #f8f8f8; border-radius: 4px; }
.srs-status b { color: #333; }
.srs-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
</style>
</head>
<body>
"""

    def __init__(self, srs_mgr: SrsManager | None = None, parent=None):
        super().__init__(parent)
        self._srs = srs_mgr
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setFont(QFont("Segoe UI", 11))
        self._current_query = ""
        self._current_mode = "id_en"
        self._current_entry: DictionaryEntry | None = None
        self._current_collection = ""
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.show_empty()

    def show_entry(self, entry: DictionaryEntry, query: str = "",
                   mode: str = "id_en", collection: str = ""):
        """Display the full detail of a dictionary entry."""
        self._current_query = query
        self._current_mode = mode
        self._current_entry = entry
        self._current_collection = collection
        html = self._build_html(entry)
        self.setHtml(html)

    def show_empty(self):
        """Show the empty-state placeholder."""
        self._current_entry = None
        self._current_collection = ""
        html = self.HTML_HEADER + '<p class="empty">Select a word to see its details</p></body></html>'
        self.setHtml(html)

    def _on_anchor_clicked(self, url):
        if url.fragment() == "save":
            if self._current_entry:
                self.save_requested.emit(self._current_entry)

    def _build_html(self, entry: DictionaryEntry) -> str:
        parts = [self.HTML_HEADER]

        # Word header
        word_html = highlight_matches(entry.word, self._current_query)
        parts.append(f"<h1>{word_html}</h1>")

        # POS
        pos = pos_label(entry.pos) if entry.pos else ""
        if pos:
            parts.append(f'<p class="pos">{pos}</p>')

        # SRS status (only when viewing from a collection context)
        if self._srs and self._current_collection:
            parts.append(_srs_status_html(self._srs, self._current_collection, entry.word))

        # Meanings / Definitions
        if self._current_mode == "id_id" and entry.meanings:
            parts.append("<h2>Meaning</h2><ul>")
            for m in entry.meanings:
                m_html = highlight_matches(m, self._current_query)
                parts.append(f"<li>{m_html}</li>")
            parts.append("</ul>")

        # Translations (ID→EN and EN→ID)
        if entry.translations and self._current_mode != "id_id":
            heading = "Translation" if len(entry.translations) <= 1 else "Translations"
            parts.append(f"<h2>{heading}</h2><ul>")
            for t in entry.translations:
                t_html = highlight_matches(t, self._current_query)
                parts.append(f"<li>{t_html}</li>")
            parts.append("</ul>")

        # English glosses (for ID→EN mode)
        if self._current_mode == "id_en" and entry.glosses and not entry.translations:
            parts.append("<h2>Translations</h2><ul>")
            for g in entry.glosses:
                g_html = highlight_matches(g, self._current_query)
                parts.append(f"<li>{g_html}</li>")
            parts.append("</ul>")

        # Synonyms
        if entry.synonyms:
            parts.append("<h2>Synonyms</h2><p>")
            for syn in entry.synonyms[:30]:
                syn_html = highlight_matches(syn, "")
                parts.append(f'<span class="syn">{syn_html}</span> ')
            if len(entry.synonyms) > 30:
                parts.append(f'<span class="syn">+{len(entry.synonyms) - 30} more</span>')
            parts.append("</p>")

        # Phrases
        if entry.phrases:
            parts.append("<h2>Phrases</h2><ul>")
            for phrase in entry.phrases:
                p_html = highlight_matches(phrase, self._current_query)
                parts.append(f"<li>{p_html}</li>")
            parts.append("</ul>")

        # Examples
        if entry.examples:
            parts.append("<h2>Examples</h2><ul>")
            for ex in entry.examples:
                if isinstance(ex, dict):
                    id_text = highlight_matches(ex.get("id", ""), self._current_query)
                    en_text = html.escape(ex.get("en", ""))
                    parts.append(f"<li>{id_text}<br><i style='color:#888;'>{en_text}</i></li>")
                else:
                    ex_html = highlight_matches(str(ex), self._current_query)
                    parts.append(f"<li>{ex_html}</li>")
            parts.append("</ul>")

        # Frequency
        freq_text = entry.frequency_text
        parts.append(f'<p class="freq"><b>Usage:</b> {freq_text}</p>')

        # Save to collection button
        parts.append(
            '<a class="save-btn" href="#save">+ Save to Collection</a>'
        )

        parts.append("</body></html>")
        return "\n".join(parts)
