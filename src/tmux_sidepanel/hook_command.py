"""The hook command: the agent waits for it on every event, so it loads as little as it can.

``python3 -m tmux_sidepanel hook <action>`` runs many times in a turn. ``main_hook`` reads that
command with the hook code only, and the command line uses the same parser and the same action.
The actions ``reap`` and ``open-panel`` are the exception: they need the configuration, so only
the command line runs them.

A hook must never block the agent. A usage mistake returns 1 (shown, not blocking), a tmux
problem prints one line and returns 0. The code 2 is never returned, because an agent can read
it as "block this action".
"""

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any, TextIO

from tmux_sidepanel.hook_runner import HookRequest, run_hook
from tmux_sidepanel.hooks import STATE_HANDLERS, SUBAGENT_UPDATES, TASK_UPDATES
from tmux_sidepanel.tmux_client import TmuxClient, TmuxError

MAXIMUM_PAYLOAD_CHARACTERS = 1_000_000
REAP_ACTION = "reap"
OPEN_PANEL_ACTION = "open-panel"
HOOK_ACTIONS = (
    *dict.fromkeys((*STATE_HANDLERS, *SUBAGENT_UPDATES, *TASK_UPDATES)),
    REAP_ACTION,
    OPEN_PANEL_ACTION,
)


class UsageError(ValueError):
    """The command line was not understood."""


class QuietParser(argparse.ArgumentParser):
    """An argument parser that raises instead of exiting with code 2."""

    def error(self, message: str):
        raise UsageError(message)


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


def add_hook_parser(commands: Any) -> None:
    hook = commands.add_parser("hook", help="apply an event of a coding agent to its pane")
    hook.add_argument("action", choices=HOOK_ACTIONS)
    hook.add_argument("--pane", default="", help="the pane, instead of TMUX_PANE")
    hook.add_argument("--kind", default="claude", help="the agent that sent the event")


def run_hook_action(
    parsed: argparse.Namespace,
    client: TmuxClient,
    environment: Mapping[str, str],
    standard_input: TextIO,
) -> None:
    pane = parsed.pane or environment.get("TMUX_PANE", "")
    if not pane:
        return
    payload = read_payload(standard_input)
    run_hook(client, HookRequest(pane, parsed.action, payload, parsed.kind))


def main_hook(
    arguments: list[str],
    environment: Mapping[str, str],
    standard_input: TextIO,
    client: TmuxClient,
) -> int:
    """Run ``hook <action>`` and nothing else of the command line. The arguments start at hook."""
    parser = QuietParser(prog="tmux_sidepanel")
    add_hook_parser(parser.add_subparsers(dest="command", required=True, parser_class=QuietParser))
    try:
        run_hook_action(parser.parse_args(arguments), client, environment, standard_input)
    except UsageError as error:
        print(f"usage error: {error}", file=sys.stderr)
        return 1
    except TmuxError as error:
        print(f"tmux: {error}", file=sys.stderr)
    return 0
