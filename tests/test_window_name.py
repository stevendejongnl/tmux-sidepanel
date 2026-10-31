"""Naming a tmux window after the session of its agent, or after its repository."""

import pytest

from tests.tmux_support import first_pane_of_window, tmux_is_installed
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.window_name import (
    MAXIMUM_NAME_LENGTH,
    chosen_name,
    name_window,
    repository_name,
)

needs_tmux = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


class TestRepositoryName:
    def test_a_folder_inside_a_repository_gives_the_name_of_the_repository(self, tmp_path):
        inner = tmp_path / "shop-api" / "src" / "orders"
        inner.mkdir(parents=True)
        (tmp_path / "shop-api" / ".git").mkdir()
        assert repository_name(str(inner)) == "shop-api"

    def test_a_worktree_has_a_git_file(self, tmp_path):
        (tmp_path / "shop-api").mkdir()
        (tmp_path / "shop-api" / ".git").write_text("gitdir: elsewhere\n")
        assert repository_name(str(tmp_path / "shop-api")) == "shop-api"

    def test_a_folder_outside_a_repository_gives_its_own_name(self, tmp_path):
        folder = tmp_path / "notes"
        folder.mkdir()
        assert repository_name(str(folder)) == "notes"

    def test_the_root_has_no_name(self):
        assert repository_name("/") == ""


class TestChosenName:
    def test_the_title_of_the_session_goes_first(self):
        assert chosen_name({"session_title": "fix retry", "cwd": "/srv/shop"}, "/srv/x") == (
            "fix retry"
        )

    def test_without_a_title_it_is_the_directory_of_the_payload(self):
        assert chosen_name({"cwd": "/srv/shop"}, "/srv/other") == "shop"

    def test_without_a_payload_it_is_the_directory_of_the_pane(self):
        assert chosen_name({}, "/srv/other") == "other"

    @pytest.mark.parametrize("title", ["", "   ", None, 7])
    def test_a_title_without_text_does_not_count(self, title):
        assert chosen_name({"session_title": title, "cwd": "/srv/shop"}, "") == "shop"

    def test_a_format_of_tmux_loses_its_hash(self):
        assert chosen_name({"session_title": "#(touch x) #[fg=red]"}, "") == "(touch x) [fg=red]"

    def test_control_characters_are_made_safe_and_a_long_title_is_clipped(self):
        name = chosen_name({"session_title": "a\x1bb" + "c" * 200}, "")
        assert name.startswith("a?b")
        assert len(name) == MAXIMUM_NAME_LENGTH


@needs_tmux
class TestNameWindow:
    def automatic_pane(self, client):
        pane = first_pane_of_window(client, "first")
        client.run("set-option", "-w", "-t", pane.window_identifier, "automatic-rename", "on")
        return self.reload(client, pane)

    def reload(self, client, pane):
        return find_pane(client.list_panes(), pane.pane_identifier)

    def test_an_automatic_name_is_replaced(self, tmux_client):
        pane = self.automatic_pane(tmux_client)
        name_window(tmux_client, pane, "shop-api")
        assert tmux_client.display(pane.pane_identifier, "#{window_name}") == "shop-api"

    def test_a_name_that_you_chose_is_kept(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        tmux_client.run("rename-window", "-t", pane.window_identifier, "mine")
        name_window(tmux_client, self.reload(tmux_client, pane), "shop-api")
        assert tmux_client.display(pane.pane_identifier, "#{window_name}") == "mine"

    def test_a_later_title_replaces_the_name_the_plugin_gave(self, tmux_client):
        pane = self.automatic_pane(tmux_client)
        name_window(tmux_client, pane, "shop-api")
        name_window(tmux_client, self.reload(tmux_client, pane), "fix retry")
        assert tmux_client.display(pane.pane_identifier, "#{window_name}") == "fix retry"

    def test_a_name_you_chose_after_the_plugin_is_kept(self, tmux_client):
        pane = self.automatic_pane(tmux_client)
        name_window(tmux_client, pane, "shop-api")
        tmux_client.run("rename-window", "-t", pane.window_identifier, "mine")
        name_window(tmux_client, self.reload(tmux_client, pane), "fix retry")
        assert tmux_client.display(pane.pane_identifier, "#{window_name}") == "mine"

    def test_a_name_that_starts_with_a_dash_is_not_read_as_a_flag(self, tmux_client):
        pane = self.automatic_pane(tmux_client)
        name_window(tmux_client, pane, "-t")
        assert tmux_client.display(pane.pane_identifier, "#{window_name}") == "-t"

    def test_a_directory_named_like_a_command_never_runs(self, tmux_client, tmp_path):
        marker = tmp_path / "ran"
        pane = self.automatic_pane(tmux_client)
        name_window(tmux_client, pane, chosen_name({"session_title": f"#(touch {marker})"}, ""))
        tmux_client.run("list-windows", "-a", "-F", "#{window_name}")
        tmux_client.run("display-message", "-p", "-t", pane.pane_identifier, "#W")
        assert not marker.exists()
