"""The tmux client, against a tmux server of its own."""

import pytest

from tests.tmux_support import add_window, split_pane, tmux_is_installed, wait_for_command
from tmux_sidepanel.options import (
    OPTION_SESSION_STATE,
    OPTION_STATE,
    OPTION_WINDOW_STATE,
    option_expression,
)
from tmux_sidepanel.tmux_client import TmuxClient, TmuxError

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def first_pane(client):
    return client.list_panes()[0]


class TestListPanes:
    def test_lists_the_pane_of_the_new_session(self, tmux_client):
        wait_for_command(tmux_client, first_pane(tmux_client).pane_identifier, "sleep")
        pane = first_pane(tmux_client)
        assert pane.session_name == "main"
        assert pane.window_name == "first"
        assert pane.current_command == "sleep"

    def test_the_identifiers_carry_their_tmux_prefixes(self, tmux_client):
        pane = first_pane(tmux_client)
        assert pane.session_identifier.startswith("$")
        assert pane.window_identifier.startswith("@")
        assert pane.pane_identifier.startswith("%")

    def test_lists_every_pane_of_every_window(self, tmux_client):
        add_window(tmux_client, "second")
        split_pane(tmux_client, "second")
        names = sorted(pane.window_name for pane in tmux_client.list_panes())
        assert names == ["first", "second", "second"]

    def test_a_new_pane_has_no_agent_options(self, tmux_client):
        pane = first_pane(tmux_client)
        assert (pane.agent_state, pane.agent_kind, pane.agent_subagents) == ("", "", "")
        assert pane.is_panel is False


class TestPaneOptions:
    def test_writes_and_reads_a_pane_option(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, "working")
        assert first_pane(tmux_client).agent_state == "working"

    def test_an_empty_value_removes_the_option(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, "working")
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, "")
        assert first_pane(tmux_client).agent_state == ""

    def test_removing_an_option_that_is_not_set_is_fine(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, "")
        assert first_pane(tmux_client).agent_state == ""

    @pytest.mark.parametrize("value", ["two words", "-starts-with-a-dash", "semi;colon", "$dollar"])
    def test_stores_awkward_values_unchanged(self, tmux_client, value):
        pane = first_pane(tmux_client)
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, value)
        assert first_pane(tmux_client).agent_state == value


class TestWindowAndSessionOptions:
    def test_writes_a_window_option(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_window_option(pane.window_identifier, OPTION_WINDOW_STATE, "blocked")
        expression = option_expression(OPTION_WINDOW_STATE)
        assert tmux_client.display(pane.pane_identifier, expression) == "blocked"

    def test_writes_a_session_option(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_session_option(pane.session_identifier, OPTION_SESSION_STATE, "done")
        expression = option_expression(OPTION_SESSION_STATE)
        assert tmux_client.display(pane.pane_identifier, expression) == "done"

    def test_an_empty_value_removes_them(self, tmux_client):
        pane = first_pane(tmux_client)
        tmux_client.write_window_option(pane.window_identifier, OPTION_WINDOW_STATE, "blocked")
        tmux_client.write_window_option(pane.window_identifier, OPTION_WINDOW_STATE, "")
        expression = option_expression(OPTION_WINDOW_STATE)
        assert tmux_client.display(pane.pane_identifier, expression) == ""


def test_display_reads_a_format_of_a_pane(tmux_client):
    pane = first_pane(tmux_client)
    assert tmux_client.display(pane.pane_identifier, "#{window_id}") == pane.window_identifier


class TestErrors:
    def test_an_unknown_command_raises_with_the_tmux_message(self, tmux_client):
        with pytest.raises(TmuxError, match="no-such-command"):
            tmux_client.run("no-such-command")

    def test_a_missing_pane_raises(self, tmux_client):
        with pytest.raises(TmuxError, match="%999"):
            tmux_client.write_pane_option("%999", OPTION_STATE, "working")

    def test_a_server_that_is_not_running_raises(self, tmp_path):
        client = TmuxClient(str(tmp_path / "nothing.sock"))
        with pytest.raises(TmuxError):
            client.list_panes()


class TestIsolation:
    def test_the_environment_of_another_server_is_ignored(self, tmux_client, monkeypatch):
        monkeypatch.setenv("TMUX", "not-a-server,1,0")
        monkeypatch.setenv("TMUX_PANE", "%999")
        assert first_pane(tmux_client).session_name == "main"


class TestStopServer:
    def test_stops_the_server(self, tmux_client):
        tmux_client.stop_server()
        with pytest.raises(TmuxError):
            tmux_client.list_panes()

    def test_stopping_twice_is_fine(self, tmux_client):
        tmux_client.stop_server()
        tmux_client.stop_server()


class TestConfigurationFile:
    def test_the_command_line_names_the_file_when_there_is_one(self):
        client = TmuxClient("/run/some.sock", "/dev/null")
        assert client.command_line(("list-panes",)) == [
            "tmux",
            "-f",
            "/dev/null",
            "-S",
            "/run/some.sock",
            "list-panes",
        ]

    def test_the_command_line_has_no_file_by_default(self):
        assert "-f" not in TmuxClient("/run/some.sock").command_line(("list-panes",))

    def test_a_server_reads_the_file_it_was_given(self, tmp_path):
        configuration = tmp_path / "tmux.conf"
        configuration.write_text("set -g @from_configuration yes\n")
        client = TmuxClient(str(tmp_path / "tmux.sock"), str(configuration))
        try:
            client.run("new-session", "-d", "-s", "main", "sleep 30")
            assert client.run("show-option", "-gv", "@from_configuration").strip() == "yes"
        finally:
            client.stop_server()
