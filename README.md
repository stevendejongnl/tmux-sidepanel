# tmux-sidepanel

A side panel for tmux. Each window gets a panel pane that shows what runs in that window:

- the panes of the window, with the state of the coding agent in each pane
- the subagents of those agents
- services (test runners, dev servers, containers) and the containers of other projects
- agent processes that no pane shows any more ("zombies")
- sections of your own, filled by a command you choose

Every row has an action menu: go to a pane, zoom it, interrupt it, stop or restart a service,
read the logs of a container, terminate a zombie or resume its session. Every section can be
turned off, renamed, reordered and given other keys.

The panel needs Python 3.11 or newer and no other packages. It is developed and tested with
tmux 3.7. The hooks use arrays of hooks, which need tmux 3.0 or newer.

## Install

With the tmux plugin manager, add this to `tmux.conf` and press prefix + I:

```tmux
set -g @plugin 'stevendejongnl/tmux-sidepanel'
```

Without the plugin manager, clone the repository and run its entry file from `tmux.conf`:

```tmux
run-shell '~/.tmux/plugins/tmux-sidepanel/tmux_sidepanel.tmux'
```

The entry file installs the tmux hooks and the key bindings. It is safe to run again.

### Report the state of your coding agent

The panel shows the state of an agent (`working`, `idle`, `blocked`, `done`) only when the agent
reports it. For Claude Code the repository is a plugin that does this with its hooks:

```
/plugin marketplace add stevendejongnl/tmux-sidepanel
/plugin install tmux-sidepanel@tmux-sidepanel
```

The hooks run `python3 -m tmux_sidepanel hook <action>`. They never block the agent: a problem
prints one line and the command still ends with code 0.

## Use

| Key | Effect |
|-----|--------|
| prefix + S | Open the panel of this window, or close it |
| prefix + F | Move the focus into the panel, or back to the pane you came from |

In the panel:

| Key | Effect |
|-----|--------|
| `j`, Down | Select the next row |
| `k`, Up | Select the previous row |
| Enter | Open the menu of the row |
| a menu key | Run that action |
| Esc | Close the menu |
| `y` | Confirm a question. Any other key cancels it. |
| `q` | Close the panel |

Actions that cannot be undone (close a pane, stop a service, terminate or kill a process) ask
first. Before a signal is sent to a process, the process is looked up again, so a process
identifier that was reused by something else is never signalled.

A state is shown with a mark in front of the row:

| State | Mark |
|-------|------|
| `blocked` | `!` |
| `done` | `+` |
| `working` | `~` |
| `idle` | `.` |
| `unknown` | `?` |

### Change the keys

Set these tmux options before the plugin loads. The value `off` turns a key off. A key that you
already use for something else is never taken over.

```tmux
set -g @sidepanel_toggle_key 'S'
set -g @sidepanel_focus_key 'F'
```

## Configuration

The file is `configuration.toml` in `$XDG_CONFIG_HOME/tmux-sidepanel/`, or in
`~/.config/tmux-sidepanel/`. A file named `config.toml` is read when it is the only one. Without
a file, the defaults apply. A mistake in the file is reported with the name of the key.

The file can run commands (custom sections), so it is refused when someone else owns it or can
write to it.

```toml
[panel]
width = 30              # 10 to 120 columns
refresh_seconds = 0.5   # 0.1 to 60
position = "left"       # left or right

[agents]
names = ["claude"]                          # program names that count as an agent
ignored_arguments = ["--chrome-native-host"]

[[sections]]
type = "panes"

[[sections]]
type = "subagents"
hide_when_empty = true

[[sections]]
type = "services"
title = "RUNNING"
row_format = "{letter} {command} {age}"

[sections.menu]
disabled_actions = ["kill"]

[sections.menu.keys]
stop = "s"

[[sections]]
type = "zombies"
hide_when_empty = true

[[sections]]
type = "custom"
identifier = "ports"
title = "PORTS"
command = ["ss", "-tlnH"]
timeout_seconds = 2
```

Sections are shown in the order of the file. Without a `[[sections]]` table, all default
sections are shown.

### Section types

| Type | Shows | Actions (default key) |
|------|-------|-----------------------|
| `panes` | The panes of the window | go (g), zoom (z), interrupt (x), directory (o), close (X) |
| `subagents` | The subagents of the agents | go (g), tasks (t) |
| `services` | Services started from the panes of the window, and its containers | go (g), stop (x), restart (r), logs (l), directory (o), kill (X) |
| `other-services` | Containers that do not belong to this window | stop (x), restart (r), logs (l), directory (o), kill (X) |
| `zombies` | Agent processes that no pane shows | open (o), terminate (x), directory (d), kill (X) |
| `custom` | The lines that your command prints | none |

Every section accepts `identifier`, `title`, `enabled`, `hide_when_empty`, `empty_text`,
`row_format` and a `menu` table with `disabled_actions` and `keys`. The placeholders of a row
format depend on the type, and an unknown placeholder is an error.

The `services` section also takes `rules` (a kind and a pattern for each), `shims` (wrapper
prefixes to remove from a command) and `letters` (the letter that shows each kind).

## Security

- Programs are started from a list of arguments, never through a shell. Container names are
  checked before they are used, and the words of a resume command are quoted for the shell.
- Text from other programs is cleaned before it reaches the screen, so a process name cannot
  send escape sequences to your terminal.
- The panel never asks for, reads or stores a password or a token.

See `SECURITY.md` to report a problem.

## Development

```
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run complexipy src devtools tests --failed --plain
```

The tests that use tmux start their own server on a private socket. They are skipped when tmux
is not installed.

Commits follow Conventional Commits. Releases are made from the tags.

## License

AGPL-3.0-or-later. See `LICENSE`.
