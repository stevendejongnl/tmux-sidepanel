"""Text from other programs, made safe to print on a terminal.

The command line of a program, the name of a window or the output of a command can hold escape
sequences. Printed as they are, they could move the cursor, change the title of the terminal or
worse. Every such character is replaced before anything is drawn.
"""

import re

UNSAFE_CHARACTERS = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")


def sanitize_for_terminal(text: str) -> str:
    """Replace control characters with a question mark, and a tab with a space."""
    return UNSAFE_CHARACTERS.sub("?", text.replace("\t", " "))
