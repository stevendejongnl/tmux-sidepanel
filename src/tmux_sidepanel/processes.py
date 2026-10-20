"""Process table logic: find agent processes that no pane shows, and read a session id.

These functions take plain data and return plain data. Reading the process table is done
elsewhere, so everything here can be tested with a small hand-made table.
"""

import os
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class Process:
    process_identifier: int
    parent_process_identifier: int
    terminal: str  # without the /dev/ prefix, "?" when there is none
    status_flags: str
    age_seconds: int
    arguments: str

    @property
    def argument_list(self) -> list[str]:
        return self.arguments.split()

    @property
    def program_name(self) -> str:
        words = self.argument_list
        return os.path.basename(words[0]) if words else ""


@dataclass(frozen=True)
class Zombie:
    process: Process
    reason: str  # "defunct", "stopped" or "no pane"

    def has_reason(self) -> bool:
        return bool(self.reason)


@dataclass(frozen=True)
class FlagWithValue:
    flag: str
    value: str

    def is_session_identifier(self) -> bool:
        return self.flag in RESUME_FLAGS and not self.value.startswith("-")


DEFAULT_AGENT_NAMES = ("claude",)
DEFAULT_IGNORED_ARGUMENTS = ("--chrome-native-host",)
RESUME_FLAGS = ("--resume", "-r", "--session-id")
REASON_BY_STATUS_LETTER = {"Z": "defunct", "T": "stopped"}


def flags_with_values(arguments: Sequence[str]) -> list[FlagWithValue]:
    return [FlagWithValue(flag, value) for flag, value in pairwise(arguments)]


def resume_session_identifier(arguments: Sequence[str]) -> str:
    """Return the session id given to --resume, -r or --session-id, or an empty string."""
    pairs = filter(FlagWithValue.is_session_identifier, flags_with_values(arguments))
    pair = next(pairs, None)
    return pair.value if pair else ""


def ancestors(process: Process, process_table: Mapping[int, Process]) -> Iterator[Process]:
    visited: set[int] = set()
    parent_identifier = process.parent_process_identifier
    while (
        parent_identifier > 1
        and parent_identifier in process_table
        and parent_identifier not in visited
    ):
        visited.add(parent_identifier)
        parent = process_table[parent_identifier]
        yield parent
        parent_identifier = parent.parent_process_identifier


def has_ancestor_on_pane(
    process: Process, process_table: Mapping[int, Process], pane_terminals: Collection[str]
) -> bool:
    """True when an ancestor runs on a pane: the process is a helper of a live session."""
    return any(
        ancestor.terminal in pane_terminals for ancestor in ancestors(process, process_table)
    )


def is_orphan(
    process: Process, process_table: Mapping[int, Process], pane_terminals: Collection[str]
) -> bool:
    on_other_terminal = process.terminal not in pane_terminals
    return on_other_terminal and not has_ancestor_on_pane(process, process_table, pane_terminals)


def zombie_reason(
    process: Process, process_table: Mapping[int, Process], pane_terminals: Collection[str]
) -> str:
    state_reason = REASON_BY_STATUS_LETTER.get(process.status_flags[:1], "")
    orphan_reason = "no pane" if is_orphan(process, process_table, pane_terminals) else ""
    return state_reason or orphan_reason


def is_agent_process(
    process: Process, agent_names: Collection[str], ignored_arguments: Collection[str]
) -> bool:
    is_agent = process.program_name in agent_names
    return is_agent and set(ignored_arguments).isdisjoint(process.argument_list)


def processes_by_identifier(process_table: Mapping[int, Process]) -> list[Process]:
    return [process_table[identifier] for identifier in sorted(process_table)]


def find_zombies(
    process_table: Mapping[int, Process],
    pane_terminals: Collection[str],
    agent_names: Collection[str] = DEFAULT_AGENT_NAMES,
    ignored_arguments: Collection[str] = DEFAULT_IGNORED_ARGUMENTS,
) -> list[Zombie]:
    """Find agent processes that are defunct, stopped, or running without any pane."""
    candidates = filter(
        lambda process: is_agent_process(process, agent_names, ignored_arguments),
        processes_by_identifier(process_table),
    )
    zombies = [
        Zombie(process, zombie_reason(process, process_table, pane_terminals))
        for process in candidates
    ]
    return list(filter(Zombie.has_reason, zombies))
