"""Action menus: which actions a row offers, with the keys and the choices of the configuration."""

import textwrap

from tests.builders import build_pane_record, build_process, section_named
from tmux_sidepanel.agents import Subagent
from tmux_sidepanel.configuration import parse_configuration
from tmux_sidepanel.custom_rows import CustomSubject
from tmux_sidepanel.menus import MenuItem, menu_items
from tmux_sidepanel.pane_rows import PaneSubject, SubagentSubject
from tmux_sidepanel.processes import Zombie
from tmux_sidepanel.service_rows import ServiceEntry, ServiceSubject
from tmux_sidepanel.zombie_rows import ZombieSubject


def entries(items):
    return [(item.key, item.action) for item in items]


def labels(items):
    return {item.action: item.label for item in items}


def service_entry(**overrides):
    values = {
        "kind": "test",
        "command": "pytest",
        "age": "3m",
        "is_container": False,
        "pane_identifier": "%5",
        "directory": "/home/someone/shop",
        "process_identifier": 10,
        "container_names": (),
        "project": "",
    }
    return ServiceEntry(**{**values, **overrides})


def zombie_subject(status_flags="Sl", directory="/home/someone/shop", pane_identifier=""):
    zombie = Zombie(build_process(5, status_flags=status_flags), "no pane")
    return ZombieSubject(zombie, directory, pane_identifier)


class TestPaneMenu:
    def test_a_plain_pane_offers_the_default_keys(self):
        subject = PaneSubject(build_pane_record(), "")
        assert entries(menu_items(section_named("panes"), subject)) == [
            ("g", "go"),
            ("z", "zoom"),
            ("x", "interrupt"),
            ("o", "directory"),
            ("X", "close"),
        ]

    def test_the_labels_say_what_each_action_does(self):
        subject = PaneSubject(build_pane_record(), "")
        assert labels(menu_items(section_named("panes"), subject)) == {
            "go": "go to pane",
            "zoom": "zoom pane",
            "interrupt": "interrupt (Ctrl-C)",
            "directory": "open directory in new window",
            "close": "close pane (kill)",
        }

    def test_an_agent_is_interrupted_with_escape(self):
        subject = PaneSubject(build_pane_record(), "working")
        assert labels(menu_items(section_named("panes"), subject))["interrupt"] == "interrupt (Esc)"

    def test_a_pane_without_a_directory_has_no_directory_action(self):
        subject = PaneSubject(build_pane_record(current_directory=""), "")
        assert "directory" not in labels(menu_items(section_named("panes"), subject))


class TestSubagentMenu:
    def test_a_subagent_can_be_found_through_its_parent(self):
        subject = SubagentSubject(build_pane_record(), Subagent("aaa111", "Explore"), "working")
        items = menu_items(section_named("subagents"), subject)
        assert entries(items) == [("g", "go"), ("t", "tasks")]
        assert labels(items)["tasks"] == "open in /tasks"


class TestServiceMenu:
    def test_a_process_can_be_stopped_and_killed_but_not_restarted(self):
        subject = ServiceSubject(service_entry())
        items = menu_items(section_named("services"), subject)
        assert entries(items) == [("g", "go"), ("x", "stop"), ("o", "directory"), ("X", "kill")]
        assert labels(items)["stop"] == "stop (graceful)"
        assert labels(items)["kill"] == "kill (force)"

    def test_a_container_can_also_be_restarted_and_show_its_logs(self):
        entry = service_entry(kind="docker", is_container=True, container_names=("shop-web-1",))
        items = menu_items(section_named("services"), ServiceSubject(entry))
        assert [item.action for item in items] == [
            "go",
            "stop",
            "restart",
            "logs",
            "directory",
            "kill",
        ]

    def test_a_service_that_no_window_owns_cannot_be_gone_to(self):
        entry = service_entry(kind="docker", is_container=True, pane_identifier="")
        items = menu_items(section_named("other-services"), ServiceSubject(entry))
        assert [item.action for item in items] == ["stop", "restart", "logs", "directory", "kill"]

    def test_a_service_without_a_directory_has_no_directory_action(self):
        subject = ServiceSubject(service_entry(directory=""))
        assert "directory" not in labels(menu_items(section_named("services"), subject))


class TestZombieMenu:
    def test_a_zombie_can_be_opened_terminated_and_killed(self):
        items = menu_items(section_named("zombies"), zombie_subject())
        assert entries(items) == [
            ("o", "open"),
            ("x", "terminate"),
            ("d", "directory"),
            ("X", "kill"),
        ]
        assert labels(items)["open"] == "open (jump or resume in new window)"
        assert labels(items)["terminate"] == "terminate (SIGTERM)"
        assert labels(items)["kill"] == "kill (SIGKILL)"

    def test_a_defunct_process_can_only_have_its_directory_opened(self):
        zombie = Zombie(build_process(5, status_flags="Z"), "defunct")
        subject = ZombieSubject(zombie, "/home/someone/shop", "")
        items = menu_items(section_named("zombies"), subject)
        assert [item.action for item in items] == ["directory"]

    def test_a_defunct_process_without_a_directory_has_no_actions(self):
        zombie = Zombie(build_process(5, status_flags="Z"), "defunct")
        assert menu_items(section_named("zombies"), ZombieSubject(zombie, "", "")) == []


class TestCustomMenu:
    def test_a_custom_row_has_no_actions(self):
        section = parse_configuration(
            textwrap.dedent(
                """
                [[sections]]
                type = "custom"
                identifier = "ports"
                command = ["ss"]
                """
            )
        ).sections[0]
        assert menu_items(section, CustomSubject("8000 api")) == []


class TestConfiguration:
    def section(self, text):
        return parse_configuration(textwrap.dedent(text)).sections[0]

    def test_a_disabled_action_is_not_offered(self):
        section = self.section(
            """
            [[sections]]
            type = "services"
            [sections.menu]
            disabled_actions = ["kill"]
            """
        )
        items = menu_items(section, ServiceSubject(service_entry()))
        assert "kill" not in [item.action for item in items]

    def test_a_remapped_key_is_used(self):
        section = self.section(
            """
            [[sections]]
            type = "services"
            [sections.menu.keys]
            stop = "s"
            """
        )
        items = menu_items(section, ServiceSubject(service_entry()))
        assert ("s", "stop") in entries(items)

    def test_a_menu_item_is_a_dataclass_with_names(self):
        item = menu_items(section_named("panes"), PaneSubject(build_pane_record(), ""))[0]
        assert item == MenuItem("g", "go to pane", "go")
