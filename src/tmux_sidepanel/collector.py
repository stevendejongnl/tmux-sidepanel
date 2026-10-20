"""Collecting a snapshot: tmux, ps, docker, /proc and the commands of custom sections.

A source is only read when an enabled section needs it, so a configuration with only panes never
starts ps or docker.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from operator import attrgetter

from tmux_sidepanel.command_runner import process_directory, run_text_command
from tmux_sidepanel.configuration import Configuration, Section
from tmux_sidepanel.containers import DOCKER_FORMAT, Container, parse_containers
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND, parse_process_table
from tmux_sidepanel.processes import Process, find_zombies
from tmux_sidepanel.snapshot import Snapshot
from tmux_sidepanel.tmux_client import TmuxClient

DEFAULT_DOCKER_COMMAND = ("docker", "ps", "--format", DOCKER_FORMAT)
PROCESS_SECTION_TYPES = {"services", "zombies"}
CONTAINER_SECTION_TYPES = {"services", "other-services"}


@dataclass(frozen=True)
class Collector:
    client: TmuxClient
    process_command: Sequence[str] = PROCESS_LIST_COMMAND
    docker_command: Sequence[str] = DEFAULT_DOCKER_COMMAND
    timeout_seconds: float = 3.0


def enabled_section_types(configuration: Configuration) -> set[str]:
    enabled = filter(attrgetter("enabled"), configuration.sections)
    return set(map(attrgetter("section_type"), enabled))


def needs_any(configuration: Configuration, section_types: Collection[str]) -> bool:
    return bool(enabled_section_types(configuration) & set(section_types))


def read_process_table(collector: Collector, configuration: Configuration) -> dict[int, Process]:
    if not needs_any(configuration, PROCESS_SECTION_TYPES):
        return {}
    return parse_process_table(
        run_text_command(collector.process_command, collector.timeout_seconds)
    )


def read_containers(collector: Collector, configuration: Configuration) -> list[Container]:
    if not needs_any(configuration, CONTAINER_SECTION_TYPES):
        return []
    return parse_containers(run_text_command(collector.docker_command, collector.timeout_seconds))


def read_process_directories(
    configuration: Configuration, process_table: dict[int, Process], panes: list[PaneRecord]
) -> dict[int, str]:
    """The working folders of the agent processes that no pane shows."""
    if not needs_any(configuration, {"zombies"}):
        return {}
    agents = configuration.agents
    pane_terminals = {pane.terminal for pane in panes}
    zombies = find_zombies(process_table, pane_terminals, agents.names, agents.ignored_arguments)
    return {
        zombie.process.process_identifier: process_directory(zombie.process.process_identifier)
        for zombie in zombies
    }


def custom_sections(configuration: Configuration) -> list[Section]:
    return list(
        filter(
            lambda section: section.enabled and section.section_type == "custom",
            configuration.sections,
        )
    )


def run_custom_section(section: Section) -> str:
    options = section.options
    return run_text_command(options["command"], options["timeout_seconds"])


def read_custom_outputs(configuration: Configuration) -> dict[str, str]:
    return {
        section.identifier: run_custom_section(section)
        for section in custom_sections(configuration)
    }


def collect_snapshot(
    collector: Collector, configuration: Configuration, window_identifier: str
) -> Snapshot:
    """Read everything the enabled sections of the configuration need, once."""
    panes = collector.client.list_panes()
    process_table = read_process_table(collector, configuration)
    return Snapshot(
        panes=panes,
        window_identifier=window_identifier,
        process_table=process_table,
        containers=read_containers(collector, configuration),
        process_directories=read_process_directories(configuration, process_table, panes),
        custom_outputs=read_custom_outputs(configuration),
    )
