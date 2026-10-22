"""The command line: hooks run it with an action, a payload on standard input and TMUX_PANE."""

import io
import sys
from operator import attrgetter
from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT, run_command
from tests.tmux_support import add_window, first_pane_of_window, tmux_is_installed
from tmux_sidepanel.command_line import CommandContext, main
from tmux_sidepanel.configuration import (
    ConfigurationError,
    default_configuration,
    parse_configuration,
)
from tmux_sidepanel.hook_command import HOOK_ACTIONS, parse_payload, read_payload
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.tmux_client import TmuxClient

SOURCE_DIRECTORY = PROJECT_ROOT / "src"
needs_tmux = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


class TerminalInput(io.StringIO):
    def isatty(self):
        return True


def build_context(
    client,
    environment=None,
    text="",
    agent_names=("claude",),
    source_directory=SOURCE_DIRECTORY,
    **overrides,
):
    return CommandContext(
        environment=environment or {},
        standard_input=io.StringIO(text),
        client=client,
        agent_names=lambda: agent_names,
        source_directory=source_directory,
        **overrides,
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
            "compacting",
            "compacted",
            "failed",
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


HEAVY_MODULES = (
    "curses",
    "tmux_sidepanel.application",
    "tmux_sidepanel.command_line",
    "tmux_sidepanel.configuration",
)


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

    def test_a_hook_does_not_load_the_code_of_the_panel(self):
        code = (
            "import runpy, sys\n"
            "sys.argv = ['tmux_sidepanel', 'hook', 'working']\n"
            "try:\n"
            "    runpy.run_module('tmux_sidepanel', run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "print(sorted(name for name in sys.modules if name in HEAVY_MODULES))\n"
        ).replace("HEAVY_MODULES", repr(HEAVY_MODULES))
        command = [sys.executable, "-c", code]
        overrides = {"PYTHONPATH": str(PROJECT_ROOT / "src")}
        result = run_command(command, directory=PROJECT_ROOT, **overrides)
        assert result.stdout.strip() == "[]"

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

    def test_setup_binds_the_keys_of_the_panel(self, tmux_client):
        main(["setup"], build_context(tmux_client))
        keys = tmux_client.run("list-keys", "-T", "prefix")
        assert "tmux_sidepanel toggle" in keys
        assert "tmux_sidepanel focus" in keys

    def test_teardown_unbinds_them(self, tmux_client):
        main(["setup"], build_context(tmux_client))
        main(["teardown"], build_context(tmux_client))
        assert "tmux_sidepanel" not in tmux_client.run("list-keys", "-T", "prefix")


class ScreenRecorder:
    """Stands in for the terminal screen and keeps the application it was asked to show."""

    def __init__(self):
        self.applications = []

    def __call__(self, application):
        self.applications.append(application)


def broken_configuration():
    raise ConfigurationError("panel.width: must be a number")


@needs_tmux
class TestPanel:
    def test_the_screen_runs_for_the_window_of_the_panel_pane(self, tmux_client):
        add_window(tmux_client, "work")
        pane = first_pane_of_window(tmux_client, "work")
        recorder = ScreenRecorder()
        context = build_context(
            tmux_client,
            {"TMUX_PANE": pane.pane_identifier},
            load_configuration=default_configuration,
            run_panel=recorder,
        )
        assert main(["panel"], context) == 0
        assert recorder.applications[0].window_identifier == pane.window_identifier

    def test_the_pane_can_be_given_on_the_command_line(self, tmux_client):
        add_window(tmux_client, "work")
        pane = first_pane_of_window(tmux_client, "work")
        recorder = ScreenRecorder()
        context = build_context(
            tmux_client, load_configuration=default_configuration, run_panel=recorder
        )
        main(["panel", "--pane", pane.pane_identifier], context)
        assert recorder.applications[0].window_identifier == pane.window_identifier

    def test_without_a_pane_it_is_a_usage_error(self, tmux_client, capsys):
        recorder = ScreenRecorder()
        context = build_context(
            tmux_client, load_configuration=default_configuration, run_panel=recorder
        )
        assert main(["panel"], context) == 1
        assert "pane" in capsys.readouterr().err
        assert recorder.applications == []

    def test_a_broken_configuration_is_reported_and_nothing_is_drawn(self, tmux_client, capsys):
        recorder = ScreenRecorder()
        context = build_context(
            tmux_client,
            {"TMUX_PANE": "%1"},
            load_configuration=broken_configuration,
            run_panel=recorder,
        )
        assert main(["panel"], context) == 1
        assert "panel.width" in capsys.readouterr().err
        assert recorder.applications == []


def panel_configuration():
    return parse_configuration('[panel]\nwidth = 25\nposition = "right"\n')


def panel_panes_of(client, window_name):
    panels = filter(attrgetter("is_panel"), client.list_panes())
    return list(filter(lambda pane: pane.window_name == window_name, panels))


@needs_tmux
class TestToggleAndFocus:
    def toggle_context(self, client, environment=None):
        return build_context(client, environment, load_configuration=panel_configuration)

    def test_toggle_opens_the_panel_in_the_given_window(self, tmux_client):
        window = first_pane_of_window(tmux_client, "first").window_identifier
        assert main(["toggle", "--window", window], self.toggle_context(tmux_client)) == 0
        panel = panel_panes_of(tmux_client, "first")[0]
        assert tmux_client.display(panel.pane_identifier, "#{pane_width}") == "25"
        assert tmux_client.display(panel.pane_identifier, "#{pane_left}") != "0"

    def test_the_panel_pane_runs_the_panel_command_of_this_plugin(self, tmux_client):
        window = first_pane_of_window(tmux_client, "first").window_identifier
        main(["toggle", "--window", window], self.toggle_context(tmux_client))
        panel = panel_panes_of(tmux_client, "first")[0]
        command = tmux_client.display(panel.pane_identifier, "#{pane_start_command}")
        assert "tmux_sidepanel panel" in command
        assert str(SOURCE_DIRECTORY) in command

    def test_toggle_twice_closes_it(self, tmux_client):
        window = first_pane_of_window(tmux_client, "first").window_identifier
        context = self.toggle_context(tmux_client)
        main(["toggle", "--window", window], context)
        main(["toggle", "--window", window], context)
        assert panel_panes_of(tmux_client, "first") == []

    def test_the_window_defaults_to_the_window_of_the_pane_of_the_caller(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        context = self.toggle_context(tmux_client, {"TMUX_PANE": pane.pane_identifier})
        main(["toggle"], context)
        assert len(panel_panes_of(tmux_client, "first")) == 1

    def test_focus_moves_into_the_panel(self, tmux_client):
        window = first_pane_of_window(tmux_client, "first").window_identifier
        main(["focus", "--window", window], self.toggle_context(tmux_client))
        active = next(filter(attrgetter("is_active"), tmux_client.list_panes()))
        assert active.is_panel

    def test_without_a_window_it_is_a_usage_error(self, tmux_client, capsys):
        assert main(["toggle"], self.toggle_context(tmux_client)) == 1
        assert "window" in capsys.readouterr().err
