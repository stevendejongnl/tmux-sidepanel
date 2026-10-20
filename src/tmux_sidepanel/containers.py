"""Containers: docker's listing parsed, placed in windows by directory, or grouped by project.

A compose container remembers the directory its project was started from. A pane that sits in
that directory, or below it, is where the container belongs. A container that no pane matches
is grouped with the others of its project.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import filterfalse, groupby

from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.text import compact_status

DOCKER_FIELD_SEPARATOR = "\t"
DOCKER_FIELD_EXPRESSIONS = (
    "{{.Names}}",
    "{{.Status}}",
    '{{.Label "com.docker.compose.service"}}',
    '{{.Label "com.docker.compose.project.working_dir"}}',
    '{{.Label "com.docker.compose.project"}}',
)
DOCKER_FORMAT = DOCKER_FIELD_SEPARATOR.join(DOCKER_FIELD_EXPRESSIONS)


@dataclass(frozen=True)
class Container:
    name: str
    status: str
    service: str
    working_directory: str
    project: str

    @property
    def is_unhealthy(self) -> bool:
        return "unhealthy" in self.status


@dataclass(frozen=True)
class BoundContainer:
    container: Container
    pane: PaneRecord


@dataclass(frozen=True)
class ContainerGroup:
    label: str
    project: str
    working_directory: str
    container_names: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class Placement:
    bound: list[BoundContainer]
    unbound: list[ContainerGroup]


@dataclass(frozen=True)
class Candidate:
    container: Container
    pane: PaneRecord | None

    def is_bound(self) -> bool:
        return self.pane is not None


def has_text(line: str) -> bool:
    return bool(line.strip())


def parse_container(line: str) -> Container:
    padded = line.split(DOCKER_FIELD_SEPARATOR) + [""] * len(DOCKER_FIELD_EXPRESSIONS)
    return Container(*padded[: len(DOCKER_FIELD_EXPRESSIONS)])


def parse_containers(output: str) -> list[Container]:
    """Read the output of ``docker ps --format DOCKER_FORMAT``."""
    return [parse_container(line) for line in filter(has_text, output.splitlines())]


def contains_directory(pane_directory: str, working_directory: str) -> bool:
    project = working_directory.rstrip("/")
    pane = pane_directory.rstrip("/")
    return bool(project) and (pane == project or pane.startswith(project + "/"))


def find_pane(container: Container, panes: Sequence[PaneRecord]) -> PaneRecord | None:
    return next(
        filter(
            lambda pane: contains_directory(pane.current_directory, container.working_directory),
            panes,
        ),
        None,
    )


def group_key(container: Container) -> str:
    return container.project or container.name


def group_label(key: str, members: list[Container]) -> str:
    return f"{key} ({len(members)})" if len(members) > 1 else members[0].name


def has_unhealthy_member(members: list[Container]) -> bool:
    return any(member.is_unhealthy for member in members)


def group_status(members: list[Container]) -> str:
    suffix = " unhealthy" if has_unhealthy_member(members) else ""
    return compact_status(members[0].status) + suffix


def make_group(key: str, members: list[Container]) -> ContainerGroup:
    return ContainerGroup(
        label=group_label(key, members),
        project=members[0].project,
        working_directory=members[0].working_directory,
        container_names=tuple(member.name for member in members),
        status=group_status(members),
    )


def group_containers(containers: list[Container]) -> list[ContainerGroup]:
    ordered = sorted(containers, key=group_key)
    return [make_group(key, list(members)) for key, members in groupby(ordered, key=group_key)]


def is_not_panel(pane: PaneRecord) -> bool:
    return not pane.is_panel


def place_containers(containers: Sequence[Container], panes: Sequence[PaneRecord]) -> Placement:
    """Bind each container to the first pane in its project directory; group the others."""
    usable_panes = list(filter(is_not_panel, panes))
    candidates = [
        Candidate(container, find_pane(container, usable_panes)) for container in containers
    ]
    bound = [
        BoundContainer(candidate.container, candidate.pane)
        for candidate in filter(Candidate.is_bound, candidates)
    ]
    unbound = [candidate.container for candidate in filterfalse(Candidate.is_bound, candidates)]
    return Placement(bound, group_containers(unbound))
