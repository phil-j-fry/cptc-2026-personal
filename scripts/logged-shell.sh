#!/usr/bin/env bash
# Start a bash session that writes two logs:
#   1. <name>_<UTC timestamp>.log       full transcript (input and output), via util-linux `script`
#   2. <name>_<UTC timestamp>.cmds.log  one line per command: time, exit code, directory, command
# The second log is the quick index for incident reports and reproduction steps.
# Usage: ./logged-shell.sh [name]   -> logs go to $LOGDIR (default ~/cptc-logs)
set -euo pipefail

LOGDIR="${LOGDIR:-$HOME/cptc-logs}"
name="${1:-$(whoami)}"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$LOGDIR/${name}_${ts}.log"
cmdlog="$LOGDIR/${name}_${ts}.cmds.log"
mkdir -p "$LOGDIR"

rc="$(mktemp)"
# Unquoted heredoc on purpose: $cmdlog is filled in now. Every \$ stays literal for the new shell.
cat >"$rc" <<EOF
[ -f ~/.bashrc ] && . ~/.bashrc
CPTC_CMDLOG='$cmdlog'
HISTTIMEFORMAT='%F %T '
HISTCONTROL=   # log every command, including repeats and ones typed with a leading space
# After each command: save the exit code first, then append one line to the command log.
# A line is written only when the history number changes, so the first prompt and
# pressing Enter on an empty line add nothing.
__cptc_log() {
  local code=\$? line num cmd
  line="\$(history 1)"
  num="\$(sed -E 's/^ *([0-9]+).*/\\1/' <<<"\$line")"
  if [ -n "\${__cptc_ready:-}" ] && [ "\$num" != "\$__cptc_last" ]; then
    cmd="\$(sed -E 's/^ *[0-9]+ +[0-9-]+ [0-9:]+ +//' <<<"\$line")"
    printf '%s (exit %s) [%s] %s\\n' "\$(date '+%F %T %Z')" "\$code" "\$PWD" "\$cmd" >> "\$CPTC_CMDLOG"
  fi
  __cptc_last="\$num"
  __cptc_ready=1
}
PROMPT_COMMAND=__cptc_log
PS1='[\D{%F %T %Z}] \u@\h:\w\\$ '
EOF

echo "Logging to $log"
echo "Command index: $cmdlog  (type 'exit' to stop)"
# util-linux script: -q quiet, -f flush after each write so the log is current.
script -q -f -c "bash --rcfile '$rc'" "$log"
rm -f "$rc"
echo "Session saved: $log"
echo "Command index: $cmdlog"
