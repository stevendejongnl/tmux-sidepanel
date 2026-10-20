"""The command that reopens the session of an agent process that no pane shows."""

import shlex


def resume_command(program: str, session_identifier: str, configuration_directory: str) -> str:
    """Resume a known session, or else continue the latest one, keeping the configuration folder.

    Every word is quoted for the shell, because the words come from the process that was found.
    """
    flags = ["--resume", session_identifier] if session_identifier else ["--continue"]
    command = " ".join(shlex.quote(word) for word in [program, *flags])
    if not configuration_directory:
        return command
    return f"CLAUDE_CONFIG_DIR={shlex.quote(configuration_directory)} {command}"
