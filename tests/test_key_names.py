"""Keys of the terminal, turned into the names that the panel understands."""

import curses

import pytest

from tmux_sidepanel.key_names import key_name


@pytest.mark.parametrize(
    ("code", "name"),
    [
        (curses.KEY_UP, "UP"),
        (curses.KEY_DOWN, "DOWN"),
        (10, "ENTER"),
        (13, "ENTER"),
        (curses.KEY_ENTER, "ENTER"),
        (27, "ESC"),
        (ord("j"), "j"),
        (ord("X"), "X"),
        (ord(" "), " "),
    ],
)
def test_a_key_has_a_name(code, name):
    assert key_name(code) == name


@pytest.mark.parametrize("code", [-1, curses.KEY_RESIZE, curses.KEY_F1, 3, 0x1F600])
def test_a_key_without_a_name_gives_an_empty_text(code):
    assert key_name(code) == ""
