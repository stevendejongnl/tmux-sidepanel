"""The actions of the menu of a service: stop, restart, logs, kill, go and open the folder.

Stopping or killing something is always confirmed first. Before a process is killed it is looked
up again, and it must still be the foreground process of the same pane, so a process identifier
that was handed to something else in the meantime is never signalled.
"""

import os
import signal
from collections.abc import Callable
from functools import partial

from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome, ask, done
from tmux_sidepanel.command_runner import run_text_command
from tmux_sidepanel.docker_actions import (
    UnsafeNameError,
    logs_command,
    require_safe_names,
    start_docker,
)
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.pane_actions import ignore_action
from tmux_sidepanel.process_table import parse_process_table
from tmux_sidepanel.service_rows import ServiceEntry, ServiceSubject, is_foreground
from tmux_sidepanel.window_actions import jump_to_pane, open_command_window, open_directory

PROCESS_CHECK_SECONDS = 3
DOCKER_PROGRESS = {"stop": "stopping", "restart": "restarting", "kill": "killing"}


def run_docker_verb(context: ActionContext, verb: str, entry: ServiceEntry) -> ActionOutcome:
    """Stop, restart or kill the containers of the entry, in the background."""
    try:
        require_safe_names(entry.container_names)
    except UnsafeNameError as error:
        return done(f"unsafe container name: {error}")
    started = start_docker(context.docker_program, [verb, *entry.container_names])
    if not started:
        return done("docker is not available")
    return done(f"{DOCKER_PROGRESS[verb]} {entry.command}")


def still_running_on_pane(context: ActionContext, entry: ServiceEntry) -> bool:
    command = context.process_command
    table = parse_process_table(run_text_command(command, PROCESS_CHECK_SECONDS))
    pane = find_pane(context.client.list_panes(), entry.pane_identifier)
    process = table.get(entry.process_identifier)
    if process is None or pane is None:
        return False
    return is_foreground(process) and process.terminal == pane.terminal


def interrupt_process(context: ActionContext, entry: ServiceEntry) -> ActionOutcome:
    context.client.run("send-keys", "-t", entry.pane_identifier, "C-c")
    return done(f"sent Ctrl-C to {entry.command}")


def kill_process(context: ActionContext, entry: ServiceEntry) -> ActionOutcome:
    if not still_running_on_pane(context, entry):
        return done("the process is no longer running there; nothing was killed")
    try:
        os.killpg(os.getpgid(entry.process_identifier), signal.SIGKILL)
    except OSError as error:
        return done(f"kill failed: {error.strerror}")
    return done(f"killed {entry.command}")


def stop_service(context: ActionContext, entry: ServiceEntry) -> ActionOutcome:
    if entry.is_container:
        return run_docker_verb(context, "stop", entry)
    return interrupt_process(context, entry)


def kill_service(context: ActionContext, entry: ServiceEntry) -> ActionOutcome:
    if entry.is_container:
        return run_docker_verb(context, "kill", entry)
    return kill_process(context, entry)


def service_go(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    jump_to_pane(context.client, subject.entry.pane_identifier)
    return done()


def service_directory(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    return open_directory(context.client, subject.entry.directory)


def service_stop(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    entry = subject.entry
    return ask(f"stop {entry.command}? y/n", partial(stop_service, context, entry))


def service_restart(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    entry = subject.entry
    if not entry.is_container:
        return done("restart is only for containers")
    prompt = f"restart {entry.command}? y/n"
    return ask(prompt, partial(run_docker_verb, context, "restart", entry))


def service_kill(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    entry = subject.entry
    return ask(f"FORCE kill {entry.command}? y/n", partial(kill_service, context, entry))


def service_logs(context: ActionContext, subject: ServiceSubject) -> ActionOutcome:
    entry = subject.entry
    if not entry.is_container:
        return done("logs are only for containers")
    try:
        command = logs_command(context.docker_program, entry.container_names, entry.project)
    except UnsafeNameError as error:
        return done(f"unsafe container name: {error}")
    return open_command_window(context.client, f"logs-{entry.command}", command)


SERVICE_ACTIONS: dict[str, Callable[[ActionContext, ServiceSubject], ActionOutcome]] = {
    "go": service_go,
    "stop": service_stop,
    "restart": service_restart,
    "logs": service_logs,
    "directory": service_directory,
    "kill": service_kill,
}


def perform_service_action(
    context: ActionContext, subject: ServiceSubject, action: str
) -> ActionOutcome:
    return SERVICE_ACTIONS.get(action, ignore_action)(context, subject)
