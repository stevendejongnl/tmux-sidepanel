"""Terminal text: anything that comes from another program is made safe to print."""

import pytest

from tmux_sidepanel.terminal_text import sanitize_for_terminal


def test_plain_text_is_unchanged():
    assert sanitize_for_terminal("uv run pytest tests/") == "uv run pytest tests/"


def test_an_escape_sequence_loses_its_escape_character():
    assert sanitize_for_terminal("\x1b[31mred\x1b[0m") == "?[31mred?[0m"


@pytest.mark.parametrize(
    "character",
    ["\x00", "\x07", "\x08", "\r", "\n", "\x7f", "\x1b", chr(0x9B), chr(0x85), chr(0x9D)],
)
def test_control_characters_become_a_question_mark(character):
    assert sanitize_for_terminal("a" + character + "b") == "a?b"


def test_a_tab_becomes_a_space():
    assert sanitize_for_terminal("a\tb") == "a b"


def test_letters_beyond_ascii_are_kept():
    text = "caf" + chr(0xE9) + " " + chr(0x4E2D)
    assert sanitize_for_terminal(text) == text


def test_empty_text_stays_empty():
    assert sanitize_for_terminal("") == ""


def test_an_operating_system_command_cannot_set_the_title():
    hostile = "\x1b]0;owned\x07"
    assert "\x1b" not in sanitize_for_terminal(hostile)
    assert "\x07" not in sanitize_for_terminal(hostile)
