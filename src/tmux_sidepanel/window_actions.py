"""Moving around in tmux: jumping to a pane, opening a folder, running a command in a new window."""

import os
from contextlib import suppress
from pathlib import PurePosixPath

from tmux_sidepanel.action_outcome import ActionOutcome, done
from tmux_sidepanel.tmux_client import TmuxClient, TmuxError

WINDOW_NAME_LIMIT = 24


def jump_to_pane(client: TmuxClient, pane_identifier: str) -> None:
    """Show the pane: its session, its window and the pane itself."""
    with suppress(TmuxError):  # with no client attached there is no session to switch
        client.run("switch-client", "-t", pane_identifier)
    client.run("select-window", "-t", pane_identifier)
    client.run("select-pane", "-t", pane_identifier)


def open_directory(client: TmuxClient, directory: str) -> ActionOutcome:
    if not directory or not os.path.isdir(directory):
        return done("no directory for this row")
    client.run("new-window", "-c", directory)
    return done(f"opened {PurePosixPath(directory).name} in new window")


def keep_open_command(command: str) -> str:
    """A shell command that, when it fails, says so and waits, so the window does not vanish."""
    report = 'printf "\\nexited with %s - press enter\\n" "$rc"; read -r _'
    return f'{command}; rc=$?; if [ "$rc" -ne 0 ]; then {report}; fi'


def open_command_window(
    client: TmuxClient, name: str, shell_command: str, directory: str = ""
) -> ActionOutcome:
    short_name = name[:WINDOW_NAME_LIMIT]
    folder_arguments = ["-c", directory] if directory else []
    client.run("new-window", "-n", short_name, *folder_arguments, keep_open_command(shell_command))
    return done(f"opened {short_name}")
