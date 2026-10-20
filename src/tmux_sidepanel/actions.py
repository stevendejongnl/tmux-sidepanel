"""The dispatcher: one entry for every action, with tmux problems turned into notices.

A pane can disappear between the moment a row is drawn and the moment an action runs, so any tmux
failure, also one that happens after a confirmation, becomes a notice and never crashes the panel.
"""

from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import Any

from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome, done
from tmux_sidepanel.pane_actions import perform_pane_action, perform_subagent_action
from tmux_sidepanel.pane_rows import PaneSubject, SubagentSubject
from tmux_sidepanel.service_actions import perform_service_action
from tmux_sidepanel.service_rows import ServiceSubject
from tmux_sidepanel.tmux_client import TmuxError
from tmux_sidepanel.zombie_actions import perform_zombie_action
from tmux_sidepanel.zombie_rows import ZombieSubject

Performer = Callable[[ActionContext, Any, str], ActionOutcome]


def perform_nothing(context: ActionContext, subject: Any, action: str) -> ActionOutcome:
    return done("nothing to do")


PERFORMERS: dict[type, Performer] = {
    PaneSubject: perform_pane_action,
    SubagentSubject: perform_subagent_action,
    ServiceSubject: perform_service_action,
    ZombieSubject: perform_zombie_action,
}


def guard_confirmation(outcome: ActionOutcome) -> ActionOutcome:
    if outcome.confirmed is None:
        return outcome
    return replace(outcome, confirmed=partial(safely, outcome.confirmed))


def safely(function: Callable[[], ActionOutcome]) -> ActionOutcome:
    """Run an action. A tmux failure becomes a notice, also in the confirmation that follows."""
    try:
        outcome = function()
    except TmuxError as error:
        return done(f"tmux: {error}")
    return guard_confirmation(outcome)


def perform_action(context: ActionContext, subject: Any, action: str) -> ActionOutcome:
    performer = PERFORMERS.get(type(subject), perform_nothing)
    return safely(partial(performer, context, subject, action))
