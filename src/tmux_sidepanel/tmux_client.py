"""A small client for the tmux command line. It runs tmux with a list of arguments, no shell.

With a socket path the client talks to that server only, and it hides the variables of the
tmux that runs the caller, so a test server can never be mixed up with a real one.
"""

import os
import subprocess
from contextlib import suppress
from dataclasses import dataclass

from tmux_sidepanel.panes import PANE_FORMAT, PaneRecord, parse_pane_records

COMMAND_TIMEOUT_SECONDS = 5
TMUX_ENVIRONMENT_VARIABLES = frozenset({"TMUX", "TMUX_PANE"})


class TmuxError(RuntimeError):
    """A tmux command failed, or tmux could not be started."""


def without_tmux_variables(environment: dict[str, str]) -> dict[str, str]:
    return {name: environment[name] for name in set(environment) - TMUX_ENVIRONMENT_VARIABLES}


@dataclass(frozen=True)
class TmuxClient:
    socket_path: str = ""

    def command_line(self, arguments: tuple[str, ...]) -> list[str]:
        base = ["tmux", "-S", self.socket_path] if self.socket_path else ["tmux"]
        return [*base, *arguments]

    def environment(self) -> dict[str, str]:
        current = dict(os.environ)
        return without_tmux_variables(current) if self.socket_path else current

    def execute(self, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                self.command_line(arguments),
                capture_output=True,
                text=True,
                env=self.environment(),
                timeout=COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TmuxError(f"tmux {' '.join(arguments)}: {error}") from error

    def run(self, *arguments: str) -> str:
        """Run a tmux command and return what it prints. A failure raises TmuxError."""
        result = self.execute(arguments)
        if result.returncode != 0:
            raise TmuxError(f"tmux {' '.join(arguments)}: {result.stderr.strip()}")
        return result.stdout

    def list_panes(self) -> list[PaneRecord]:
        return parse_pane_records(self.run("list-panes", "-a", "-F", PANE_FORMAT))

    def display(self, target: str, expression: str) -> str:
        """Expand a tmux format in the context of a target, for example '#{window_id}'."""
        return self.run("display-message", "-p", "-t", target, expression).rstrip("\n")

    def write_option(self, scope_flags: list[str], target: str, option: str, value: str) -> None:
        """Set an option, or remove it when the value is empty. The dashes keep values safe."""
        target_arguments = [*scope_flags, "-t", target]
        set_arguments = ["set-option", *target_arguments, "--", option, value]
        unset_arguments = ["set-option", "-u", *target_arguments, "--", option]
        self.run(*(set_arguments if value else unset_arguments))

    def write_pane_option(self, pane_identifier: str, option: str, value: str) -> None:
        self.write_option(["-p"], pane_identifier, option, value)

    def write_window_option(self, window_identifier: str, option: str, value: str) -> None:
        self.write_option(["-w"], window_identifier, option, value)

    def write_session_option(self, session_identifier: str, option: str, value: str) -> None:
        self.write_option([], session_identifier, option, value)

    def stop_server(self) -> None:
        with suppress(TmuxError):
            self.run("kill-server")
