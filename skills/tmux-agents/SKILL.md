---
name: tmux-agents
description: "Control tmux panes and other coding agents with the tmux-sidepanel command. Use only when the user asks you to run a command in another pane, read another pane, or start or prompt another agent in tmux. Do not use it only because a task could use a background terminal or parallel work. TMUX must be set."
---

# tmux-agents

The command `tmux-sidepanel` controls tmux panes and coding agents. It prints JSON.

Before you use it, make sure you are in tmux:

```bash
test -n "${TMUX:-}" && test -n "${TMUX_PANE:-}"
```

If the check fails, tell the user that you are not in tmux. Do not continue.

## Model

- A window is a workspace. A pane is a terminal.
- A pane identifier looks like `%12`. Get identifiers from the JSON output. Do not guess them.
- Each agent reports its state through hooks. The states are `idle`, `working`, `blocked` and `done`.
- The state `blocked` means that the agent waits for an approval or an answer.
- The state `unknown` means that the pane runs an agent that has not reported a state.
- An empty state means that the pane has no agent.
- An agent can have a name. A name matches `[a-z][a-z0-9_-]{0,31}`. A name is unique.
- A command accepts a pane identifier or an agent name as its target.

Success prints `{"result": ...}` and exits with code 0. Failure prints `{"error": {"code": ..., "message": ...}}` on standard error and exits with code 1. Use the code, not the message, to decide what to do.

Run `tmux-sidepanel --help`, `tmux-sidepanel pane --help` or `tmux-sidepanel agent --help` for the syntax.

## Find state

```bash
tmux-sidepanel list
tmux-sidepanel list --agents
tmux-sidepanel current
tmux-sidepanel get <pane-or-name>
```

A pane has these fields:

- `session`, `window` and `window_name`: where the pane is.
- `pane_id` and `pane`: the identifier and the index of the pane.
- `active`: true when the pane has the focus.
- `directory` and `command`: the current directory and the running program.
- `state`, `kind` and `name`: the agent in the pane.

The panel panes of the plugin are not in the list.

## Run a command in another pane

Make a new pane next to your pane. The focus stays where it is.

```bash
tmux-sidepanel pane split --direction right --directory "$PWD"
```

Read the new identifier from `.result.pane_id`. Use `--direction down` for a narrow pane. Do not split many times in the same direction.

```bash
tmux-sidepanel pane run <pane-id> "just test"
tmux-sidepanel pane wait-output <pane-id> --match "passed" --timeout 120000
tmux-sidepanel pane read <pane-id> --lines 120
```

`pane run` types the text and presses Enter. It does not show that the command ran.

`pane wait-output` also matches text that you typed. Choose a match text that only the output contains. With `--regex`, the characters `^` and `$` match at each line.

Close a pane that you made when you no longer need it:

```bash
tmux-sidepanel pane close <pane-id>
```

## Start and prompt an agent

1. Make a new pane. The pane must show a shell prompt with nothing running.
2. Start the agent with a unique name:

```bash
tmux-sidepanel agent start reviewer --pane <pane-id> --kind claude
```

The kind must be one of the configured agents. Put the arguments of the agent after `--`.

3. Send work. With `--wait`, the command returns when the state is `idle`, `done` or `blocked`:

```bash
tmux-sidepanel agent prompt reviewer "Review the current diff. Report only actionable findings." --wait --timeout 120000
tmux-sidepanel pane read reviewer --lines 120
```

`agent prompt` refuses an agent in the state `blocked`. The error code is `agent_blocked`. Read the pane to see the question. Ask the user before you answer it.

If the error code is `agent_prompt_stalled` or `timeout`, the prompt can still arrive. Read the pane before you send the prompt again.

Other commands:

```bash
tmux-sidepanel agent wait reviewer --until blocked --timeout 120000
tmux-sidepanel agent send-keys reviewer esc
tmux-sidepanel agent name <pane-or-name> reviewer
tmux-sidepanel agent list
```

If `agent start` does not report in time, the error code is `agent_not_ready`. The name stays on the pane.

## Rules

- Do not close panes that you did not make. The command refuses to close your own pane (`own_pane`).
- Do not kill sessions or the tmux server.
- Do not use the pane with the focus as a target. Use `current`, a pane identifier or an agent name.
- Do not answer an approval question for the user.
- Do not start a program that is not a configured agent (`bad_kind`).
