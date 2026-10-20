"""Text for the command parser of tmux, and for its format expansion."""

import re

CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
CHARACTERS_WITH_A_MEANING = str.maketrans({"\\": "\\\\", '"': '\\"', "$": "\\$"})


def quote_for_tmux(text: str) -> str:
    """Wrap text in double quotes so the parser of tmux reads it back unchanged.

    Control characters are refused. A command never needs them, and they are hard to quote.
    """
    if CONTROL_CHARACTERS.search(text):
        raise ValueError(f"cannot quote text with a control character: {text!r}")
    return '"' + text.translate(CHARACTERS_WITH_A_MEANING) + '"'


def escape_for_format(text: str) -> str:
    """Make text safe inside a command that tmux expands formats in, such as run-shell."""
    return text.replace("#", "##")
