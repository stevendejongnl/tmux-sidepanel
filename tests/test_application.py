"""The application: the panel of the window of the panel pane, and the actions of its rows."""

import pytest

from tests.tmux_support import (
    add_window,
    first_pane_of_window,
    split_pane,
    tmux_is_installed,
)
from tmux_sidepanel.application import build_application, current_panel, perform_for
from tmux_sidepanel.configuration import parse_configuration
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.pane_rows import PaneSubject

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")

PANES_ONLY = '[[sections]]\ntype = "panes"\n'


def build_for_window(tmux_client, name):
    pane = first_pane_of_window(tmux_client, name)
    configuration = parse_configuration(PANES_ONLY)
    return build_application(tmux_client, configuration, pane.pane_identifier)


class TestWindow:
    def test_the_window_is_the_window_of_the_panel_pane(self, tmux_client):
        add_window(tmux_client, "work")
        application = build_for_window(tmux_client, "work")
        pane = first_pane_of_window(tmux_client, "work")
        assert application.window_identifier == pane.window_identifier

    def test_an_unknown_pane_gives_no_window(self, tmux_client):
        configuration = parse_configuration(PANES_ONLY)
        application = build_application(tmux_client, configuration, "%9999")
        assert application.window_identifier == ""


class TestPanel:
    def test_the_panel_lists_the_panes_of_the_window_only(self, tmux_client):
        add_window(tmux_client, "work")
        split_pane(tmux_client, "work")
        panel = current_panel(build_for_window(tmux_client, "work"))
        assert len(panel.sections[0].rows) == 2

    def test_another_window_does_not_show_up(self, tmux_client):
        add_window(tmux_client, "work")
        panel = current_panel(build_for_window(tmux_client, "first"))
        assert len(panel.sections[0].rows) == 1


class TestPerformer:
    def test_the_performer_runs_an_action_on_the_subject(self, tmux_client):
        add_window(tmux_client, "work")
        application = build_for_window(tmux_client, "work")
        pane = first_pane_of_window(tmux_client, "work")
        outcome = perform_for(application)(PaneSubject(pane, ""), "go")
        assert outcome.notice == ""
        assert find_pane(tmux_client.list_panes(), pane.pane_identifier).is_window_active

    def test_a_subject_that_is_gone_becomes_a_notice(self, tmux_client):
        add_window(tmux_client, "work")
        application = build_for_window(tmux_client, "work")
        pane = first_pane_of_window(tmux_client, "work")
        tmux_client.run("kill-window", "-t", "work")
        outcome = perform_for(application)(PaneSubject(pane, ""), "go")
        assert outcome.notice.startswith("tmux:")
