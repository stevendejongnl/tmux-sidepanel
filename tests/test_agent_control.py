"""The commands that control coding agents: list, name, send-keys, wait, prompt and start."""

import io
import json
import threading
import time
from dataclasses import dataclass

import pytest

from tests.tmux_support import (
    captured_text,
    first_pane_of_window,
    install_echo_agent,
    tmux_is_installed,
    wait_for_command,
    wait_until,
)
from tmux_sidepanel.command_line import CommandContext, main

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


@dataclass(frozen=True)
class CommandRun:
    code: int
    standard_output: str
    standard_error: str

    @property
    def result(self):
        return json.loads(self.standard_output)["result"]

    @property
    def error_code(self):
        return json.loads(self.standard_error)["error"]["code"]


def build_context(client, caller_pane=""):
    environment = {"TMUX_PANE": caller_pane} if caller_pane else {}
    return CommandContext(environment, io.StringIO(""), client, lambda: ("claude", "cat"))


def run_command(client, capsys, arguments, caller_pane=""):
    code = main(arguments, build_context(client, caller_pane))
    captured = capsys.readouterr()
    return CommandRun(code, captured.out, captured.err)


def set_state(client, pane, state):
    client.run("set-option", "-p", "-t", pane, "@sidepanel_state", state)


def set_name(client, pane, name):
    client.run("set-option", "-p", "-t", pane, "@sidepanel_name", name)


def set_states_later(client, pane, states, delay_seconds=0.4):
    """Change the state of a pane one step at a time, as the hooks of an agent would."""

    def change():
        for state in states:
            time.sleep(delay_seconds)
            set_state(client, pane, state)

    thread = threading.Thread(target=change)
    thread.start()
    return thread


def set_state_when_running(client, pane, command, state):
    """Report a state as the hooks of an agent would, once the agent is really running."""

    def change():
        wait_for_command(client, pane, command)
        set_state(client, pane, state)

    thread = threading.Thread(target=change)
    thread.start()
    return thread


@pytest.fixture
def agent_pane(tmux_client):
    """A pane that runs cat, so that it prints whatever is typed into it, with a state."""
    pane = tmux_client.run(
        "split-window", "-d", "-P", "-F", "#{pane_id}", "-t", "main:first", "cat"
    ).strip()
    wait_for_command(tmux_client, pane, "cat")
    set_state(tmux_client, pane, "idle")
    return pane


class TestAgentList:
    def test_lists_only_panes_with_an_agent(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "list"])
        assert [item["pane_id"] for item in run.result] == [agent_pane]


class TestAgentName:
    def test_gives_the_agent_a_name_that_finds_it_again(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "name", agent_pane, "reviewer"])
        assert run.result["name"] == "reviewer"
        assert run_command(tmux_client, capsys, ["get", "reviewer"]).result["pane_id"] == agent_pane

    @pytest.mark.parametrize("name", ["Upper", "1start", "has space", "", "x" * 33])
    def test_a_bad_name_is_refused(self, tmux_client, capsys, agent_pane, name):
        run = run_command(tmux_client, capsys, ["agent", "name", agent_pane, name])
        assert run.error_code == "bad_name"

    def test_a_name_that_is_taken_is_refused(self, tmux_client, capsys, agent_pane):
        other = first_pane_of_window(tmux_client, "first").pane_identifier
        set_state(tmux_client, other, "idle")
        set_name(tmux_client, other, "taken")
        tmux_client.run("respawn-pane", "-k", "-t", other, "cat")
        wait_for_command(tmux_client, other, "cat")
        run = run_command(tmux_client, capsys, ["agent", "name", agent_pane, "taken"])
        assert run.error_code == "name_taken"


class TestAgentSendKeys:
    def test_sends_named_keys_to_the_pane(self, tmux_client, capsys, agent_pane):
        tmux_client.run("send-keys", "-t", agent_pane, "-l", "typed")
        run = run_command(tmux_client, capsys, ["agent", "send-keys", agent_pane, "enter"])
        assert run.result == {"pane_id": agent_pane, "sent": ["enter"]}
        assert wait_until(lambda: captured_text(tmux_client, agent_pane).count("typed") == 2)

    def test_a_control_key_is_understood(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "send-keys", agent_pane, "ctrl+d"])
        assert run.code == 0

    def test_an_unknown_key_is_refused(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "send-keys", agent_pane, "hyper"])
        assert run.error_code == "bad_key"


class TestAgentWait:
    def test_returns_when_the_agent_has_settled(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "wait", agent_pane, "--timeout", "3000"])
        assert run.result == {"pane_id": agent_pane, "state": "idle"}

    def test_waits_for_the_state_that_was_asked_for(self, tmux_client, capsys, agent_pane):
        set_state(tmux_client, agent_pane, "working")
        thread = set_states_later(tmux_client, agent_pane, ["blocked"])
        arguments = ["agent", "wait", agent_pane, "--until", "blocked", "--timeout", "10000"]
        run = run_command(tmux_client, capsys, arguments)
        thread.join()
        assert run.result["state"] == "blocked"

    def test_a_timeout_is_an_error_with_a_code(self, tmux_client, capsys, agent_pane):
        set_state(tmux_client, agent_pane, "working")
        run = run_command(tmux_client, capsys, ["agent", "wait", agent_pane, "--timeout", "300"])
        assert run.error_code == "timeout"


class TestAgentPrompt:
    def test_types_the_text_and_presses_enter(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "prompt", agent_pane, "hello there"])
        assert run.result == {"pane_id": agent_pane, "submitted": True}
        assert wait_until(lambda: captured_text(tmux_client, agent_pane).count("hello there") == 2)

    def test_text_with_special_characters_arrives_unchanged(self, tmux_client, capsys, agent_pane):
        text = 'it\'s a $HOME `date` "quoted" line'
        run_command(tmux_client, capsys, ["agent", "prompt", agent_pane, text])
        assert wait_until(lambda: captured_text(tmux_client, agent_pane).count(text) == 2)

    def test_a_blocked_agent_is_not_prompted(self, tmux_client, capsys, agent_pane):
        set_state(tmux_client, agent_pane, "blocked")
        run = run_command(tmux_client, capsys, ["agent", "prompt", agent_pane, "text"])
        assert run.error_code == "agent_blocked"
        assert "text" not in captured_text(tmux_client, agent_pane)

    def test_a_pane_without_an_agent_is_not_prompted(self, tmux_client, capsys, agent_pane):
        set_state(tmux_client, agent_pane, "")
        run = run_command(tmux_client, capsys, ["agent", "prompt", agent_pane, "text"])
        assert run.error_code == "not_an_agent"

    def test_wait_returns_the_state_after_the_work(self, tmux_client, capsys, agent_pane):
        thread = set_states_later(tmux_client, agent_pane, ["working", "done"])
        arguments = ["agent", "prompt", agent_pane, "go", "--wait", "--timeout", "15000"]
        run = run_command(tmux_client, capsys, arguments)
        thread.join()
        assert run.result == {"pane_id": agent_pane, "state": "done"}

    def test_wait_reports_an_agent_that_never_starts_working(self, tmux_client, capsys, agent_pane):
        arguments = ["agent", "prompt", agent_pane, "go", "--wait", "--timeout", "1500"]
        run = run_command(tmux_client, capsys, arguments)
        assert run.error_code in {"timeout", "agent_prompt_stalled"}


class TestAgentStart:
    @pytest.fixture
    def shell_pane(self, tmux_client, tmp_path):
        install_echo_agent(tmp_path)
        shell = f"env PATH={tmp_path}:/usr/bin:/bin sh"  # the pane finds the fake agent first
        pane = tmux_client.run(
            "split-window", "-d", "-P", "-F", "#{pane_id}", "-t", "main:first", shell
        ).strip()
        wait_for_command(tmux_client, pane, "sh")
        return pane

    def test_starts_the_agent_in_a_shell_pane_and_names_it(self, tmux_client, capsys, shell_pane):
        thread = set_state_when_running(tmux_client, shell_pane, "claude", "idle")
        arguments = ["agent", "start", "worker", "--pane", shell_pane, "--timeout", "15000"]
        run = run_command(tmux_client, capsys, arguments)
        thread.join()
        assert run.result["name"] == "worker"
        assert run.result["state"] == "idle"

    def test_a_pane_that_does_not_show_a_shell_is_refused(self, tmux_client, capsys, agent_pane):
        run = run_command(tmux_client, capsys, ["agent", "start", "w", "--pane", agent_pane])
        assert run.error_code == "pane_not_available"

    def test_a_kind_that_is_not_an_agent_is_refused(self, tmux_client, capsys, shell_pane):
        arguments = ["agent", "start", "w", "--pane", shell_pane, "--kind", "rm"]
        assert run_command(tmux_client, capsys, arguments).error_code == "bad_kind"

    def test_a_bad_name_is_refused_before_anything_runs(self, tmux_client, capsys, shell_pane):
        arguments = ["agent", "start", "Bad Name", "--pane", shell_pane]
        assert run_command(tmux_client, capsys, arguments).error_code == "bad_name"

    def test_an_agent_that_does_not_report_in_time_is_an_error(
        self, tmux_client, capsys, shell_pane
    ):
        arguments = ["agent", "start", "late", "--pane", shell_pane, "--timeout", "500"]
        run = run_command(tmux_client, capsys, arguments)
        assert run.error_code == "agent_not_ready"
