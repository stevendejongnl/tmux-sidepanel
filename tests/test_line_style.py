"""How a line looks: its colour and emphasis, decided before anything is drawn."""

import pytest

from tmux_sidepanel.line_style import KIND_COLORS, STATE_COLORS, LineStyle, line_style
from tmux_sidepanel.line_style import SECTION_COLORS as section_colors
from tmux_sidepanel.panel_layout import Line
from tmux_sidepanel.panel_screen import COLORS


def build_line(kind="row", state="", is_active=False, selection_index=0, section_type=""):
    return Line("text", kind, state, is_active, selection_index, section_type)


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


SECTION_COLORS = [
    ("panes", "blue"),
    ("subagents", "cyan"),
    ("services", "green"),
    ("zombies", "red"),
    ("custom", "magenta"),
]


@pytest.mark.parametrize(("section_type", "color"), SECTION_COLORS)
def test_the_title_of_a_section_has_the_color_of_its_type(section_type, color):
    assert line_style(build_line("title", section_type=section_type), False).color == color


@pytest.mark.parametrize(("section_type", "color"), SECTION_COLORS)
def test_a_row_without_a_state_has_the_color_of_its_section(section_type, color):
    assert line_style(build_line(section_type=section_type), False).color == color


def test_the_state_of_a_row_wins_over_the_color_of_its_section():
    assert line_style(build_line(state="blocked", section_type="panes"), False).color == "red"


@pytest.mark.parametrize("kind", ["empty", "menu", "blank", "notice"])
def test_only_titles_and_rows_take_the_color_of_their_section(kind):
    assert line_style(build_line(kind, section_type="panes"), False).color != "blue"


def test_every_color_that_is_used_can_be_drawn():
    used = {*STATE_COLORS.values(), *KIND_COLORS.values(), *section_colors.values()}
    assert used <= set(COLORS)
