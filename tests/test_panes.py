"""Pane records: tmux's pane listing parsed into plain data."""

import dataclasses

import pytest

from tmux_sidepanel.panes import (
    FIELD_SEPARATOR,
    PANE_FIELDS,
    PANE_FORMAT,
    PaneParseError,
    PaneRecord,
    parse_pane_records,
)

DEFAULT_VALUES = {
    "session_name": "main",
    "window_identifier": "@3",
    "window_index": "3",
    "window_name": "trydent",
    "pane_identifier": "%7",
    "pane_index": "2",
    "terminal": "/dev/pts/6",
    "current_command": "claude",
    "current_directory": "/home/someone/project",
    "is_active": "1",
    "is_window_active": "1",
    "is_session_attached": "1",
    "agent_state": "working",
    "agent_kind": "claude",
    "agent_name": "",
    "agent_subagents": "aaa111:Explore",
    "is_panel": "",
}


def build_line(**overrides):
    values = {**DEFAULT_VALUES, **overrides}
    return FIELD_SEPARATOR.join(values[field.name] for field in PANE_FIELDS)


def parse_one(**overrides):
    return parse_pane_records(build_line(**overrides))[0]


def test_the_format_has_one_expression_per_field():
    expressions = [field.expression for field in PANE_FIELDS]
    assert PANE_FORMAT.split(FIELD_SEPARATOR) == expressions


def test_the_fields_match_the_record():
    record_fields = [field.name for field in dataclasses.fields(PaneRecord)]
    assert [field.name for field in PANE_FIELDS] == record_fields


def test_every_expression_reads_a_tmux_variable():
    for field in PANE_FIELDS:
        assert field.expression.startswith("#{")


def test_parses_a_line_into_a_record():
    assert parse_one() == PaneRecord(
        session_name="main",
        window_identifier="@3",
        window_index=3,
        window_name="trydent",
        pane_identifier="%7",
        pane_index=2,
        terminal="pts/6",
        current_command="claude",
        current_directory="/home/someone/project",
        is_active=True,
        is_window_active=True,
        is_session_attached=True,
        agent_state="working",
        agent_kind="claude",
        agent_name="",
        agent_subagents="aaa111:Explore",
        is_panel=False,
    )


@pytest.mark.parametrize(
    ("terminal", "expected"),
    [("/dev/pts/6", "pts/6"), ("pts/6", "pts/6"), ("", "")],
)
def test_the_device_prefix_is_removed_from_the_terminal(terminal, expected):
    assert parse_one(terminal=terminal).terminal == expected


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("0", False), ("", False)])
def test_flags(value, expected):
    assert parse_one(is_active=value).is_active is expected


def test_the_panel_marker_is_read_from_its_option():
    assert parse_one(is_panel="1").is_panel is True
    assert parse_one(is_panel="").is_panel is False


@pytest.mark.parametrize(("count", "expected"), [("0", False), ("1", True), ("2", True)])
def test_a_session_counts_as_attached_when_a_client_is_attached(count, expected):
    assert parse_one(is_session_attached=count).is_session_attached is expected


def test_empty_options_stay_empty():
    record = parse_one(agent_state="", agent_kind="", agent_subagents="")
    assert (record.agent_state, record.agent_kind, record.agent_subagents) == ("", "", "")


def test_window_names_may_contain_spaces_and_unicode():
    name = "my project caf" + chr(0xE9)  # written as a number so this file stays plain ASCII
    assert parse_one(window_name=name).window_name == name


def test_reads_several_lines_and_skips_blank_ones():
    output = build_line(pane_identifier="%1") + "\n\n" + build_line(pane_identifier="%2") + "\n"
    records = parse_pane_records(output)
    assert [record.pane_identifier for record in records] == ["%1", "%2"]


def test_empty_output_gives_no_records():
    assert parse_pane_records("") == []


def test_the_wrong_number_of_fields_names_the_line():
    output = build_line() + "\nonly" + FIELD_SEPARATOR + "two\n"
    with pytest.raises(PaneParseError, match="line 2"):
        parse_pane_records(output)


def test_a_bad_number_names_the_line():
    with pytest.raises(PaneParseError, match="line 1"):
        parse_pane_records(build_line(window_index="three"))
