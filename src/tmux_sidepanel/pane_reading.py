"""Reading the text of a pane."""

from tmux_sidepanel.tmux_client import TmuxClient

SOURCES = ("visible", "recent", "recent-unwrapped")


def capture_arguments(source: str, lines: int) -> list[str]:
    history = ["-S", f"-{lines}"]
    return {"visible": [], "recent": history, "recent-unwrapped": ["-J", *history]}[source]


def read_pane_text(client: TmuxClient, pane_identifier: str, source: str, lines: int) -> str:
    """The visible screen, or the last lines of the history (wrapped lines can be joined)."""
    text = client.run(
        "capture-pane", "-p", "-t", pane_identifier, *capture_arguments(source, lines)
    )
    rows = text.rstrip("\n").split("\n")
    return "\n".join(rows if source == "visible" else rows[-lines:])
