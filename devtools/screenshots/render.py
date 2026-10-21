"""One screenshot of the demo tmux: attach in a pty, read the screen with pyte, draw it as HTML and
let Chromium take the picture. The text is checked for personal data before the picture is made.

Usage: render.py SOCKET OUTPUT_PNG [KEYS_FOR_THE_PANEL ...]   (keys are tmux key names)
"""

import fcntl
import getpass
import html
import os
import pty
import select
import socket
import struct
import subprocess
import sys
import termios
import time
from dataclasses import dataclass
from pathlib import Path

import pyte

COLUMNS = 150
ROWS = 40
PANEL_PANE = "%5"
DEFAULT_FOREGROUND = "#c0caf5"
DEFAULT_BACKGROUND = "#1a1b26"
PALETTE = {
    "black": "#1a1b26",
    "red": "#f7768e",
    "green": "#9ece6a",
    "brown": "#e0af68",
    "blue": "#7aa2f7",
    "magenta": "#bb9af7",
    "cyan": "#7dcfff",
    "white": "#a9b1d6",
    "brightblack": "#565f89",
    "brightred": "#f7768e",
    "brightgreen": "#9ece6a",
    "brightbrown": "#e0af68",
    "brightblue": "#7aa2f7",
    "brightmagenta": "#bb9af7",
    "brightcyan": "#7dcfff",
    "brightwhite": "#c0caf5",
}


class QuietScreen(pyte.Screen):
    """pyte fails on the status queries of tmux, and the demo does not need an answer."""

    def report_device_status(self, *arguments, **options):
        return None

    def report_device_attributes(self, *arguments, **options):
        return None


def color_of(name, default):
    if name == "default":
        return default
    if name in PALETTE:
        return PALETTE[name]
    return f"#{name}" if len(name) == 6 else default


def environment_without_tmux():
    environment = dict(os.environ)
    environment.pop("TMUX", None)
    return environment


@dataclass(frozen=True)
class Client:
    process_identifier: int
    descriptor: int


def start_client(socket_path):
    process_identifier, descriptor = pty.fork()
    if process_identifier == 0:
        os.environ.pop("TMUX", None)
        os.environ["TERM"] = "xterm-256color"
        os.execvp("tmux", ["tmux", "-S", socket_path, "attach", "-t", "work"])
    size = struct.pack("HHHH", ROWS, COLUMNS, 0, 0)
    fcntl.ioctl(descriptor, termios.TIOCSWINSZ, size)
    return Client(process_identifier, descriptor)


def feed_when_ready(descriptor, stream):
    readable = select.select([descriptor], [], [], 0.1)[0]
    if readable:
        stream.feed(os.read(descriptor, 65536))


def read_for(descriptor, stream, seconds):
    end = time.time() + seconds
    while time.time() < end:
        feed_when_ready(descriptor, stream)


def send_keys(socket_path, keys):
    command = ["tmux", "-S", socket_path, "send-keys", "-t", PANEL_PANE, *keys.split(",")]
    subprocess.run(command, env=environment_without_tmux(), check=True)


def row_of(screen, row):
    return [screen.buffer[row][column] for column in range(COLUMNS)]


def grid_of(screen):
    return [row_of(screen, row) for row in range(ROWS)]


def capture(socket_path, key_groups):
    client = start_client(socket_path)
    screen = QuietScreen(COLUMNS, ROWS)
    stream = pyte.ByteStream(screen)
    read_for(client.descriptor, stream, 2.0)
    for keys in key_groups:
        send_keys(socket_path, keys)
        read_for(client.descriptor, stream, 1.0)
    grid = grid_of(screen)
    command = ["tmux", "-S", socket_path, "detach-client"]
    subprocess.run(command, env=environment_without_tmux(), check=True)
    os.close(client.descriptor)
    os.waitpid(client.process_identifier, 0)
    return grid


def cell_html(character):
    foreground = color_of(character.fg, DEFAULT_FOREGROUND)
    background = color_of(character.bg, DEFAULT_BACKGROUND)
    if character.reverse:
        foreground, background = background, foreground
    weight = "font-weight:700;" if character.bold else ""
    style = f"color:{foreground};background:{background};{weight}"
    return f'<span style="{style}">{html.escape(character.data) or " "}</span>'


def line_of(row):
    return "".join(character.data for character in row)


def row_html(row):
    return "".join(cell_html(character) for character in row)


def text_of(grid):
    return "\n".join(map(line_of, grid))


def page_of(grid):
    body = "\n".join(map(row_html, grid))
    return (
        "<!doctype html><meta charset=utf-8><style>"
        f"html,body{{margin:0;background:{DEFAULT_BACKGROUND}}}"
        "pre{margin:0;padding:18px 22px;width:max-content;font:15px/1.25 "
        "'JetBrainsMono Nerd Font Mono','JetBrains Mono',monospace;"
        f"background:{DEFAULT_BACKGROUND}}}</style><pre>{body}</pre>"
    )


def personal_strings():
    names = [getpass.getuser(), str(Path.home()), socket.gethostname(), "/home/", "/Users/"]
    return list(filter(None, names))


def refuse_personal_text(text):
    found = list(filter(text.__contains__, personal_strings()))
    if found:
        sys.exit(f"The screenshot would show personal text: {found}. Nothing was written.")


def take_picture(page_path, output_path):
    command = [
        "chromium",
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=2",
        "--window-size=1380,880",
        f"--screenshot={output_path}",
        f"file://{page_path}",
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(arguments):
    socket_path, output_path, *key_groups = arguments
    grid = capture(socket_path, key_groups)
    refuse_personal_text(text_of(grid))
    page_path = Path(output_path).with_suffix(".html")
    page_path.write_text(page_of(grid))
    take_picture(page_path, output_path)
    page_path.unlink()


if __name__ == "__main__":
    main(sys.argv[1:])
