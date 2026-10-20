"""The skill of the plugin: its commands must exist, and the wrapper that runs them must work."""

import re
import shlex
import shutil

import pytest

from tests.conftest import PROJECT_ROOT, run_command
from tmux_sidepanel.command_line import UsageError, build_parser
from tmux_sidepanel.pane_description import PaneDescription

SKILL_PATH = PROJECT_ROOT / "skills" / "tmux-agents" / "SKILL.md"
WRAPPER_PATH = PROJECT_ROOT / "bin" / "tmux-sidepanel"
COMMAND_LINE = re.compile(r"^tmux-sidepanel (?P<arguments>.+)$", re.MULTILINE)
CODE_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
PLACEHOLDER = re.compile(r"<[a-z-]+>")


def skill_text():
    return SKILL_PATH.read_text(encoding="ascii")


def example_commands():
    blocks = CODE_BLOCK.findall(skill_text())
    return COMMAND_LINE.findall("\n".join(blocks))


def missing_from_skill(patterns):
    text = skill_text()
    return list(filter(lambda pattern: pattern not in text, patterns))


def parsed_arguments(arguments):
    words = shlex.split(PLACEHOLDER.sub("%1", arguments))
    return build_parser().parse_args(words)


class TestWrapper:
    def test_it_is_executable(self):
        assert WRAPPER_PATH.stat().st_mode & 0o111

    @pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed")
    def test_it_passes_shellcheck(self):
        assert run_command(["shellcheck", WRAPPER_PATH]).returncode == 0

    def test_it_runs_the_command_line_of_the_plugin(self, tmp_path):
        result = run_command([WRAPPER_PATH, "list"], directory="/", TMUX_TMPDIR=str(tmp_path))
        assert "tmux:" in result.stderr
        assert "Traceback" not in result.stderr

    def test_it_can_be_run_from_another_directory(self):
        result = run_command([WRAPPER_PATH, "--help"], directory="/")
        assert "tmux_sidepanel" in result.stdout


class TestSkill:
    def test_the_front_matter_names_the_skill(self):
        text = skill_text()
        assert text.startswith("---\nname: tmux-agents\n")
        assert "description:" in text.split("---")[1]

    def test_it_says_when_not_to_use_it(self):
        assert "Use only when" in skill_text().split("---")[1]

    def test_it_has_example_commands(self):
        assert len(example_commands()) >= 10

    @pytest.mark.parametrize("arguments", example_commands())
    def test_every_example_command_is_understood(self, arguments):
        try:
            parsed_arguments(arguments)
        except UsageError as error:
            pytest.fail(f"{arguments}: {error}")

    def test_every_field_of_a_pane_is_explained(self):
        fields = [f"`{name}`" for name in PaneDescription.__dataclass_fields__]
        assert missing_from_skill(fields) == []

    def test_every_error_code_is_explained(self):
        codes = ["agent_blocked", "timeout", "agent_prompt_stalled", "own_pane", "bad_kind"]
        assert missing_from_skill(codes) == []

    def test_it_is_plain_ascii_without_emoji(self):
        assert skill_text().isascii()
