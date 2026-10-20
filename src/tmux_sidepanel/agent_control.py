"""The commands that control coding agents: list, name, send-keys, wait, prompt and start.

The state of an agent is the pane option that its hooks keep up to date. A command that sends
text to an agent first looks at that state, and it never answers a question of the agent for you.
"""

import argparse
import os
import re
import shlex
from dataclasses import asdict
from typing import Any

from tmux_sidepanel.agent_commands import print_result
from tmux_sidepanel.agent_output import AgentCommandError
from tmux_sidepanel.command_context import CommandContext
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.options import OPTION_NAME, OPTION_STATE
from tmux_sidepanel.pane_commands import resolved_pane
from tmux_sidepanel.pane_description import agent_name, describe_pane, describe_panes
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.tmux_client import TmuxClient
from tmux_sidepanel.waiting import MILLISECONDS_PER_SECOND, REAL_TIME, wait_for

NAME_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,31}")
SETTLED_STATES = ("idle", "done", "blocked")
ACTIVE_STATES = ("working", "blocked")
STATES = ("idle", "working", "blocked", "done")
SHELL_PROGRAMS = ("zsh", "bash", "fish", "sh")
KEY_NAMES = {
    "esc": "Escape",
    "enter": "Enter",
    "tab": "Tab",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "space": "Space",
    "backspace": "BSpace",
}
CONTROL_KEY = re.compile(r"ctrl\+(\w)")
PROMPT_START_MILLISECONDS = 5000
PASTE_PAUSE_SECONDS = 0.15
DEFAULT_START_TIMEOUT = 30000
STALLED_MESSAGE = "no working or blocked state within 5 s; the prompt may still be delivered"


def add_agent_control_parsers(commands: Any) -> None:
    agent = commands.add_parser("agent", help="control a coding agent").add_subparsers(
        dest="agent_command", required=True
    )
    agent.add_parser("list", help="list the panes that run an agent")
    name = agent.add_parser("name", help="give an agent a name")
    name.add_argument("target")
    name.add_argument("agent_name", metavar="name")
    keys = agent.add_parser("send-keys", help="send keys to an agent")
    keys.add_argument("target")
    keys.add_argument("keys", nargs="+")
    wait = agent.add_parser("wait", help="wait until an agent settles, or reaches a state")
    wait.add_argument("target")
    wait.add_argument("--until", choices=list(STATES))
    wait.add_argument("--timeout", type=int, help="milliseconds")
    prompt = agent.add_parser("prompt", help="send a prompt to an agent")
    prompt.add_argument("target")
    prompt.add_argument("text")
    prompt.add_argument("--wait", action="store_true", help="wait until the agent has finished")
    prompt.add_argument("--timeout", type=int, help="milliseconds")
    start = agent.add_parser("start", help="start an agent in a pane that shows a shell")
    start.add_argument("agent_name", metavar="name")
    start.add_argument("--pane", required=True)
    start.add_argument("--kind", default="claude")
    start.add_argument("--timeout", type=int, default=DEFAULT_START_TIMEOUT, help="milliseconds")
    start.add_argument("agent_arguments", nargs="*", metavar="args", help="arguments after --")


def validated_name(name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        raise AgentCommandError("bad_name", "a name matches [a-z][a-z0-9_-]{0,31}")
    return name


def is_named_elsewhere(pane: PaneRecord, name: str, context: CommandContext) -> bool:
    return agent_name(pane, context.agent_names()) == name


def require_free_name(context: CommandContext, name: str) -> None:
    named = filter(
        lambda pane: is_named_elsewhere(pane, name, context), context.client.list_panes()
    )
    if next(named, None) is not None:
        raise AgentCommandError("name_taken", f"agent {name} is already live")


def described_pane(context: CommandContext, pane_identifier: str) -> dict[str, Any]:
    pane = find_pane(context.client.list_panes(), pane_identifier)
    return asdict(describe_pane(pane, context.agent_names()))


def pane_state(client: TmuxClient, pane_identifier: str) -> str:
    return client.display(pane_identifier, "#{" + OPTION_STATE + "}")


def run_agent_list_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    described = describe_panes(context.client.list_panes(), context.agent_names(), True)
    print_result([asdict(item) for item in described])


def run_agent_name_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    name = validated_name(parsed.agent_name)
    pane = resolved_pane(context, parsed.target)
    require_free_name(context, name)
    context.client.write_pane_option(pane.pane_identifier, OPTION_NAME, name)
    print_result(described_pane(context, pane.pane_identifier))


def tmux_key(key: str) -> str:
    lowered = key.lower()
    control = CONTROL_KEY.fullmatch(lowered)
    if lowered in KEY_NAMES:
        return KEY_NAMES[lowered]
    if control:
        return f"C-{control.group(1)}"
    raise AgentCommandError("bad_key", f"unknown key {key}")


def run_agent_send_keys_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    keys = [tmux_key(key) for key in parsed.keys]
    pane = resolved_pane(context, parsed.target)
    context.client.run("send-keys", "-t", pane.pane_identifier, *keys)
    print_result({"pane_id": pane.pane_identifier, "sent": parsed.keys})


def state_timeout_message(state: str) -> str:
    return f"state {state or 'none'} when the time was up"


def wait_for_states(
    client: TmuxClient, pane_identifier: str, accepted: tuple[str, ...], timeout: int | None
) -> str:
    return wait_for(
        lambda: pane_state(client, pane_identifier),
        lambda state: state in accepted,
        timeout,
        state_timeout_message,
    )


def run_agent_wait_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    pane = resolved_pane(context, parsed.target)
    accepted = (parsed.until,) if parsed.until else SETTLED_STATES
    state = wait_for_states(context.client, pane.pane_identifier, accepted, parsed.timeout)
    print_result({"pane_id": pane.pane_identifier, "state": state})


def require_ready_for_prompt(state: str) -> None:
    if state == "blocked":
        raise AgentCommandError(
            "agent_blocked", "the agent waits at an approval or question; read the pane first"
        )
    if not state:
        raise AgentCommandError("not_an_agent", "the pane has no agent state")


def submit_text(client: TmuxClient, pane_identifier: str, text: str) -> None:
    """Paste the text as one piece, then press Enter, so a newline in it does not submit early."""
    buffer = f"sidepanel-prompt-{os.getpid()}"
    client.run("set-buffer", "-b", buffer, "--", text)
    client.run("paste-buffer", "-p", "-d", "-b", buffer, "-t", pane_identifier)
    REAL_TIME.sleep(PASTE_PAUSE_SECONDS)
    client.run("send-keys", "-t", pane_identifier, "Enter")


def is_short_timeout(timeout: int | None) -> bool:
    return timeout is not None and timeout <= PROMPT_START_MILLISECONDS


def stalled_or_timeout(error: AgentCommandError, timeout: int | None) -> AgentCommandError:
    if is_short_timeout(timeout):
        return error
    return AgentCommandError("agent_prompt_stalled", STALLED_MESSAGE)


def wait_for_activity(client: TmuxClient, pane_identifier: str, timeout: int | None) -> None:
    """The agent must start working, or ask something, soon after the prompt."""
    limit = (
        PROMPT_START_MILLISECONDS if timeout is None else min(timeout, PROMPT_START_MILLISECONDS)
    )
    try:
        wait_for_states(client, pane_identifier, ACTIVE_STATES, limit)
    except AgentCommandError as error:
        raise stalled_or_timeout(error, timeout) from error


def milliseconds_left(timeout: int | None, started: float) -> int | None:
    if timeout is None:
        return None
    spent = (REAL_TIME.clock() - started) * MILLISECONDS_PER_SECOND
    return max(0, int(timeout - spent))


def run_agent_prompt_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    pane = resolved_pane(context, parsed.target)
    identifier = pane.pane_identifier
    require_ready_for_prompt(pane_state(context.client, identifier))
    started = REAL_TIME.clock()
    submit_text(context.client, identifier, parsed.text)
    if not parsed.wait:
        print_result({"pane_id": identifier, "submitted": True})
        return
    wait_for_activity(context.client, identifier, parsed.timeout)
    remaining = milliseconds_left(parsed.timeout, started)
    state = wait_for_states(context.client, identifier, SETTLED_STATES, remaining)
    print_result({"pane_id": identifier, "state": state})


def require_known_kind(context: CommandContext, kind: str) -> None:
    if kind not in context.agent_names():
        raise AgentCommandError("bad_kind", f"{kind} is not one of the configured agents")


def require_shell_pane(pane: PaneRecord) -> None:
    if pane.current_command not in SHELL_PROGRAMS:
        message = f"the pane runs {pane.current_command}, it needs an idle shell"
        raise AgentCommandError("pane_not_available", message)


def start_command_text(parsed: argparse.Namespace) -> str:
    return " ".join(shlex.quote(word) for word in [parsed.kind, *parsed.agent_arguments])


def wait_until_ready(client: TmuxClient, pane_identifier: str, parsed: argparse.Namespace) -> None:
    try:
        wait_for_states(client, pane_identifier, SETTLED_STATES, parsed.timeout)
    except AgentCommandError as error:
        message = f"{parsed.agent_name} is not ready after {parsed.timeout} ms; the name is kept"
        raise AgentCommandError("agent_not_ready", message) from error


def run_agent_start_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    name = validated_name(parsed.agent_name)
    require_known_kind(context, parsed.kind)
    require_free_name(context, name)
    pane = resolved_pane(context, parsed.pane)
    require_shell_pane(pane)
    identifier = pane.pane_identifier
    context.client.write_pane_option(identifier, OPTION_NAME, name)
    context.client.write_pane_option(identifier, OPTION_STATE, "")
    context.client.run("send-keys", "-t", identifier, "-l", start_command_text(parsed))
    context.client.run("send-keys", "-t", identifier, "Enter")
    wait_until_ready(context.client, identifier, parsed)
    print_result(described_pane(context, identifier))


AGENT_CONTROL_COMMANDS = {
    "list": run_agent_list_command,
    "name": run_agent_name_command,
    "send-keys": run_agent_send_keys_command,
    "wait": run_agent_wait_command,
    "prompt": run_agent_prompt_command,
    "start": run_agent_start_command,
}


def run_agent_command(parsed: argparse.Namespace, context: CommandContext) -> None:
    AGENT_CONTROL_COMMANDS[parsed.agent_command](parsed, context)
