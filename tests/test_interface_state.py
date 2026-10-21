"""The keys of the panel: moving, opening a menu, running an action and answering a prompt."""

from dataclasses import dataclass

from tests.builders import build_pane_record
from tmux_sidepanel.action_outcome import ask, done
from tmux_sidepanel.configuration import default_configuration
from tmux_sidepanel.custom_rows import CustomSubject
from tmux_sidepanel.interface_state import (
    Click,
    InterfaceContext,
    InterfaceState,
    handle_click,
    handle_key,
)
from tmux_sidepanel.pane_rows import PaneSubject
from tmux_sidepanel.panel_layout import NO_SELECTION, Line
from tmux_sidepanel.rows import PanelView, Row, SectionView


@dataclass(frozen=True)
class PerformedAction:
    subject: object
    action: str


class Performer:
    """Records the actions that would run and answers with a fixed outcome."""

    def __init__(self, outcome=None):
        self.outcome = outcome or done("went")
        self.calls = []
        self.confirmed = []

    def confirm(self):
        self.confirmed.append(1)
        return done("closed")

    def __call__(self, subject, action):
        self.calls.append(PerformedAction(subject, action))
        return self.outcome


def pane_subject(identifier="%1"):
    return PaneSubject(build_pane_record(pane_identifier=identifier), "")


def pane_section(count=3):
    rows = tuple(
        Row(f"row {number}", "", False, pane_subject(f"%{number}")) for number in range(count)
    )
    return SectionView("panes", "panes", "PANES", "none", rows)


def build_context(panel=None, performer=None):
    panel = panel or PanelView((pane_section(),))
    return InterfaceContext(panel, default_configuration(), performer or Performer())


def press(context, state, *keys):
    for key in keys:
        state = handle_key(context, state, key)
    return state


class TestMoving:
    def test_down_and_j_move_the_selection_down(self):
        context = build_context()
        assert press(context, InterfaceState(), "j").selected == 1
        assert press(context, InterfaceState(), "DOWN").selected == 1

    def test_up_and_k_move_the_selection_up(self):
        context = build_context()
        assert press(context, InterfaceState(selected=2), "k").selected == 1
        assert press(context, InterfaceState(selected=2), "UP").selected == 1

    def test_the_selection_stops_at_the_last_row(self):
        assert press(build_context(), InterfaceState(selected=2), "j").selected == 2

    def test_the_selection_stops_at_the_first_row(self):
        assert press(build_context(), InterfaceState(), "k").selected == 0

    def test_a_selection_beyond_a_shrunken_panel_is_pulled_back(self):
        context = build_context(PanelView((pane_section(2),)))
        assert press(context, InterfaceState(selected=7), "k").selected == 0

    def test_q_finishes(self):
        assert press(build_context(), InterfaceState(), "q").is_finished

    def test_a_key_clears_the_notice(self):
        assert press(build_context(), InterfaceState(notice="old"), "j").notice == ""


class TestMenu:
    def test_enter_opens_the_menu_of_the_selected_row(self):
        state = press(build_context(), InterfaceState(), "ENTER")
        assert [item.action for item in state.menu][:2] == ["go", "zoom"]

    def test_a_row_without_actions_says_so(self):
        row = Row("custom", "", False, CustomSubject("some line"))
        panel = PanelView((SectionView("panes", "panes", "C", "", (row,)),))
        state = press(build_context(panel), InterfaceState(), "ENTER")
        assert state.menu == () and "no actions" in state.notice

    def test_enter_on_an_empty_panel_does_nothing(self):
        panel = PanelView((pane_section(0),))
        assert press(build_context(panel), InterfaceState(), "ENTER") == InterfaceState()

    def test_escape_closes_the_menu(self):
        state = press(build_context(), InterfaceState(), "ENTER", "ESC")
        assert state.menu == ()

    def test_the_key_of_an_action_runs_it_on_the_selected_row(self):
        performer = Performer(done("went"))
        context = build_context(performer=performer)
        state = press(context, InterfaceState(selected=1), "ENTER", "z")
        assert performer.calls[0].subject.pane.pane_identifier == "%1"
        assert performer.calls[0].action == "zoom"
        assert state.notice == "went"
        assert state.menu == ()

    def test_enter_runs_the_highlighted_action(self):
        performer = Performer()
        press(build_context(performer=performer), InterfaceState(), "ENTER", "DOWN", "ENTER")
        assert performer.calls[0].action == "zoom"

    def test_up_moves_the_highlight_back(self):
        state = press(build_context(), InterfaceState(), "ENTER", "DOWN", "UP")
        assert state.menu_selected == 0

    def test_an_unknown_key_keeps_the_menu_open(self):
        performer = Performer()
        state = press(build_context(performer=performer), InterfaceState(), "ENTER", "!")
        assert state.menu != () and performer.calls == []


class TestPrompt:
    def confirmable(self):
        performer = Performer()
        performer.outcome = ask("close it? y/n", performer.confirm)
        return performer

    def test_a_prompt_waits_and_does_not_run_yet(self):
        performer = self.confirmable()
        state = press(build_context(performer=performer), InterfaceState(), "ENTER", "X")
        assert state.pending.prompt == "close it? y/n"
        assert state.menu == ()
        assert performer.confirmed == []

    def test_yes_runs_the_confirmed_action(self):
        performer = self.confirmable()
        state = press(build_context(performer=performer), InterfaceState(), "ENTER", "X", "y")
        assert state.pending is None
        assert state.notice == "closed"
        assert performer.confirmed == [1]

    def test_any_other_key_cancels(self):
        performer = self.confirmable()
        state = press(build_context(performer=performer), InterfaceState(), "ENTER", "X", "n")
        assert state.pending is None
        assert state.notice == "cancelled"
        assert performer.confirmed == []


def row_click(selection_index, is_secondary=False):
    line = Line(f"  row {selection_index}", "row", "", False, selection_index)
    return Click(line, is_secondary)


def menu_click(item_number):
    return Click(Line(" x  item", "menu", "", False, item_number), False)


def blank_click():
    return Click(Line("", "blank", "", False, NO_SELECTION), True)


class TestClicking:
    def test_a_left_click_selects_the_row(self):
        state = handle_click(build_context(), InterfaceState(), row_click(2))
        assert state.selected == 2
        assert not state.menu

    def test_a_right_click_selects_the_row_and_opens_its_menu(self):
        state = handle_click(build_context(), InterfaceState(), row_click(1, True))
        assert state.selected == 1
        assert state.menu
        assert state.menu_selected == 0

    def test_a_click_on_a_title_or_a_blank_line_does_nothing(self):
        state = InterfaceState(selected=1)
        assert handle_click(build_context(), state, blank_click()) == state

    def test_a_click_on_a_menu_item_runs_its_action(self):
        performer = Performer()
        context = build_context(performer=performer)
        opened = handle_click(context, InterfaceState(selected=1), row_click(1, True))
        state = handle_click(context, opened, menu_click(1))
        assert [call.action for call in performer.calls] == [opened.menu[1].action]
        assert performer.calls[0].subject.pane.pane_identifier == "%1"
        assert not state.menu
        assert state.notice == "went"

    def test_a_click_outside_the_menu_closes_it_without_an_action(self):
        performer = Performer()
        context = build_context(performer=performer)
        opened = handle_click(context, InterfaceState(), row_click(0, True))
        state = handle_click(context, opened, row_click(2))
        assert not state.menu
        assert state.selected == 0
        assert performer.calls == []

    def test_a_click_answers_a_question_with_no(self):
        pending = ask("close it? y/n", lambda: done("closed"))
        state = handle_click(build_context(), InterfaceState(pending=pending), row_click(0))
        assert state.pending is None
        assert state.notice == "cancelled"

    def test_a_click_without_rows_does_nothing(self):
        empty = PanelView((SectionView("panes", "panes", "PANES", "none", ()),))
        state = handle_click(build_context(empty), InterfaceState(), row_click(0, True))
        assert state == InterfaceState()
