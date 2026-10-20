"""Rows and views: what the panel shows, before anything is drawn."""

from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.terminal_text import sanitize_for_terminal

STATE_MARKS = {"blocked": "!", "done": "+", "working": "~", "idle": ".", "unknown": "?", "": " "}


@dataclass(frozen=True)
class Row:
    text: str
    state: str
    is_active: bool
    subject: Any  # what the row stands for, so a menu knows what to act on


@dataclass(frozen=True)
class SectionView:
    identifier: str
    section_type: str
    title: str
    empty_text: str
    rows: tuple[Row, ...]

    @property
    def is_empty(self) -> bool:
        return not self.rows


@dataclass(frozen=True)
class PanelView:
    sections: tuple[SectionView, ...]


def state_mark(state: str) -> str:
    return STATE_MARKS.get(state, " ")


def format_row(row_format: str, fields: dict[str, str]) -> str:
    """Fill a row format. Values are made safe, and gaps left by empty values are closed."""
    text = row_format.format(**fields)
    return " ".join(sanitize_for_terminal(text).split())
