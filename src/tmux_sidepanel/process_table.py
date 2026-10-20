"""Process table: the output of ps parsed into Process objects.

The ``etimes`` column (elapsed seconds) exists in the ps of Linux, not in the one of macOS.
"""

import re
from re import Match

from tmux_sidepanel.processes import Process

PROCESS_LIST_COMMAND = ("ps", "-eo", "pid=,ppid=,tty=,stat=,etimes=,args=")

PROCESS_LINE_PATTERN = re.compile(
    r"^\s*(?P<process_identifier>\d+)\s+(?P<parent_process_identifier>\d+)\s+"
    r"(?P<terminal>\S+)\s+(?P<status_flags>\S+)\s+(?P<age_seconds>\d+)\s*(?P<arguments>.*)$"
)


def process_from_match(match: Match[str]) -> Process:
    return Process(
        process_identifier=int(match.group("process_identifier")),
        parent_process_identifier=int(match.group("parent_process_identifier")),
        terminal=match.group("terminal"),
        status_flags=match.group("status_flags"),
        age_seconds=int(match.group("age_seconds")),
        arguments=match.group("arguments").strip(),
    )


def parse_process_table(output: str) -> dict[int, Process]:
    """Read the output of ``PROCESS_LIST_COMMAND``. Lines that do not fit are skipped."""
    matches = filter(None, map(PROCESS_LINE_PATTERN.match, output.splitlines()))
    processes = map(process_from_match, matches)
    return {process.process_identifier: process for process in processes}
