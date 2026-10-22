"""The README: its configuration example must be valid, and it must describe the real keys."""

import re

from tests.conftest import PROJECT_ROOT
from tmux_sidepanel.configuration import SECTION_SPECIFICATIONS, parse_configuration
from tmux_sidepanel.key_bindings import DEFAULT_KEYS
from tmux_sidepanel.rows import STATE_MARKS

README_PATH = PROJECT_ROOT / "README.md"
TOML_BLOCK = re.compile(r"```toml\n(.*?)```", re.DOTALL)


def readme_text():
    return README_PATH.read_text(encoding="ascii")


def toml_blocks():
    return TOML_BLOCK.findall(readme_text())


def test_the_readme_has_a_configuration_example():
    assert toml_blocks()


def test_every_configuration_example_is_valid():
    assert all(map(parse_configuration, toml_blocks()))


def missing_from_readme(patterns):
    text = readme_text()
    return list(filter(lambda pattern: pattern not in text, patterns))


def test_the_readme_names_every_section_type():
    names = [f"`{name}`" for name in SECTION_SPECIFICATIONS]
    assert missing_from_readme(names) == []


def test_the_readme_names_the_default_keys():
    keys = [f"prefix + {key}" for key in DEFAULT_KEYS.values()]
    assert missing_from_readme(keys) == []


def test_the_readme_explains_the_marks_of_the_states():
    states = [f"`{state}`" for state in filter(None, STATE_MARKS)]
    assert missing_from_readme(states) == []


def test_the_readme_names_the_license():
    assert "AGPL-3.0-or-later" in readme_text()


def test_the_readme_names_every_command_for_scripts():
    commands = [f"tmux-sidepanel {name}" for name in ["list", "current", "get", "pane", "agent"]]
    assert missing_from_readme(commands) == []


def test_the_readme_warns_about_other_hooks_that_report_the_state():
    assert missing_from_readme(["Remove any other hook", "`@sidepanel_state`"]) == []
