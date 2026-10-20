"""Waiting for something to happen, with a time limit that a test can control."""

import pytest

from tmux_sidepanel.agent_output import AgentCommandError
from tmux_sidepanel.waiting import Waiter, wait_for


class FakeTime:
    """A clock that only moves when somebody sleeps."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def build_waiter(fake, interval_seconds=0.5):
    return Waiter(fake.clock, fake.sleep, interval_seconds)


def observations(*values):
    remaining = list(values)
    return lambda: remaining.pop(0) if len(remaining) > 1 else remaining[0]


def is_ready(value):
    return value == "ready"


def timeout_message(value):
    return f"still {value}"


class TestWaitFor:
    def test_returns_at_once_when_it_is_ready(self):
        fake = FakeTime()
        found = wait_for(observations("ready"), is_ready, 1000, timeout_message, build_waiter(fake))
        assert found == "ready"
        assert fake.sleeps == []

    def test_polls_until_it_is_ready(self):
        fake = FakeTime()
        observe = observations("busy", "busy", "ready")
        found = wait_for(observe, is_ready, 5000, timeout_message, build_waiter(fake))
        assert found == "ready"
        assert fake.sleeps == [0.5, 0.5]

    def test_gives_up_at_the_timeout_and_says_what_it_saw(self):
        fake = FakeTime()
        with pytest.raises(AgentCommandError) as caught:
            wait_for(observations("busy"), is_ready, 1000, timeout_message, build_waiter(fake))
        assert caught.value.code == "timeout"
        assert caught.value.message == "still busy"
        assert fake.now == 1.0

    def test_without_a_timeout_it_waits_as_long_as_needed(self):
        fake = FakeTime()
        observe = observations(*(["busy"] * 50), "ready")
        assert wait_for(observe, is_ready, None, timeout_message, build_waiter(fake)) == "ready"

    def test_a_timeout_of_zero_looks_once(self):
        fake = FakeTime()
        with pytest.raises(AgentCommandError):
            wait_for(observations("busy"), is_ready, 0, timeout_message, build_waiter(fake))
        assert fake.sleeps == []

    def test_the_last_sleep_does_not_pass_the_timeout(self):
        fake = FakeTime()
        with pytest.raises(AgentCommandError):
            wait_for(observations("busy"), is_ready, 700, timeout_message, build_waiter(fake))
        assert fake.sleeps == [0.5, pytest.approx(0.2)]
