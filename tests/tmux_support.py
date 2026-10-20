"""Helpers that start tmux servers for tests. Every server has its own socket, never the user's."""

import shutil
import time
from pathlib import Path

from tmux_sidepanel.tmux_client import TmuxClient

SLEEP_COMMAND = "sleep 600"
WAIT_SECONDS = 5


def tmux_is_installed():
    return shutil.which("tmux") is not None


def start_server(socket_directory):
    """Start a detached server with one session 'main' and one window 'first'."""
    client = TmuxClient(str(Path(socket_directory) / "tmux.sock"))
    client.run(
        "new-session", "-d", "-s", "main", "-n", "first", "-x", "120", "-y", "30", SLEEP_COMMAND
    )
    return client


def add_window(client, name, command=SLEEP_COMMAND):
    client.run("new-window", "-d", "-n", name, command)


def split_pane(client, window_name, command=SLEEP_COMMAND):
    client.run("split-window", "-d", "-t", f"main:{window_name}", command)


def install_fake_agent(directory):
    """A program named claude that only sleeps, so a pane can run something with an agent's name."""
    program = Path(directory) / "claude"
    shutil.copy(shutil.which("sleep"), program)
    return program


def panes_of_window(client, window_name):
    return list(filter(lambda pane: pane.window_name == window_name, client.list_panes()))


def first_pane_of_window(client, window_name):
    return panes_of_window(client, window_name)[0]


def current_command_of(client, pane_identifier):
    return client.display(pane_identifier, "#{pane_current_command}")


def wait_for_command(client, pane_identifier, command):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline and current_command_of(client, pane_identifier) != command:
        time.sleep(0.05)
