"""The sections of the panel that list the panes of a window and the subagents of its agents."""

from dataclasses import dataclass
from itertools import chain
from operator import attrgetter
from pathlib import PurePosixPath

from tmux_sidepanel.agents import Subagent, parse_subagents
from tmux_sidepanel.configuration import AgentSettings, Section
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.rows import Row, SectionView, format_row, state_mark
from tmux_sidepanel.snapshot import Snapshot

SUBAGENT_STATE = "working"
ERROR_KIND = "error"
ERROR_STATE = "blocked"


@dataclass(frozen=True)
class PaneSubject:
    pane: PaneRecord
    state: str


@dataclass(frozen=True)
class SubagentSubject:
    pane: PaneRecord
    subagent: Subagent
    parent_state: str


def runs_agent(pane: PaneRecord, agents: AgentSettings) -> bool:
    return pane.current_command in agents.names


def effective_state(pane: PaneRecord, agents: AgentSettings) -> str:
    """The state to show. A state on a pane that no longer runs the agent is stale and ignored."""
    if not runs_agent(pane, agents):
        return ""
    return pane.agent_state or "unknown"


def directory_name(pane: PaneRecord) -> str:
    return PurePosixPath(pane.current_directory).name


def program_name(pane: PaneRecord, state: str) -> str:
    name = pane.agent_name or (pane.agent_kind if state else pane.current_command)
    return name or pane.current_command


def subagent_note(pane: PaneRecord, state: str) -> str:
    count = len(parse_subagents(pane.agent_subagents)) if state else 0
    return f"(+{count} sub)" if count else ""


def pane_label(pane: PaneRecord, state: str) -> str:
    name = program_name(pane, state)
    folder = directory_name(pane)
    parts = [name, "" if folder == name else folder, subagent_note(pane, state)]
    return " ".join(filter(None, parts))


def pane_fields(pane: PaneRecord, state: str) -> dict[str, str]:
    return {
        "mark": state_mark(state),
        "label": pane_label(pane, state),
        "directory": directory_name(pane),
        "command": pane.current_command,
        "state": state,
    }


def own_panes(snapshot: Snapshot) -> list[PaneRecord]:
    """The panes of the window of the panel, in order, without the panel itself."""
    regular = filter(PaneRecord.is_not_panel, snapshot.panes)
    in_window = filter(lambda pane: pane.window_identifier == snapshot.window_identifier, regular)
    return sorted(in_window, key=attrgetter("pane_index"))


def pane_row(section: Section, pane: PaneRecord, agents: AgentSettings) -> Row:
    state = effective_state(pane, agents)
    text = format_row(section.row_format, pane_fields(pane, state))
    return Row(text, state, pane.is_active, PaneSubject(pane, state))


def section_view(section: Section, rows: tuple[Row, ...]) -> SectionView:
    return SectionView(
        section.identifier, section.section_type, section.title, section.empty_text, rows
    )


def build_pane_section(section: Section, snapshot: Snapshot, agents: AgentSettings) -> SectionView:
    rows = tuple(pane_row(section, pane, agents) for pane in own_panes(snapshot))
    return section_view(section, rows)


def subagent_row_state(subagent: Subagent) -> str:
    """A row about an error stands out like a pane that waits for you."""
    return ERROR_STATE if subagent.kind == ERROR_KIND else SUBAGENT_STATE


def subagent_fields(subagent: Subagent) -> dict[str, str]:
    return {
        "mark": state_mark(subagent_row_state(subagent)),
        "label": subagent.label,
        "kind": subagent.kind,
        "identifier": subagent.identifier,
    }


def subagent_row(section: Section, pane: PaneRecord, subagent: Subagent, state: str) -> Row:
    text = format_row(section.row_format, subagent_fields(subagent))
    return Row(text, subagent_row_state(subagent), False, SubagentSubject(pane, subagent, state))


def pane_subagent_rows(section: Section, pane: PaneRecord, agents: AgentSettings) -> list[Row]:
    state = effective_state(pane, agents)
    entries = f"{pane.agent_subagents} {pane.agent_tasks}"
    subagents = parse_subagents(entries) if state else []
    return [subagent_row(section, pane, subagent, state) for subagent in subagents]


def build_subagent_section(
    section: Section, snapshot: Snapshot, agents: AgentSettings
) -> SectionView:
    per_pane = (pane_subagent_rows(section, pane, agents) for pane in own_panes(snapshot))
    return section_view(section, tuple(chain.from_iterable(per_pane)))
