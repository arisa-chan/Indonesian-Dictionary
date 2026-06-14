"""Data models for the Indonesian Dictionary application."""

from dataclasses import dataclass, field


@dataclass
class DictionaryEntry:
    """A single dictionary entry with all available fields."""

    word: str
    pos: str | None = None
    meanings: list[str] = field(default_factory=list)
    glosses: list[str] = field(default_factory=list)
    translations: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    frequency_rank: int | None = None

    @property
    def frequency_label(self) -> str:
        """Descriptive frequency category."""
        if self.frequency_rank is None:
            return "Unknown"
        r = self.frequency_rank
        if r <= 500:
            return "Very Common"
        elif r <= 2000:
            return "Common"
        elif r <= 10000:
            return "Uncommon"
        elif r <= 50000:
            return "Rare"
        else:
            return "Very Rare"

    @property
    def frequency_text(self) -> str:
        """Formatted frequency string for display."""
        if self.frequency_rank is None:
            return "Unknown"
        return f"{self.frequency_label} (#{self.frequency_rank:,})"
