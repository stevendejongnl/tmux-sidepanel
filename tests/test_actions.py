"""The dispatcher: one entry for every action, and tmux problems turned into notices."""

import pytest

from tests.builders import build_pane_record
from tests.tmux_support import add_window, first_pane_of_window, tmux_is_installed
from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome, ask, done
from tmux_sidepanel.actions import perform_action, safely
from tmux_sidepanel.custom_rows import CustomSubject
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.pane_rows import PaneSubject
from tmux_sidepanel.tmux_client import TmuxClient, TmuxError


def raise_tmux_error():
    raise TmuxError("tmux select-pane: can't find pane: %9")


class TestSafely:
    def test_passes_the_outcome_through(self):
        assert safely(lambda: done("fine")) == done("fine")

    def test_turns_a_tmux_error_into_a_notice(self):
        outcome = safely(raise_tmux_error)
        assert outcome.notice.startswith("tmux:")
        assert "can't find pane" in outcome.notice

    def test_a_confirmation_that_fails_later_is_turned_into_a_notice_too(self):
        outcome = safely(lambda: ask("really? y/n", raise_tmux_error))
        assert outcome.prompt == "really? y/n"
        assert outcome.confirmed().notice.startswith("tmux:")

    def test_a_confirmation_that_works_keeps_its_result(self):
        outcome = safely(lambda: ask("really? y/n", lambda: done("did it")))
        assert outcome.confirmed() == done("did it")


class TestPerformAction:
    def test_a_row_without_actions_says_so(self):
        context = ActionContext(client=TmuxClient())
        outcome = perform_action(context, CustomSubject("8000 api"), "go")
        assert outcome == ActionOutcome(notice="nothing to do")

    def test_a_subject_nobody_knows_says_so(self):
        context = ActionContext(client=TmuxClient())
        assert perform_action(context, object(), "go").notice == "nothing to do"

    def test_an_unknown_action_says_so(self):
        context = ActionContext(client=TmuxClient())
        subject = PaneSubject(build_pane_record(), "")
        assert perform_action(context, subject, "explode").notice == "nothing to do"

    def test_a_pane_that_is_gone_gives_a_notice_not_a_crash(self, tmp_path):
        context = ActionContext(client=TmuxClient(str(tmp_path / "nothing.sock")))
        subject = PaneSubject(build_pane_record(pane_identifier="%9"), "")
        outcome = perform_action(context, subject, "go")
        assert outcome.notice.startswith("tmux:")


@pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")
class TestWithTmux:
    def test_a_pane_action_reaches_the_pane_performer(self, tmux_client):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        subject = PaneSubject(pane, "")
        perform_action(ActionContext(client=tmux_client), subject, "go")
        assert find_pane(tmux_client.list_panes(), pane.pane_identifier).is_window_active

    def test_a_destructive_action_asks_first(self, tmux_client):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        outcome = perform_action(ActionContext(client=tmux_client), PaneSubject(pane, ""), "close")
        assert outcome.prompt.startswith("CLOSE")
