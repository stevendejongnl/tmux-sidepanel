"""Hook events: how a hook changes the state of its pane and the subagents it lists.

A hook is a short command that the coding agent runs on an event. These functions only decide
what should change. Applying the change to tmux is done elsewhere.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.agents import Subagent, format_subagents, parse_subagents

UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")

NOTIFICATION_STATES = {
    "permission_prompt": "blocked",
    "elicitation_dialog": "blocked",
    "idle_prompt": "idle",
}


@dataclass(frozen=True)
class StateChange:
    operation: str  # "set", "clear" or "keep"
    state: str = ""


@dataclass(frozen=True)
class HookContext:
    payload: dict[str, Any]
    pane_is_focused: bool
    current_state: str


KEEP_STATE = StateChange("keep")
CLEAR_STATE = StateChange("clear")


def fixed_state(state: str) -> Callable[[HookContext], StateChange]:
    return lambda context: StateChange("set", state)


def clear_state(context: HookContext) -> StateChange:
    return CLEAR_STATE


def keep_state(context: HookContext) -> StateChange:
    return KEEP_STATE


def done_change(context: HookContext) -> StateChange:
    """A finished turn in a pane you are looking at counts as seen."""
    return StateChange("set", "idle" if context.pane_is_focused else "done")


def seen_change(context: HookContext) -> StateChange:
    """Looking at a pane that finished makes it idle."""
    return StateChange("set", "idle") if context.current_state == "done" else KEEP_STATE


def notification_change(context: HookContext) -> StateChange:
    state = NOTIFICATION_STATES.get(context.payload.get("notification_type", ""), "")
    return StateChange("set", state) if state else KEEP_STATE


STATE_HANDLERS = {
    "working": fixed_state("working"),
    "idle": fixed_state("idle"),
    "blocked": fixed_state("blocked"),
    "done": done_change,
    "seen": seen_change,
    "notification": notification_change,
    "clear": clear_state,
}


def state_change(action: str, context: HookContext) -> StateChange:
    """What an action does to the state of the pane. An unknown action changes nothing."""
    return STATE_HANDLERS.get(action, keep_state)(context)


def sanitized_token(value: Any, fallback: str) -> str:
    """Make a payload value safe to store as one word: odd characters become underscores."""
    return UNSAFE_CHARACTERS.sub("_", str(value)) or fallback


def payload_subagent(payload: dict[str, Any]) -> Subagent:
    identifier = sanitized_token(payload.get("agent_id", ""), "")
    kind = sanitized_token(payload.get("agent_type", ""), "agent")
    return Subagent(identifier, kind)


def without_subagent(subagents: list[Subagent], subagent: Subagent) -> list[Subagent]:
    return list(filter(lambda existing: existing.identifier != subagent.identifier, subagents))


def with_subagent(subagents: list[Subagent], subagent: Subagent) -> list[Subagent]:
    return [*without_subagent(subagents, subagent), subagent]


def keep_subagents(subagents: list[Subagent], subagent: Subagent) -> list[Subagent]:
    return subagents


SUBAGENT_UPDATES = {"sub-start": with_subagent, "sub-stop": without_subagent}


def updated_subagents(current: str, action: str, payload: dict[str, Any]) -> str:
    """The stored subagent entries after a start or stop. Other actions change nothing."""
    subagent = payload_subagent(payload)
    update = SUBAGENT_UPDATES.get(action, keep_subagents)
    chosen = update if subagent.has_identifier() else keep_subagents
    return format_subagents(chosen(parse_subagents(current), subagent))
