"""Talking to docker: safe names, starting a command in the background, and the logs command.

Container names and project names come from the output of docker, which is outside data. They are
checked against the rule that docker itself uses for names before they are put in any command.
"""

import re
import shlex
import subprocess
import threading
from collections.abc import Sequence

SAFE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


class UnsafeNameError(ValueError):
    """A container or project name is not one that docker would have made."""


def is_unsafe(name: str) -> bool:
    return not SAFE_NAME_PATTERN.fullmatch(name)


def require_safe_names(names: Sequence[str]) -> None:
    unsafe = list(filter(is_unsafe, names))
    if unsafe:
        raise UnsafeNameError(f"unsafe name {unsafe[0]!r}")


def start_docker(program: str, arguments: Sequence[str]) -> bool:
    """Start docker in the background and return at once. False means it could not be started.

    The command may take seconds, as a stop does, so a thread waits for it and so it is reaped
    instead of staying behind as a defunct process.
    """
    try:
        process = subprocess.Popen(
            [program, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    threading.Thread(target=process.wait, daemon=True).start()
    return True


def logs_command(program: str, names: Sequence[str], project: str) -> str:
    """The shell command that follows the logs of one container, or of a whole compose project."""
    if not names:
        raise UnsafeNameError("no container name")
    require_safe_names(names)
    quoted_program = shlex.quote(program)
    if project and len(names) > 1:
        require_safe_names([project])
        return f"{quoted_program} compose -p {project} logs -f --tail 100"
    return f"{quoted_program} logs -f --tail 200 {names[0]}"
