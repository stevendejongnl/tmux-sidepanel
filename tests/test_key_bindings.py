"""The keys of the prefix table that toggle and focus the panel."""

from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT
from tests.tmux_support import tmux_is_installed
from tmux_sidepanel.key_bindings import (
    binding_command,
    configured_key,
    install_key_bindings,
    remove_key_bindings,
    user_command_of_key,
)

SOURCE_DIRECTORY = PROJECT_ROOT / "src"
pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def bound_command(client, key):
    return user_command_of_key(client.run("list-keys", "-T", "prefix"), key)


class TestConfiguredKey:
    def test_the_defaults_are_s_and_f(self, tmux_client):
        assert configured_key(tmux_client, "toggle") == "S"
        assert configured_key(tmux_client, "focus") == "F"

    def test_an_option_of_the_user_replaces_the_default(self, tmux_client):
        tmux_client.run("set-option", "-g", "@sidepanel_toggle_key", "P")
        assert configured_key(tmux_client, "toggle") == "P"

    @pytest.mark.parametrize("value", ["off", "none"])
    def test_off_disables_the_key(self, tmux_client, value):
        tmux_client.run("set-option", "-g", "@sidepanel_focus_key", value)
        assert configured_key(tmux_client, "focus") == ""


class TestBindingCommand:
    def test_runs_the_command_of_the_plugin_for_the_window_of_the_key(self):
        command = binding_command(Path("/opt/some place/src"), "toggle")
        assert "tmux_sidepanel toggle --window #{window_id}" in command
        assert "'/opt/some place/src'" in command

    def test_the_hashes_of_the_directory_are_escaped_for_tmux(self):
        assert "/opt/a##b" in binding_command(Path("/opt/a#b"), "focus")


class TestParsing:
    LISTING = (
        "bind-key    -T prefix S       run-shell -b 'echo hi'\n"
        "bind-key -r -T prefix Up      select-pane -U\n"
        "bind-key    -T prefix s       choose-tree -Zs\n"
    )

    def test_finds_the_command_of_a_key(self):
        assert user_command_of_key(self.LISTING, "S") == "run-shell -b 'echo hi'"

    def test_a_key_with_flags_is_found(self):
        assert user_command_of_key(self.LISTING, "Up") == "select-pane -U"

    def test_the_case_of_the_key_matters(self):
        assert user_command_of_key(self.LISTING, "s") == "choose-tree -Zs"

    def test_an_unbound_key_has_no_command(self):
        assert user_command_of_key(self.LISTING, "Q") == ""


class TestInstall:
    def test_binds_the_default_keys(self, tmux_client):
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        assert "tmux_sidepanel toggle" in bound_command(tmux_client, "S")
        assert "tmux_sidepanel focus" in bound_command(tmux_client, "F")

    def test_binds_the_keys_of_the_options(self, tmux_client):
        tmux_client.run("set-option", "-g", "@sidepanel_toggle_key", "P")
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        assert "tmux_sidepanel toggle" in bound_command(tmux_client, "P")
        assert bound_command(tmux_client, "S") == ""

    def test_a_disabled_key_is_not_bound(self, tmux_client):
        tmux_client.run("set-option", "-g", "@sidepanel_focus_key", "off")
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        assert bound_command(tmux_client, "F") == ""

    def test_installing_again_changes_nothing(self, tmux_client):
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        first = tmux_client.run("list-keys", "-T", "prefix")
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        assert tmux_client.run("list-keys", "-T", "prefix") == first

    def test_a_key_that_the_user_uses_for_something_else_is_left_alone(self, tmux_client):
        tmux_client.run("bind-key", "-T", "prefix", "S", "display-message", "mine")
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        assert bound_command(tmux_client, "S") == "display-message mine"


class TestRemove:
    def test_removes_the_keys_that_it_installed(self, tmux_client):
        install_key_bindings(tmux_client, SOURCE_DIRECTORY)
        remove_key_bindings(tmux_client)
        assert bound_command(tmux_client, "S") == ""
        assert bound_command(tmux_client, "F") == ""

    def test_leaves_a_key_of_the_user_alone(self, tmux_client):
        tmux_client.run("bind-key", "-T", "prefix", "S", "display-message", "mine")
        remove_key_bindings(tmux_client)
        assert bound_command(tmux_client, "S") == "display-message mine"

    def test_removing_without_an_installation_is_fine(self, tmux_client):
        remove_key_bindings(tmux_client)
