"""The command line of the plugin.

A hook of the coding agent runs ``python3 -m tmux_sidepanel hook <action>``, with the payload of
the event as JSON on standard input and the pane in ``TMUX_PANE``.

A hook must never block the agent. A usage mistake returns 1 (shown, not blocking), a tmux
problem prints one line and returns 0. The code 2 is never returned, because an agent can read
it as "block this action".
"""

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from tmux_sidepanel.hook_runner import HookRequest, reap_stale_panes, run_hook
from tmux_sidepanel.hook_setup import install_hooks, remove_hooks
from tmux_sidepanel.hooks import STATE_HANDLERS, SUBAGENT_UPDATES
from tmux_sidepanel.tmux_client import TmuxClient, TmuxError

MAXIMUM_PAYLOAD_CHARACTERS = 1_000_000
REAP_ACTION = "reap"
HOOK_ACTIONS = (*STATE_HANDLERS, *SUBAGENT_UPDATES, REAP_ACTION)


class UsageError(ValueError):
    """The command line was not understood."""


class QuietParser(argparse.ArgumentParser):
    """An argument parser that raises instead of exiting with code 2."""

    def error(self, message: str):
        raise UsageError(message)


PACKAGE_SOURCE_DIRECTORY = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommandContext:
    environment: Mapping[str, str]
    standard_input: TextIO
    client: TmuxClient
    agent_names: Callable[[], tuple[str, ...]]
    source_directory: Path = PACKAGE_SOURCE_DIRECTORY


def parse_payload(text: str) -> dict[str, Any]:
    """The JSON object a hook receives. Anything else gives an empty payload."""
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def read_payload(stream: TextIO) -> dict[str, Any]:
    if stream.isatty():
        return {}
    return parse_payload(stream.read(MAXIMUM_PAYLOAD_CHARACTERS))


def build_parser() -> argparse.ArgumentParser:
    parser = QuietParser(prog="tmux_sidepanel")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=QuietParser)
    hook = commands.add_parser("hook", help="apply an event of a coding agent to its pane")
    hook.add_argument("action", choices=HOOK_ACTIONS)
    hook.add_argument("--pane", default="", help="the pane, instead of TMUX_PANE")
    hook.add_argument("--kind", default="claude", help="the agent that sent the event")
    commands.add_parser("setup", help="install the hooks of tmux, safe to run again")
    commands.add_parser("teardown", help="remove the hooks of tmux that setup installed")
    return parser


def run_hook_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    if parsed.action == REAP_ACTION:
        reap_stale_panes(context.client, context.agent_names())
        return
    pane = parsed.pane or context.environment.get("TMUX_PANE", "")
    if not pane:
        return
    payload = read_payload(context.standard_input)
    run_hook(context.client, HookRequest(pane, parsed.action, payload, parsed.kind))


def run_setup_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    install_hooks(context.client, context.source_directory)


def run_teardown_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    remove_hooks(context.client)


COMMANDS = {"hook": run_hook_command, "setup": run_setup_command, "teardown": run_teardown_command}


def main(arguments: list[str], context: CommandContext) -> int:
    try:
        parsed = build_parser().parse_args(arguments)
    except UsageError as error:
        print(f"usage error: {error}", file=sys.stderr)
        return 1
    try:
        COMMANDS[parsed.command](parsed, context)
    except TmuxError as error:
        print(f"tmux: {error}", file=sys.stderr)
    return 0
