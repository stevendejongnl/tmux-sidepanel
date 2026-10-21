"""The lines under the panel: the menu of a row, a question to confirm, or a notice."""

from tmux_sidepanel.action_outcome import ask, done
from tmux_sidepanel.footer import footer_lines
from tmux_sidepanel.interface_state import InterfaceState
from tmux_sidepanel.menus import MenuItem

ITEMS = (MenuItem("g", "go to pane", "go"), MenuItem("z", "zoom pane", "zoom"))


def texts(lines):
    return [line.text for line in lines]


def test_nothing_to_say_gives_no_lines():
    assert footer_lines(InterfaceState(), 40) == []


def test_a_notice_is_one_line():
    lines = footer_lines(InterfaceState(notice="opened shop"), 40)
    assert texts(lines) == ["opened shop"]
    assert lines[0].kind == "notice"


def test_a_menu_has_a_line_for_each_action_with_its_key():
    lines = footer_lines(InterfaceState(menu=ITEMS), 40)
    assert texts(lines) == [" g  go to pane", " z  zoom pane"]
    assert {line.kind for line in lines} == {"menu"}


def test_the_highlighted_action_is_marked_as_active():
    lines = footer_lines(InterfaceState(menu=ITEMS, menu_selected=1), 40)
    assert [line.is_active for line in lines] == [False, True]


def test_a_prompt_is_one_line_and_hides_the_menu_and_the_notice():
    pending = ask("close it? y/n", lambda: done())
    lines = footer_lines(InterfaceState(menu=ITEMS, notice="old", pending=pending), 40)
    assert texts(lines) == ["close it? y/n"]
    assert lines[0].kind == "prompt"


def test_the_menu_hides_the_notice():
    assert len(footer_lines(InterfaceState(menu=ITEMS, notice="old"), 40)) == 2


def test_lines_are_clipped_to_the_width():
    lines = footer_lines(InterfaceState(notice="x" * 80), 20)
    assert len(lines[0].text) == 20


def test_a_menu_line_carries_the_number_of_its_action():
    lines = footer_lines(InterfaceState(menu=ITEMS), 40)
    assert [line.selection_index for line in lines] == [0, 1]
