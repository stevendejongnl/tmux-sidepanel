"""The hooks of tmux that the plugin installs.

Each hook gets a fixed place in the array of its hook, so installing again replaces the entry
instead of adding a second one, and the hooks of the user next to it are never touched.
"""

import shlex
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from tmux_sidepanel.tmux_client import TmuxClient, TmuxError
from tmux_sidepanel.tmux_syntax import escape_for_format, quote_for_tmux

HOOK_INDEX_BASE = 9100


@dataclass(frozen=True)
class HookDefinition:
    hook_name: str
    arguments: str


@dataclass(frozen=True)
class HookInstallation:
    hook_name: str
    index: int
    tmux_command: str

    @property
    def target(self) -> str:
        return f"{self.hook_name}[{self.index}]"


HOOK_DEFINITIONS = (
    HookDefinition("after-select-pane", "hook seen --pane #{pane_id}"),
    HookDefinition("after-select-window", "hook seen --pane #{pane_id}"),
    HookDefinition("client-session-changed", "hook seen --pane #{pane_id}"),
    HookDefinition("client-attached", "hook reap"),
)


def shell_command(source_directory: Path, arguments: str) -> str:
    """The command a hook runs. The directory is quoted for the shell, and its hashes for tmux."""
    quoted_directory = escape_for_format(shlex.quote(str(source_directory)))
    return f"PYTHONPATH={quoted_directory} python3 -m tmux_sidepanel {arguments}"


def installation_for(
    definition: HookDefinition, index: int, source_directory: Path
) -> HookInstallation:
    command = shell_command(source_directory, definition.arguments)
    return HookInstallation(definition.hook_name, index, "run-shell -b " + quote_for_tmux(command))


def hook_installations(source_directory: Path) -> list[HookInstallation]:
    return [
        installation_for(definition, HOOK_INDEX_BASE + position, source_directory)
        for position, definition in enumerate(HOOK_DEFINITIONS)
    ]


def install_hook(client: TmuxClient, installation: HookInstallation) -> None:
    client.run("set-hook", "-g", installation.target, installation.tmux_command)


def install_hooks(client: TmuxClient, source_directory: Path) -> None:
    for installation in hook_installations(source_directory):
        install_hook(client, installation)


def remove_hook(client: TmuxClient, installation: HookInstallation) -> None:
    with suppress(TmuxError):
        client.run("set-hook", "-gu", installation.target)


def remove_hooks(client: TmuxClient) -> None:
    for installation in hook_installations(Path("/")):
        remove_hook(client, installation)
