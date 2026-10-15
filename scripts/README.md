# Scripts

The rulebook says teams may be asked to demonstrate or explain any pre-written code. Keep everything here short enough that any team member can explain it line by line.

| Script | Purpose |
|---|---|
| `logged-shell.sh` | Records a timestamped terminal session for evidence. It also writes a one-line-per-command index (time, exit code, directory, command) to `*.cmds.log`, the quick reference for incident reports and reproduction steps. Needs util-linux `script` (default on Kali/Debian). **Walkthrough: `logged-shell.md`.** |

Rule: no exploit code copied from elsewhere without understanding it, and no credentials or targets hard-coded.
