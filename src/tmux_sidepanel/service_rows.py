"""The sections that list the services of a window and the services that no window owns.

A service is a command that runs in the foreground of a pane and that a rule recognises, such as a
test run or a development server, or a container that belongs to the folder of a pane.
"""

from dataclasses import dataclass
from itertools import chain, islice
from operator import attrgetter
from typing import Any

from tmux_sidepanel.configuration import AgentSettings, Section
from tmux_sidepanel.containers import BoundContainer, ContainerGroup, place_containers
from tmux_sidepanel.pane_rows import own_panes, runs_agent, section_view
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.processes import Process
from tmux_sidepanel.rows import Row, SectionView, format_row
from tmux_sidepanel.services import classify, display_command, strip_shims
from tmux_sidepanel.snapshot import Snapshot
from tmux_sidepanel.text import compact_status, format_age

FOREGROUND_FLAG = "+"
WORKING_KINDS = ("test",)


@dataclass(frozen=True)
class ServiceEntry:
    kind: str
    command: str
    age: str
    is_container: bool
    pane_identifier: str  # empty when no window owns the service
    directory: str
    process_identifier: int  # zero for a container
    container_names: tuple[str, ...]
    project: str


@dataclass(frozen=True)
class ServiceSubject:
    entry: ServiceEntry


def is_foreground(process: Process) -> bool:
    return FOREGROUND_FLAG in process.status_flags


def is_service_pane(pane: PaneRecord, agents: AgentSettings) -> bool:
    return not pane.has_agent_state() and not runs_agent(pane, agents)


def foreground_processes(pane: PaneRecord, snapshot: Snapshot) -> list[Process]:
    on_pane = filter(
        lambda process: process.terminal == pane.terminal and is_foreground(process),
        snapshot.process_table.values(),
    )
    return sorted(on_pane, key=attrgetter("process_identifier"))


def process_entry(process: Process, pane: PaneRecord, options: dict[str, Any]) -> ServiceEntry:
    stripped = strip_shims(process.arguments, options["shims"])
    return ServiceEntry(
        kind=classify(stripped, options["rules"]),
        command=display_command(stripped),
        age=format_age(process.age_seconds),
        is_container=False,
        pane_identifier=pane.pane_identifier,
        directory=pane.current_directory,
        process_identifier=process.process_identifier,
        container_names=(),
        project="",
    )


def has_kind(entry: ServiceEntry) -> bool:
    return bool(entry.kind)


def pane_service(
    pane: PaneRecord, snapshot: Snapshot, options: dict[str, Any]
) -> list[ServiceEntry]:
    """The service of a pane: its first foreground process that a rule recognises."""
    entries = [
        process_entry(process, pane, options) for process in foreground_processes(pane, snapshot)
    ]
    return list(islice(filter(has_kind, entries), 1))


def process_services(
    snapshot: Snapshot, agents: AgentSettings, options: dict[str, Any]
) -> list[ServiceEntry]:
    panes = filter(lambda pane: is_service_pane(pane, agents), own_panes(snapshot))
    return list(chain.from_iterable(pane_service(pane, snapshot, options) for pane in panes))


def bound_container_entry(bound: BoundContainer) -> ServiceEntry:
    container = bound.container
    return ServiceEntry(
        kind="docker",
        command=container.name,
        age=compact_status(container.status),
        is_container=True,
        pane_identifier=bound.pane.pane_identifier,
        directory=container.working_directory,
        process_identifier=0,
        container_names=(container.name,),
        project=container.project,
    )


def container_services(snapshot: Snapshot) -> list[ServiceEntry]:
    bound = place_containers(snapshot.containers, snapshot.panes).bound
    in_window = filter(
        lambda item: item.pane.window_identifier == snapshot.window_identifier, bound
    )
    return [bound_container_entry(item) for item in in_window]


def group_entry(group: ContainerGroup) -> ServiceEntry:
    return ServiceEntry(
        kind="docker",
        command=group.label,
        age=group.status,
        is_container=True,
        pane_identifier="",
        directory=group.working_directory,
        process_identifier=0,
        container_names=group.container_names,
        project=group.project,
    )


def entry_letter(entry: ServiceEntry, letters: dict[str, str]) -> str:
    return letters.get(entry.kind) or entry.kind[:1].upper() or "?"


def entry_state(entry: ServiceEntry) -> str:
    return "working" if entry.kind in WORKING_KINDS else "idle"


def entry_fields(entry: ServiceEntry, letters: dict[str, str]) -> dict[str, str]:
    return {
        "letter": entry_letter(entry, letters),
        "kind": entry.kind,
        "command": entry.command,
        "age": entry.age,
        "mark": " ",
    }


def service_row(section: Section, entry: ServiceEntry) -> Row:
    letters = section.options.get("letters", {})
    text = format_row(section.row_format, entry_fields(entry, letters))
    return Row(text, entry_state(entry), False, ServiceSubject(entry))


def build_service_section(
    section: Section, snapshot: Snapshot, agents: AgentSettings
) -> SectionView:
    entries = process_services(snapshot, agents, section.options) + container_services(snapshot)
    return section_view(section, tuple(service_row(section, entry) for entry in entries))


def build_other_service_section(section: Section, snapshot: Snapshot) -> SectionView:
    groups = place_containers(snapshot.containers, snapshot.panes).unbound
    return section_view(
        section, tuple(service_row(section, group_entry(group)) for group in groups)
    )
