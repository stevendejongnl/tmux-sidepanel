"""The panel on a real terminal: a pane of a test server runs it and receives keys."""

import shlex
import sys

import pytest

from tests.conftest import PROJECT_ROOT
from tests.tmux_support import (
    captured_text,
    first_pane_of_window,
    tmux_is_installed,
    wait_until,
    window_names,
)

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")

SOURCE = PROJECT_ROOT / "src"


def panel_command(configuration_folder):
    words = [
        "env",
        f"XDG_CONFIG_HOME={configuration_folder}",
        f"PYTHONPATH={SOURCE}",
        sys.executable,
        "-m",
        "tmux_sidepanel",
        "panel",
    ]
    return " ".join(map(shlex.quote, words))


@pytest.fixture
def panel_pane(tmux_client, tmp_path):
    tmux_client.run("new-window", "-d", "-n", "panel", panel_command(tmp_path))
    return first_pane_of_window(tmux_client, "panel").pane_identifier


def shows(tmux_client, pane, text):
    return wait_until(lambda: text in captured_text(tmux_client, pane))


def press(tmux_client, pane, *keys):
    tmux_client.run("send-keys", "-t", pane, *keys)


def test_it_draws_the_title_of_the_panes_section(tmux_client, panel_pane):
    assert shows(tmux_client, panel_pane, "PANES")


def test_enter_opens_the_menu_and_escape_closes_it(tmux_client, panel_pane):
    assert shows(tmux_client, panel_pane, "PANES")
    press(tmux_client, panel_pane, "Enter")
    assert shows(tmux_client, panel_pane, "go to pane")
    press(tmux_client, panel_pane, "Escape")
    assert wait_until(lambda: "go to pane" not in captured_text(tmux_client, panel_pane))


def test_the_key_of_an_action_runs_it_and_says_so(tmux_client, panel_pane):
    assert shows(tmux_client, panel_pane, "PANES")
    press(tmux_client, panel_pane, "Enter", "g")
    assert wait_until(lambda: "go to pane" not in captured_text(tmux_client, panel_pane))


def test_q_ends_the_panel(tmux_client, panel_pane):
    assert shows(tmux_client, panel_pane, "PANES")
    press(tmux_client, panel_pane, "q")
    assert wait_until(lambda: "panel" not in window_names(tmux_client))
