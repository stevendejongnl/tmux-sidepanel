"""Running programs and reading their output.

Nothing here raises or hangs. A program that fails, is missing or takes too long gives no output,
because the panel must keep drawing whatever happens to the things it looks at. Programs are
started from a list of arguments, never through a shell.
"""

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

MAXIMUM_OUTPUT_CHARACTERS = 1_000_000


def run_text_command(command: Sequence[str], timeout_seconds: float) -> str:
    """The standard output of a program, or an empty text when it fails, is missing or is slow."""
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout[:MAXIMUM_OUTPUT_CHARACTERS] if result.returncode == 0 else ""


def process_directory(process_identifier: int) -> str:
    """The working folder of a process, or an empty text when it cannot be read."""
    try:
        return os.readlink(f"/proc/{process_identifier}/cwd")
    except OSError:
        return ""


def process_environment_value(process_identifier: int, name: str) -> str:
    """One variable of the environment of a process, or an empty text when it cannot be read."""
    try:
        data = Path(f"/proc/{process_identifier}/environ").read_bytes()
    except OSError:
        return ""
    prefix = name.encode() + b"="
    entries = filter(lambda entry: entry.startswith(prefix), data.split(b"\0"))
    return next(entries, prefix)[len(prefix) :].decode(errors="replace")
