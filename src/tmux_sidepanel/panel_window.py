"""The panel pane of a window: open it, close it and move the focus to it and back."""

import shlex
from dataclasses import dataclass
from pathlib import Path

from tmux_sidepanel.options import OPTION_PANEL
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.tmux_client import TmuxClient

SIDE_FLAGS = {"left": ["-b"], "right": []}


@dataclass(frozen=True)
class PanelLayout:
    command: str  # the shell command that runs in the panel pane
    width: int
    position: str  # left or right


def panel_command(source_directory: Path) -> str:
    """The shell command that shows the panel, whatever the directory of the pane is."""
    return f"PYTHONPATH={shlex.quote(str(source_directory))} python3 -m tmux_sidepanel panel"


def is_panel_of_window(pane: PaneRecord, window_identifier: str) -> bool:
    return pane.is_panel and pane.window_identifier == window_identifier


def panels_of_window(client: TmuxClient, window_identifier: str) -> list[PaneRecord]:
    panes = client.list_panes()
    return list(filter(lambda pane: is_panel_of_window(pane, window_identifier), panes))


def open_panel(client: TmuxClient, window_identifier: str, layout: PanelLayout) -> str:
    """Split the whole height of the window, without taking the focus. Returns the new pane."""
    side = SIDE_FLAGS.get(layout.position, [])
    pane_identifier = client.run(
        "split-window",
        *["-d", "-h", "-f", *side, "-l", str(layout.width)],
        *["-t", window_identifier, "-P", "-F", "#{pane_id}", layout.command],
    ).strip()
    client.write_pane_option(pane_identifier, OPTION_PANEL, "1")
    return pane_identifier


def close_panel(client: TmuxClient, panel: PaneRecord) -> None:
    client.run("kill-pane", "-t", panel.pane_identifier)


def toggle_panel(client: TmuxClient, window_identifier: str, layout: PanelLayout) -> None:
    panels = panels_of_window(client, window_identifier)
    if not panels:
        open_panel(client, window_identifier, layout)
        return
    for panel in panels:
        close_panel(client, panel)


def ensure_panel(client: TmuxClient, window_identifier: str, layout: PanelLayout) -> None:
    """Open the panel when the window has none. A panel that is open is left alone."""
    if not panels_of_window(client, window_identifier):
        open_panel(client, window_identifier, layout)


def focus_panel(client: TmuxClient, window_identifier: str, layout: PanelLayout) -> None:
    """Move the focus into the panel, or back to the pane before it when it is already there."""
    panels = panels_of_window(client, window_identifier)
    if not panels:
        client.run("select-pane", "-t", open_panel(client, window_identifier, layout))
        return
    if panels[0].is_active:
        client.run("select-pane", "-l", "-t", window_identifier)
        return
    client.run("select-pane", "-t", panels[0].pane_identifier)
