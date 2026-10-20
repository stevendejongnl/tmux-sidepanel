"""Describing panes for a program that reads JSON, and finding a pane by identifier or name."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from tmux_sidepanel.agent_output import AgentCommandError
from tmux_sidepanel.panes import PaneRecord

CURRENT = "current"


@dataclass(frozen=True)
class PaneDescription:
    session: str
    window: int
    window_name: str
    pane_id: str
    pane: int
    active: bool
    directory: str
    command: str
    state: str  # idle, working, blocked, done, unknown, or empty for a pane without an agent
    kind: str
    name: str


def runs_agent(pane: PaneRecord, agent_names: Collection[str]) -> bool:
    return pane.current_command in agent_names


def agent_state(pane: PaneRecord, agent_names: Collection[str]) -> str:
    """The state to show. A state on a pane that no longer runs the agent is stale and ignored."""
    if not runs_agent(pane, agent_names):
        return ""
    return pane.agent_state or "unknown"


def agent_kind(pane: PaneRecord, agent_names: Collection[str]) -> str:
    if not runs_agent(pane, agent_names):
        return ""
    return pane.agent_kind or pane.current_command


def agent_name(pane: PaneRecord, agent_names: Collection[str]) -> str:
    return pane.agent_name if runs_agent(pane, agent_names) else ""


def describe_pane(pane: PaneRecord, agent_names: Collection[str]) -> PaneDescription:
    return PaneDescription(
        session=pane.session_name,
        window=pane.window_index,
        window_name=pane.window_name,
        pane_id=pane.pane_identifier,
        pane=pane.pane_index,
        active=pane.is_active and pane.is_window_active,
        directory=pane.current_directory,
        command=pane.current_command,
        state=agent_state(pane, agent_names),
        kind=agent_kind(pane, agent_names),
        name=agent_name(pane, agent_names),
    )


def describe_panes(
    panes: Sequence[PaneRecord], agent_names: Collection[str], only_agents: bool = False
) -> list[PaneDescription]:
    """The panes that are not panels, and with only_agents the ones that run an agent."""
    described = [
        describe_pane(pane, agent_names) for pane in filter(PaneRecord.is_not_panel, panes)
    ]
    return list(filter(lambda item: item.state, described)) if only_agents else described


def find_by_identifier(panes: Sequence[PaneRecord], identifier: str) -> PaneRecord:
    found = next(filter(lambda pane: pane.pane_identifier == identifier, panes), None)
    if found is None:
        raise AgentCommandError("pane_not_found", f"no pane {identifier}")
    return found


def find_by_name(
    panes: Sequence[PaneRecord], name: str, agent_names: Collection[str]
) -> PaneRecord:
    named = list(filter(lambda pane: agent_name(pane, agent_names) == name, panes))
    if not named:
        raise AgentCommandError("agent_not_found", f"no pane or agent named {name}")
    if len(named) > 1:
        raise AgentCommandError("ambiguous_name", f"{len(named)} panes named {name}")
    return named[0]


def target_or_current(target: str | None, current_pane: str) -> str:
    chosen = current_pane if target in (None, CURRENT) else target
    if not chosen:
        raise AgentCommandError("not_in_tmux", "TMUX_PANE is not set")
    return chosen


def resolve_pane(
    panes: Sequence[PaneRecord],
    target: str | None,
    current_pane: str,
    agent_names: Collection[str],
) -> PaneRecord:
    """The pane for a pane identifier, a unique agent name, or the pane of the caller."""
    chosen = target_or_current(target, current_pane)
    if chosen.startswith("%"):
        return find_by_identifier(panes, chosen)
    return find_by_name(panes, chosen, agent_names)
