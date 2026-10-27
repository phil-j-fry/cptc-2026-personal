# Team scripts breakdown

Every block of `scripts/pull.sh` and `scripts/make-workcopy.sh`, the Chunk S changes to `scripts/logged-shell.sh`, their tests in `tools/tests/test_scripts.py`, and the related edits outside `tools/`. The shared test helpers in `tests/support.py` are described in [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy); these tests use only `make_worktree()` and `write_fake_file()` from it. The rulebook says Operations may ask us to explain our code, so each entry has a line range, a one-line description, and **If Operations asks:** a plain answer a student can give.

Line ranges match the code at the end of Chunk S (team scripts). `logged-shell.sh` itself has a line-by-line walkthrough in `scripts/logged-shell.md`; this file covers only what Chunk S changed in it. The implementor updates this file at the end of every review chunk; the code reviewer checks it.

| Term | Meaning |
|---|---|
| working copy | `~/cptc-work`: a plain copy of the repo with no `.git`, where all event work happens |
| clone | the git copy of the team repo on a box; `make-workcopy.sh` copies from it, and nobody works in it |
| report writer | the teammate who pulls everyone's files and assembles the report |
| teammate list | `~/cptc-work/teammates.txt`: one `name<TAB>login<TAB>IP` line per teammate, written by `pull.sh --setup` |
| pull key | `~/.ssh/cptc_ed25519` (and `.pub`): an SSH key used only for pulls, with no passphrase |
| incoming | `incoming/<name>/`: a read-only mirror of a teammate's four shared folders (rule R18) |
| the four folders | `findings/`, `evidence/`, `field-notes/` and `tracker/`: the only folders a pull copies |
| saved name | `~/cptc-work/.cptc-name`: your name on one line, written by `make-workcopy.sh`, read by `logged-shell.sh` |
| safe name | lowercase letters, digits and `-`, starting with a letter or digit (`^[a-z0-9][a-z0-9-]*$`), checked in the C locale |
| stub | a fake command the tests put on `PATH` (fake `ssh`, `rsync`, `git`, ...) that records its arguments and does nothing else |
| mutation check | breaking one part of a script on purpose (in `tools/tests/.tmp/`) and checking that a test fails |

## Size and explainability

| File | Lines |
|---|---|
| `scripts/pull.sh` | 252 |
| `scripts/make-workcopy.sh` | 78 |
| `scripts/logged-shell.sh` | 85 (was 47; Chunk S added `pick_name()`) |
| `tools/tests/test_scripts.py` | 1044 (72 tests) |

Plain Bash, no clever one-liners: every check is its own line with a why-comment (user, 2026-10-20: simplicity beats line count). The programs each script calls directly, besides bash's own built-ins:

| Script | Calls |
|---|---|
| `pull.sh` | `cat`, `mkdir`, `mktemp`, `mv`, `ssh-keygen`, `ssh-copy-id`, `rsync` (which starts `ssh`) |
| `make-workcopy.sh` | `git`, `rm`, `mkdir`, `cp` |
| `logged-shell.sh` | `whoami`, `date`, `mkdir`, `mktemp`, `cat`, `script`, `rm`; the logged shell it starts also runs `sed` and `date` after each command |

In the tests, `PATH` holds only the stubs, the base real commands and each test class's extras (section 2), so a script that started calling anything outside those would fail with "command not found".

## 1. The scripts

### `scripts/pull.sh`

#### Header, `set -euo pipefail`, `LC_ALL=C` and the rules - lines 1-34
The usage comment, strict mode, the C locale, the paths (`WORKDIR`, `CONFIG`, `KEY`) and the four format rules: `NAME_RULE`, `LOGIN_RULE`, `IP_RULE`, `COUNT_RULE`.

**If Operations asks:** "The top of the script says how to use it and sets the rules every answer must pass. A name can only be lowercase letters, digits and dashes, so it can't point outside the teammate's `incoming/` folder."

**Why `LC_ALL=C`:** in some locales (e.g. Latin-1) `[a-z]` also matches accented letters. The C locale makes it the 26 ASCII letters (SCR-01 round-1 CR-1).

**Limit:** `IP_RULE` checks only four dot-separated numbers, not that each is 255 or less; a wrong address shows up when `ssh-copy-id` can't connect. `LOGIN_RULE` accepts only lowercase Linux-style logins (e.g. `kali`).

#### `fail()` - lines 36-39
Prints `pull: <message>` to stderr and exits 1.

**If Operations asks:** "Every error goes through one line, so each message starts with `pull:` and the script always stops with exit code 1."

#### `ask()` - lines 41-49
Prints a question, then reads one answer; stops setup if there is no answer.

**If Operations asks:** "It asks one question and reads one answer. If the answers run out, setup stops instead of guessing."

**Why `printf`, not `read -p`:** `read -p` shows nothing when the answers come from a file or a pipe, so the tests couldn't see the questions.

#### `check_value()` - lines 51-54
Stops with `<field> "<value>" is not allowed. <hint>` unless the value matches its rule.

**If Operations asks:** "Each answer is checked against its rule, and a bad one stops setup with a message saying which field and why."

#### `confirm_replace()` - lines 56-63
Shows the existing teammate list and asks whether to replace it; succeeds only on exactly `yes`.

**If Operations asks:** "If there's already a list, it shows it and asks first. Only a typed `yes` replaces it; anything else keeps it."

#### `run_setup()` - lines 65-78
`--setup`: needs `~/cptc-work`; on an existing list that isn't replaced, re-checks it with `check_list()` and keeps it; otherwise asks for every teammate; then makes the key and copies it to everyone.

**If Operations asks:** "Setup either takes a new list or keeps the old one after checking it, and then sets up the SSH key for each teammate. Rerunning it after one teammate's box wasn't ready doesn't mean retyping the whole team."

**Why keep the list on anything but `yes`:** at kickoff, a rerun usually means one teammate's SSH server wasn't up yet (SQ-08 A, SCR-04).

#### `ask_for_teammates()` - lines 80-110
Asks the count, then each teammate's name, login and IP once; refuses a repeated name; writes the whole list at once.

**If Operations asks:** "It asks each question once, checks each answer, and saves nothing until every answer is fine. Then it writes the whole file in one step."

**Why `mktemp` then `mv`:** the rename is one step, so a crash leaves the old list or the new one, never half of each. `mktemp` makes the file mode 600 (owner only), and it holds engagement IPs.

**Limit:** a Ctrl-C between `mktemp` and `mv` can leave a hidden `.teammates.XXXXXX` file in `~/cptc-work` (also git-ignored).

#### `make_key()` - lines 112-130
Reuses `~/.ssh/cptc_ed25519` if both halves exist; refuses half a key or a broken symlink at either path; otherwise creates `~/.ssh` (mode 700) and an Ed25519 key with no passphrase.

**If Operations asks:** "Pulls use their own key, never your personal one. It's created only if it isn't there, and a half-made or broken key is refused rather than overwritten."

**Why `-L` as well as `-e`:** `-e` misses a broken symlink, and `ssh-keygen` would write through it (SCR-02 round-1 CR-1).

#### `copy_key_to_teammates()` - lines 132-151
Runs `ssh-copy-id -i <key>.pub login@IP` once per teammate; a failure is named and the rest still run; exits 1 naming everyone who failed.

**If Operations asks:** "This is the one time each teammate's password is typed. After it, pulls log in with the key."

**Why file descriptor 3:** the list is read on descriptor 3, so `ssh-copy-id` keeps the keyboard for the password and can't swallow the rest of the list.

**Why `|| [ -n "$name" ]`:** a hand-edited kept list can lose its final newline; `read` then fails on that last line but has filled it in, so this keeps it, as `check_list()` does. Without it the last teammate got no key and setup still printed "Setup done" (Chunk S CR-1).

#### `require_config()` - lines 153-157
Stops with `no teammate list at ... Run setup first: <script> --setup` if the list is missing.

**If Operations asks:** "Without the list there's nobody to pull, so it says exactly which command to run."

#### `check_list()` - lines 159-177
Re-checks every line of the list with setup's rules, including repeated names, naming the line number; keeps a last line with no newline.

**If Operations asks:** "The list could have been edited by hand, so before every pull, and before setup reuses it, each line is checked again. A bad line stops everything before any connection."

**Why check repeated names here too:** two rows for one name would both mirror into one `incoming/<name>/` folder (SCR-03 round-1 CR-1).

#### `pull_one()` - lines 179-209
Refuses a symlinked `incoming/<name>/`, creates it, then one `rsync` call that mirrors only the four folders.

**If Operations asks:** "One connection per teammate copies just their findings, evidence, field notes and tracker into their `incoming/` folder. Files they deleted are deleted here too, and nothing is ever written on their box."

| Option | What it does |
|---|---|
| `-a` | copies files with their times and permissions; symlinks stay symlinks |
| `--include='/findings/***'` (and the other three) + `--exclude='*'` | only the four folders, anchored to the top of the teammate's `cptc-work/` |
| `--delete` | a file the teammate deleted is deleted here |
| `--delete-excluded` | anything else in `incoming/<name>/` (e.g. left from an unzip) is removed too |
| `-e "ssh -i '<key>' -o IdentitiesOnly=yes -o BatchMode=yes"` | logs in with the pull key only, and fails instead of asking for a password |

**Why `IdentitiesOnly`:** without it, ssh also offers keys from your agent, so a teammate missing the pull key could still be pulled with a personal key (SCR-03 round-1 CR-2).

**Limit:** a single quote in the home folder path would break the `-e` string (Kali homes are `/home/<login>`). A teammate's symlinks are copied as links; `compile.py` refuses ones that resolve outside the working copy (OQ-17). The filter flags were checked against Apple's openrsync on the Mac; GNU rsync 3.x on Kali is a manual check at the Chunk S stop.

#### `run_pull()` - lines 211-234
Pulls every teammate, or only the exact name given; a failure is named and the rest still pull; then `Pulled N teammate(s).`, and exit 1 naming anyone not pulled.

**If Operations asks:** "If one box is off, the others are still pulled, and the script says who's missing and exits with an error, so a partial pull is never silent."

#### `main()` + `main "$@"` - lines 236-252
Refuses more than one argument and an empty name; runs setup, or checks the list, the key and `incoming/` (no symlink), then pulls.

**If Operations asks:** "`pull.sh` pulls everyone, `pull.sh alice` pulls only alice, and `pull.sh --setup` is the one-time setup. Every check runs before any connection."

**Why refuse an empty name:** `pull.sh ""` (e.g. from an unset variable) would otherwise mean everyone.

### `scripts/make-workcopy.sh`

#### Header, strict mode, `LC_ALL=C` and `NAME_RULE` - lines 1-20
Usage, what it creates, and the same safe-name rule as `pull.sh`.

**If Operations asks:** "At kickoff each person runs this once. It makes `~/cptc-work`, a copy of the team repo that can't be committed from."

#### `fail()` + `fail_partial()` - lines 22-31
`fail()` stops with `make-workcopy: <message>`; `fail_partial()` adds that `~/cptc-work` is incomplete and should be deleted before running again.

**If Operations asks:** "If something goes wrong after the copy exists, it says so and tells you to delete it and start over. The script never deletes anything itself."

#### `check_arguments()` - lines 33-41
Exactly two arguments, a safe name, a non-empty source, and no `~/cptc-work` (a folder, file, symlink or broken link); all before `git` runs.

**If Operations asks:** "It refuses before touching anything if you already have a working copy, so it can never overwrite event work."

#### `main()` + `main "$@"` - lines 43-78
`git clone -- <source> ~/cptc-work`, delete its `.git`, refuse source symlinks on every path it writes through and an existing `tracker/`, `exclude.txt` or `.cptc-name`, require `templates/tracker/`, then create `field-notes/<name>/`, `incoming/`, `tracker/`, an empty `exclude.txt` and `.cptc-name`.

**If Operations asks:** "It clones the repo, removes the git folder, checks nothing in the clone could redirect a write, and then creates our standard folders and files."

**Why `--` after `clone`:** a source starting with `-` (e.g. `--upload-pack=x`) would otherwise be read as a git option.

**Why refuse source symlinks:** a repo can contain symlinks, and `mkdir -p field-notes/alice` through a linked `field-notes` would write outside `~/cptc-work` (SWC-01 round-1 CR-1).

**Limit:** `git clone` copies only what is committed in the source clone: uncommitted edits and deletions, and untracked files, are not carried over. The docs say to run `git status` in the clone first.

### `scripts/logged-shell.sh` (Chunk S changes only)

#### `pick_name()` - lines 9-45
The session name: a typed name if it is safe (otherwise one line and `return 1`), else the one-line `~/cptc-work/.cptc-name`, else `whoami` with a one-line warning.

**If Operations asks:** "The log files are named after you. It takes the name you type, or the one saved when you made your working copy, or your login as a last resort with a warning."

**Why a typed name is checked:** a name with `/` or `..` would put the logs outside `~/cptc-logs/` (SQ-09 A, SLOG-02).

**Why `printf`, not `echo`:** `echo` treats some words, such as `-n`, as its own options (SLOG-01 round-1 CR-1).

**Why two `read`s:** the saved file must hold exactly one line; `$(< file)` would strip any number of trailing newlines (SLOG-01 round-1 CR-2). The first `read` fails on a last line with no newline but still fills `saved`. That failure can't stop the script: the only call (line 48) is on the left of `||`, where bash ignores `set -e`.

**Why `local LC_ALL=C`:** it pins `[a-z]` for the check only; `pick_name` runs in `$(...)`, so the logged shell keeps your locale.

#### The call - line 48
`name="$(pick_name "${1:-}")" || exit 1`: a refused typed name stops the script before the log folder, the startup file or any log is made.

**If Operations asks:** "A bad name stops it right there, before anything is written."

## 2. Test helpers: `tests/test_scripts.py`

`tests/support.py` is shared; see [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy).

### Module docstring + imports - lines 1-18
What the tests isolate (fake HOME, stub-only `PATH`, no network, no real `~/.ssh`, every write inside the repo), then `support` first.

**If Operations asks:** "The tests never touch the real machine: each runs in a throwaway folder inside the repo, with fake network commands."

### Paths, `BASH`, `STUBBED_COMMANDS`, `STUB`, `REAL_COMMANDS` + answer fixtures - lines 20-43
The script paths; bash found once on the real `PATH`; the five stubbed commands and the stub that records `<command> [arg] [arg]...`; the real commands every test gets (`cat`, `mkdir`, `mktemp`, `mv`: all `pull.sh` needs) and the two more `make-workcopy.sh` needs (`cp`, `rm`); a two-teammate answer set and its expected file. `LoggedShellNameTests` adds the real `date` and `rm` and fakes `script` and `whoami`.

**If Operations asks:** "Each fake command writes down how it was called, so a test can check the exact `ssh` or `rsync` command without running it."

**Why brackets:** an empty argument (the `-N ""` passphrase) shows up as `[]`.

**Why per-script real commands:** a shared list would let `pull.sh` start calling `cp` or `rm` unnoticed (SWC-01 round-1 CR-2).

### `make_stub_path()` + `link_real_commands()` - lines 46-62
Creates `HOME/bin` with the stubs and symlinks to the allowed real commands.

**If Operations asks:** "The test's `PATH` holds only these, so any other command a script tried would fail with 'command not found'."

### `ScriptTestCase` - lines 65-105
Each test gets a fake HOME from `make_worktree()`, the stub `PATH` and `~/cptc-work`; `run_script()` runs bash with only `HOME` and `PATH` (plus `LC_ALL` or extra variables when a test asks); `stub_calls()`, `workdir_names()` and `fail_stub()` (a stub that fails when its arguments contain a given text). Skips if bash is missing.

**If Operations asks:** "Every test starts from an empty fake home folder, so no test can see the real home folder or another test's files."

### `FAKE_GIT_CLONE` + `FAKE_REPO_FILES` - lines 648-662
A fake `git clone` that copies `HOME/fake-repo` (with its own `.git`) to the destination, and that repo's files.

### `FAKE_SCRIPT` + `FAKE_WHOAMI` - lines 865-870
A fake util-linux `script` that records its call and the `LC_ALL` it got, and never records anything; a fake `whoami` that prints `kali`.

**If Operations asks:** "The logging tests never start a real recorder; a fake one just notes how it was called."

## 3. Tests

#### `PullSetupTests` - lines 108-148
- `--setup` prints each question once, then the key lines; writes the exact list bytes, mode 600, no temp file left; calls only `ssh-keygen` and two `ssh-copy-id`s
- spaces around an answer are dropped
- no `~/cptc-work` is refused
- answers running out stop setup with nothing written

#### `PullSetupRefusalTests` - lines 151-228
- unsafe names (`..`, `../x`, `a/b`, `-rf`, `Alice`, a tab, `~x`, empty, ...), each in a fresh HOME, refused with nothing written
- accented letters refused in a Latin-1 locale (bytes) and in UTF-8
- a repeated name, bad logins (including `-oproxycommand`), bad IPs and bad counts refused

#### `PullSetupRerunTests` - lines 231-334
- anything but `yes` keeps the list: exact output, key step, one `ssh-copy-id` per kept teammate, bytes unchanged
- keeping the list reuses an existing key, still names a failed copy, and still copies the key to a last line with no newline (Chunk S CR-1)
- a bad kept list (path name, repeated name, bad login, bad IP) is named by line and runs no ssh at all
- `yes` replaces the list and sets up the new teammates; `yes` plus a bad answer keeps the old list

#### `PullKeySetupTests` - lines 337-451
- a missing key is created with the exact `ssh-keygen` arguments and `~/.ssh` mode 700; an existing key is reused untouched
- each teammate's login and IP go to their own `ssh-copy-id`
- half a key, or a broken symlink at either key path, is refused with no ssh and nothing created
- an `ssh-keygen` failure stops before copying; a failed copy is named and the rest still run; every failure is named
- the script never contains `sudo`

#### `PullTests` - lines 454-606
- no name pulls everyone once, with the exact `rsync` arguments; a name pulls only that teammate
- unknown or inexact names (`carol`, `ali`, `Alice`, `alice `) and an empty name pull nobody
- a failed teammate is named and the rest still pull; one named teammate failing exits 1
- a missing key, a symlinked `incoming/` and a symlinked `incoming/alice/` are refused (others still pulled)
- a bad or repeated line in a hand-edited list stops every pull; a last line with no newline still counts; an empty list and too many arguments are refused

#### `PullRealRsyncTests` - lines 609-645
- replays the recorded `rsync` arguments through the real local rsync (local folders, no `-e`): only the four folders remain, and deleted and stray files are removed. Skips if rsync is missing.

**Limit:** it ran here on Apple's openrsync; on Linux CI it checks GNU rsync only if rsync is installed there.

#### `MakeWorkcopyTests` - lines 665-862
- the exact `git clone -- ...` call and the full resulting layout (no `.git`, the tracker copy, empty `exclude.txt`, `.cptc-name`); the source keeps its `.git`
- a Git URL and a `-`-leading source are passed after `--` as given
- an existing folder, file, symlink or broken symlink at `~/cptc-work`, unsafe names (also in Latin-1), wrong argument counts and an empty source are refused before git
- a failed clone stops everything; a source without `templates/tracker/`, or with its own `tracker/`, `exclude.txt` or `.cptc-name`, stops with the "incomplete" message and adds nothing
- source symlinks at `templates`, `templates/tracker`, `field-notes`, `field-notes/alice` and `incoming`, and broken links where files are made, are refused with their targets untouched
- the script never contains `sudo`

#### `LoggedShellNameTests` - lines 873-1026
- a typed name wins over the saved one; a typed name breaking the rule (`../x`, `a/b`, `-n`, `Alice`, `café`, ...) is refused with one line, no `script` call, no log folder and no temp file (also in Latin-1)
- a saved name is used without a warning (with or without a final newline)
- no saved name, no working copy, an invalid saved name (two lines, blank lines, wrong letters, ...), an unreadable file or a folder in its place: the one-line warning and `kali`
- the logged session keeps the caller's `LC_ALL`; logs go to `LOGDIR` with the `.cmds.log` index beside them

#### `PullMissingConfigTests` - lines 1029-1040
- `pull.sh` and `pull.sh alice` without a list say how to run setup, and call no stub

**If Operations asks:** "These run each script on fake data in a fake home folder, with fake network commands, and check exactly what it printed, wrote and tried to run. We also broke each part of the scripts on purpose and checked that a test failed."

## 4. Related edits outside tools/

### `.gitignore` lines 11-13 and 36
Lines 11-13: a comment, then `/teammates.txt` and `/.teammates.*` (the list and setup's temp copy), in the event working-files section (SDOC-01). Line 36: `exclude.txt` replaces `ot-hosts.txt` among the scan files (one skip list; edited by another session, in the Chunk S commit).

**If Operations asks:** "The teammate list has engagement IPs and the skip list has the client's exclusions, so git ignores both even if someone saves them inside a clone."

### `scripts/logged-shell.md`
"How to use it" (the name rule, the saved name and the fallback warning); the "Line by line" entry for lines 9–45 and every later line reference renumbered to the new script (SLOG-01, SLOG-02); the Windows section's `prompt` line and its explanation (SDOC-04).

**If Operations asks:** "The walkthrough matches the script line for line, and the Windows box gets a prompt that shows the time."

**Limit:** the PowerShell `prompt` line hasn't been run here (no PowerShell on the Mac); it is a manual check at the Chunk S stop.

### Team-repo staging copies (`_staging/to-team-repo/`, git-ignored here)
- `README.md`: the working copy is made with `make-workcopy.sh` (with the committed-only warning in bold), and its list of what the script creates names the empty `exclude.txt` as the scans' skip list (line 57, CS-01); pulls use `pull.sh --setup`, `pull.sh` and `pull.sh <name>`; numbered step 2 makes the working copy before the logged shell (SDOC-02, SCR-04).
- `checklists/00-kickoff.md`: the working-copy step uses the script and names `exclude.txt` (SDOC-02, CS-01); the SSH step adds `pull.sh --setup`; the tracker item is "Check that ... exists". Line 15, rewritten by another session, now builds `exclude.txt` from the SOW exclusions.
- `WORKFLOWS.md`: steps 1.1, 1.10 and 2.2 use the scripts; D-11 in steps 1.10, 2.4 and 2.5; D-12's order in step 2.6 (SDOC-03). The user confirms the whole diff at the Chunk S stop.

**If Operations asks:** "The team's instructions now say to run the scripts instead of typing the commands by hand."

### `templates/tracker/README.md` line 13
The `hosts.csv` row now says to add `ot-do-not-touch` hosts to `exclude.txt` tagged `# OT`, instead of `ot-hosts.txt` (one skip list; edited by another session, in the Chunk S commit).

**If Operations asks:** "OT hosts go in the same skip list as the scope exclusions, marked `# OT`, so one `--excludefile` keeps scans off both."

### `TODO.md` item 13, lines 21 and 24
`ot-hosts.txt` is now `exclude.txt` in the Medium option and in the list of files `make-workcopy.sh` creates (CS-01).

### `tools/compile-breakdown.md` lines 1142 and 1144
The `ModuleSafetyTests` entry now says the tests check imports and banned names, not that they prove the tool can't run commands (C-N1-04).

### `tools/README.md` (in `tools/`, not code)
New sections "Making your working copy" and "Pulling teammates' work" (lines 26-87); in the first, the created files include an empty `exclude.txt`, described as the scans' skip list (SOW exclusions, OT hosts tagged `# OT`; line 42, CS-01), and the "incomplete" failure row names `exclude.txt` (line 52); the intro, the table and line 5 name the scripts; the logged-shell name bullet (line 97); D-11 in "The checks" (line 192) and "One ID = one file" (line 220); the tool-fix line (line 362).

### Files added
`scripts/pull.sh`, `scripts/make-workcopy.sh`, `tools/tests/test_scripts.py` and this file. The `checklists/` changes in `git status` are the user's own edits, not Chunk S; `checklists/10` and `30` among them also use `exclude.txt` and its `# OT` tag, so they match the new skip list.
