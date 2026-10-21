"""The state of the panel and what each key does to it.

Nothing here draws or runs a program itself. The keys change the state, and an action is run
through the function that the context carries, so the whole behaviour can be tested without a
terminal.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from tmux_sidepanel.action_outcome import ActionOutcome
from tmux_sidepanel.configuration import Configuration, Section
from tmux_sidepanel.menus import MenuItem, menu_items
from tmux_sidepanel.panel_layout import Line, SelectableRow, selectable_rows
from tmux_sidepanel.rows import PanelView

Performer = Callable[[Any, str], ActionOutcome]

DOWN_KEYS = ("j", "DOWN")
UP_KEYS = ("k", "UP")
CANCELLED = "cancelled"
NO_ACTIONS = "no actions for this row"


@dataclass(frozen=True)
class InterfaceContext:
    panel: PanelView
    configuration: Configuration
    perform: Performer


@dataclass(frozen=True)
class Click:
    line: Line  # the line under the mouse
    is_secondary: bool  # the right button


@dataclass(frozen=True)
class InterfaceState:
    selected: int = 0
    menu: tuple[MenuItem, ...] = ()
    menu_selected: int = 0
    pending: ActionOutcome | None = None
    notice: str = ""
    is_finished: bool = False


def clamp(value: int, count: int) -> int:
    return max(0, min(value, count - 1))


def clamp_selection(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    count = len(selectable_rows(context.panel))
    return replace(state, selected=clamp(state.selected, count))


def section_of(context: InterfaceContext, selectable: SelectableRow) -> Section:
    sections = context.configuration.sections
    matching = filter(lambda section: section.identifier == selectable.section_identifier, sections)
    return next(matching)


def selected_row(context: InterfaceContext, state: InterfaceState) -> SelectableRow | None:
    rows = selectable_rows(context.panel)
    return rows[state.selected] if rows else None


def apply_outcome(state: InterfaceState, outcome: ActionOutcome) -> InterfaceState:
    closed = replace(state, menu=(), menu_selected=0)
    if outcome.prompt:
        return replace(closed, pending=outcome)
    return replace(closed, pending=None, notice=outcome.notice)


def run_action(context: InterfaceContext, state: InterfaceState, action: str) -> InterfaceState:
    selectable = selected_row(context, state)
    return apply_outcome(state, context.perform(selectable.row.subject, action))


def move_selection(context: InterfaceContext, state: InterfaceState, step: int) -> InterfaceState:
    count = len(selectable_rows(context.panel))
    return replace(state, selected=clamp(state.selected + step, count))


def move_highlight(state: InterfaceState, step: int) -> InterfaceState:
    return replace(state, menu_selected=clamp(state.menu_selected + step, len(state.menu)))


def open_menu(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    selectable = selected_row(context, state)
    if selectable is None:
        return state
    items = menu_items(section_of(context, selectable), selectable.row.subject)
    if not items:
        return replace(state, notice=NO_ACTIONS)
    return replace(state, menu=tuple(items), menu_selected=0)


def finish(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    return replace(state, is_finished=True)


def close_menu(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    return replace(state, menu=(), menu_selected=0)


def run_highlighted(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    return run_action(context, state, state.menu[state.menu_selected].action)


def menu_navigation(key: str) -> Callable[[InterfaceContext, InterfaceState], InterfaceState]:
    steps = {"DOWN": 1, "UP": -1}
    if key in steps:
        return lambda context, state: move_highlight(state, steps[key])
    return {"ESC": close_menu, "ENTER": run_highlighted}.get(key, keep_state)


def keep_state(context: InterfaceContext, state: InterfaceState) -> InterfaceState:
    return state


def key_of_action(state: InterfaceState, key: str) -> str:
    matching = filter(lambda item: item.key == key, state.menu)
    return next(matching, MenuItem("", "", "")).action


def handle_menu_key(context: InterfaceContext, state: InterfaceState, key: str) -> InterfaceState:
    action = key_of_action(state, key)
    if action:
        return run_action(context, state, action)
    return menu_navigation(key)(context, state)


def handle_prompt_key(context: InterfaceContext, state: InterfaceState, key: str) -> InterfaceState:
    pending = state.pending
    if key != "y":
        return replace(state, pending=None, notice=CANCELLED)
    return apply_outcome(replace(state, pending=None), pending.confirmed())


def normal_navigation(key: str) -> Callable[[InterfaceContext, InterfaceState], InterfaceState]:
    if key in DOWN_KEYS:
        return lambda context, state: move_selection(context, state, 1)
    if key in UP_KEYS:
        return lambda context, state: move_selection(context, state, -1)
    return {"ENTER": open_menu, "q": finish}.get(key, keep_state)


def handle_normal_key(context: InterfaceContext, state: InterfaceState, key: str) -> InterfaceState:
    return normal_navigation(key)(context, state)


def handle_key(context: InterfaceContext, state: InterfaceState, key: str) -> InterfaceState:
    state = clamp_selection(context, replace(state, notice=""))
    if state.pending is not None:
        return handle_prompt_key(context, state, key)
    if state.menu:
        return handle_menu_key(context, state, key)
    return handle_normal_key(context, state, key)


def click_on_row(context: InterfaceContext, state: InterfaceState, click: Click) -> InterfaceState:
    selected = replace(state, selected=click.line.selection_index)
    return open_menu(context, selected) if click.is_secondary else selected


def click_in_menu(context: InterfaceContext, state: InterfaceState, click: Click) -> InterfaceState:
    if click.line.kind == "menu":
        return run_action(context, state, state.menu[click.line.selection_index].action)
    return close_menu(context, state)


def handle_click(context: InterfaceContext, state: InterfaceState, click: Click) -> InterfaceState:
    state = clamp_selection(context, replace(state, notice=""))
    if state.pending is not None:
        return replace(state, pending=None, notice=CANCELLED)
    if state.menu:
        return click_in_menu(context, state, click)
    if click.line.kind == "row":
        return click_on_row(context, state, click)
    return state
