"""Applying a hook event to tmux: the state of the pane, its subagents and the roll-ups."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from typing import Any

from tmux_sidepanel.hooks import (
    HookContext,
    StateChange,
    state_change,
    updated_subagents,
    updated_tasks,
)
from tmux_sidepanel.options import (
    OPTION_KIND,
    OPTION_NAME,
    OPTION_SESSION_STATE,
    OPTION_STATE,
    OPTION_SUBAGENTS,
    OPTION_TASKS,
    OPTION_WINDOW_STATE,
)
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.rollup import session_states, stale_agent_panes, window_states
from tmux_sidepanel.tmux_client import TmuxClient

AGENT_OPTIONS = (OPTION_STATE, OPTION_KIND, OPTION_NAME, OPTION_SUBAGENTS, OPTION_TASKS)


@dataclass(frozen=True)
class HookRequest:
    pane_identifier: str
    action: str
    payload: dict[str, Any]
    agent_kind: str = "claude"


def find_pane(panes: Iterable[PaneRecord], pane_identifier: str) -> PaneRecord | None:
    return next(filter(lambda pane: pane.pane_identifier == pane_identifier, panes), None)


def clear_agent_options(client: TmuxClient, pane_identifier: str) -> None:
    for option in AGENT_OPTIONS:
        client.write_pane_option(pane_identifier, option, "")


def apply_set(
    client: TmuxClient, pane: PaneRecord, request: HookRequest, change: StateChange
) -> None:
    """Write what differs. Most events repeat the state, and each write is a tmux command."""
    if pane.agent_state != change.state:
        client.write_pane_option(pane.pane_identifier, OPTION_STATE, change.state)
    if pane.agent_kind != request.agent_kind:
        client.write_pane_option(pane.pane_identifier, OPTION_KIND, request.agent_kind)


def apply_clear(
    client: TmuxClient, pane: PaneRecord, request: HookRequest, change: StateChange
) -> None:
    clear_agent_options(client, pane.pane_identifier)


def apply_keep(
    client: TmuxClient, pane: PaneRecord, request: HookRequest, change: StateChange
) -> None:
    return None


CHANGE_APPLIERS = {"set": apply_set, "clear": apply_clear, "keep": apply_keep}


def resulting_state(pane: PaneRecord, change: StateChange) -> str:
    return {"set": change.state, "clear": "", "keep": pane.agent_state}[change.operation]


def apply_state_change(client: TmuxClient, pane: PaneRecord, request: HookRequest) -> str:
    """Apply the change to the pane and return the state it has afterwards."""
    context = HookContext(request.payload, pane.is_focused, pane.agent_state)
    change = state_change(request.action, context)
    CHANGE_APPLIERS[change.operation](client, pane, request, change)
    return resulting_state(pane, change)


def apply_subagents(client: TmuxClient, pane: PaneRecord, request: HookRequest) -> None:
    updated = updated_subagents(pane.agent_subagents, request.action, request.payload)
    if updated != pane.agent_subagents:
        client.write_pane_option(pane.pane_identifier, OPTION_SUBAGENTS, updated)


def apply_tasks(client: TmuxClient, pane: PaneRecord, request: HookRequest) -> None:
    updated = updated_tasks(pane.agent_tasks, request.action, request.payload)
    if updated != pane.agent_tasks:
        client.write_pane_option(pane.pane_identifier, OPTION_TASKS, updated)


def pane_with_state(item: PaneRecord, pane: PaneRecord, state: str) -> PaneRecord:
    same_pane = item.pane_identifier == pane.pane_identifier
    return replace(item, agent_state=state) if same_pane else item


def with_state(panes: list[PaneRecord], pane: PaneRecord, state: str) -> list[PaneRecord]:
    """The panes as they are after this pane got its state, without asking tmux again."""
    return [pane_with_state(item, pane, state) for item in panes]


def write_rollups_of(client: TmuxClient, pane: PaneRecord, panes: list[PaneRecord]) -> None:
    """Write the window and session roll-ups that this pane belongs to."""
    window_state = window_states(panes).get(pane.window_identifier, "")
    session_state = session_states(panes).get(pane.session_identifier, "")
    client.write_window_option(pane.window_identifier, OPTION_WINDOW_STATE, window_state)
    client.write_session_option(pane.session_identifier, OPTION_SESSION_STATE, session_state)


def run_hook(client: TmuxClient, request: HookRequest) -> None:
    """Apply one hook event. A pane that does not exist is ignored."""
    panes = client.list_panes()
    pane = find_pane(panes, request.pane_identifier)
    if pane is None:
        return
    state = apply_state_change(client, pane, request)
    apply_subagents(client, pane, request)
    apply_tasks(client, pane, request)
    if state != pane.agent_state:
        write_rollups_of(client, pane, with_state(panes, pane, state))


def write_window_rollups(client: TmuxClient, panes: list[PaneRecord]) -> None:
    for window_identifier, state in window_states(panes).items():
        client.write_window_option(window_identifier, OPTION_WINDOW_STATE, state)


def write_session_rollups(client: TmuxClient, panes: list[PaneRecord]) -> None:
    for session_identifier, state in session_states(panes).items():
        client.write_session_option(session_identifier, OPTION_SESSION_STATE, state)


def refresh_rollups(client: TmuxClient) -> None:
    """Recompute the roll-up of every window and session from the panes."""
    panes = client.list_panes()
    write_window_rollups(client, panes)
    write_session_rollups(client, panes)


def reap_stale_panes(client: TmuxClient, agent_names: Collection[str]) -> None:
    """Clear the state of panes whose agent is gone, for example after a crash."""
    for pane in stale_agent_panes(client.list_panes(), agent_names):
        clear_agent_options(client, pane.pane_identifier)
    refresh_rollups(client)
