"""The commands for programs and other agents: list, current and get print JSON."""

import io
import json
from dataclasses import dataclass

import pytest

from tests.tmux_support import add_window, first_pane_of_window, tmux_is_installed
from tmux_sidepanel.command_line import CommandContext, main

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def build_context(client, caller_pane="", agent_names=("claude",)):
    environment = {"TMUX_PANE": caller_pane} if caller_pane else {}
    return CommandContext(
        environment=environment,
        standard_input=io.StringIO(""),
        client=client,
        agent_names=lambda: agent_names,
    )


@dataclass(frozen=True)
class CommandRun:
    code: int
    standard_output: str
    standard_error: str


def run_command(client, capsys, arguments, caller_pane=""):
    code = main(arguments, build_context(client, caller_pane))
    captured = capsys.readouterr()
    return CommandRun(code, captured.out, captured.err)


def result_of(output):
    return json.loads(output)["result"]


class TestList:
    def test_lists_the_panes_of_all_windows(self, tmux_client, capsys):
        add_window(tmux_client, "second")
        run = run_command(tmux_client, capsys, ["list"])
        assert run.code == 0
        names = {item["window_name"] for item in result_of(run.standard_output)}
        assert names == {"first", "second"}

    def test_a_pane_has_the_described_fields(self, tmux_client, capsys):
        run = run_command(tmux_client, capsys, ["list"])
        item = result_of(run.standard_output)[0]
        assert set(item) == {
            "session",
            "window",
            "window_name",
            "pane_id",
            "pane",
            "active",
            "directory",
            "command",
            "state",
            "kind",
            "name",
        }

    def test_panel_panes_are_hidden(self, tmux_client, capsys):
        pane = first_pane_of_window(tmux_client, "first")
        tmux_client.run("set-option", "-p", "-t", pane.pane_identifier, "@sidepanel_panel", "1")
        run = run_command(tmux_client, capsys, ["list"])
        assert result_of(run.standard_output) == []

    def test_agents_only_leaves_out_plain_panes(self, tmux_client, capsys):
        run = run_command(tmux_client, capsys, ["list", "--agents"])
        assert result_of(run.standard_output) == []


class TestCurrentAndGet:
    def test_current_is_the_pane_of_the_caller(self, tmux_client, capsys):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        run = run_command(tmux_client, capsys, ["current"], caller_pane=pane.pane_identifier)
        assert result_of(run.standard_output)["pane_id"] == pane.pane_identifier

    def test_current_outside_tmux_is_an_error_with_a_code(self, tmux_client, capsys):
        run = run_command(tmux_client, capsys, ["current"])
        assert run.code == 1
        assert run.standard_output == ""
        assert json.loads(run.standard_error)["error"]["code"] == "not_in_tmux"

    def test_get_finds_a_pane_by_its_identifier(self, tmux_client, capsys):
        pane = first_pane_of_window(tmux_client, "first")
        run = run_command(tmux_client, capsys, ["get", pane.pane_identifier])
        assert result_of(run.standard_output)["window_name"] == "first"

    def test_get_of_an_unknown_pane_is_an_error_with_a_code(self, tmux_client, capsys):
        run = run_command(tmux_client, capsys, ["get", "%999"])
        assert run.code == 1
        assert json.loads(run.standard_error)["error"]["code"] == "pane_not_found"
