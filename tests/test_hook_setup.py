"""The tmux hooks of the plugin: where they go, that they repeat safely, that they run."""

import shutil
import time
from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT
from tests.tmux_support import panes_of_window, split_pane, tmux_is_installed
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.hook_setup import (
    HOOK_INDEX_BASE,
    hook_installations,
    install_hooks,
    remove_hooks,
)
from tmux_sidepanel.options import OPTION_STATE

SOURCE_DIRECTORY = PROJECT_ROOT / "src"
needs_tmux = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def hooks_listing(client):
    return client.run("show-hooks", "-g")


def stored_state(client, pane):
    return find_pane(client.list_panes(), pane.pane_identifier).agent_state


def wait_for_stored_state(client, pane, state):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and stored_state(client, pane) != state:
        time.sleep(0.05)


class TestInstallations:
    def installations(self, source=Path("/opt/some place/src")):
        return hook_installations(source)

    def test_covers_the_expected_hooks(self):
        names = [installation.hook_name for installation in self.installations()]
        assert names == [
            "after-select-pane",
            "after-select-window",
            "client-session-changed",
            "client-attached",
        ]

    def test_every_index_is_unique_and_reserved_for_the_plugin(self):
        indexes = [installation.index for installation in self.installations()]
        assert len(set(indexes)) == len(indexes)
        assert min(indexes) >= HOOK_INDEX_BASE

    def tmux_commands(self):
        return [installation.tmux_command for installation in self.installations()]

    def test_the_focus_hooks_tell_the_command_which_pane(self):
        focus_commands = list(filter(lambda command: "hook seen" in command, self.tmux_commands()))
        assert len(focus_commands) == 3
        assert all("--pane #{pane_id}" in command for command in focus_commands)

    def test_a_hook_runs_in_the_background(self):
        commands = self.tmux_commands()
        assert all(command.startswith("run-shell -b ") for command in commands)

    def test_the_command_puts_the_source_directory_on_the_python_path(self):
        command = self.installations(Path("/opt/plugin/src"))[0].tmux_command
        assert "PYTHONPATH=/opt/plugin/src python3 -m tmux_sidepanel hook" in command

    def test_a_directory_with_a_space_is_quoted_for_the_shell(self):
        command = self.installations(Path("/opt/some place/src"))[0].tmux_command
        assert "PYTHONPATH='/opt/some place/src'" in command

    def test_a_hash_in_the_directory_is_escaped_for_tmux_formats(self):
        command = self.installations(Path("/opt/a#b/src"))[0].tmux_command
        assert "a##b" in command


@needs_tmux
class TestInstall:
    def test_adds_the_hooks_at_the_reserved_indexes(self, tmux_client):
        install_hooks(tmux_client, SOURCE_DIRECTORY)
        listing = hooks_listing(tmux_client)
        for installation in hook_installations(SOURCE_DIRECTORY):
            assert f"{installation.hook_name}[{installation.index}]" in listing

    def test_installing_twice_does_not_duplicate(self, tmux_client):
        install_hooks(tmux_client, SOURCE_DIRECTORY)
        install_hooks(tmux_client, SOURCE_DIRECTORY)
        assert hooks_listing(tmux_client).count("tmux_sidepanel hook seen") == 3

    def test_a_hook_of_the_user_is_kept(self, tmux_client):
        tmux_client.run("set-hook", "-g", "after-select-pane", "display-message mine")
        install_hooks(tmux_client, SOURCE_DIRECTORY)
        assert "display-message mine" in hooks_listing(tmux_client)

    def test_remove_deletes_only_the_hooks_of_the_plugin(self, tmux_client):
        tmux_client.run("set-hook", "-g", "after-select-pane", "display-message mine")
        install_hooks(tmux_client, SOURCE_DIRECTORY)
        remove_hooks(tmux_client)
        listing = hooks_listing(tmux_client)
        assert "tmux_sidepanel" not in listing
        assert "display-message mine" in listing

    def test_removing_when_nothing_is_installed_is_fine(self, tmux_client):
        remove_hooks(tmux_client)

    def test_the_installed_hook_runs_even_from_an_awkward_directory(self, tmux_client, tmp_path):
        awkward = tmp_path / "an odd 'name' #here" / "src"
        shutil.copytree(SOURCE_DIRECTORY, awkward, ignore=shutil.ignore_patterns("__pycache__"))
        install_hooks(tmux_client, awkward)
        split_pane(tmux_client, "first")
        first, second = panes_of_window(tmux_client, "first")[:2]
        # tmux fires the hook only when the selected pane really changes.
        tmux_client.run("select-pane", "-t", second.pane_identifier)
        tmux_client.write_pane_option(first.pane_identifier, OPTION_STATE, "done")
        tmux_client.run("select-pane", "-t", first.pane_identifier)
        wait_for_stored_state(tmux_client, first, "idle")
        assert stored_state(tmux_client, first) == "idle"
