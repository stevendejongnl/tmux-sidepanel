"""Commit message style for this repository.

Messages follow the Conventional Commits layout: a typed header of at most 72
characters, a blank line, a body wrapped at 72 characters, and no emoji.

Usage: python -m devtools.commitlint <message-file>
"""

import re
import sys
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

COMMIT_TYPES = (
    "feat",
    "fix",
    "docs",
    "test",
    "refactor",
    "chore",
    "build",
    "ci",
    "perf",
    "style",
    "revert",
)
HEADER_PATTERN = re.compile(rf"^({'|'.join(COMMIT_TYPES)})(\([a-z0-9._-]+\))?: \S.*$")
MAXIMUM_LINE_LENGTH = 72

URL_PATTERN = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class CodePointRange:
    first: int
    last: int

    def as_class_text(self) -> str:
        return f"{chr(self.first)}-{chr(self.last)}"


# Symbols and emoji blocks, written as numbers so this file stays plain ASCII.
EMOJI_RANGES = (
    CodePointRange(0x2600, 0x27BF),
    CodePointRange(0x2B00, 0x2BFF),
    CodePointRange(0xFE0F, 0xFE0F),
    CodePointRange(0x1F000, 0x1FAFF),
)
EMOJI_PATTERN = re.compile("[" + "".join(map(CodePointRange.as_class_text, EMOJI_RANGES)) + "]")


@dataclass(frozen=True)
class Check:
    failed: bool
    message: str

    def problems(self) -> list[str]:
        return [self.message] if self.failed else []


@dataclass(frozen=True)
class NumberedLine:
    number: int
    text: str

    def is_too_long(self) -> bool:
        return len(self.text) > MAXIMUM_LINE_LENGTH and not URL_PATTERN.search(self.text)

    def has_emoji(self) -> bool:
        return bool(EMOJI_PATTERN.search(self.text))

    def describe_length(self) -> str:
        return (
            f"line {self.number} is {len(self.text)} characters, the limit is {MAXIMUM_LINE_LENGTH}"
        )

    def describe_emoji(self) -> str:
        return f"line {self.number}: remove the emoji"


def is_not_comment(line: str) -> bool:
    return not line.startswith("#")


def message_lines(text: str) -> list[str]:
    """The lines git keeps: without comment lines and without trailing blank lines."""
    kept = "\n".join(filter(is_not_comment, text.splitlines())).rstrip()
    return kept.split("\n") if kept else []


def numbered_lines(lines: list[str], first_number: int) -> list[NumberedLine]:
    return [NumberedLine(number, text) for number, text in enumerate(lines, start=first_number)]


def header_problems(header: str) -> list[str]:
    allowed_types = ", ".join(COMMIT_TYPES)
    checks = [
        Check(
            not HEADER_PATTERN.match(header),
            f"header must look like 'type(scope): subject', type one of {allowed_types}",
        ),
        Check(
            len(header) > MAXIMUM_LINE_LENGTH,
            f"header is {len(header)} characters, the limit is {MAXIMUM_LINE_LENGTH}",
        ),
        Check(header.endswith("."), "header must not end with a period"),
    ]
    return list(chain.from_iterable(check.problems() for check in checks))


def spacing_problems(lines: list[str]) -> list[str]:
    has_text_in_second_line = len(lines) > 1 and bool(lines[1].strip())
    return Check(has_text_in_second_line, "a blank line must follow the header").problems()


def length_problems(lines: list[str]) -> list[str]:
    too_long = filter(NumberedLine.is_too_long, numbered_lines(lines[1:], first_number=2))
    return [line.describe_length() for line in too_long]


def emoji_problems(lines: list[str]) -> list[str]:
    with_emoji = filter(NumberedLine.has_emoji, numbered_lines(lines, first_number=1))
    return [line.describe_emoji() for line in with_emoji]


def check_message(text: str) -> list[str]:
    """Return every problem found in a commit message; an empty list means it is fine."""
    lines = message_lines(text)
    return (
        [
            *header_problems(lines[0]),
            *spacing_problems(lines),
            *length_problems(lines),
            *emoji_problems(lines),
        ]
        if lines
        else ["the message is empty"]
    )


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        print("usage: python -m devtools.commitlint <message-file>", file=sys.stderr)
        return 2
    problems = check_message(Path(arguments[0]).read_text(encoding="utf-8"))
    for problem in problems:
        print(f"commit message: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
