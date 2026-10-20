"""The commands for programs and other agents: they read panes and print JSON."""

import argparse
from dataclasses import asdict
from typing import Any

from tmux_sidepanel.agent_output import result_text
from tmux_sidepanel.command_context import CommandContext
from tmux_sidepanel.pane_description import describe_pane, describe_panes, resolve_pane


def add_agent_parsers(commands: Any) -> None:
    listing = commands.add_parser("list", help="list the panes as JSON")
    listing.add_argument("--agents", action="store_true", help="only panes that run an agent")
    commands.add_parser("current", help="describe the pane of the caller")
    get = commands.add_parser("get", help="describe one pane, by identifier or agent name")
    get.add_argument("target")


def print_result(result: Any) -> None:
    print(result_text(result))


def caller_pane(context: CommandContext) -> str:
    return context.environment.get("TMUX_PANE", "")


def described_target(context: CommandContext, target: str | None) -> dict[str, Any]:
    agent_names = context.agent_names()
    panes = context.client.list_panes()
    pane = resolve_pane(panes, target, caller_pane(context), agent_names)
    return asdict(describe_pane(pane, agent_names))


def run_list_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    panes = context.client.list_panes()
    described = describe_panes(panes, context.agent_names(), parsed.agents)
    print_result([asdict(item) for item in described])


def run_current_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    print_result(described_target(context, None))


def run_get_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    print_result(described_target(context, parsed.target))


AGENT_COMMANDS = {
    "list": run_list_command,
    "current": run_current_command,
    "get": run_get_command,
}
