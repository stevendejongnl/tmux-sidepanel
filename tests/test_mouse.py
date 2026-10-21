"""Mouse events of the terminal, turned into the clicks that the panel understands."""

import curses

import pytest

from tmux_sidepanel.mouse import click_at
from tmux_sidepanel.panel_layout import NO_SELECTION, Line

LINES = [
    Line("PANES", "title", "", False, NO_SELECTION),
    Line("  one", "row", "", False, 0),
    Line("  two", "row", "", False, 1),
]


@pytest.mark.parametrize("buttons", [curses.BUTTON1_PRESSED, curses.BUTTON1_CLICKED])
def test_the_left_button_is_a_primary_click_on_the_line_under_it(buttons):
    click = click_at(LINES, 2, buttons)
    assert (click.line, click.is_secondary) == (LINES[2], False)


@pytest.mark.parametrize("buttons", [curses.BUTTON3_PRESSED, curses.BUTTON3_CLICKED])
def test_the_right_button_is_a_secondary_click(buttons):
    assert click_at(LINES, 1, buttons).is_secondary is True


@pytest.mark.parametrize(
    "buttons", [curses.BUTTON1_RELEASED, curses.BUTTON3_RELEASED, curses.BUTTON2_PRESSED, 0]
)
def test_other_mouse_events_are_ignored(buttons):
    assert click_at(LINES, 1, buttons) is None


@pytest.mark.parametrize("row", [-1, 3, 40])
def test_a_click_below_the_lines_is_ignored(row):
    assert click_at(LINES, row, curses.BUTTON1_PRESSED) is None
