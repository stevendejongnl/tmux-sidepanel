"""The lines of the panel, ready to draw: titles, rows and empty texts, clipped to the width."""

from dataclasses import dataclass
from itertools import chain

from tmux_sidepanel.rows import PanelView, Row, SectionView

ELLIPSIS = "..."
INDENT = "  "
NO_SELECTION = -1


@dataclass(frozen=True)
class SelectableRow:
    section_identifier: str
    row: Row


@dataclass(frozen=True)
class Line:
    text: str
    kind: str  # title, row, empty or blank
    state: str
    is_active: bool
    selection_index: int  # the position among the selectable rows, or -1


def clip_text(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= len(ELLIPSIS):
        return text[: max(width, 0)]
    return text[: width - len(ELLIPSIS)] + ELLIPSIS


def section_rows(section: SectionView) -> list[SelectableRow]:
    return [SelectableRow(section.identifier, row) for row in section.rows]


def selectable_rows(panel: PanelView) -> list[SelectableRow]:
    return list(chain.from_iterable(map(section_rows, panel.sections)))


def title_line(section: SectionView, width: int) -> Line:
    return Line(clip_text(section.title, width), "title", "", False, NO_SELECTION)


def empty_line(section: SectionView, width: int) -> Line:
    return Line(clip_text(INDENT + section.empty_text, width), "empty", "", False, NO_SELECTION)


def row_line(row: Row, selection_index: int, width: int) -> Line:
    text = clip_text(INDENT + row.text, width)
    return Line(text, "row", row.state, row.is_active, selection_index)


def section_lines(section: SectionView, first_index: int, width: int) -> list[Line]:
    if section.is_empty:
        return [title_line(section, width), empty_line(section, width)]
    rows = [row_line(row, first_index + offset, width) for offset, row in enumerate(section.rows)]
    return [title_line(section, width), *rows]


def separator_lines(lines_so_far: list[Line]) -> list[Line]:
    """One blank line between sections, none before the first."""
    return [Line("", "blank", "", False, NO_SELECTION)] if lines_so_far else []


def build_lines(panel: PanelView, width: int) -> list[Line]:
    lines: list[Line] = []
    selected_so_far = 0
    for section in panel.sections:
        lines.extend(separator_lines(lines) + section_lines(section, selected_so_far, width))
        selected_so_far += len(section.rows)
    return lines
