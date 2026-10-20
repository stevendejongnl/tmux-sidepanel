"""What a command of the command line needs from its surroundings, so a test can replace it."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from tmux_sidepanel.application import Application
from tmux_sidepanel.configuration import (
    Configuration,
    find_configuration_path,
    load_configuration,
)
from tmux_sidepanel.tmux_client import TmuxClient

PACKAGE_SOURCE_DIRECTORY = Path(__file__).resolve().parents[1]


def load_default_configuration() -> Configuration:
    return load_configuration(find_configuration_path())


def show_panel_screen(application: Application) -> None:
    from tmux_sidepanel.panel_screen import run_panel

    run_panel(application)


@dataclass(frozen=True)
class CommandContext:
    environment: Mapping[str, str]
    standard_input: TextIO
    client: TmuxClient
    agent_names: Callable[[], tuple[str, ...]]
    source_directory: Path = PACKAGE_SOURCE_DIRECTORY
    load_configuration: Callable[[], Configuration] = load_default_configuration
    run_panel: Callable[[Application], None] = show_panel_screen
