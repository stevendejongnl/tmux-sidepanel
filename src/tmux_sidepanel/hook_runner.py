"""Applying a hook event to tmux: the state of the pane, its subagents and the roll-ups."""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.hooks import HookContext, StateChange, state_change, updated_subagents
from tmux_sidepanel.options import (
    OPTION_KIND,
    OPTION_NAME,
    OPTION_SESSION_STATE,
    OPTION_STATE,
    OPTION_SUBAGENTS,
    OPTION_WINDOW_STATE,
)
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.rollup import session_states, stale_agent_panes, window_states
from tmux_sidepanel.tmux_client import TmuxClient

AGENT_OPTIONS = (OPTION_STATE, OPTION_KIND, OPTION_NAME, OPTION_SUBAGENTS)


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
    client.write_pane_option(pane.pane_identifier, OPTION_STATE, change.state)
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


def apply_state_change(client: TmuxClient, pane: PaneRecord, request: HookRequest) -> None:
    context = HookContext(request.payload, pane.is_focused, pane.agent_state)
    change = state_change(request.action, context)
    CHANGE_APPLIERS[change.operation](client, pane, request, change)


def apply_subagents(client: TmuxClient, pane: PaneRecord, request: HookRequest) -> None:
    updated = updated_subagents(pane.agent_subagents, request.action, request.payload)
    if updated != pane.agent_subagents:
        client.write_pane_option(pane.pane_identifier, OPTION_SUBAGENTS, updated)


def write_rollups_of(client: TmuxClient, pane: PaneRecord) -> None:
    """Write the window and session roll-ups that this pane belongs to."""
    panes = client.list_panes()
    window_state = window_states(panes).get(pane.window_identifier, "")
    session_state = session_states(panes).get(pane.session_identifier, "")
    client.write_window_option(pane.window_identifier, OPTION_WINDOW_STATE, window_state)
    client.write_session_option(pane.session_identifier, OPTION_SESSION_STATE, session_state)


def run_hook(client: TmuxClient, request: HookRequest) -> None:
    """Apply one hook event. A pane that does not exist is ignored."""
    pane = find_pane(client.list_panes(), request.pane_identifier)
    if pane is None:
        return
    apply_state_change(client, pane, request)
    apply_subagents(client, pane, request)
    write_rollups_of(client, pane)


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
