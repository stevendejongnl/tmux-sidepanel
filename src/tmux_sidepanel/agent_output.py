"""The JSON that the commands for other programs print: a result, or an error with a code."""

import json
from typing import Any


class AgentCommandError(Exception):
    """A command could not do what was asked. The code is stable, the message is for people."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def result_text(result: Any) -> str:
    return json.dumps({"result": result}, indent=2)


def error_text(error: AgentCommandError) -> str:
    return json.dumps({"error": {"code": error.code, "message": error.message}})
