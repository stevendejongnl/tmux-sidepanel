"""The section that lists agent processes no pane shows, and the section of custom commands."""

import textwrap

from tests.builders import build_pane_record, build_process, section_named
from tmux_sidepanel.configuration import AgentSettings, parse_configuration
from tmux_sidepanel.custom_rows import (
    MAXIMUM_LINE_CHARACTERS,
    MAXIMUM_ROWS,
    CustomSubject,
    build_custom_section,
)
from tmux_sidepanel.snapshot import Snapshot
from tmux_sidepanel.zombie_rows import ZombieSubject, build_zombie_section

AGENTS = AgentSettings()


def snapshot_of(processes=(), panes=(), directories=None):
    table = {process.process_identifier: process for process in processes}
    return Snapshot(
        panes=list(panes),
        window_identifier="@1",
        process_table=table,
        process_directories=directories or {},
    )


def zombie_view(snapshot):
    return build_zombie_section(section_named("zombies"), snapshot, AGENTS)


def texts(view):
    return [row.text for row in view.rows]


class TestZombies:
    def test_an_agent_without_a_pane_is_listed_with_its_folder_and_age(self):
        process = build_process(123, "/opt/bin/claude", age_seconds=120)
        snapshot = snapshot_of([process], directories={123: "/home/someone/shop"})
        assert texts(zombie_view(snapshot)) == ["Z shop 123 no pane 2m"]

    def test_an_unknown_folder_shows_a_question_mark(self):
        snapshot = snapshot_of([build_process(123, "/opt/bin/claude")])
        assert texts(zombie_view(snapshot)) == ["Z ? 123 no pane 10s"]

    def test_a_row_is_shown_as_a_problem(self):
        snapshot = snapshot_of([build_process(123)])
        assert zombie_view(snapshot).rows[0].state == "blocked"

    def test_an_agent_on_a_pane_is_not_a_zombie(self):
        pane = build_pane_record(terminal="pts/1")
        snapshot = snapshot_of([build_process(123, terminal="pts/1")], [pane])
        assert zombie_view(snapshot).rows == ()

    def test_a_helper_of_a_live_session_is_not_a_zombie(self):
        pane = build_pane_record(terminal="pts/1")
        session = build_process(100, terminal="pts/1")
        helper = build_process(101, "/opt/bin/claude --output-format stream-json", parent=100)
        assert zombie_view(snapshot_of([session, helper], [pane])).rows == ()

    def test_a_stopped_agent_on_a_pane_remembers_the_pane(self):
        pane = build_pane_record(pane_identifier="%4", terminal="pts/1")
        process = build_process(123, terminal="pts/1", status_flags="T")
        subject = zombie_view(snapshot_of([process], [pane])).rows[0].subject
        assert isinstance(subject, ZombieSubject)
        assert subject.pane_identifier == "%4"
        assert subject.zombie.reason == "stopped"

    def test_a_zombie_without_a_pane_has_no_pane_identifier(self):
        subject = zombie_view(snapshot_of([build_process(123)])).rows[0].subject
        assert subject.pane_identifier == ""

    def test_the_row_remembers_the_directory(self):
        snapshot = snapshot_of([build_process(123)], directories={123: "/home/someone/shop"})
        assert zombie_view(snapshot).rows[0].subject.directory == "/home/someone/shop"

    def test_a_defunct_agent_is_listed_too(self):
        process = build_process(123, terminal="pts/1", status_flags="Z")
        pane = build_pane_record(terminal="pts/1")
        assert "defunct" in texts(zombie_view(snapshot_of([process], [pane])))[0]

    def test_the_agent_names_come_from_the_settings(self):
        process = build_process(123, "/usr/bin/codex exec")
        snapshot = snapshot_of([process])
        assert zombie_view(snapshot).rows == ()
        view = build_zombie_section(
            section_named("zombies"), snapshot, AgentSettings(names=("codex",))
        )
        assert len(view.rows) == 1

    def test_the_rows_are_ordered_by_process_identifier(self):
        snapshot = snapshot_of([build_process(300), build_process(100), build_process(200)])
        assert [
            row.subject.zombie.process.process_identifier for row in zombie_view(snapshot).rows
        ] == [
            100,
            200,
            300,
        ]


class TestCustomSection:
    CONFIGURATION = """
        [[sections]]
        type = "custom"
        identifier = "ports"
        title = "PORTS"
        command = ["ss", "-ltn"]
        """

    def build(self, output, text=CONFIGURATION):
        section = parse_configuration(textwrap.dedent(text)).sections[0]
        snapshot = Snapshot(panes=[], window_identifier="@1", custom_outputs={"ports": output})
        return build_custom_section(section, snapshot)

    def test_every_line_of_the_output_is_a_row(self):
        assert texts(self.build("8000 api\n8001 web\n")) == ["8000 api", "8001 web"]

    def test_blank_lines_are_skipped(self):
        assert texts(self.build("one\n\n  \ntwo")) == ["one", "two"]

    def test_no_output_gives_no_rows(self):
        assert self.build("").rows == ()

    def test_a_section_without_any_output_gives_no_rows(self):
        section = parse_configuration(textwrap.dedent(self.CONFIGURATION)).sections[0]
        snapshot = Snapshot(panes=[], window_identifier="@1")
        assert build_custom_section(section, snapshot).rows == ()

    def test_the_title_comes_from_the_section(self):
        assert self.build("x").title == "PORTS"

    def test_too_many_lines_are_cut(self):
        output = "\n".join(f"line {number}" for number in range(MAXIMUM_ROWS + 20))
        assert len(self.build(output).rows) == MAXIMUM_ROWS

    def test_a_long_line_is_cut(self):
        text = texts(self.build("x" * (MAXIMUM_LINE_CHARACTERS + 100)))[0]
        assert len(text) == MAXIMUM_LINE_CHARACTERS

    def test_escape_sequences_in_the_output_cannot_reach_the_terminal(self):
        assert "\x1b" not in texts(self.build("\x1b[2Jcleared"))[0]

    def test_the_row_format_of_the_section_is_used(self):
        text = self.CONFIGURATION + '        row_format = "> {text}"\n'
        assert texts(self.build("8000 api", text)) == ["> 8000 api"]

    def test_the_row_remembers_its_line_and_has_no_state(self):
        row = self.build("8000 api").rows[0]
        assert row.subject == CustomSubject("8000 api")
        assert row.state == ""
        assert row.is_active is False
