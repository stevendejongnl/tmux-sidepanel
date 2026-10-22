"""The Claude Code plugin layer: the manifest, the marketplace entry and the hooks file."""

import json
import re
from itertools import chain

import pytest

from tests.conftest import PROJECT_ROOT, run_command
from tests.tmux_support import tmux_is_installed
from tmux_sidepanel.command_line import HOOK_ACTIONS

MANIFEST_PATH = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = PROJECT_ROOT / ".claude-plugin" / "marketplace.json"
HOOKS_PATH = PROJECT_ROOT / "hooks" / "hooks.json"

ALLOWED_MANIFEST_KEYS = {
    "name",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
}

ACTION_BY_EVENT = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "PostToolUse": "working",
    "Notification": "notification",
    "Stop": "done",
    "SessionEnd": "clear",
    "SubagentStart": "sub-start",
    "SubagentStop": "sub-stop",
    "PreCompact": "compacting",
    "PostCompact": "compacted",
    "StopFailure": "failed",
}

COMMAND_PATTERN = re.compile(
    r'^PYTHONPATH="\$\{CLAUDE_PLUGIN_ROOT\}/src" '
    r"python3 -m tmux_sidepanel hook (?P<action>[a-z-]+)$"
)


def load_json(path):
    return json.loads(path.read_text())


def hook_commands(entry):
    return [hook["command"] for hook in entry["hooks"]]


def event_commands(event_name):
    entries = load_json(HOOKS_PATH)["hooks"][event_name]
    return list(chain.from_iterable(map(hook_commands, entries)))


def action_of(command):
    return COMMAND_PATTERN.match(command).group("action")


class TestManifest:
    def test_names_the_plugin(self):
        manifest = load_json(MANIFEST_PATH)
        assert manifest["name"] == "tmux-sidepanel"
        assert manifest["description"]

    def test_has_an_author(self):
        assert load_json(MANIFEST_PATH)["author"]["name"]

    def test_only_uses_known_keys(self):
        assert set(load_json(MANIFEST_PATH)) <= ALLOWED_MANIFEST_KEYS

    def test_has_no_version_because_releases_are_tags(self):
        assert "version" not in load_json(MANIFEST_PATH)


class TestMarketplace:
    def test_offers_this_plugin_from_the_root_of_the_repository(self):
        marketplace = load_json(MARKETPLACE_PATH)
        plugin = marketplace["plugins"][0]
        assert len(marketplace["plugins"]) == 1
        assert plugin["name"] == load_json(MANIFEST_PATH)["name"]
        assert plugin["source"] == "./"

    def test_has_an_owner(self):
        assert load_json(MARKETPLACE_PATH)["owner"]["name"]


class TestHooks:
    def test_covers_exactly_the_expected_events(self):
        assert set(load_json(HOOKS_PATH)["hooks"]) == set(ACTION_BY_EVENT)

    def test_never_gates_a_tool_call(self):
        assert "PreToolUse" not in load_json(HOOKS_PATH)["hooks"]

    @pytest.mark.parametrize("event_name", sorted(ACTION_BY_EVENT))
    def test_each_event_runs_one_command_with_the_right_action(self, event_name):
        commands = event_commands(event_name)
        assert len(commands) == 1
        assert action_of(commands[0]) == ACTION_BY_EVENT[event_name]

    @pytest.mark.parametrize("event_name", sorted(ACTION_BY_EVENT))
    def test_each_command_is_exactly_the_plain_form(self, event_name):
        assert COMMAND_PATTERN.match(event_commands(event_name)[0])

    def test_every_action_is_one_the_command_line_knows(self):
        assert set(ACTION_BY_EVENT.values()) <= set(HOOK_ACTIONS)

    @pytest.mark.parametrize("event_name", sorted(ACTION_BY_EVENT))
    def test_each_hook_is_a_short_command(self, event_name):
        hook = load_json(HOOKS_PATH)["hooks"][event_name][0]["hooks"][0]
        assert hook["type"] == "command"
        assert 1 <= hook["timeout"] <= 10


@pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")
def test_the_command_of_the_hooks_file_works_when_run_through_a_shell(default_server_environment):
    listing = ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{@sidepanel_state}"]
    pane = run_command(listing, **default_server_environment).stdout.split()[0]
    command = event_commands("UserPromptSubmit")[0]
    command = command.replace("${CLAUDE_PLUGIN_ROOT}", str(PROJECT_ROOT))
    overrides = {**default_server_environment, "TMUX_PANE": pane}
    result = run_command(["bash", "-c", command], directory=PROJECT_ROOT, **overrides)
    assert result.returncode == 0, result.stderr
    assert run_command(listing, **default_server_environment).stdout.split()[1] == "working"
