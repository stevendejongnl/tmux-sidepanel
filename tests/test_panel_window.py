"""Opening, closing and focusing the panel pane of a window."""

from operator import attrgetter

import pytest

from tests.tmux_support import add_window, first_pane_of_window, panes_of_window, tmux_is_installed
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.panel_window import PanelLayout, focus_panel, toggle_panel

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")

COMMAND = "sleep 600"


def layout(width=30, position="left"):
    return PanelLayout(COMMAND, width, position)


def window_of(client, name):
    return first_pane_of_window(client, name).window_identifier


def panel_panes(client, name):
    return list(filter(attrgetter("is_panel"), panes_of_window(client, name)))


def active_pane(client, name):
    return next(filter(attrgetter("is_active"), panes_of_window(client, name)))


class TestToggle:
    def test_the_first_toggle_opens_a_panel_pane(self, tmux_client):
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout())
        assert len(panel_panes(tmux_client, "first")) == 1
        assert len(panes_of_window(tmux_client, "first")) == 2

    def test_the_second_toggle_closes_it(self, tmux_client):
        window = window_of(tmux_client, "first")
        toggle_panel(tmux_client, window, layout())
        toggle_panel(tmux_client, window, layout())
        assert panel_panes(tmux_client, "first") == []
        assert len(panes_of_window(tmux_client, "first")) == 1

    def test_the_panel_has_the_given_width(self, tmux_client):
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout(width=24))
        panel = panel_panes(tmux_client, "first")[0]
        assert tmux_client.display(panel.pane_identifier, "#{pane_width}") == "24"

    def test_the_panel_is_on_the_left_by_default(self, tmux_client):
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout())
        panel = panel_panes(tmux_client, "first")[0]
        assert tmux_client.display(panel.pane_identifier, "#{pane_left}") == "0"

    def test_the_panel_can_be_on_the_right(self, tmux_client):
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout(position="right"))
        panel = panel_panes(tmux_client, "first")[0]
        assert tmux_client.display(panel.pane_identifier, "#{pane_left}") != "0"

    def test_opening_the_panel_keeps_the_focus_where_it_was(self, tmux_client):
        before = active_pane(tmux_client, "first").pane_identifier
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout())
        assert active_pane(tmux_client, "first").pane_identifier == before

    def test_other_windows_are_left_alone(self, tmux_client):
        add_window(tmux_client, "second")
        toggle_panel(tmux_client, window_of(tmux_client, "first"), layout())
        assert panel_panes(tmux_client, "second") == []


class TestFocus:
    def test_without_a_panel_it_opens_one_and_focuses_it(self, tmux_client):
        focus_panel(tmux_client, window_of(tmux_client, "first"), layout())
        assert active_pane(tmux_client, "first").is_panel

    def test_with_a_panel_it_moves_the_focus_to_it(self, tmux_client):
        window = window_of(tmux_client, "first")
        toggle_panel(tmux_client, window, layout())
        focus_panel(tmux_client, window, layout())
        assert active_pane(tmux_client, "first").is_panel

    def test_from_the_panel_it_returns_to_the_previous_pane(self, tmux_client):
        window = window_of(tmux_client, "first")
        before = active_pane(tmux_client, "first").pane_identifier
        focus_panel(tmux_client, window, layout())
        focus_panel(tmux_client, window, layout())
        assert active_pane(tmux_client, "first").pane_identifier == before

    def test_the_panel_stays_open_after_returning(self, tmux_client):
        window = window_of(tmux_client, "first")
        focus_panel(tmux_client, window, layout())
        focus_panel(tmux_client, window, layout())
        pane = find_pane(
            tmux_client.list_panes(), panel_panes(tmux_client, "first")[0].pane_identifier
        )
        assert pane.is_panel
