#!/usr/bin/env bash
# Start a bash session whose input and output are recorded to a log file,
# with a timestamp, user, host, and directory in every prompt line.
# Usage: ./logged-shell.sh [name]   -> logs to $LOGDIR/<name>_<UTC timestamp>.log
set -euo pipefail

LOGDIR="${LOGDIR:-$HOME/cptc-logs}"
name="${1:-$(whoami)}"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$LOGDIR/${name}_${ts}.log"
mkdir -p "$LOGDIR"

rc="$(mktemp)"
cat >"$rc" <<'EOF'
[ -f ~/.bashrc ] && . ~/.bashrc
PS1='[\D{%F %T %Z}] \u@\h:\w\$ '
EOF

echo "Logging to $log  (type 'exit' to stop)"
# util-linux script: -q quiet, -f flush after each write so the log is current.
script -q -f -c "bash --rcfile '$rc'" "$log"
rm -f "$rc"
echo "Session saved: $log"
