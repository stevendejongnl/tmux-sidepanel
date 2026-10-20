"""Waiting for something to happen, with a time limit that a test can control."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from tmux_sidepanel.agent_output import AgentCommandError

Observed = TypeVar("Observed")
MILLISECONDS_PER_SECOND = 1000


@dataclass(frozen=True)
class Waiter:
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    interval_seconds: float = 0.2


def seconds_left(deadline: float | None, waiter: Waiter) -> float | None:
    return None if deadline is None else deadline - waiter.clock()


def sleep_before_next_look(left: float | None, waiter: Waiter) -> None:
    """Sleep one interval, or less when the time limit comes sooner."""
    waiter.sleep(waiter.interval_seconds if left is None else min(waiter.interval_seconds, left))


REAL_TIME = Waiter()


def deadline_for(timeout_milliseconds: int | None, waiter: Waiter) -> float | None:
    if timeout_milliseconds is None:
        return None
    return waiter.clock() + timeout_milliseconds / MILLISECONDS_PER_SECOND


def fail_when_out_of_time(
    left: float | None, seen: Observed, timeout_message: Callable[[Observed], str]
) -> None:
    if left is not None and left <= 0:
        raise AgentCommandError("timeout", timeout_message(seen))


def look_again(
    observe: Callable[[], Observed],
    seen: Observed,
    deadline: float | None,
    timeout_message: Callable[[Observed], str],
    waiter: Waiter,
) -> Observed:
    left = seconds_left(deadline, waiter)
    fail_when_out_of_time(left, seen, timeout_message)
    sleep_before_next_look(left, waiter)
    return observe()


def wait_for(
    observe: Callable[[], Observed],
    is_ready: Callable[[Observed], bool],
    timeout_milliseconds: int | None,
    timeout_message: Callable[[Observed], str],
    waiter: Waiter = REAL_TIME,
) -> Observed:
    """Look until is_ready accepts what is seen. Without a timeout it waits as long as needed."""
    deadline = deadline_for(timeout_milliseconds, waiter)
    seen = observe()
    while not is_ready(seen):
        seen = look_again(observe, seen, deadline, timeout_message, waiter)
    return seen
