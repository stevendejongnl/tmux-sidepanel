"""Small text helpers for rows: ages and container status."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AgeUnit:
    letter: str
    seconds_per_unit: int
    minimum_seconds: int


AGE_UNITS = (
    AgeUnit("d", 86400, 86400),
    AgeUnit("h", 3600, 3600),
    AgeUnit("m", 60, 60),
    AgeUnit("s", 1, 0),
)

STATUS_UNIT_LETTERS = {
    "second": "s",
    "minute": "m",
    "hour": "h",
    "day": "d",
    "week": "w",
    "month": "mo",
    "year": "y",
}

LESS_THAN_A_SECOND = "Less than a second"

RUNNING_STATUS_PATTERN = re.compile(
    r"^Up (?:About )?(?:an? |(?P<count>\d+|<1) )?"
    r"(?P<unit>second|minute|hour|day|week|month|year)s?(?P<rest>.*)$"
)


def is_old_enough(seconds: int, unit: AgeUnit) -> bool:
    return seconds >= unit.minimum_seconds


def format_age(seconds: int) -> str:
    """Turn a number of seconds into a short age such as 5s, 3m, 2h or 4d."""
    seconds = max(0, int(seconds))
    unit = next(filter(lambda candidate: is_old_enough(seconds, candidate), AGE_UNITS))
    return f"{seconds // unit.seconds_per_unit}{unit.letter}"


def render_running_status(match: re.Match[str]) -> str:
    count = match.group("count") or "1"
    unit_letter = STATUS_UNIT_LETTERS[match.group("unit")]
    return f"{count}{unit_letter}{match.group('rest')}".strip()


def compact_status(status: str) -> str:
    """Shorten a running container status: 'Up 6 hours (healthy)' becomes '6h (healthy)'.

    Any other status, for example 'Exited (0) 2 hours ago', is returned unchanged.
    """
    match = RUNNING_STATUS_PATTERN.match(status.replace(LESS_THAN_A_SECOND, "<1 second"))
    return render_running_status(match) if match else status
