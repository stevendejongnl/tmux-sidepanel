"""Configuration: defaults, parsing, validation and loading."""

import os
import textwrap
from pathlib import Path

import pytest

from tmux_sidepanel.configuration import (
    ConfigurationError,
    configuration_path,
    default_configuration,
    find_configuration_path,
    load_configuration,
    parse_configuration,
)
from tmux_sidepanel.services import DEFAULT_RULES


def parse_text(text):
    return parse_configuration(textwrap.dedent(text))


def section_identifiers(configuration):
    return [section.identifier for section in configuration.sections]


class TestDefaults:
    def test_the_panel_defaults(self):
        panel = default_configuration().panel
        assert (panel.width, panel.refresh_seconds, panel.position) == (30, 0.5, "left")

    def test_the_panel_opens_with_an_agent_by_default(self):
        assert default_configuration().panel.open_with_agent is True

    def test_the_panel_names_the_window_by_default(self):
        assert default_configuration().panel.name_window is True

    def test_the_agent_defaults(self):
        agents = default_configuration().agents
        assert agents.names == ("claude",)
        assert agents.ignored_arguments == ("--chrome-native-host",)

    def test_the_default_sections_in_order(self):
        configuration = default_configuration()
        assert section_identifiers(configuration) == [
            "panes",
            "subagents",
            "services",
            "other-services",
            "zombies",
        ]
        assert [section.title for section in configuration.sections] == [
            "PANES",
            "AGENTS",
            "SERVICES",
            "OTHER SERVICES",
            "ZOMBIES",
        ]

    def test_every_default_section_is_enabled_and_shows_none_when_empty(self):
        for section in default_configuration().sections:
            assert section.enabled is True
            assert section.hide_when_empty is False
            assert section.empty_text == "none"

    def test_the_default_service_rules_are_the_built_in_rules(self):
        services = default_configuration().sections[2]
        assert services.options["rules"] == DEFAULT_RULES

    def test_the_default_service_letters(self):
        letters = default_configuration().sections[2].options["letters"]
        assert letters == {"docker": "D", "test": "T", "server": "S", "uv": "U"}

    def test_the_default_menu_keys(self):
        panes, subagents, services, other_services, zombies = default_configuration().sections
        assert panes.menu.keys == {
            "go": "g",
            "zoom": "z",
            "interrupt": "x",
            "directory": "o",
            "close": "X",
        }
        assert subagents.menu.keys == {"go": "g", "tasks": "t"}
        assert services.menu.keys["stop"] == "x"
        assert services.menu.keys["kill"] == "X"
        assert "go" not in other_services.menu.keys
        assert zombies.menu.keys == {"open": "o", "terminate": "x", "directory": "d", "kill": "X"}

    def test_empty_text_gives_the_defaults(self):
        assert parse_text("") == default_configuration()


class TestPanelAndAgents:
    def test_overrides_the_panel(self):
        panel = parse_text(
            """
            [panel]
            width = 40
            refresh_seconds = 1
            position = "right"
            """
        ).panel
        assert (panel.width, panel.refresh_seconds, panel.position) == (40, 1.0, "right")

    @pytest.mark.parametrize(
        "line",
        ["width = 5", "width = 500", 'width = "wide"', "width = 30.5", "width = true"],
    )
    def test_refuses_a_bad_width(self, line):
        with pytest.raises(ConfigurationError, match=r"panel\.width"):
            parse_text(f"[panel]\n{line}\n")

    @pytest.mark.parametrize(
        "line",
        ["refresh_seconds = 0.01", "refresh_seconds = 100", 'refresh_seconds = "fast"'],
    )
    def test_refuses_a_bad_refresh(self, line):
        with pytest.raises(ConfigurationError, match=r"panel\.refresh_seconds"):
            parse_text(f"[panel]\n{line}\n")

    def test_opening_with_an_agent_can_be_turned_off(self):
        assert parse_text("[panel]\nopen_with_agent = false\n").panel.open_with_agent is False

    def test_refuses_a_bad_value_for_opening_with_an_agent(self):
        with pytest.raises(ConfigurationError, match=r"panel\.open_with_agent"):
            parse_text('[panel]\nopen_with_agent = "yes"\n')

    def test_naming_the_window_can_be_turned_off(self):
        assert parse_text("[panel]\nname_window = false\n").panel.name_window is False

    def test_refuses_a_bad_value_for_naming_the_window(self):
        with pytest.raises(ConfigurationError, match=r"panel\.name_window"):
            parse_text('[panel]\nname_window = "yes"\n')

    def test_refuses_a_bad_position(self):
        with pytest.raises(ConfigurationError, match=r"panel\.position"):
            parse_text('[panel]\nposition = "top"\n')

    def test_overrides_the_agents(self):
        agents = parse_text(
            """
            [agents]
            names = ["claude", "codex"]
            ignored_arguments = ["--bridge"]
            """
        ).agents
        assert agents.names == ("claude", "codex")
        assert agents.ignored_arguments == ("--bridge",)

    @pytest.mark.parametrize("value", ['"claude"', "[1]", "[]", '[""]'])
    def test_refuses_bad_agent_names(self, value):
        with pytest.raises(ConfigurationError, match=r"agents\.names"):
            parse_text(f"[agents]\nnames = {value}\n")


class TestUnknownKeys:
    def test_refuses_an_unknown_top_level_key(self):
        with pytest.raises(ConfigurationError, match="colour"):
            parse_text("colour = 1\n")

    def test_refuses_an_unknown_panel_key_and_names_the_allowed_ones(self):
        with pytest.raises(ConfigurationError, match=r"panel.*widht.*width"):
            parse_text("[panel]\nwidht = 1\n")

    def test_refuses_an_unknown_section_key(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\].*colour"):
            parse_text('[[sections]]\ntype = "panes"\ncolour = 1\n')


class TestSections:
    def test_the_list_sets_the_order_and_inherits_defaults(self):
        configuration = parse_text(
            """
            [[sections]]
            type = "services"

            [[sections]]
            type = "panes"
            title = "WINDOW"

            [[sections]]
            type = "zombies"
            enabled = false
            """
        )
        assert section_identifiers(configuration) == ["services", "panes", "zombies"]
        titles = [section.title for section in configuration.sections]
        assert titles == ["SERVICES", "WINDOW", "ZOMBIES"]
        assert [section.enabled for section in configuration.sections] == [True, True, False]

    def test_hide_when_empty_and_empty_text(self):
        section = parse_text(
            """
            [[sections]]
            type = "zombies"
            hide_when_empty = true
            empty_text = "all clear"
            """
        ).sections[0]
        assert section.hide_when_empty is True
        assert section.empty_text == "all clear"

    def test_refuses_an_unknown_type(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.type"):
            parse_text('[[sections]]\ntype = "weather"\n')

    def test_refuses_a_missing_type(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.type"):
            parse_text('[[sections]]\ntitle = "x"\n')

    def test_refuses_a_duplicate_identifier(self):
        with pytest.raises(ConfigurationError, match="duplicate"):
            parse_text('[[sections]]\ntype = "panes"\n[[sections]]\ntype = "panes"\n')

    def test_two_sections_of_one_type_need_different_identifiers(self):
        configuration = parse_text(
            """
            [[sections]]
            type = "services"
            identifier = "mine"
            [[sections]]
            type = "services"
            identifier = "everything"
            """
        )
        assert section_identifiers(configuration) == ["mine", "everything"]

    @pytest.mark.parametrize("identifier", ["Bad", "1abc", "has space", "", "a" * 40])
    def test_refuses_a_bad_identifier(self, identifier):
        text = f'[[sections]]\ntype = "panes"\nidentifier = "{identifier}"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.identifier"):
            parse_text(text)

    def test_refuses_a_title_with_a_control_character(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.title"):
            parse_text('[[sections]]\ntype = "panes"\ntitle = "bad\\u001btitle"\n')


class TestServices:
    def test_custom_rules_replace_the_defaults(self):
        options = (
            parse_text(
                """
            [[sections]]
            type = "services"
            shims = ['^node\\s+\\S*/safe-chain\\s+']

            [[sections.rules]]
            kind = "build"
            pattern = '^cargo build'

            [sections.letters]
            build = "B"
            """
            )
            .sections[0]
            .options
        )
        assert [rule.kind for rule in options["rules"]] == ["build"]
        assert options["shims"] == (r"^node\s+\S*/safe-chain\s+",)
        assert options["letters"] == {"build": "B"}

    def test_a_kind_without_a_letter_gets_its_first_letter(self):
        options = (
            parse_text(
                """
            [[sections]]
            type = "services"
            [[sections.rules]]
            kind = "build"
            pattern = '^cargo build'
            """
            )
            .sections[0]
            .options
        )
        assert options["letters"] == {"build": "B"}

    def test_refuses_a_rule_without_a_pattern(self):
        text = '[[sections]]\ntype = "services"\n[[sections.rules]]\nkind = "build"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.rules\[0\]"):
            parse_text(text)

    def test_refuses_a_broken_pattern_and_names_the_rule(self):
        text = (
            '[[sections]]\ntype = "services"\n[[sections.rules]]\n'
            'kind = "build"\npattern = "(unclosed"\n'
        )
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.rules\[0\].*build"):
            parse_text(text)

    def test_refuses_a_broken_shim(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.shims\[0\]"):
            parse_text('[[sections]]\ntype = "services"\nshims = ["(unclosed"]\n')

    def test_refuses_a_letter_that_is_not_one_character(self):
        text = '[[sections]]\ntype = "services"\n[sections.letters]\ndocker = "DD"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.letters\.docker"):
            parse_text(text)

    def test_other_section_types_refuse_rules(self):
        text = (
            '[[sections]]\ntype = "panes"\n[[sections.rules]]\nkind = "build"\npattern = "cargo"\n'
        )
        with pytest.raises(ConfigurationError, match=r"sections\[0\].*rules"):
            parse_text(text)


class TestMenu:
    def test_disables_actions(self):
        menu = (
            parse_text(
                """
            [[sections]]
            type = "services"
            [sections.menu]
            disabled_actions = ["kill", "restart"]
            """
            )
            .sections[0]
            .menu
        )
        assert menu.disabled_actions == frozenset({"kill", "restart"})

    def test_remaps_a_key_and_keeps_the_others(self):
        keys = (
            parse_text(
                """
            [[sections]]
            type = "services"
            [sections.menu.keys]
            stop = "s"
            """
            )
            .sections[0]
            .menu.keys
        )
        assert keys["stop"] == "s"
        assert keys["restart"] == "r"

    def test_refuses_an_action_the_section_does_not_have(self):
        text = '[[sections]]\ntype = "subagents"\n[sections.menu]\ndisabled_actions = ["kill"]\n'
        with pytest.raises(
            ConfigurationError, match=r"sections\[0\]\.menu\.disabled_actions.*kill"
        ):
            parse_text(text)

    def test_refuses_a_key_for_an_unknown_action(self):
        text = '[[sections]]\ntype = "panes"\n[sections.menu.keys]\nexplode = "e"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.menu\.keys\.explode"):
            parse_text(text)

    @pytest.mark.parametrize("key", ["j", "k", "q", "h", "ab", "", " "])
    def test_refuses_a_reserved_or_bad_key(self, key):
        text = f'[[sections]]\ntype = "panes"\n[sections.menu.keys]\ngo = "{key}"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.menu\.keys\.go"):
            parse_text(text)

    def test_refuses_two_actions_on_one_key(self):
        text = '[[sections]]\ntype = "panes"\n[sections.menu.keys]\ngo = "z"\n'
        with pytest.raises(ConfigurationError, match="already used"):
            parse_text(text)

    def test_a_disabled_action_does_not_block_its_key(self):
        text = (
            '[[sections]]\ntype = "panes"\n[sections.menu]\ndisabled_actions = ["zoom"]\n'
            '[sections.menu.keys]\ngo = "z"\n'
        )
        assert parse_text(text).sections[0].menu.keys["go"] == "z"


class TestRowFormat:
    def test_accepts_known_placeholders(self):
        text = '[[sections]]\ntype = "services"\nrow_format = "{letter}|{command}|{age}"\n'
        assert parse_text(text).sections[0].row_format == "{letter}|{command}|{age}"

    def test_refuses_an_unknown_placeholder_and_lists_the_allowed_ones(self):
        text = '[[sections]]\ntype = "services"\nrow_format = "{bogus}"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.row_format.*bogus.*letter"):
            parse_text(text)

    @pytest.mark.parametrize(
        "row_format",
        ["{label.__class__}", "{label[0]}", "{label!r}", "{label:>10}", "{label", "label}", "{}"],
    )
    def test_refuses_anything_but_a_plain_placeholder(self, row_format):
        text = f'[[sections]]\ntype = "panes"\nrow_format = "{row_format}"\n'
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.row_format"):
            parse_text(text)


class TestCustomSection:
    CUSTOM_SECTION = """
        [[sections]]
        type = "custom"
        identifier = "ports"
        title = "PORTS"
        command = ["ss", "-ltn"]
        timeout_seconds = 3
        """

    def test_reads_a_custom_section(self):
        section = parse_text(self.CUSTOM_SECTION).sections[0]
        assert section.section_type == "custom"
        assert section.options["command"] == ("ss", "-ltn")
        assert section.options["timeout_seconds"] == 3.0

    def test_the_timeout_defaults_to_two_seconds(self):
        text = self.CUSTOM_SECTION.replace("timeout_seconds = 3", "")
        assert parse_text(text).sections[0].options["timeout_seconds"] == 2.0

    def test_needs_an_identifier(self):
        text = self.CUSTOM_SECTION.replace('identifier = "ports"', "")
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.identifier"):
            parse_text(text)

    @pytest.mark.parametrize("value", ['"ss -ltn"', "[]", '[""]', "[1]"])
    def test_refuses_a_command_that_is_not_a_list_of_words(self, value):
        text = self.CUSTOM_SECTION.replace('["ss", "-ltn"]', value)
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.command"):
            parse_text(text)

    @pytest.mark.parametrize("value", ["0", "100", '"slow"'])
    def test_refuses_a_bad_timeout(self, value):
        text = self.CUSTOM_SECTION.replace("timeout_seconds = 3", f"timeout_seconds = {value}")
        with pytest.raises(ConfigurationError, match=r"sections\[0\]\.timeout_seconds"):
            parse_text(text)

    def test_other_section_types_refuse_a_command(self):
        with pytest.raises(ConfigurationError, match=r"sections\[0\].*command"):
            parse_text('[[sections]]\ntype = "panes"\ncommand = ["ls"]\n')


class TestPath:
    def test_uses_the_configuration_home_variable(self):
        environment = {"XDG_CONFIG_HOME": "/configuration-home", "HOME": "/home/someone"}
        assert configuration_path(environment) == Path(
            "/configuration-home/tmux-sidepanel/configuration.toml"
        )

    def test_falls_back_to_the_dot_config_folder(self):
        assert configuration_path({"HOME": "/home/someone"}) == Path(
            "/home/someone/.config/tmux-sidepanel/configuration.toml"
        )

    def test_ignores_a_relative_value(self):
        environment = {"XDG_CONFIG_HOME": "relative/folder", "HOME": "/home/someone"}
        assert configuration_path(environment) == Path(
            "/home/someone/.config/tmux-sidepanel/configuration.toml"
        )

    def test_needs_a_home_folder(self):
        with pytest.raises(ConfigurationError, match="HOME"):
            configuration_path({})


class TestFindConfigurationPath:
    @pytest.fixture
    def folder(self, tmp_path):
        folder = tmp_path / "tmux-sidepanel"
        folder.mkdir()
        return folder

    def find(self, tmp_path):
        environment = {"XDG_CONFIG_HOME": str(tmp_path), "HOME": "/home/someone"}
        return find_configuration_path(environment)

    def test_prefers_configuration_toml_when_both_exist(self, tmp_path, folder):
        (folder / "configuration.toml").write_text("")
        (folder / "config.toml").write_text("")
        assert self.find(tmp_path) == folder / "configuration.toml"

    def test_accepts_config_toml_when_it_is_the_only_one(self, tmp_path, folder):
        (folder / "config.toml").write_text("")
        assert self.find(tmp_path) == folder / "config.toml"

    def test_defaults_to_configuration_toml_when_neither_exists(self, tmp_path, folder):
        assert self.find(tmp_path) == folder / "configuration.toml"

    def test_works_when_the_folder_does_not_exist(self, tmp_path):
        assert self.find(tmp_path) == tmp_path / "tmux-sidepanel" / "configuration.toml"


class TestLoad:
    def write_file(self, directory, text, mode=0o600):
        path = directory / "configuration.toml"
        path.write_text(textwrap.dedent(text))
        path.chmod(mode)
        return path

    def test_a_missing_file_gives_the_defaults(self, tmp_path):
        assert load_configuration(tmp_path / "missing.toml") == default_configuration()

    def test_reads_a_file(self, tmp_path):
        path = self.write_file(tmp_path, "[panel]\nwidth = 44\n")
        assert load_configuration(path).panel.width == 44

    def test_a_syntax_error_names_the_file_and_the_line(self, tmp_path):
        path = self.write_file(tmp_path, "[panel]\nwidth = \n")
        with pytest.raises(ConfigurationError, match=r"configuration\.toml.*line 2"):
            load_configuration(path)

    def test_a_value_error_names_the_file(self, tmp_path):
        path = self.write_file(tmp_path, "[panel]\nwidth = 1\n")
        with pytest.raises(ConfigurationError, match=r"configuration\.toml.*panel\.width"):
            load_configuration(path)

    def test_refuses_a_file_that_others_can_write(self, tmp_path):
        path = self.write_file(tmp_path, "[panel]\nwidth = 40\n", mode=0o666)
        with pytest.raises(ConfigurationError, match="writable"):
            load_configuration(path)

    def test_refuses_a_file_that_the_group_can_write(self, tmp_path):
        path = self.write_file(tmp_path, "[panel]\nwidth = 40\n", mode=0o620)
        with pytest.raises(ConfigurationError, match="writable"):
            load_configuration(path)

    def test_refuses_a_huge_file(self, tmp_path):
        path = self.write_file(tmp_path, "# " + "x" * 70000 + "\n")
        with pytest.raises(ConfigurationError, match="too large"):
            load_configuration(path)

    def test_refuses_a_directory(self, tmp_path):
        with pytest.raises(ConfigurationError, match="not a file"):
            load_configuration(tmp_path)

    def test_refuses_a_file_that_belongs_to_someone_else(self, tmp_path, monkeypatch):
        path = self.write_file(tmp_path, "[panel]\nwidth = 40\n")
        other_user = path.stat().st_uid + 1
        monkeypatch.setattr("tmux_sidepanel.configuration.os.geteuid", lambda: other_user)
        with pytest.raises(ConfigurationError, match="owned by"):
            load_configuration(path)

    def test_the_real_user_owns_the_test_file(self, tmp_path):
        path = self.write_file(tmp_path, "")
        assert path.stat().st_uid == os.geteuid()
