"""Mouse events of the terminal, turned into the clicks that the panel understands."""

import curses

from tmux_sidepanel.interface_state import Click
from tmux_sidepanel.panel_layout import Line

PRIMARY_BUTTONS = curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED
SECONDARY_BUTTONS = curses.BUTTON3_PRESSED | curses.BUTTON3_CLICKED


def click_at(lines: list[Line], row: int, buttons: int) -> Click | None:
    """The click of a mouse event on the line at that screen row, or None to ignore the event."""
    if not buttons & (PRIMARY_BUTTONS | SECONDARY_BUTTONS) or not 0 <= row < len(lines):
        return None
    return Click(lines[row], bool(buttons & SECONDARY_BUTTONS))
