"""The lines under the panel: a question to confirm, the menu of a row, or a notice."""

from tmux_sidepanel.interface_state import InterfaceState
from tmux_sidepanel.menus import MenuItem
from tmux_sidepanel.panel_layout import NO_SELECTION, Line, clip_text


def footer_line(text: str, kind: str, width: int, is_highlighted: bool = False) -> Line:
    return Line(clip_text(text, width), kind, "", is_highlighted, NO_SELECTION)


def menu_line(item: MenuItem, is_highlighted: bool, width: int) -> Line:
    return footer_line(f" {item.key}  {item.label}", "menu", width, is_highlighted)


def menu_lines(state: InterfaceState, width: int) -> list[Line]:
    return [
        menu_line(item, number == state.menu_selected, width)
        for number, item in enumerate(state.menu)
    ]


def footer_lines(state: InterfaceState, width: int) -> list[Line]:
    if state.pending is not None:
        return [footer_line(state.pending.prompt, "prompt", width)]
    if state.menu:
        return menu_lines(state, width)
    if state.notice:
        return [footer_line(state.notice, "notice", width)]
    return []
