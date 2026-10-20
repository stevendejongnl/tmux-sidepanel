"""The actions of the menu of a zombie: open, terminate, kill and open the folder.

Before any signal is sent the process is looked up again and must still be an agent process that
no pane shows, so a process identifier that was handed to something else is never signalled.
"""

import os
import signal
from collections.abc import Callable
from contextlib import suppress
from functools import partial
from pathlib import PurePosixPath

from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome, ask, done
from tmux_sidepanel.command_runner import process_environment_value, run_text_command
from tmux_sidepanel.pane_actions import ignore_action
from tmux_sidepanel.process_table import parse_process_table
from tmux_sidepanel.processes import Zombie, find_zombies, resume_session_identifier
from tmux_sidepanel.resume import resume_command
from tmux_sidepanel.window_actions import jump_to_pane, open_command_window, open_directory
from tmux_sidepanel.zombie_rows import ZombieSubject

PROCESS_CHECK_SECONDS = 3
RESUMABLE_PROGRAM = "claude"


def still_zombie(context: ActionContext, zombie: Zombie) -> bool:
    table = parse_process_table(run_text_command(context.process_command, PROCESS_CHECK_SECONDS))
    pane_terminals = {pane.terminal for pane in context.client.list_panes()}
    current = find_zombies(table, pane_terminals, context.agent_names)
    return any(
        item.process.process_identifier == zombie.process.process_identifier for item in current
    )


def wake_stopped_process(zombie: Zombie, signal_number: int) -> None:
    """A stopped process only acts on a polite request to end once it is running again."""
    needs_wake = zombie.reason == "stopped" and signal_number == signal.SIGTERM
    if not needs_wake:
        return
    with suppress(OSError):
        os.kill(zombie.process.process_identifier, signal.SIGCONT)


def signal_zombie(
    context: ActionContext, zombie: Zombie, signal_number: int, name: str
) -> ActionOutcome:
    process_identifier = zombie.process.process_identifier
    if not still_zombie(context, zombie):
        return done("the process is no longer a zombie; nothing was signalled")
    try:
        os.kill(process_identifier, signal_number)
    except OSError as error:
        return done(f"signal failed: {error.strerror}")
    wake_stopped_process(zombie, signal_number)
    return done(f"sent {name} to {process_identifier}")


def resume_in_new_window(context: ActionContext, subject: ZombieSubject) -> ActionOutcome:
    process = subject.zombie.process
    if process.program_name != RESUMABLE_PROGRAM:
        return done(f"resume is only known for {RESUMABLE_PROGRAM}")
    arguments = process.argument_list
    command = resume_command(
        arguments[0],
        resume_session_identifier(arguments),
        process_environment_value(process.process_identifier, "CLAUDE_CONFIG_DIR"),
    )
    folder = PurePosixPath(subject.directory).name or str(process.process_identifier)
    return open_command_window(context.client, f"resume-{folder}", command, subject.directory)


def zombie_open(context: ActionContext, subject: ZombieSubject) -> ActionOutcome:
    if subject.pane_identifier:
        jump_to_pane(context.client, subject.pane_identifier)
        return done()
    return resume_in_new_window(context, subject)


def zombie_terminate(context: ActionContext, subject: ZombieSubject) -> ActionOutcome:
    process_identifier = subject.zombie.process.process_identifier
    then = partial(signal_zombie, context, subject.zombie, signal.SIGTERM, "TERM")
    return ask(f"terminate {process_identifier}? y/n", then)


def zombie_kill(context: ActionContext, subject: ZombieSubject) -> ActionOutcome:
    process_identifier = subject.zombie.process.process_identifier
    then = partial(signal_zombie, context, subject.zombie, signal.SIGKILL, "KILL")
    return ask(f"FORCE kill {process_identifier}? y/n", then)


def zombie_directory(context: ActionContext, subject: ZombieSubject) -> ActionOutcome:
    return open_directory(context.client, subject.directory)


ZOMBIE_ACTIONS: dict[str, Callable[[ActionContext, ZombieSubject], ActionOutcome]] = {
    "open": zombie_open,
    "terminate": zombie_terminate,
    "kill": zombie_kill,
    "directory": zombie_directory,
}


def perform_zombie_action(
    context: ActionContext, subject: ZombieSubject, action: str
) -> ActionOutcome:
    return ZOMBIE_ACTIONS.get(action, ignore_action)(context, subject)
