"""How a line looks: its colour and emphasis, decided before anything is drawn."""

from dataclasses import dataclass

from tmux_sidepanel.panel_layout import Line

STATE_COLORS = {"blocked": "red", "done": "green", "working": "yellow", "unknown": "magenta"}
KIND_COLORS = {"prompt": "red", "notice": "cyan"}
SECTION_COLORS = {
    "panes": "blue",
    "subagents": "cyan",
    "services": "green",
    "zombies": "red",
    "custom": "magenta",
}
SECTION_KINDS = {"title", "row"}
BOLD_KINDS = {"title", "prompt"}


@dataclass(frozen=True)
class LineStyle:
    color: str
    is_bold: bool
    is_reversed: bool
    is_dim: bool


def section_color(line: Line) -> str:
    return SECTION_COLORS.get(line.section_type, "") if line.kind in SECTION_KINDS else ""


def line_color(line: Line) -> str:
    return KIND_COLORS.get(line.kind) or STATE_COLORS.get(line.state) or section_color(line)


def is_bold_line(line: Line) -> bool:
    return line.kind in BOLD_KINDS or (line.kind == "row" and line.is_active)


def is_highlighted_menu_item(line: Line) -> bool:
    return line.kind == "menu" and line.is_active


def line_style(line: Line, is_selected: bool) -> LineStyle:
    return LineStyle(
        color=line_color(line),
        is_bold=is_bold_line(line),
        is_reversed=is_selected or is_highlighted_menu_item(line),
        is_dim=line.kind == "empty",
    )
