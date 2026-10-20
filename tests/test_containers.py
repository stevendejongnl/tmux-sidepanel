"""Containers: docker's listing parsed, placed in windows by directory, or grouped by project."""

from tests.builders import build_container, build_pane_record
from tmux_sidepanel.containers import (
    DOCKER_FIELD_SEPARATOR,
    DOCKER_FORMAT,
    ContainerGroup,
    parse_containers,
    place_containers,
)

TRYDENT_DIRECTORY = "/home/someone/trydent"
SHOP_DIRECTORY = "/mnt/data/shop"


def build_line(container):
    values = [
        container.name,
        container.status,
        container.service,
        container.working_directory,
        container.project,
    ]
    return DOCKER_FIELD_SEPARATOR.join(values)


class TestParse:
    def test_the_format_asks_for_five_fields(self):
        assert len(DOCKER_FORMAT.split(DOCKER_FIELD_SEPARATOR)) == 5

    def test_reads_a_line(self):
        container = build_container(
            "trydent-trytond-1", "Up 6 hours", TRYDENT_DIRECTORY, "trydent", "trytond"
        )
        assert parse_containers(build_line(container)) == [container]

    def test_reads_several_lines_and_skips_blank_ones(self):
        output = (
            build_line(build_container("a-1")) + "\n\n" + build_line(build_container("b-1")) + "\n"
        )
        assert [container.name for container in parse_containers(output)] == ["a-1", "b-1"]

    def test_a_container_without_compose_labels_has_empty_fields(self):
        output = "standalone\tUp 2 days\t\t\t\n"
        container = parse_containers(output)[0]
        assert (container.service, container.working_directory, container.project) == ("", "", "")

    def test_a_short_line_is_padded(self):
        container = parse_containers("standalone\tUp 2 days\n")[0]
        assert container.status == "Up 2 days"
        assert container.project == ""

    def test_empty_output_gives_no_containers(self):
        assert parse_containers("") == []

    def test_an_unhealthy_status_is_recognised(self):
        assert build_container(status="Up 6 hours (unhealthy)").is_unhealthy
        assert not build_container(status="Up 6 hours (healthy)").is_unhealthy


class TestPlacement:
    def panes(self):
        return [
            build_pane_record(
                pane_identifier="%1", window_identifier="@1", current_directory=TRYDENT_DIRECTORY
            ),
            build_pane_record(
                pane_identifier="%2",
                window_identifier="@2",
                current_directory="/home/someone/other",
            ),
        ]

    def test_a_container_binds_to_the_pane_in_its_project_directory(self):
        container = build_container("trydent-1", directory=TRYDENT_DIRECTORY)
        placement = place_containers([container], self.panes())
        assert [bound.pane.pane_identifier for bound in placement.bound] == ["%1"]
        assert placement.bound[0].container == container
        assert placement.unbound == []

    def test_a_pane_inside_a_subfolder_of_the_project_counts(self):
        panes = [
            build_pane_record(pane_identifier="%9", current_directory=TRYDENT_DIRECTORY + "/src")
        ]
        placement = place_containers([build_container(directory=TRYDENT_DIRECTORY)], panes)
        assert placement.bound[0].pane.pane_identifier == "%9"

    def test_a_folder_that_only_starts_with_the_same_text_does_not_count(self):
        panes = [build_pane_record(current_directory=TRYDENT_DIRECTORY + "-old")]
        placement = place_containers([build_container(directory=TRYDENT_DIRECTORY)], panes)
        assert placement.bound == []
        assert len(placement.unbound) == 1

    def test_a_trailing_slash_is_ignored(self):
        panes = [build_pane_record(current_directory=TRYDENT_DIRECTORY + "/")]
        placement = place_containers([build_container(directory=TRYDENT_DIRECTORY + "/")], panes)
        assert len(placement.bound) == 1

    def test_the_first_matching_pane_wins(self):
        panes = [
            build_pane_record(pane_identifier="%1", current_directory=TRYDENT_DIRECTORY),
            build_pane_record(pane_identifier="%2", current_directory=TRYDENT_DIRECTORY),
        ]
        placement = place_containers([build_container(directory=TRYDENT_DIRECTORY)], panes)
        assert placement.bound[0].pane.pane_identifier == "%1"

    def test_the_panel_itself_never_counts_as_a_pane(self):
        panes = [build_pane_record(current_directory=TRYDENT_DIRECTORY, is_panel=True)]
        placement = place_containers([build_container(directory=TRYDENT_DIRECTORY)], panes)
        assert placement.bound == []

    def test_a_container_without_a_directory_is_unbound(self):
        placement = place_containers([build_container("standalone")], self.panes())
        assert placement.bound == []
        assert [group.label for group in placement.unbound] == ["standalone"]


class TestGroups:
    def shop(self, number, status="Up 6 hours"):
        return build_container(f"shop-web-{number}", status, SHOP_DIRECTORY, "shop")

    def groups(self, containers):
        return place_containers(containers, []).unbound

    def test_containers_of_one_project_become_one_group(self):
        groups = self.groups([self.shop(1), self.shop(2), self.shop(3)])
        assert len(groups) == 1
        assert groups[0].label == "shop (3)"
        assert groups[0].container_names == ("shop-web-1", "shop-web-2", "shop-web-3")

    def test_a_group_remembers_the_project_and_its_directory(self):
        group = self.groups([self.shop(1), self.shop(2)])[0]
        assert (group.project, group.working_directory) == ("shop", SHOP_DIRECTORY)

    def test_a_single_container_keeps_its_own_name(self):
        assert self.groups([self.shop(1)])[0].label == "shop-web-1"

    def test_the_status_is_shortened(self):
        assert self.groups([self.shop(1)])[0].status == "6h"

    def test_an_unhealthy_container_marks_the_group(self):
        group = self.groups([self.shop(1), self.shop(2, "Up 6 hours (unhealthy)")])[0]
        assert group.status.endswith("unhealthy")

    def test_a_single_unhealthy_container_does_not_repeat_the_word(self):
        group = self.groups([self.shop(1, "Up 6 hours (unhealthy)")])[0]
        assert group.status == "6h (unhealthy)"

    def test_an_unhealthy_container_after_a_healthy_one_still_marks_the_group(self):
        group = self.groups([self.shop(1), self.shop(2, "Up 6 hours (unhealthy)")])[0]
        assert group.status == "6h unhealthy"

    def test_projects_are_listed_in_name_order(self):
        other = build_container("blog-1", "Up 1 hour", "/mnt/data/blog", "blog")
        labels = [group.label for group in self.groups([self.shop(1), other])]
        assert labels == ["blog-1", "shop-web-1"]

    def test_a_group_is_a_dataclass_with_names(self):
        group = self.groups([self.shop(1)])[0]
        assert isinstance(group, ContainerGroup)
