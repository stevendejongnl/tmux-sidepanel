"""The command line: hooks run it with an action, a payload on standard input and TMUX_PANE."""

import io
import sys
from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT, run_command
from tests.tmux_support import add_window, first_pane_of_window, tmux_is_installed
from tmux_sidepanel.command_line import (
    HOOK_ACTIONS,
    CommandContext,
    main,
    parse_payload,
    read_payload,
)
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.tmux_client import TmuxClient

SOURCE_DIRECTORY = PROJECT_ROOT / "src"
needs_tmux = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


class TerminalInput(io.StringIO):
    def isatty(self):
        return True


def build_context(
    client, environment=None, text="", agent_names=("claude",), source_directory=SOURCE_DIRECTORY
):
    return CommandContext(
        environment=environment or {},
        standard_input=io.StringIO(text),
        client=client,
        agent_names=lambda: agent_names,
        source_directory=source_directory,
    )


def reload_pane(client, pane):
    return find_pane(client.list_panes(), pane.pane_identifier)


class TestPayload:
    def test_reads_an_object(self):
        assert parse_payload('{"agent_id": "aaa111"}') == {"agent_id": "aaa111"}

    @pytest.mark.parametrize("text", ["", "not json", "[1, 2]", '"text"', "42", "null"])
    def test_anything_else_gives_an_empty_payload(self, text):
        assert parse_payload(text) == {}

    def test_reads_from_a_stream(self):
        assert read_payload(io.StringIO('{"a": 1}')) == {"a": 1}

    def test_a_terminal_is_not_read(self):
        assert read_payload(TerminalInput('{"a": 1}')) == {}

    def test_an_enormous_payload_is_cut_and_ignored(self):
        assert read_payload(io.StringIO('{"a": "' + "x" * 2_000_000 + '"}')) == {}


class TestUsage:
    @pytest.mark.parametrize(
        "arguments",
        [[], ["bogus"], ["hook"], ["hook", "bogus"], ["hook", "working", "--unknown"]],
    )
    def test_a_usage_mistake_returns_one_never_two(self, arguments, capsys):
        assert main(arguments, build_context(TmuxClient())) == 1
        assert "usage" in capsys.readouterr().err.lower()

    @pytest.mark.parametrize("arguments", [["setup", "extra"], ["teardown", "--bogus"]])
    def test_setup_and_teardown_take_no_arguments(self, arguments):
        assert main(arguments, build_context(TmuxClient())) == 1

    def test_every_action_is_known(self):
        expected = {
            "working",
            "idle",
            "blocked",
            "done",
            "seen",
            "notification",
            "clear",
            "sub-start",
            "sub-stop",
            "reap",
        }
        assert set(HOOK_ACTIONS) == expected

    def test_without_a_pane_nothing_happens(self):
        assert main(["hook", "working"], build_context(TmuxClient())) == 0


@needs_tmux
class TestHook:
    def test_the_pane_comes_from_the_environment(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier})
        assert main(["hook", "working"], context) == 0
        assert reload_pane(tmux_client, pane).agent_state == "working"

    def test_a_pane_option_beats_the_environment(self, tmux_client):
        add_window(tmux_client, "second")
        first = first_pane_of_window(tmux_client, "first")
        second = first_pane_of_window(tmux_client, "second")
        context = build_context(tmux_client, {"TMUX_PANE": first.pane_identifier})
        main(["hook", "working", "--pane", second.pane_identifier], context)
        assert reload_pane(tmux_client, second).agent_state == "working"
        assert reload_pane(tmux_client, first).agent_state == ""

    def test_the_agent_kind_can_be_given(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier})
        main(["hook", "working", "--kind", "codex"], context)
        assert reload_pane(tmux_client, pane).agent_kind == "codex"

    def test_the_payload_comes_from_standard_input(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        payload = '{"agent_id": "aaa111", "agent_type": "Explore"}'
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier}, payload)
        main(["hook", "sub-start"], context)
        assert reload_pane(tmux_client, pane).agent_subagents == "aaa111:Explore"

    def test_a_notification_uses_its_type(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        payload = '{"notification_type": "permission_prompt"}'
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier}, payload)
        main(["hook", "notification"], context)
        assert reload_pane(tmux_client, pane).agent_state == "blocked"

    def test_a_broken_payload_does_not_stop_the_hook(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier}, "{broken")
        assert main(["hook", "working"], context) == 0
        assert reload_pane(tmux_client, pane).agent_state == "working"

    def test_reap_clears_a_pane_whose_agent_is_gone(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = build_context(tmux_client, {"TMUX_PANE": pane.pane_identifier})
        main(["hook", "working"], context)
        assert main(["hook", "reap"], context) == 0
        assert reload_pane(tmux_client, pane).agent_state == ""

    def test_reap_uses_the_agent_names_of_the_configuration(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = build_context(tmux_client, {}, agent_names=("sleep",))
        main(["hook", "working", "--pane", pane.pane_identifier], context)
        main(["hook", "reap"], context)
        assert reload_pane(tmux_client, pane).agent_state == "working"


class TestTmuxProblems:
    def test_a_tmux_failure_never_blocks_the_agent(self, tmp_path, capsys):
        client = TmuxClient(str(tmp_path / "nothing.sock"))
        context = build_context(client, {"TMUX_PANE": "%1"})
        assert main(["hook", "working"], context) == 0
        assert "tmux" in capsys.readouterr().err


class TestModule:
    def run_module(self, *arguments, **overrides):
        command = [sys.executable, "-m", "tmux_sidepanel", *arguments]
        return run_command(
            command, directory=PROJECT_ROOT, PYTHONPATH=str(PROJECT_ROOT / "src"), **overrides
        )

    def test_a_usage_mistake_exits_with_one(self):
        assert self.run_module("hook", "bogus").returncode == 1

    def test_a_hook_without_a_pane_exits_with_zero(self):
        assert self.run_module("hook", "working").returncode == 0

    def test_a_hook_outside_tmux_exits_with_zero(self):
        result = self.run_module("hook", "working", TMUX_PANE="%1")
        assert result.returncode == 0


@needs_tmux
class TestModuleWithRealTmux:
    def list_option(self, expression, overrides):
        command = ["tmux", "list-panes", "-a", "-F", expression]
        return run_command(command, **overrides).stdout.strip()

    def test_a_hook_run_as_a_module_changes_the_state_of_its_pane(self, default_server_environment):
        pane = self.list_option("#{pane_id}", default_server_environment)
        command = [sys.executable, "-m", "tmux_sidepanel", "hook", "working"]
        source = str(PROJECT_ROOT / "src")
        overrides = {**default_server_environment, "TMUX_PANE": pane, "PYTHONPATH": source}
        result = run_command(command, directory=PROJECT_ROOT, **overrides)
        assert result.returncode == 0, result.stderr
        state = self.list_option("#{@sidepanel_state}", default_server_environment)
        assert state == "working"
        window_state = self.list_option("#{@sidepanel_window_state}", default_server_environment)
        assert window_state == "working"


@needs_tmux
class TestSetup:
    def hooks(self, client):
        return client.run("show-hooks", "-g")

    def test_setup_installs_the_hooks(self, tmux_client):
        assert main(["setup"], build_context(tmux_client)) == 0
        assert "after-select-pane[9100]" in self.hooks(tmux_client)

    def test_teardown_removes_them(self, tmux_client):
        main(["setup"], build_context(tmux_client))
        assert main(["teardown"], build_context(tmux_client)) == 0
        assert "tmux_sidepanel" not in self.hooks(tmux_client)

    def test_setup_puts_the_given_source_directory_in_the_commands(self, tmux_client):
        context = build_context(tmux_client, source_directory=Path("/opt/plugin/src"))
        main(["setup"], context)
        assert "PYTHONPATH=/opt/plugin/src" in self.hooks(tmux_client)
