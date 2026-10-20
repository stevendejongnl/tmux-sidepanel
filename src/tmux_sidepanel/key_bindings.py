"""The keys of the prefix table that toggle and focus the panel.

A key can be changed with a tmux option, or turned off with the value off. A key that the user
already uses for something else is never taken over, and never removed.
"""

import re
import shlex
from pathlib import Path

from tmux_sidepanel.tmux_client import TmuxClient
from tmux_sidepanel.tmux_syntax import escape_for_format, quote_for_tmux

DEFAULT_KEYS = {"toggle": "S", "focus": "F"}
DISABLED_VALUES = {"off", "none"}
PLUGIN_MARK = "tmux_sidepanel"
BINDING_PATTERN = re.compile(r"^bind-key\s+(?:-\S+\s+)*-T prefix\s+(\S+)\s+(.*)$")


def option_name(action: str) -> str:
    return f"@sidepanel_{action}_key"


def configured_key(client: TmuxClient, action: str) -> str:
    """The key of an action: the option of the user, the default, or empty when turned off."""
    value = client.run("show-option", "-gqv", option_name(action)).strip()
    if value in DISABLED_VALUES:
        return ""
    return value or DEFAULT_KEYS[action]


def binding_command(source_directory: Path, action: str) -> str:
    directory = escape_for_format(shlex.quote(str(source_directory)))
    command = f"PYTHONPATH={directory} python3 -m tmux_sidepanel {action} --window #{{window_id}}"
    return "run-shell -b " + quote_for_tmux(command)


def user_command_of_key(listing: str, key: str) -> str:
    """The command that a key of the prefix table runs, from the output of list-keys."""
    matches = filter(None, map(BINDING_PATTERN.match, listing.splitlines()))
    first = next(filter(lambda match: match.group(1) == key, matches), None)
    return first.group(2) if first else ""


def is_free_or_ours(command: str) -> bool:
    return not command or PLUGIN_MARK in command


def prefix_listing(client: TmuxClient) -> str:
    return client.run("list-keys", "-T", "prefix")


def install_key_binding(client: TmuxClient, source_directory: Path, action: str) -> None:
    key = configured_key(client, action)
    if not key:
        return
    if not is_free_or_ours(user_command_of_key(prefix_listing(client), key)):
        return
    client.run("bind-key", "-T", "prefix", key, binding_command(source_directory, action))


def install_key_bindings(client: TmuxClient, source_directory: Path) -> None:
    for action in DEFAULT_KEYS:
        install_key_binding(client, source_directory, action)


def remove_key_binding(client: TmuxClient, action: str) -> None:
    key = configured_key(client, action)
    if key and PLUGIN_MARK in user_command_of_key(prefix_listing(client), key):
        client.run("unbind-key", "-T", "prefix", key)


def remove_key_bindings(client: TmuxClient) -> None:
    for action in DEFAULT_KEYS:
        remove_key_binding(client, action)
