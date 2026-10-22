"""Hook events: how a hook changes the state of its pane and the subagents it lists.

A hook is a short command that the coding agent runs on an event. These functions only decide
what should change. Applying the change to tmux is done elsewhere.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from tmux_sidepanel.agents import Subagent, format_subagents, parse_subagents

UNSAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")
UNSAFE_DESCRIPTION_CHARACTERS = re.compile(r"[^A-Za-z0-9_.-]")

NOTIFICATION_STATES = {
    "permission_prompt": "blocked",
    "elicitation_dialog": "blocked",
    "idle_prompt": "idle",
}
FAILURE = Subagent("failure", "error")
FAILURE_FALLBACK = "Stopped_on_an_error"


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
    "failed": fixed_state("blocked"),
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
MAX_TASK_DESCRIPTION = 40
PATH_KEYS = ("file_path", "notebook_path")
DESCRIBED_TOOLS = ("Bash", "Agent", "Task")
MCP_PREFIX = "mcp__"
COMPACTION = Subagent("compaction", "compact", "Summarizing_context")


def updated_subagents(current: str, action: str, payload: dict[str, Any]) -> str:
    """The stored subagent entries after a start or stop. Other actions change nothing."""
    subagent = payload_subagent(payload)
    update = SUBAGENT_UPDATES.get(action, keep_subagents)
    chosen = update if subagent.has_identifier() else keep_subagents
    return format_subagents(chosen(parse_subagents(current), subagent))


def task_entry(identifier: Any, kind: Any, description: Any = "") -> Subagent:
    text = UNSAFE_DESCRIPTION_CHARACTERS.sub("_", str(description))[:MAX_TASK_DESCRIPTION]
    return Subagent(sanitized_token(identifier, ""), sanitized_token(kind, "task"), text)


def is_listed_task(task: dict[str, Any]) -> bool:
    """A running task that is not a subagent: those have their own start and stop hooks."""
    return task.get("status", "running") == "running" and task.get("type") != "subagent"


def snapshot_tasks(payload: dict[str, Any]) -> list[Subagent]:
    running = filter(is_listed_task, payload["background_tasks"])
    tasks = [
        task_entry(task.get("id", ""), task.get("type", ""), task.get("description", ""))
        for task in running
    ]
    crons = [task_entry(cron.get("id", ""), "cron") for cron in payload.get("session_crons", [])]
    return list(filter(Subagent.has_identifier, [*tasks, *crons]))


def started_task(payload: dict[str, Any]) -> Subagent:
    """The background command that a Bash call has just started, or an entry without identifier."""
    identifier = payload.get("tool_response", {}).get("backgroundTaskId", "")
    description = payload.get("tool_input", {}).get("description", "")
    return task_entry(identifier, "shell", description)


def tool_target(payload: dict[str, Any]) -> str:
    """What a tool call works on, for a person to read. Never a command, a URL or a pattern."""
    name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input")
    arguments = tool_input if isinstance(tool_input, dict) else {}
    path = next(filter(None, map(arguments.get, PATH_KEYS)), "")
    description = arguments.get("description", "") if name in DESCRIBED_TOOLS else ""
    if name.startswith(MCP_PREFIX):
        return name.removeprefix(MCP_PREFIX).replace("__", " ")
    return f"{name} {PurePosixPath(str(path)).name if path else description}".strip()


def tool_row(payload: dict[str, Any]) -> Subagent:
    return task_entry(
        sanitized_token(payload.get("tool_use_id", ""), ""), "tool", tool_target(payload)
    )


def add_tool(tasks: list[Subagent], payload: dict[str, Any]) -> list[Subagent]:
    row = tool_row(payload)
    return with_subagent(tasks, row) if row.has_identifier() else tasks


def add_compaction(tasks: list[Subagent], payload: dict[str, Any]) -> list[Subagent]:
    return with_subagent(tasks, COMPACTION)


def remove_compaction(tasks: list[Subagent], payload: dict[str, Any]) -> list[Subagent]:
    return without_subagent(tasks, COMPACTION)


def add_failure(tasks: list[Subagent], payload: dict[str, Any]) -> list[Subagent]:
    reason = payload.get("error") or FAILURE_FALLBACK
    return with_subagent(tasks, task_entry(FAILURE.identifier, FAILURE.kind, reason))


TASK_UPDATES = {
    "compacting": add_compaction,
    "compacted": remove_compaction,
    "failed": add_failure,
    "tool-start": add_tool,
}


def without_ended_work(tasks: list[Subagent], payload: dict[str, Any]) -> list[Subagent]:
    """New work means the failure is over, and the tool call of the event is done."""
    ended_tool = Subagent(sanitized_token(payload.get("tool_use_id", ""), ""), "tool")
    return without_subagent(without_subagent(tasks, FAILURE), ended_tool)


def updated_tasks(current: str, action: str, payload: dict[str, Any]) -> str:
    """The stored background tasks. A snapshot (Stop) replaces the list, a started command adds.

    A compaction is listed from its start to its end. A failed turn is listed until the agent
    works again. A snapshot ends both, because it replaces the list.
    """
    tasks = parse_subagents(current)
    if action in TASK_UPDATES:
        return format_subagents(TASK_UPDATES[action](tasks, payload))
    if "background_tasks" in payload:
        return format_subagents(snapshot_tasks(payload))
    working = without_ended_work(tasks, payload) if action == "working" else tasks
    started = started_task(payload)
    return format_subagents(
        with_subagent(working, started) if started.has_identifier() else working
    )
