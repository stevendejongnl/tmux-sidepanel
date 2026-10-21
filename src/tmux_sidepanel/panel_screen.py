"""The terminal screen of the panel, drawn with curses.

This is the only module that touches the terminal. What to show and what each key does is decided
by the modules around it, so this one only draws lines and reads keys.
"""

import curses
import os
from dataclasses import dataclass

from tmux_sidepanel.application import Application, current_panel, perform_for
from tmux_sidepanel.footer import footer_lines
from tmux_sidepanel.interface_state import (
    InterfaceContext,
    InterfaceState,
    handle_click,
    handle_key,
)
from tmux_sidepanel.key_names import key_name
from tmux_sidepanel.line_style import LineStyle, line_style
from tmux_sidepanel.mouse import click_at
from tmux_sidepanel.panel_layout import Line, build_lines
from tmux_sidepanel.rows import PanelView
from tmux_sidepanel.screen_layout import compose_screen, line_of_selection

COLORS = {
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "blue": curses.COLOR_BLUE,
}
ESCAPE_DELAY_MILLISECONDS = "25"


def color_pairs() -> dict[str, int]:
    return {name: number for number, name in enumerate(COLORS, start=1)}


def start_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    for name, number in color_pairs().items():
        curses.init_pair(number, COLORS[name], -1)


def emphasis_of(style: LineStyle) -> int:
    attributes = curses.A_BOLD if style.is_bold else 0
    attributes |= curses.A_REVERSE if style.is_reversed else 0
    return attributes | (curses.A_DIM if style.is_dim else 0)


def attribute_of(style: LineStyle) -> int:
    color = curses.color_pair(color_pairs()[style.color]) if style.color else 0
    return emphasis_of(style) | color


def draw_line(screen: curses.window, row: int, line: Line, is_selected: bool) -> None:
    width = screen.getmaxyx()[1]
    try:
        screen.addnstr(
            row,
            0,
            line.text.ljust(width - 1),
            width - 1,
            attribute_of(line_style(line, is_selected)),
        )
    except curses.error:
        return


def screen_lines(screen: curses.window, panel: PanelView, state: InterfaceState) -> list[Line]:
    height, width = screen.getmaxyx()
    body = build_lines(panel, width - 1)
    selected_line = line_of_selection(body, state.selected)
    return compose_screen(body, footer_lines(state, width - 1), height, selected_line)


def draw(screen: curses.window, panel: PanelView, state: InterfaceState) -> None:
    lines = screen_lines(screen, panel, state)
    screen.erase()
    for row, line in enumerate(lines):
        draw_line(screen, row, line, line.selection_index == state.selected and line.kind == "row")
    screen.refresh()


def read_key(screen: curses.window) -> str:
    return key_name(screen.getch())


def is_idle(state: InterfaceState) -> bool:
    return not state.menu and state.pending is None


def refreshed_panel(application: Application, panel: PanelView, state: InterfaceState) -> PanelView:
    """The panel is kept as it is while a menu or a question is open, so the rows do not move."""
    return current_panel(application) if is_idle(state) else panel


def interface_context(application: Application, panel: PanelView) -> InterfaceContext:
    return InterfaceContext(panel, application.configuration, perform_for(application))


def step(
    application: Application, panel: PanelView, state: InterfaceState, key: str
) -> InterfaceState:
    if not key:
        return state
    return handle_key(interface_context(application, panel), state, key)


@dataclass(frozen=True)
class MouseEvent:
    row: int
    buttons: int


def mouse_event() -> MouseEvent:
    """The mouse event that the terminal reported, or one without buttons when it is lost."""
    try:
        event = curses.getmouse()
    except curses.error:
        return MouseEvent(0, 0)
    return MouseEvent(row=event[2], buttons=event[4])


def click_step(
    screen: curses.window, application: Application, panel: PanelView, state: InterfaceState
) -> InterfaceState:
    event = mouse_event()
    click = click_at(screen_lines(screen, panel, state), event.row, event.buttons)
    if click is None:
        return state
    return handle_click(interface_context(application, panel), state, click)


def next_state(
    screen: curses.window, application: Application, panel: PanelView, state: InterfaceState
) -> InterfaceState:
    key = read_key(screen)
    if key == "MOUSE":
        return click_step(screen, application, panel, state)
    return step(application, panel, state, key)


def run_screen(screen: curses.window, application: Application) -> None:
    curses.curs_set(0)
    screen.keypad(True)
    start_colors()
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    curses.mouseinterval(0)
    screen.timeout(int(application.configuration.panel.refresh_seconds * 1000))
    state = InterfaceState()
    panel = current_panel(application)
    while not state.is_finished:
        draw(screen, panel, state)
        state = next_state(screen, application, panel, state)
        panel = refreshed_panel(application, panel, state)


def run_panel(application: Application) -> None:
    os.environ.setdefault("ESCDELAY", ESCAPE_DELAY_MILLISECONDS)
    curses.wrapper(run_screen, application)
