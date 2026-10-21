#!/usr/bin/env bash
# Rebuild the pictures of the README in assets/: the banner and the screenshots of a demo tmux that
# holds invented data only. Run it after every change that the user can see, and look at the pictures.
# Needs: tmux, chromium, rsvg-convert, ImageMagick (magick), unshare, and the dev dependencies (uv sync).
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repository=$(cd "$here/../.." && pwd)
work=${TMPDIR:-/tmp}/tmux-sidepanel-demo
socket=$work/tmux.sock
assets=$repository/assets

mkdir -p "$assets"

stop_demo() {
    # SIGKILL ends the first process of the namespace (the namespace ignores other signals from outside),
    # and the namespace takes all demo processes with it.
    [ -n "${unshare_pid:-}" ] && kill -KILL "$(pgrep -P "$unshare_pid")" 2>/dev/null || true
}
trap stop_demo EXIT

mkdir -p "$(dirname "$work")"
unshare --user --map-user="$(id -u)" --map-group="$(id -g)" --pid --fork --mount-proc \
    bash -c "bash '$here/build_demo.sh' '$work' '$repository'; exec sleep 600" \
    </dev/null >"$(dirname "$work")/tmux-sidepanel-demo.log" 2>&1 &
unshare_pid=$!

for _ in $(seq 1 60); do
    ready=$(env -u TMUX tmux -S "$socket" list-panes -a -F '#{@sidepanel_panel}' 2>/dev/null | grep -c 1 || true)
    [ "$ready" -ge 1 ] && break
    sleep 0.5
done
sleep 2

cd "$repository"
uv run python devtools/screenshots/render.py "$socket" "$work/panel.png"
uv run python devtools/screenshots/render.py "$socket" "$work/panel-menu.png" Enter
magick "$work/panel.png" -crop 2760x1600+0+0 +repage "$assets/panel.png"
magick "$work/panel-menu.png" -crop 2760x1600+0+0 +repage "$assets/panel-menu.png"
rsvg-convert -w 2560 "$here/banner.svg" -o "$assets/banner.png"
echo "Wrote $assets/banner.png, panel.png and panel-menu.png. Look at them before you commit."
