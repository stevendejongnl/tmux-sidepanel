"""The section that shows the output of a command of the user, one row for each line."""

from dataclasses import dataclass
from itertools import islice

from tmux_sidepanel.configuration import Section
from tmux_sidepanel.pane_rows import section_view
from tmux_sidepanel.rows import Row, SectionView, format_row
from tmux_sidepanel.snapshot import Snapshot

MAXIMUM_ROWS = 50
MAXIMUM_LINE_CHARACTERS = 200


@dataclass(frozen=True)
class CustomSubject:
    line: str


def has_text(line: str) -> bool:
    return bool(line.strip())


def output_lines(output: str) -> list[str]:
    lines = filter(has_text, output.splitlines())
    return [line[:MAXIMUM_LINE_CHARACTERS] for line in islice(lines, MAXIMUM_ROWS)]


def custom_row(section: Section, line: str) -> Row:
    return Row(format_row(section.row_format, {"text": line}), "", False, CustomSubject(line))


def build_custom_section(section: Section, snapshot: Snapshot) -> SectionView:
    output = snapshot.custom_outputs.get(section.identifier, "")
    return section_view(section, tuple(custom_row(section, line) for line in output_lines(output)))
