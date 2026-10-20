"""Service rules: classify a command line, with the rules as plain data."""

import time

import pytest

from tmux_sidepanel.services import (
    DEFAULT_RULES,
    RuleError,
    classify,
    compile_rule,
    display_command,
    strip_shims,
)


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("docker compose up -d", "docker"),
        ("/usr/bin/docker-compose up", "docker"),
        ("podman run alpine", "docker"),
        ("make up", "docker"),
        ("make docker-run", "docker"),
        ("uv run pytest tests/", "test"),
        ("pytest -x", "test"),
        ("npm test", "test"),
        ("npm run test:watch", "test"),
        ("npx vitest run", "test"),
        ("npx jest --watch", "test"),
        ("make test", "test"),
        ("make unit-tests", "test"),
        ("nox -s tests", "test"),
        ("npx playwright test", "test"),
        ("cargo test", "test"),
        ("go test ./...", "test"),
        ("python manage.py test", "test"),
        ("npm run dev", "server"),
        ("npm run watch", "server"),
        ("pnpm start", "server"),
        ("node /x/node_modules/.bin/vite", "server"),
        ("uv run uvicorn app:app", "server"),
        ("gunicorn app:app", "server"),
        ("flask run", "server"),
        ("nodemon index.js", "server"),
        ("expo start", "server"),
        ("make run", "server"),
        ("storybook dev -p 6008", "server"),
        ("python3 -m http.server 8765", "server"),
        ("uv sync", "uv"),
        ("uv run python script.py", "uv"),
        ("/home/me/.local/bin/uv tool list", "uv"),
        ("nvim foo.py", ""),
        ("htop", ""),
        ("ssh example.org", ""),
        ("npm run lint", ""),
        ("make build", ""),
        ("mypy src", ""),
        ("ruff check", ""),
        ("", ""),
    ],
)
def test_default_rules(command, kind):
    assert classify(command) == kind


def test_the_first_matching_rule_wins():
    rules = (compile_rule("a", r"run"), compile_rule("b", r"run"))
    assert classify("run it", rules) == "a"


def test_custom_rules_replace_the_defaults():
    rules = (compile_rule("build", r"^cargo build"),)
    assert classify("cargo build --release", rules) == "build"
    assert classify("docker compose up", rules) == ""


def test_the_default_rules_come_in_a_stable_order():
    assert [rule.kind for rule in DEFAULT_RULES] == ["docker", "test", "server", "uv"]


def test_a_broken_pattern_names_the_rule():
    with pytest.raises(RuleError, match="mine"):
        compile_rule("mine", r"(unclosed")


def test_an_oversized_pattern_is_refused():
    with pytest.raises(RuleError, match="too long"):
        compile_rule("mine", "a" * 1000)


def test_an_empty_kind_is_refused():
    with pytest.raises(RuleError, match="kind"):
        compile_rule("", r"x")


def test_a_huge_command_line_is_classified_quickly():
    started = time.monotonic()
    classify("npm " + "run " * 50000 + "dev")
    assert time.monotonic() - started < 0.5


class TestStripShims:
    SHIM = r"^node\s+\S*/safe-chain\s+"

    def test_removes_a_leading_wrapper(self):
        command = "node /home/me/.npm-global/bin/safe-chain python3 -m http.server"
        assert strip_shims(command, [self.SHIM]) == "python3 -m http.server"

    def test_leaves_other_commands_alone(self):
        assert strip_shims("uv run pytest", [self.SHIM]) == "uv run pytest"

    def test_applies_every_shim_in_order(self):
        shims = [r"^sudo\s+", r"^env\s+"]
        assert strip_shims("sudo env make test", shims) == "make test"

    def test_no_shims_changes_nothing(self):
        assert strip_shims("make test", []) == "make test"

    def test_a_broken_shim_is_reported(self):
        with pytest.raises(RuleError, match="shim"):
            strip_shims("make test", [r"(unclosed"])


class TestDisplayCommand:
    def test_drops_the_directory_of_the_program(self):
        assert display_command("/home/me/.local/bin/uv run pytest") == "uv run pytest"

    def test_keeps_a_plain_command(self):
        assert display_command("uv run pytest") == "uv run pytest"

    def test_keeps_directories_in_the_arguments(self):
        assert display_command("pytest /tmp/some/dir") == "pytest /tmp/some/dir"
