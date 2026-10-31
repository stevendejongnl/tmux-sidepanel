"""Fitting the lines of the panel and the footer on a screen of a given height."""

from collections.abc import Sequence

from tmux_sidepanel.panel_layout import NO_SELECTION, Line

BLANK = Line("", "blank", "", False, NO_SELECTION)


def line_of_selection(lines: list[Line], selection_index: int) -> int:
    """The position of the line that holds the selected row, or 0 when there is none."""
    indexes = [line.selection_index for line in lines]
    return indexes.index(selection_index) if selection_index in indexes else 0


def first_visible_line(line_count: int, body_height: int, selected_line: int) -> int:
    """The first line to show, so that the selected line is the last one when it is far down."""
    scrolled = selected_line - body_height + 1
    return max(0, min(scrolled, line_count - body_height))


def compose_screen(
    body: list[Line],
    footer: list[Line],
    height: int,
    selected_line: int,
    header: Sequence[Line] = (),
) -> list[Line]:
    """The footer at the bottom, the header on top, and between them the body that fits.

    On a short screen the footer goes first, because it can hold a question.
    """
    kept_footer = footer[: max(height, 0)]
    free_height = max(height - len(kept_footer), 0)
    kept_header = list(header[:free_height])
    body_height = free_height - len(kept_header)
    first = first_visible_line(len(body), body_height, selected_line)
    shown = body[first : first + body_height]
    padding = [BLANK] * (body_height - len(shown)) if kept_footer else []
    return kept_header + shown + padding + kept_footer
