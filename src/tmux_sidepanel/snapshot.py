"""A snapshot: everything the panel needs to know at one moment, as plain data."""

from dataclasses import dataclass, field

from tmux_sidepanel.containers import Container
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.processes import Process


@dataclass(frozen=True)
class Snapshot:
    panes: list[PaneRecord]
    window_identifier: str  # the window the panel is in
    process_table: dict[int, Process] = field(default_factory=dict)
    containers: list[Container] = field(default_factory=list)
    process_directories: dict[int, str] = field(default_factory=dict)
    custom_outputs: dict[str, str] = field(default_factory=dict)
    home_directory: str = ""
