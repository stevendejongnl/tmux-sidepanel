"""The commands that control a pane: split, run, read, wait-output and close."""

import argparse
import re
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from tmux_sidepanel.agent_commands import caller_pane, print_result
from tmux_sidepanel.agent_output import AgentCommandError
from tmux_sidepanel.command_context import CommandContext
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.pane_description import describe_pane, resolve_pane
from tmux_sidepanel.pane_reading import SOURCES, read_pane_text
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.waiting import wait_for

DEFAULT_READ_LINES = 120
DEFAULT_WAIT_LINES = 200
DIRECTION_FLAGS = {"right": "-h", "down": "-v"}


def add_pane_parsers(commands: Any) -> None:
    pane = commands.add_parser("pane", help="control a pane").add_subparsers(
        dest="pane_command", required=True
    )
    split = pane.add_parser("split", help="make a new pane next to a pane")
    split.add_argument("--target", help="the pane to split, the pane of the caller by default")
    split.add_argument("--direction", choices=list(DIRECTION_FLAGS), default="right")
    split.add_argument("--directory", help="the directory the new pane starts in")
    split.add_argument("--focus", action="store_true", help="move the focus to the new pane")
    run = pane.add_parser("run", help="type a command in a pane and press Enter")
    run.add_argument("target")
    run.add_argument("typed_command", metavar="command")
    read = pane.add_parser("read", help="read the text of a pane")
    read.add_argument("target")
    read.add_argument("--source", choices=list(SOURCES), default="recent-unwrapped")
    read.add_argument("--lines", type=int, default=DEFAULT_READ_LINES)
    wait = pane.add_parser("wait-output", help="wait until the text of a pane matches")
    wait.add_argument("target")
    wait.add_argument("--match", help="text that must appear")
    wait.add_argument("--regex", help="pattern that must match a line (^ and $ match at each line)")
    wait.add_argument("--timeout", type=int, help="milliseconds")
    wait.add_argument("--lines", type=int, default=DEFAULT_WAIT_LINES)
    close = pane.add_parser("close", help="close a pane")
    close.add_argument("target")


def resolved_pane(context: CommandContext, target: str | None) -> PaneRecord:
    panes = context.client.list_panes()
    return resolve_pane(panes, target, caller_pane(context), context.agent_names())


def split_flags(parsed: argparse.Namespace) -> list[str]:
    focus_flags = [] if parsed.focus else ["-d"]
    directory_flags = ["-c", parsed.directory] if parsed.directory else []
    return [DIRECTION_FLAGS[parsed.direction], *focus_flags, *directory_flags]


def run_split_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    base = resolved_pane(context, parsed.target)
    created = context.client.run(
        "split-window", "-P", "-F", "#{pane_id}", "-t", base.pane_identifier, *split_flags(parsed)
    )
    pane = find_pane(context.client.list_panes(), created.strip())
    print_result(asdict(describe_pane(pane, context.agent_names())))


def run_run_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    pane = resolved_pane(context, parsed.target)
    context.client.run("send-keys", "-t", pane.pane_identifier, "-l", parsed.typed_command)
    context.client.run("send-keys", "-t", pane.pane_identifier, "Enter")
    print_result({"pane_id": pane.pane_identifier, "queued": True})


def run_read_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    pane = resolved_pane(context, parsed.target)
    text = read_pane_text(context.client, pane.pane_identifier, parsed.source, parsed.lines)
    print_result({"pane_id": pane.pane_identifier, "text": text})


def compiled_regex(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.MULTILINE)
    except re.error as error:
        raise AgentCommandError("bad_arguments", f"--regex is not valid: {error}") from error


def output_matcher(parsed: argparse.Namespace) -> Callable[[str], bool]:
    if parsed.regex:
        pattern = compiled_regex(parsed.regex)
        return lambda text: pattern.search(text) is not None
    if parsed.match:
        return lambda text: parsed.match in text
    raise AgentCommandError("bad_arguments", "wait-output needs --match or --regex")


def run_wait_output_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    matches = output_matcher(parsed)
    pane = resolved_pane(context, parsed.target)

    def observe() -> str:
        return read_pane_text(
            context.client, pane.pane_identifier, "recent-unwrapped", parsed.lines
        )

    wait_for(observe, matches, parsed.timeout, lambda text: "no match before the timeout")
    print_result({"pane_id": pane.pane_identifier, "matched": True})


def run_close_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    pane = resolved_pane(context, parsed.target)
    if pane.pane_identifier == caller_pane(context):
        raise AgentCommandError("own_pane", "the pane of the caller is never closed")
    context.client.run("kill-pane", "-t", pane.pane_identifier)
    print_result({"pane_id": pane.pane_identifier, "closed": True})


PANE_COMMANDS = {
    "split": run_split_command,
    "run": run_run_command,
    "read": run_read_command,
    "wait-output": run_wait_output_command,
    "close": run_close_command,
}


def run_pane_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    PANE_COMMANDS[parsed.pane_command](parsed, context)
