"""The sections that list the services of a window and the services that no window owns."""

import textwrap

from tests.builders import (
    build_container,
    build_pane_record,
    build_process,
    section_named,
)
from tmux_sidepanel.configuration import AgentSettings, parse_configuration
from tmux_sidepanel.service_rows import (
    ServiceSubject,
    build_other_service_section,
    build_service_section,
)
from tmux_sidepanel.snapshot import Snapshot

AGENTS = AgentSettings()
WINDOW = "@1"
SHOP_DIRECTORY = "/home/someone/shop"


def shell_pane(identifier="%5", terminal="pts/5", window=WINDOW, **overrides):
    values = {"current_command": "zsh", "current_directory": SHOP_DIRECTORY, **overrides}
    return build_pane_record(
        pane_identifier=identifier, terminal=terminal, window_identifier=window, **values
    )


def foreground(identifier, arguments, terminal="pts/5", age_seconds=180, flags="S+"):
    return build_process(
        identifier, arguments, terminal=terminal, status_flags=flags, age_seconds=age_seconds
    )


def snapshot_of(panes, processes=(), containers=()):
    table = {process.process_identifier: process for process in processes}
    return Snapshot(
        panes=list(panes),
        window_identifier=WINDOW,
        process_table=table,
        containers=list(containers),
    )


def services_view(snapshot, section=None):
    return build_service_section(section or section_named("services"), snapshot, AGENTS)


def other_view(snapshot):
    return build_other_service_section(section_named("other-services"), snapshot)


def texts(view):
    return [row.text for row in view.rows]


def section_from(text):
    return parse_configuration(textwrap.dedent(text)).sections[0]


class TestProcessServices:
    def test_a_test_runner_in_a_plain_pane_is_listed(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest -x tests")])
        assert texts(services_view(snapshot)) == ["T pytest -x tests 3m"]

    def test_the_directory_of_the_program_is_dropped(self):
        snapshot = snapshot_of(
            [shell_pane()], [foreground(10, "/home/me/.local/bin/uv run pytest")]
        )
        assert texts(services_view(snapshot)) == ["T uv run pytest 3m"]

    def test_a_server_gets_its_own_letter(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "npm run dev")])
        assert texts(services_view(snapshot)) == ["S npm run dev 3m"]

    def test_a_process_that_is_not_in_the_foreground_is_ignored(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest", flags="S")])
        assert services_view(snapshot).rows == ()

    def test_a_process_on_another_terminal_is_ignored(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest", terminal="pts/9")])
        assert services_view(snapshot).rows == ()

    def test_a_pane_of_another_window_is_ignored(self):
        pane = shell_pane(window="@2")
        assert services_view(snapshot_of([pane], [foreground(10, "pytest")])).rows == ()

    def test_a_program_that_is_not_a_service_is_ignored(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "nvim notes.md")])
        assert services_view(snapshot).rows == ()

    def test_an_agent_pane_is_never_a_service(self):
        pane = shell_pane(current_command="claude", agent_state="working")
        assert services_view(snapshot_of([pane], [foreground(10, "pytest")])).rows == ()

    def test_the_first_process_of_a_pane_that_is_a_service_wins(self):
        processes = [foreground(11, "python3 -m http.server"), foreground(10, "uv run pytest")]
        snapshot = snapshot_of([shell_pane()], processes)
        assert texts(services_view(snapshot)) == ["T uv run pytest 3m"]

    def test_the_panel_itself_is_never_a_service(self):
        pane = shell_pane(is_panel=True)
        assert services_view(snapshot_of([pane], [foreground(10, "pytest")])).rows == ()

    def test_every_pane_with_a_service_gets_a_row(self):
        panes = [shell_pane("%5", "pts/5", pane_index=1), shell_pane("%6", "pts/6", pane_index=2)]
        processes = [foreground(10, "pytest"), foreground(20, "npm run dev", terminal="pts/6")]
        assert texts(services_view(snapshot_of(panes, processes))) == [
            "T pytest 3m",
            "S npm run dev 3m",
        ]

    def test_a_test_run_is_shown_as_working_and_the_rest_as_idle(self):
        panes = [shell_pane("%5", "pts/5", pane_index=1), shell_pane("%6", "pts/6", pane_index=2)]
        processes = [foreground(10, "pytest"), foreground(20, "npm run dev", terminal="pts/6")]
        view = services_view(snapshot_of(panes, processes))
        assert [row.state for row in view.rows] == ["working", "idle"]

    def test_the_row_remembers_what_a_menu_needs(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest")])
        subject = services_view(snapshot).rows[0].subject
        assert isinstance(subject, ServiceSubject)
        entry = subject.entry
        assert (entry.kind, entry.pane_identifier, entry.process_identifier) == ("test", "%5", 10)
        assert entry.directory == SHOP_DIRECTORY
        assert entry.is_container is False

    def test_hostile_text_in_a_command_cannot_reach_the_terminal(self):
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest \x1b]0;owned\x07")])
        assert "\x1b" not in texts(services_view(snapshot))[0]


class TestConfiguredRules:
    CONFIGURATION = """
        [[sections]]
        type = "services"
        shims = ['^node\\s+\\S*/safe-chain\\s+']
        [[sections.rules]]
        kind = "build"
        pattern = '^cargo build'
        """

    def test_custom_rules_and_letters_are_used(self):
        section = section_from(self.CONFIGURATION)
        snapshot = snapshot_of([shell_pane()], [foreground(10, "cargo build --release")])
        assert texts(services_view(snapshot, section)) == ["B cargo build --release 3m"]

    def test_the_default_rules_no_longer_apply(self):
        section = section_from(self.CONFIGURATION)
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest")])
        assert services_view(snapshot, section).rows == ()

    def test_a_wrapper_in_front_of_the_command_is_removed(self):
        section = section_from(
            """
            [[sections]]
            type = "services"
            shims = ['^node\\s+\\S*/safe-chain\\s+']
            """
        )
        arguments = "node /home/me/bin/safe-chain pytest -x"
        snapshot = snapshot_of([shell_pane()], [foreground(10, arguments)])
        assert texts(services_view(snapshot, section)) == ["T pytest -x 3m"]

    def test_the_row_format_of_the_section_is_used(self):
        section = section_from(
            """
            [[sections]]
            type = "services"
            row_format = "{kind}: {command}"
            """
        )
        snapshot = snapshot_of([shell_pane()], [foreground(10, "pytest")])
        assert texts(services_view(snapshot, section)) == ["test: pytest"]


class TestContainersInServices:
    def test_a_container_of_the_directory_of_a_pane_is_listed_as_docker(self):
        container = build_container("shop-web-1", "Up 6 hours", SHOP_DIRECTORY, "shop")
        snapshot = snapshot_of([shell_pane()], containers=[container])
        assert texts(services_view(snapshot)) == ["D shop-web-1 6h"]

    def test_the_container_row_remembers_the_container_and_its_pane(self):
        container = build_container("shop-web-1", "Up 6 hours", SHOP_DIRECTORY, "shop")
        snapshot = snapshot_of([shell_pane()], containers=[container])
        entry = services_view(snapshot).rows[0].subject.entry
        assert entry.is_container is True
        assert entry.container_names == ("shop-web-1",)
        assert entry.pane_identifier == "%5"
        assert entry.project == "shop"

    def test_a_container_that_belongs_to_another_window_is_left_out(self):
        container = build_container("shop-web-1", "Up 6 hours", SHOP_DIRECTORY, "shop")
        snapshot = snapshot_of([shell_pane(window="@2")], containers=[container])
        assert services_view(snapshot).rows == ()

    def test_an_unhealthy_status_stays_visible(self):
        container = build_container("shop-web-1", "Up 6 hours (unhealthy)", SHOP_DIRECTORY, "shop")
        snapshot = snapshot_of([shell_pane()], containers=[container])
        assert texts(services_view(snapshot)) == ["D shop-web-1 6h (unhealthy)"]


class TestOtherServices:
    def shop(self, number, status="Up 6 hours"):
        return build_container(f"shop-web-{number}", status, "/mnt/data/shop", "shop")

    def test_containers_that_no_pane_matches_are_grouped_by_project(self):
        snapshot = snapshot_of([shell_pane()], containers=[self.shop(1), self.shop(2)])
        assert texts(other_view(snapshot)) == ["D shop (2) 6h"]

    def test_a_container_that_belongs_to_a_window_is_not_listed_here(self):
        container = build_container("shop-web-1", "Up 6 hours", SHOP_DIRECTORY, "shop")
        assert other_view(snapshot_of([shell_pane()], containers=[container])).rows == ()

    def test_an_unhealthy_container_marks_the_group(self):
        snapshot = snapshot_of([shell_pane()], containers=[self.shop(1, "Up 6 hours (unhealthy)")])
        assert texts(other_view(snapshot)) == ["D shop-web-1 6h (unhealthy)"]

    def test_the_row_remembers_the_group_for_the_menu(self):
        snapshot = snapshot_of([shell_pane()], containers=[self.shop(1), self.shop(2)])
        entry = other_view(snapshot).rows[0].subject.entry
        assert entry.container_names == ("shop-web-1", "shop-web-2")
        assert entry.directory == "/mnt/data/shop"
        assert entry.pane_identifier == ""
        assert entry.project == "shop"

    def test_the_title_comes_from_the_section(self):
        assert other_view(snapshot_of([])).title == "OTHER SERVICES"
