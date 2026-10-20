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


def split_new_pane(client, capsys, *extra):
    run = run_command(client, capsys, ["pane", "split", "--target", first_pane_id(client), *extra])
    return result_of(run.standard_output)


def first_pane_id(client):
    return first_pane_of_window(client, "first").pane_identifier


def pane_ids(client):
    return {pane.pane_identifier for pane in client.list_panes()}


class TestPaneSplit:
    def test_splits_next_to_the_target_and_describes_the_new_pane(self, tmux_client, capsys):
        before = pane_ids(tmux_client)
        described = split_new_pane(tmux_client, capsys)
        assert described["pane_id"] in pane_ids(tmux_client) - before
        assert described["window_name"] == "first"

    def test_the_focus_stays_where_it_was(self, tmux_client, capsys):
        described = split_new_pane(tmux_client, capsys)
        assert described["active"] is False

    def test_the_focus_can_move_to_the_new_pane(self, tmux_client, capsys):
        described = split_new_pane(tmux_client, capsys, "--focus")
        assert described["active"] is True

    def test_the_new_pane_can_be_below(self, tmux_client, capsys):
        described = split_new_pane(tmux_client, capsys, "--direction", "down")
        top = tmux_client.display(first_pane_id(tmux_client), "#{pane_top}")
        assert tmux_client.display(described["pane_id"], "#{pane_top}") != top

    def test_the_new_pane_can_start_in_a_directory(self, tmux_client, capsys, tmp_path):
        described = split_new_pane(tmux_client, capsys, "--directory", str(tmp_path))
        assert described["directory"] == str(tmp_path)

    def test_without_a_target_it_splits_the_pane_of_the_caller(self, tmux_client, capsys):
        caller = first_pane_id(tmux_client)
        run = run_command(tmux_client, capsys, ["pane", "split"], caller_pane=caller)
        assert run.code == 0


@pytest.fixture
def shell_pane(tmux_client, capsys):
    return split_new_pane(tmux_client, capsys)["pane_id"]


def wait_for_text(tmux_client, capsys, pane, text):
    arguments = ["pane", "wait-output", pane, "--match", text, "--timeout", "10000"]
    return run_command(tmux_client, capsys, arguments)


class TestPaneRun:
    def test_runs_the_command_in_the_pane(self, tmux_client, capsys, shell_pane):
        run = run_command(tmux_client, capsys, ["pane", "run", shell_pane, "echo $((20+22))"])
        assert result_of(run.standard_output) == {"pane_id": shell_pane, "queued": True}
        assert wait_for_text(tmux_client, capsys, shell_pane, "42").code == 0

    def test_an_unknown_pane_is_an_error(self, tmux_client, capsys):
        run = run_command(tmux_client, capsys, ["pane", "run", "%999", "ls"])
        assert json.loads(run.standard_error)["error"]["code"] == "pane_not_found"


class TestPaneRead:
    def print_sum(self, tmux_client, capsys, pane):
        run_command(tmux_client, capsys, ["pane", "run", pane, "echo $((30+12))"])
        wait_for_text(tmux_client, capsys, pane, "42")

    def test_reads_the_text_of_the_pane(self, tmux_client, capsys, shell_pane):
        self.print_sum(tmux_client, capsys, shell_pane)
        run = run_command(tmux_client, capsys, ["pane", "read", shell_pane])
        assert "42" in result_of(run.standard_output)["text"]

    def test_the_number_of_lines_is_limited(self, tmux_client, capsys, shell_pane):
        self.print_sum(tmux_client, capsys, shell_pane)
        run = run_command(tmux_client, capsys, ["pane", "read", shell_pane, "--lines", "2"])
        assert len(result_of(run.standard_output)["text"].split("\n")) <= 2

    @pytest.mark.parametrize("source", ["visible", "recent", "recent-unwrapped"])
    def test_every_source_works(self, tmux_client, capsys, shell_pane, source):
        self.print_sum(tmux_client, capsys, shell_pane)
        run = run_command(tmux_client, capsys, ["pane", "read", shell_pane, "--source", source])
        assert "42" in result_of(run.standard_output)["text"]


class TestPaneWaitOutput:
    def test_a_regex_can_be_matched(self, tmux_client, capsys, shell_pane):
        run_command(tmux_client, capsys, ["pane", "run", shell_pane, "echo $((50+7))"])
        arguments = ["pane", "wait-output", shell_pane, "--regex", "^5[0-9]$", "--timeout", "10000"]
        assert run_command(tmux_client, capsys, arguments).code == 0

    def test_a_timeout_is_an_error_with_a_code(self, tmux_client, capsys, shell_pane):
        arguments = [
            "pane",
            "wait-output",
            shell_pane,
            "--match",
            "never-printed",
            "--timeout",
            "300",
        ]
        run = run_command(tmux_client, capsys, arguments)
        assert run.code == 1
        assert json.loads(run.standard_error)["error"]["code"] == "timeout"

    def test_it_needs_something_to_match(self, tmux_client, capsys, shell_pane):
        run = run_command(tmux_client, capsys, ["pane", "wait-output", shell_pane])
        assert json.loads(run.standard_error)["error"]["code"] == "bad_arguments"

    def test_a_broken_regex_is_reported(self, tmux_client, capsys, shell_pane):
        run = run_command(tmux_client, capsys, ["pane", "wait-output", shell_pane, "--regex", "("])
        assert json.loads(run.standard_error)["error"]["code"] == "bad_arguments"


class TestPaneClose:
    def test_closes_the_pane(self, tmux_client, capsys, shell_pane):
        run = run_command(tmux_client, capsys, ["pane", "close", shell_pane])
        assert result_of(run.standard_output) == {"pane_id": shell_pane, "closed": True}
        assert shell_pane not in pane_ids(tmux_client)

    def test_the_pane_of_the_caller_is_never_closed(self, tmux_client, capsys, shell_pane):
        run = run_command(
            tmux_client, capsys, ["pane", "close", shell_pane], caller_pane=shell_pane
        )
        assert json.loads(run.standard_error)["error"]["code"] == "own_pane"
        assert shell_pane in pane_ids(tmux_client)
