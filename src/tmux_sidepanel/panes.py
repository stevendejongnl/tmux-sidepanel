"""Pane records: what tmux says about every pane, parsed into plain data.

``PANE_FORMAT`` is the format string to give to ``tmux list-panes -a -F``. Each line of the
output is then read by ``parse_pane_records``.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.options import (
    OPTION_KIND,
    OPTION_NAME,
    OPTION_PANEL,
    OPTION_STATE,
    OPTION_SUBAGENTS,
    OPTION_TASKS,
    option_expression,
)

FIELD_SEPARATOR = "\x1f"
# Older versions of tmux print the separator on the command line as the text \037. A backslash
# in front of it is the escape of a backslash in a value, so that one is not a separator.
ESCAPED_FIELD_SEPARATOR = re.compile(r"(?<!\\)\\037")
# The same versions escape a backslash, a dollar sign and unprintable characters in every value.
PRINTED_ESCAPE = re.compile(r"\\(?:(?P<symbol>[\\$])|(?P<octal>[0-7]{3}))")
OCTAL_BASE = 8


class PaneParseError(ValueError):
    """A line of the pane listing could not be read."""


@dataclass(frozen=True)
class PaneRecord:
    session_name: str
    session_identifier: str
    window_identifier: str
    window_index: int
    window_name: str
    pane_identifier: str
    pane_index: int
    terminal: str  # without the /dev/ prefix
    current_command: str
    current_directory: str
    is_active: bool
    is_window_active: bool
    is_session_attached: bool
    agent_state: str
    agent_kind: str
    agent_name: str
    agent_subagents: str
    agent_tasks: str
    is_panel: bool
    is_last: bool

    @property
    def is_focused(self) -> bool:
        return self.is_active and self.is_window_active and self.is_session_attached

    def is_not_panel(self) -> bool:
        return not self.is_panel

    def has_agent_state(self) -> bool:
        return bool(self.agent_state)


def to_text(value: str) -> str:
    return value


def to_integer(value: str) -> int:
    return int(value)


def to_boolean(value: str) -> bool:
    return value == "1"


def to_attached(value: str) -> bool:
    return int(value) > 0


def to_terminal(value: str) -> str:
    return value.removeprefix("/dev/")


@dataclass(frozen=True)
class PaneField:
    name: str
    expression: str
    convert: Callable[[str], Any]


PANE_FIELDS = (
    PaneField("session_name", "#{session_name}", to_text),
    PaneField("session_identifier", "#{session_id}", to_text),
    PaneField("window_identifier", "#{window_id}", to_text),
    PaneField("window_index", "#{window_index}", to_integer),
    PaneField("window_name", "#{window_name}", to_text),
    PaneField("pane_identifier", "#{pane_id}", to_text),
    PaneField("pane_index", "#{pane_index}", to_integer),
    PaneField("terminal", "#{pane_tty}", to_terminal),
    PaneField("current_command", "#{pane_current_command}", to_text),
    PaneField("current_directory", "#{pane_current_path}", to_text),
    PaneField("is_active", "#{pane_active}", to_boolean),
    PaneField("is_window_active", "#{window_active}", to_boolean),
    PaneField("is_session_attached", "#{session_attached}", to_attached),
    PaneField("agent_state", option_expression(OPTION_STATE), to_text),
    PaneField("agent_kind", option_expression(OPTION_KIND), to_text),
    PaneField("agent_name", option_expression(OPTION_NAME), to_text),
    PaneField("agent_subagents", option_expression(OPTION_SUBAGENTS), to_text),
    PaneField("agent_tasks", option_expression(OPTION_TASKS), to_text),
    PaneField("is_panel", option_expression(OPTION_PANEL), to_boolean),
    PaneField("is_last", "#{pane_last}", to_boolean),
)

PANE_FORMAT = FIELD_SEPARATOR.join(field.expression for field in PANE_FIELDS)


@dataclass(frozen=True)
class OutputLine:
    number: int
    text: str

    def has_text(self) -> bool:
        return bool(self.text.strip())


def require_field_count(values: list[str], line_number: int) -> None:
    if len(values) != len(PANE_FIELDS):
        raise PaneParseError(
            f"line {line_number}: expected {len(PANE_FIELDS)} fields, found {len(values)}"
        )


def convert_fields(values: list[str]) -> dict[str, Any]:
    return {
        field.name: field.convert(value) for field, value in zip(PANE_FIELDS, values, strict=True)
    }


def restore_printed_escape(match: re.Match[str]) -> str:
    symbol = match.group("symbol")
    return symbol if symbol else chr(int(match.group("octal"), OCTAL_BASE))


def split_fields(text: str) -> list[str]:
    """Split a line into its values. Output of an older tmux is escaped, so it is restored."""
    if not ESCAPED_FIELD_SEPARATOR.search(text):
        return text.split(FIELD_SEPARATOR)
    printed = ESCAPED_FIELD_SEPARATOR.split(text)
    return [PRINTED_ESCAPE.sub(restore_printed_escape, value) for value in printed]


def parse_pane_record(line: OutputLine) -> PaneRecord:
    values = split_fields(line.text)
    require_field_count(values, line.number)
    try:
        converted = convert_fields(values)
    except ValueError as error:
        raise PaneParseError(f"line {line.number}: {error}") from error
    return PaneRecord(**converted)


def parse_pane_records(output: str) -> list[PaneRecord]:
    """Read the output of ``tmux list-panes -a -F PANE_FORMAT``."""
    lines = [OutputLine(number, text) for number, text in enumerate(output.splitlines(), start=1)]
    return [parse_pane_record(line) for line in filter(OutputLine.has_text, lines)]
