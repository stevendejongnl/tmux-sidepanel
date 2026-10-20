"""Helpers that start tmux servers for tests. Every server has its own socket, never the user's."""

import shutil
import time
from collections.abc import Callable
from pathlib import Path

from tmux_sidepanel.tmux_client import TmuxClient, TmuxError

SLEEP_COMMAND = "sleep 600"
WAIT_SECONDS = 5


NO_CONFIGURATION = "/dev/null"  # a test server must not read the configuration of the user


def tmux_is_installed():
    return shutil.which("tmux") is not None


def start_server(socket_directory):
    """Start a detached server with one session 'main' and one window 'first'."""
    client = TmuxClient(str(Path(socket_directory) / "tmux.sock"), NO_CONFIGURATION)
    try:
        client.run(
            "new-session", "-d", "-s", "main", "-n", "first", "-x", "120", "-y", "30", SLEEP_COMMAND
        )
    except TmuxError:
        client.stop_server()  # a server that starts too slowly must not outlive the test
        raise
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


def install_echo_agent(directory):
    """A program named claude that echoes what it receives, so a test can see the keys it got."""
    program = Path(directory) / "claude"
    shutil.copy(shutil.which("cat"), program)
    return program


def wait_until(condition: Callable[[], bool], seconds=WAIT_SECONDS):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not condition():
        time.sleep(0.05)
    return condition()


def window_names(client):
    return sorted({pane.window_name for pane in client.list_panes()})


def first_pane_of_window_starting(client, prefix):
    names = filter(lambda name: name.startswith(prefix), window_names(client))
    return first_pane_of_window(client, next(names))


def pane_identifiers(client):
    return [pane.pane_identifier for pane in client.list_panes()]


def captured_text(client, pane_identifier):
    return client.run("capture-pane", "-p", "-t", pane_identifier)


def install_argument_agent(directory):
    """A program named claude that prints how it was started and then stays alive for a while."""
    program = Path(directory) / "claude"
    program.write_text(
        '#!/bin/sh\necho "arguments: $* configuration: $CLAUDE_CONFIG_DIR"\nsleep 30\n'
    )
    program.chmod(0o755)
    return program
