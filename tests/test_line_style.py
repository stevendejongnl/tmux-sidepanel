"""How a line looks: its colour and emphasis, decided before anything is drawn."""

import pytest

from tmux_sidepanel.line_style import LineStyle, line_style
from tmux_sidepanel.panel_layout import Line


def build_line(kind="row", state="", is_active=False, selection_index=0):
    return Line("text", kind, state, is_active, selection_index)


@pytest.mark.parametrize(
    ("state", "color"),
    [
        ("blocked", "red"),
        ("done", "green"),
        ("working", "yellow"),
        ("unknown", "magenta"),
        ("idle", ""),
        ("", ""),
    ],
)
def test_the_state_of_a_row_gives_its_color(state, color):
    assert line_style(build_line(state=state), False).color == color


def test_a_title_is_bold():
    assert line_style(build_line("title"), False) == LineStyle("", True, False, False)


def test_an_empty_text_is_dim():
    assert line_style(build_line("empty"), False).is_dim


def test_the_active_row_is_bold():
    assert line_style(build_line(is_active=True), False).is_bold


def test_the_selected_row_is_reversed():
    assert line_style(build_line(), True).is_reversed


def test_the_highlighted_menu_item_is_reversed():
    assert line_style(build_line("menu", is_active=True), False).is_reversed


def test_a_menu_item_that_is_not_highlighted_is_plain():
    assert line_style(build_line("menu"), False) == LineStyle("", False, False, False)


def test_a_prompt_is_bold_and_red():
    style = line_style(build_line("prompt"), False)
    assert (style.color, style.is_bold) == ("red", True)


def test_a_notice_is_cyan():
    assert line_style(build_line("notice"), False).color == "cyan"
