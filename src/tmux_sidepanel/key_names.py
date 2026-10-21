"""The names of the keys that the panel reacts to."""

import curses

NAMED_KEYS = {
    curses.KEY_UP: "UP",
    curses.KEY_DOWN: "DOWN",
    curses.KEY_ENTER: "ENTER",
    10: "ENTER",
    13: "ENTER",
    27: "ESC",
    curses.KEY_MOUSE: "MOUSE",
}
FIRST_PRINTABLE = 32
LAST_PRINTABLE = 126


def is_printable(code: int) -> bool:
    return FIRST_PRINTABLE <= code <= LAST_PRINTABLE


def key_name(code: int) -> str:
    """The name of a key, the character of a printable key, or an empty text when unknown."""
    if code in NAMED_KEYS:
        return NAMED_KEYS[code]
    return chr(code) if is_printable(code) else ""
