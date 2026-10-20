"""Entry point: ``python3 -m tmux_sidepanel``."""

import os
import sys

from tmux_sidepanel.command_line import CommandContext, main
from tmux_sidepanel.configuration import (
    AgentSettings,
    ConfigurationError,
    find_configuration_path,
    load_configuration,
)
from tmux_sidepanel.tmux_client import TmuxClient


def configured_agent_names() -> tuple[str, ...]:
    """The agent names of the configuration file. A broken file falls back to the defaults."""
    try:
        return load_configuration(find_configuration_path()).agents.names
    except ConfigurationError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return AgentSettings().names


def run() -> int:
    context = CommandContext(os.environ, sys.stdin, TmuxClient(), configured_agent_names)
    return main(sys.argv[1:], context)


if __name__ == "__main__":
    raise SystemExit(run())
