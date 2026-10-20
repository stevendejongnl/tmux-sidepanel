"""The section that lists agent processes that no pane shows."""

from dataclasses import dataclass
from pathlib import PurePosixPath

from tmux_sidepanel.configuration import AgentSettings, Section
from tmux_sidepanel.pane_rows import section_view
from tmux_sidepanel.processes import Zombie, find_zombies
from tmux_sidepanel.rows import Row, SectionView, format_row
from tmux_sidepanel.snapshot import Snapshot
from tmux_sidepanel.text import format_age

ZOMBIE_STATE = "blocked"
UNKNOWN_NAME = "?"


@dataclass(frozen=True)
class ZombieSubject:
    zombie: Zombie
    directory: str
    pane_identifier: str  # the pane a stopped agent still sits in, otherwise empty


def pane_identifier_of(zombie: Zombie, snapshot: Snapshot) -> str:
    pane = next(filter(lambda item: item.terminal == zombie.process.terminal, snapshot.panes), None)
    return pane.pane_identifier if pane else ""


def zombie_fields(zombie: Zombie, directory: str) -> dict[str, str]:
    return {
        "name": PurePosixPath(directory).name or UNKNOWN_NAME,
        "process_identifier": str(zombie.process.process_identifier),
        "reason": zombie.reason,
        "age": format_age(zombie.process.age_seconds),
        "directory": directory,
    }


def zombie_row(section: Section, zombie: Zombie, snapshot: Snapshot) -> Row:
    directory = snapshot.process_directories.get(zombie.process.process_identifier, "")
    text = format_row(section.row_format, zombie_fields(zombie, directory))
    subject = ZombieSubject(zombie, directory, pane_identifier_of(zombie, snapshot))
    return Row(text, ZOMBIE_STATE, False, subject)


def build_zombie_section(
    section: Section, snapshot: Snapshot, agents: AgentSettings
) -> SectionView:
    pane_terminals = {pane.terminal for pane in snapshot.panes}
    zombies = find_zombies(
        snapshot.process_table, pane_terminals, agents.names, agents.ignored_arguments
    )
    return section_view(section, tuple(zombie_row(section, zombie, snapshot) for zombie in zombies))
