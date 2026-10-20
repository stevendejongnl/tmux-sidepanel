"""Service rules: classify a command line as docker, test, server and so on.

A rule is a kind and a pattern. The first rule whose pattern matches wins. The rules are plain
data, so a user can replace them. Short runs such as lint or build are not services and match
no rule.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache, reduce

MAXIMUM_COMMAND_LENGTH = 500
MAXIMUM_PATTERN_LENGTH = 300


class RuleError(ValueError):
    """A rule or shim pattern is not usable."""


@dataclass(frozen=True)
class Rule:
    kind: str
    pattern: re.Pattern[str]

    def matches(self, command: str) -> bool:
        return bool(self.pattern.search(command))


@dataclass(frozen=True)
class RuleDefinition:
    kind: str
    pattern: str


def compile_pattern(pattern: str, name: str) -> re.Pattern[str]:
    if len(pattern) > MAXIMUM_PATTERN_LENGTH:
        raise RuleError(
            f"{name}: pattern is too long ({len(pattern)} characters, "
            f"the limit is {MAXIMUM_PATTERN_LENGTH})"
        )
    try:
        return re.compile(pattern)
    except re.error as error:
        raise RuleError(f"{name}: {error}") from error


def compile_rule(kind: str, pattern: str) -> Rule:
    if not kind:
        raise RuleError("rule kind must not be empty")
    return Rule(kind, compile_pattern(pattern, f"rule {kind!r}"))


def compile_definition(definition: RuleDefinition) -> Rule:
    return compile_rule(definition.kind, definition.pattern)


DEFAULT_RULE_DEFINITIONS = (
    RuleDefinition(
        "docker",
        r"^(\S*/)?(docker|docker-compose|podman)(\s|$)|\bmake\s+(up|docker-\S+)\b",
    ),
    RuleDefinition(
        "test",
        r"(^|[\s/])(pytest|py\.test|jest|vitest|nox|tox)(\s|$)"
        r"|\b(npm|pnpm|yarn)\s+(run\s+)?test(:\S+)?\b"
        r"|\bcargo\s+test\b|\bgo\s+test\b"
        r"|\bmake\s+(\S*test\S*|unit-tests|integration-tests)\b"
        r"|playwright\s+test|manage\.py\s+test",
    ),
    RuleDefinition(
        "server",
        r"\b(npm|pnpm|yarn)\s+(run\s+)?(dev|start|serve|watch\S*|storybook|static:dev)\b"
        r"|\b(vite|nodemon|webpack(-dev-server)?|expo|react-native|docusaurus"
        r"|vue-cli-service|storybook)\b"
        r"|uvicorn|gunicorn|hypercorn|flask\s+run|fastapi\s+(dev|run)|runserver|http\.server"
        r"|\bmake\s+(run|dev|serve)\b",
    ),
    RuleDefinition("uv", r"^(\S*/)?uv(\s|$)"),
)

DEFAULT_RULES = tuple(compile_definition(definition) for definition in DEFAULT_RULE_DEFINITIONS)


def classify(command: str, rules: Iterable[Rule] = DEFAULT_RULES) -> str:
    """Return the kind of the first matching rule, or an empty string."""
    shortened = command[:MAXIMUM_COMMAND_LENGTH]
    rule = next(filter(lambda candidate: candidate.matches(shortened), rules), None)
    return rule.kind if rule else ""


@lru_cache(maxsize=64)
def compiled_shim(pattern: str) -> re.Pattern[str]:
    return compile_pattern(pattern, f"shim {pattern!r}")


def remove_shim(command: str, pattern: str) -> str:
    return compiled_shim(pattern).sub("", command, count=1)


def strip_shims(command: str, shims: Iterable[str]) -> str:
    """Remove wrapper prefixes, for example a launcher that runs node before the real command."""
    return reduce(remove_shim, shims, command)


def display_command(command: str) -> str:
    """Drop the directory of the program: '/usr/bin/uv run x' becomes 'uv run x'."""
    return re.sub(r"^\S*/(\S+)", r"\1", command)
