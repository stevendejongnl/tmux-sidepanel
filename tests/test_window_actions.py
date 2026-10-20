"""Moving around in tmux: jumping to a pane, opening a folder, running a command in a new window."""

import subprocess

import pytest

from tests.tmux_support import (
    add_window,
    captured_text,
    first_pane_of_window,
    tmux_is_installed,
    wait_until,
    window_names,
)
from tmux_sidepanel.action_outcome import ActionOutcome
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.tmux_client import TmuxError
from tmux_sidepanel.window_actions import (
    jump_to_pane,
    keep_open_command,
    open_command_window,
    open_directory,
)

needs_tmux = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


class TestOutcome:
    def test_an_outcome_defaults_to_nothing_to_say_and_nothing_to_confirm(self):
        outcome = ActionOutcome()
        assert (outcome.notice, outcome.prompt, outcome.confirmed) == ("", "", None)


class TestKeepOpenCommand:
    def run_in_shell(self, command, typed=""):
        return subprocess.run(
            ["sh", "-c", keep_open_command(command)],
            input=typed,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_a_command_that_works_prints_nothing_extra(self):
        assert self.run_in_shell("true").stdout == ""

    def test_a_command_that_fails_says_so_and_waits_for_enter(self):
        result = self.run_in_shell("false", typed="\n")
        assert "exited with 1" in result.stdout

    def test_the_output_of_the_command_is_kept(self):
        assert "hello" in self.run_in_shell("echo hello").stdout


@needs_tmux
class TestJump:
    def test_makes_the_pane_and_its_window_active(self, tmux_client):
        add_window(tmux_client, "second")
        second = first_pane_of_window(tmux_client, "second")
        jump_to_pane(tmux_client, second.pane_identifier)
        record = find_pane(tmux_client.list_panes(), second.pane_identifier)
        assert record.is_active
        assert record.is_window_active

    def test_a_pane_that_does_not_exist_raises(self, tmux_client):
        with pytest.raises(TmuxError):
            jump_to_pane(tmux_client, "%999")


@needs_tmux
class TestOpenDirectory:
    def test_opens_a_new_window_in_the_folder(self, tmux_client, tmp_path):
        folder = tmp_path / "shop"
        folder.mkdir()
        outcome = open_directory(tmux_client, str(folder))
        assert "shop" in outcome.notice
        found = wait_until(
            lambda: str(folder) in [pane.current_directory for pane in tmux_client.list_panes()]
        )
        assert found

    def test_a_folder_that_does_not_exist_opens_nothing(self, tmux_client, tmp_path):
        before = window_names(tmux_client)
        outcome = open_directory(tmux_client, str(tmp_path / "missing"))
        assert "no directory" in outcome.notice
        assert window_names(tmux_client) == before

    def test_an_empty_folder_name_opens_nothing(self, tmux_client):
        assert "no directory" in open_directory(tmux_client, "").notice


@needs_tmux
class TestCommandWindow:
    def test_runs_the_command_in_a_new_window_with_the_given_name(self, tmux_client):
        outcome = open_command_window(tmux_client, "greeting", "echo hello-from-window; sleep 30")
        assert "greeting" in outcome.notice
        assert "greeting" in window_names(tmux_client)
        pane = first_pane_of_window(tmux_client, "greeting")
        assert wait_until(
            lambda: "hello-from-window" in captured_text(tmux_client, pane.pane_identifier)
        )

    def test_a_failing_command_keeps_its_window_open_with_a_message(self, tmux_client):
        open_command_window(tmux_client, "broken", "false")
        pane = first_pane_of_window(tmux_client, "broken")
        assert wait_until(
            lambda: "exited with 1" in captured_text(tmux_client, pane.pane_identifier)
        )

    def test_the_command_can_start_in_a_folder(self, tmux_client, tmp_path):
        open_command_window(tmux_client, "here", "pwd; sleep 30", directory=str(tmp_path))
        pane = first_pane_of_window(tmux_client, "here")
        assert wait_until(lambda: str(tmp_path) in captured_text(tmux_client, pane.pane_identifier))

    def test_a_long_name_is_shortened(self, tmux_client):
        open_command_window(tmux_client, "x" * 80, "sleep 5")
        assert all(len(name) <= 24 for name in window_names(tmux_client))
