"""Entry point: ``python3 -m tmux_sidepanel``.

A hook runs on every event of the agent, so ``hook <action>`` takes a short way in that loads
the hook code only. Every other command loads the whole command line.
"""

import os
import sys

CONFIGURED_HOOK_ACTIONS = (["reap"], ["open-panel"])


def is_plain_hook(arguments: list[str]) -> bool:
    """True for ``hook <action>``. Two actions need the configuration, so they are not."""
    return arguments[:1] == ["hook"] and arguments[1:2] not in CONFIGURED_HOOK_ACTIONS


def run_hook(arguments: list[str]) -> int:
    from tmux_sidepanel.hook_command import main_hook
    from tmux_sidepanel.tmux_client import TmuxClient

    return main_hook(arguments, os.environ, sys.stdin, TmuxClient())


def run_command_line(arguments: list[str]) -> int:
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

    context = CommandContext(os.environ, sys.stdin, TmuxClient(), configured_agent_names)
    return main(arguments, context)


def run() -> int:
    arguments = sys.argv[1:]
    return run_hook(arguments) if is_plain_hook(arguments) else run_command_line(arguments)


if __name__ == "__main__":
    raise SystemExit(run())
