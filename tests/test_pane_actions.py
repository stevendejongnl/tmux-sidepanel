"""The actions of the menu of a pane and of a subagent."""

from dataclasses import replace

import pytest

from tests.tmux_support import (
    add_window,
    captured_text,
    first_pane_of_window,
    install_echo_agent,
    pane_identifiers,
    split_pane,
    tmux_is_installed,
    wait_for_command,
    wait_until,
)
from tmux_sidepanel.action_outcome import ActionContext
from tmux_sidepanel.agents import Subagent
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.pane_actions import perform_pane_action, perform_subagent_action
from tmux_sidepanel.pane_rows import PaneSubject, SubagentSubject

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def build_context(client):
    return ActionContext(client=client)


def subject_of(client, pane, state=""):
    return PaneSubject(find_pane(client.list_panes(), pane.pane_identifier), state)


def start_echo_agent(client, directory):
    program = install_echo_agent(directory)
    add_window(client, "agent", str(program))
    pane = first_pane_of_window(client, "agent")
    wait_for_command(client, pane.pane_identifier, "claude")
    return pane


class TestGo:
    def test_jumps_to_the_pane(self, tmux_client):
        add_window(tmux_client, "second")
        second = first_pane_of_window(tmux_client, "second")
        perform_pane_action(build_context(tmux_client), subject_of(tmux_client, second), "go")
        assert find_pane(tmux_client.list_panes(), second.pane_identifier).is_window_active


class TestZoom:
    def test_zooms_the_pane(self, tmux_client):
        split_pane(tmux_client, "first")
        pane = first_pane_of_window(tmux_client, "first")
        perform_pane_action(build_context(tmux_client), subject_of(tmux_client, pane), "zoom")
        assert tmux_client.display(pane.pane_identifier, "#{window_zoomed_flag}") == "1"


class TestDirectory:
    def test_opens_the_folder_of_the_pane(self, tmux_client, tmp_path):
        pane = first_pane_of_window(tmux_client, "first")
        subject = PaneSubject(replace(pane, current_directory=str(tmp_path)), "")
        outcome = perform_pane_action(build_context(tmux_client), subject, "directory")
        assert tmp_path.name in outcome.notice


class TestInterrupt:
    def test_an_agent_gets_escape_without_asking(self, tmux_client, tmp_path):
        pane = start_echo_agent(tmux_client, tmp_path)
        subject = subject_of(tmux_client, pane, state="working")
        outcome = perform_pane_action(build_context(tmux_client), subject, "interrupt")
        assert outcome.prompt == ""
        assert "Esc" in outcome.notice
        assert wait_until(lambda: "^[" in captured_text(tmux_client, pane.pane_identifier))

    def test_a_plain_pane_asks_before_it_sends_control_c(self, tmux_client):
        add_window(tmux_client, "second", "cat")
        pane = first_pane_of_window(tmux_client, "second")
        wait_for_command(tmux_client, pane.pane_identifier, "cat")
        outcome = perform_pane_action(
            build_context(tmux_client), subject_of(tmux_client, pane), "interrupt"
        )
        assert outcome.prompt.endswith("y/n")
        assert "Ctrl-C" in outcome.prompt
        assert pane.pane_identifier in pane_identifiers(tmux_client)

    def test_after_the_confirmation_the_program_is_interrupted(self, tmux_client):
        add_window(tmux_client, "second", "cat")
        pane = first_pane_of_window(tmux_client, "second")
        wait_for_command(tmux_client, pane.pane_identifier, "cat")
        outcome = perform_pane_action(
            build_context(tmux_client), subject_of(tmux_client, pane), "interrupt"
        )
        outcome.confirmed()
        assert wait_until(lambda: pane.pane_identifier not in pane_identifiers(tmux_client))


class TestClose:
    def test_asks_first_and_names_what_will_be_closed(self, tmux_client):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        outcome = perform_pane_action(
            build_context(tmux_client), subject_of(tmux_client, pane), "close"
        )
        assert outcome.prompt.startswith("CLOSE")
        assert pane.pane_identifier in pane_identifiers(tmux_client)

    def test_an_agent_pane_says_that_the_session_ends(self, tmux_client):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        subject = subject_of(tmux_client, pane, state="working")
        outcome = perform_pane_action(build_context(tmux_client), subject, "close")
        assert "session" in outcome.prompt

    def test_after_the_confirmation_the_pane_is_gone(self, tmux_client):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        outcome = perform_pane_action(
            build_context(tmux_client), subject_of(tmux_client, pane), "close"
        )
        outcome.confirmed()
        assert pane.pane_identifier not in pane_identifiers(tmux_client)


class TestSubagent:
    def subagent_subject(self, client, pane, parent_state):
        record = find_pane(client.list_panes(), pane.pane_identifier)
        return SubagentSubject(record, Subagent("aaa111", "Explore"), parent_state)

    def test_go_jumps_to_the_parent_pane(self, tmux_client):
        add_window(tmux_client, "second")
        second = first_pane_of_window(tmux_client, "second")
        subject = self.subagent_subject(tmux_client, second, "working")
        perform_subagent_action(build_context(tmux_client), subject, "go")
        assert find_pane(tmux_client.list_panes(), second.pane_identifier).is_window_active

    def test_tasks_types_the_command_into_the_parent(self, tmux_client, tmp_path):
        pane = start_echo_agent(tmux_client, tmp_path)
        subject = self.subagent_subject(tmux_client, pane, "idle")
        outcome = perform_subagent_action(build_context(tmux_client), subject, "tasks")
        assert "/tasks" in outcome.notice
        assert wait_until(lambda: "/tasks" in captured_text(tmux_client, pane.pane_identifier))

    @pytest.mark.parametrize("parent_state", ["blocked", "unknown"])
    def test_tasks_does_not_type_into_a_parent_that_waits_on_input(
        self, tmux_client, tmp_path, parent_state
    ):
        pane = start_echo_agent(tmux_client, tmp_path)
        subject = self.subagent_subject(tmux_client, pane, parent_state)
        outcome = perform_subagent_action(build_context(tmux_client), subject, "tasks")
        assert "yourself" in outcome.notice
        assert "/tasks" not in captured_text(tmux_client, pane.pane_identifier)
