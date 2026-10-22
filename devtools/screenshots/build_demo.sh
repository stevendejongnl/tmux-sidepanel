#!/usr/bin/env bash
# Start a demo tmux with invented data on its own socket. Run it inside a PID namespace (make.sh does):
# the panel reads the process table, and without the namespace it would show the processes of the
# machine that builds the screenshots.
# Usage: build_demo.sh WORK_DIRECTORY REPOSITORY
# The work directory is deleted first, so its name must be exactly tmux-sidepanel-demo.
set -euo pipefail

work=${1:?work directory}
repository=${2:?repository}

case "$work" in
    /?*/tmux-sidepanel-demo) ;;
    *)
        echo "Refusing to delete '$work': the name of the work directory must be tmux-sidepanel-demo." >&2
        exit 1
        ;;
esac

socket=$work/tmux.sock
home=$work/home
project=$home/projects/shop-api

rm -rf -- "$work"
mkdir -p "$home/.config/tmux-sidepanel" "$project/src" "$work/bin"
cp "$(command -v sleep)" "$work/bin/claude"

cat > "$home/.config/tmux-sidepanel/configuration.toml" <<'TOML'
[panel]
width = 34
refresh_seconds = 0.5

[[sections]]
type = "panes"

[[sections]]
type = "subagents"
hide_when_empty = true

[[sections]]
type = "services"

[[sections]]
type = "zombies"
hide_when_empty = true
TOML
chmod 600 "$home/.config/tmux-sidepanel/configuration.toml"

cat > "$work/tmux.conf" <<'CONF'
set -g default-terminal "tmux-256color"
set -g status-style "bg=#1a1b26,fg=#a9b1d6"
set -g status-left "#[bg=#7aa2f7,fg=#1a1b26,bold] work #[default] "
set -g status-right "#[fg=#565f89]demo "
set -g window-status-current-style "bg=#292e42,fg=#c0caf5,bold"
set -g pane-border-style "fg=#3b4261"
set -g pane-active-border-style "fg=#7aa2f7"
set -g base-index 1
set -g allow-rename off
set -g automatic-rename off
CONF

demo_tmux() {
    env -u TMUX -u TMUX_PLUGIN_MANAGER_PATH HOME="$home" PATH="$work/bin:$PATH" \
        tmux -S "$socket" -f "$work/tmux.conf" "$@"
}

demo_tmux new-session -d -s work -n shop-api -x 150 -y 40 -c "$project" \
    "printf '\\n  Reading src/orders/export.py\\n  Editing src/orders/export.py\\n  Running tests/test_export.py\\n\\n'; exec claude 3000"
first=$(demo_tmux list-panes -t work:shop-api -F '#{pane_id}' | sed -n 1p)
second=$(demo_tmux split-window -h -P -F '#{pane_id}' -t "$first" -c "$project" \
    "printf '\\n  The retry helper needs a decision:\\n  keep the backoff or switch to a fixed delay?\\n\\n  [1] keep   [2] fixed delay\\n\\n'; exec claude 3000")
demo_tmux split-window -v -t "$second" -c "$project" \
    "printf '\\n  \$ pytest -q tests/\\n  .......................... [ 62%%]\\n'; exec -a 'pytest -q tests/' sleep 3000"
demo_tmux new-window -d -t work -n web -c "$project" \
    "printf '\\n  VITE ready in 312 ms\\n  Local: http://localhost:5173/\\n'; exec -a 'npm run dev' sleep 3000"
demo_tmux new-window -d -t work -n docs -c "$project" "exec bash --norc"

# an agent that no pane shows: the panel lists it as a zombie
(cd "$project" && setsid "$work/bin/claude" 3000 </dev/null >/dev/null 2>&1 &)

sleep 1
demo_tmux set-option -p -t "$first" @sidepanel_kind claude
demo_tmux set-option -p -t "$first" @sidepanel_state working
demo_tmux set-option -p -t "$first" @sidepanel_name "add order export"
demo_tmux set-option -p -t "$first" @sidepanel_subagents "a1b2c3d4:explore e5f6a7b8:review"
demo_tmux set-option -p -t "$first" @sidepanel_tasks "k9m2x1:shell:Run_the_test_watcher d4e5f6:monitor:Follow_the_build_log"
demo_tmux set-option -p -t "$second" @sidepanel_kind claude
demo_tmux set-option -p -t "$second" @sidepanel_state blocked
demo_tmux set-option -p -t "$second" @sidepanel_name "fix payment retry"

demo_tmux select-window -t work:shop-api
demo_tmux select-pane -t "$first"
window=$(demo_tmux display -p -t work:shop-api '#{window_id}')
env -u TMUX -u TMUX_PLUGIN_MANAGER_PATH HOME="$home" TMUX="$socket,0,0" PYTHONPATH="$repository/src" \
    python3 -m tmux_sidepanel toggle --window "$window"
