"""Naming a tmux window after the session of its agent, or else after its repository.

A name that someone chose is never replaced. tmux turns ``automatic-rename`` off when a window
gets a name, so the plugin stores the name it gave to recognize its own work later.
"""

from pathlib import Path
from typing import Any

from tmux_sidepanel.options import OPTION_WINDOW_NAME, option_expression
from tmux_sidepanel.panel_layout import clip_text
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.terminal_text import sanitize_for_terminal
from tmux_sidepanel.tmux_client import TmuxClient

MAXIMUM_NAME_LENGTH = 30
GIT_ENTRY = ".git"  # a folder in a repository, a file in a worktree


def repository_name(directory: str) -> str:
    """The name of the repository that holds the directory, or else of the directory itself."""
    path = Path(directory)
    roots = filter(lambda folder: (folder / GIT_ENTRY).exists(), [path, *path.parents])
    return next(roots, path).name


def session_title(payload: dict[str, Any]) -> str:
    title = payload.get("session_title")
    return title.strip() if isinstance(title, str) else ""


def chosen_name(payload: dict[str, Any], pane_directory: str) -> str:
    """The name for the window. rename-window runs a format like #(command), so hashes go."""
    directory = str(payload.get("cwd") or pane_directory)
    name = session_title(payload) or repository_name(directory)
    return clip_text(sanitize_for_terminal(name).replace("#", "").strip(), MAXIMUM_NAME_LENGTH)


def may_rename(client: TmuxClient, pane: PaneRecord) -> bool:
    """True when nobody chose the name: tmux made it, or the plugin gave it."""
    window = pane.window_identifier
    if client.display(window, "#{automatic-rename}") == "1":
        return True
    return pane.window_name == client.display(window, option_expression(OPTION_WINDOW_NAME))


def name_window(client: TmuxClient, pane: PaneRecord, name: str) -> None:
    if not name or name == pane.window_name or not may_rename(client, pane):
        return
    client.run("rename-window", "-t", pane.window_identifier, "--", name)
    client.write_window_option(pane.window_identifier, OPTION_WINDOW_NAME, name)
