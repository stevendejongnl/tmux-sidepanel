"""The actions of the menu of a pane and of a subagent."""

from collections.abc import Callable
from functools import partial

from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome, ask, done
from tmux_sidepanel.pane_rows import PaneSubject, SubagentSubject
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.window_actions import jump_to_pane, open_directory

WAITING_STATES = ("blocked", "unknown")


def ignore_action(context: ActionContext, subject: object) -> ActionOutcome:
    return done("nothing to do")


def pane_go(context: ActionContext, subject: PaneSubject) -> ActionOutcome:
    jump_to_pane(context.client, subject.pane.pane_identifier)
    return done()


def pane_zoom(context: ActionContext, subject: PaneSubject) -> ActionOutcome:
    context.client.run("resize-pane", "-Z", "-t", subject.pane.pane_identifier)
    return done()


def pane_directory(context: ActionContext, subject: PaneSubject) -> ActionOutcome:
    return open_directory(context.client, subject.pane.current_directory)


def send_control_c(context: ActionContext, pane: PaneRecord) -> ActionOutcome:
    context.client.run("send-keys", "-t", pane.pane_identifier, "C-c")
    return done("sent Ctrl-C to the pane")


def pane_interrupt(context: ActionContext, subject: PaneSubject) -> ActionOutcome:
    """An agent is interrupted with Escape at once. Ctrl-C to any other program is confirmed."""
    if subject.state:
        context.client.run("send-keys", "-t", subject.pane.pane_identifier, "Escape")
        return done("sent Esc to the agent")
    prompt = f"send Ctrl-C to {subject.pane.current_command}? y/n"
    return ask(prompt, partial(send_control_c, context, subject.pane))


def close_pane(context: ActionContext, pane: PaneRecord) -> ActionOutcome:
    context.client.run("kill-pane", "-t", pane.pane_identifier)
    return done("closed the pane")


def pane_close(context: ActionContext, subject: PaneSubject) -> ActionOutcome:
    what = "agent pane (the session ends)" if subject.state else "pane"
    prompt = f"CLOSE {what} {subject.pane.current_command}? y/n"
    return ask(prompt, partial(close_pane, context, subject.pane))


PANE_ACTIONS: dict[str, Callable[[ActionContext, PaneSubject], ActionOutcome]] = {
    "go": pane_go,
    "zoom": pane_zoom,
    "interrupt": pane_interrupt,
    "directory": pane_directory,
    "close": pane_close,
}


def perform_pane_action(context: ActionContext, subject: PaneSubject, action: str) -> ActionOutcome:
    return PANE_ACTIONS.get(action, ignore_action)(context, subject)


def subagent_go(context: ActionContext, subject: SubagentSubject) -> ActionOutcome:
    jump_to_pane(context.client, subject.pane.pane_identifier)
    return done()


def subagent_tasks(context: ActionContext, subject: SubagentSubject) -> ActionOutcome:
    """Open /tasks in the parent. Nothing is typed into a parent that waits on an answer."""
    jump_to_pane(context.client, subject.pane.pane_identifier)
    if subject.parent_state in WAITING_STATES:
        return done("the parent waits on input; type /tasks yourself")
    context.client.run("send-keys", "-t", subject.pane.pane_identifier, "-l", "/tasks")
    context.client.run("send-keys", "-t", subject.pane.pane_identifier, "Enter")
    return done("sent /tasks to the parent pane; pick the subagent row")


SUBAGENT_ACTIONS: dict[str, Callable[[ActionContext, SubagentSubject], ActionOutcome]] = {
    "go": subagent_go,
    "tasks": subagent_tasks,
}


def perform_subagent_action(
    context: ActionContext, subject: SubagentSubject, action: str
) -> ActionOutcome:
    return SUBAGENT_ACTIONS.get(action, ignore_action)(context, subject)
