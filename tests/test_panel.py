"""The whole panel: the sections of the configuration, in order, built from a snapshot."""

import textwrap

from tests.builders import build_pane_record, build_process
from tmux_sidepanel.configuration import default_configuration, parse_configuration
from tmux_sidepanel.panel import build_panel
from tmux_sidepanel.snapshot import Snapshot


def snapshot_of(panes=(), processes=(), custom_outputs=None):
    return Snapshot(
        panes=list(panes),
        window_identifier="@1",
        process_table={process.process_identifier: process for process in processes},
        custom_outputs=custom_outputs or {},
    )


def configuration_from(text):
    return parse_configuration(textwrap.dedent(text))


def identifiers(panel):
    return [view.identifier for view in panel.sections]


def test_the_default_configuration_gives_the_five_sections_in_order():
    panel = build_panel(default_configuration(), snapshot_of())
    assert identifiers(panel) == ["panes", "subagents", "services", "other-services", "zombies"]


def test_an_empty_snapshot_gives_empty_sections_with_their_titles():
    panel = build_panel(default_configuration(), snapshot_of())
    assert all(view.is_empty for view in panel.sections)
    assert [view.title for view in panel.sections][0] == "PANES"


def test_the_order_of_the_configuration_is_kept():
    configuration = configuration_from(
        """
        [[sections]]
        type = "zombies"
        [[sections]]
        type = "panes"
        """
    )
    assert identifiers(build_panel(configuration, snapshot_of())) == ["zombies", "panes"]


def test_a_disabled_section_is_left_out():
    configuration = configuration_from(
        """
        [[sections]]
        type = "panes"
        [[sections]]
        type = "zombies"
        enabled = false
        """
    )
    assert identifiers(build_panel(configuration, snapshot_of())) == ["panes"]


def test_an_empty_section_that_asks_to_be_hidden_is_left_out():
    configuration = configuration_from(
        """
        [[sections]]
        type = "panes"
        [[sections]]
        type = "zombies"
        hide_when_empty = true
        """
    )
    assert identifiers(build_panel(configuration, snapshot_of())) == ["panes"]


def test_a_section_that_asks_to_be_hidden_when_empty_stays_when_it_has_rows():
    configuration = configuration_from(
        """
        [[sections]]
        type = "zombies"
        hide_when_empty = true
        """
    )
    panel = build_panel(configuration, snapshot_of(processes=[build_process(123)]))
    assert identifiers(panel) == ["zombies"]
    assert len(panel.sections[0].rows) == 1


def test_the_panes_of_the_window_are_listed():
    panes = [build_pane_record(current_command="vim", current_directory="/x/notes")]
    panel = build_panel(default_configuration(), snapshot_of(panes))
    assert [row.text for row in panel.sections[0].rows] == ["vim notes"]


def test_a_custom_section_shows_the_output_of_its_command():
    configuration = configuration_from(
        """
        [[sections]]
        type = "custom"
        identifier = "ports"
        title = "PORTS"
        command = ["ss", "-ltn"]
        """
    )
    panel = build_panel(configuration, snapshot_of(custom_outputs={"ports": "8000 api\n8001 web"}))
    assert [row.text for row in panel.sections[0].rows] == ["8000 api", "8001 web"]
    assert panel.sections[0].title == "PORTS"


def test_two_sections_of_one_type_each_use_their_own_options():
    configuration = configuration_from(
        """
        [[sections]]
        type = "services"
        identifier = "tests"
        title = "TESTS"
        [[sections.rules]]
        kind = "test"
        pattern = "pytest"

        [[sections]]
        type = "services"
        identifier = "servers"
        title = "SERVERS"
        [[sections.rules]]
        kind = "server"
        pattern = "http.server"
        """
    )
    pane = build_pane_record(terminal="pts/5", current_command="zsh")
    processes = [
        build_process(10, "pytest", terminal="pts/5", status_flags="S+"),
    ]
    panel = build_panel(configuration, snapshot_of([pane], processes))
    assert [len(view.rows) for view in panel.sections] == [1, 0]
