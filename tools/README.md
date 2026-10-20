# Tools and scripts: how to run them

This is the one README for the team's tools and scripts: `tools/compile.py`, `tools/notebook.py` (planned) and `scripts/logged-shell.sh`. It says what each one does, how to run it, and the rules every one of them follows.

**Before running anything, set up your working copy, `~/cptc-work`**: comp repo `README.md` → "Working copy and moving files on the day". Every command below runs from inside `~/cptc-work`, never from the git clone.

## Rules for everything in `tools/` and `scripts/`

- **Explain it or it doesn't go in (rule R4).** Every script or tool must be explainable line by line, written by us, standard library only, with no copied code we don't understand. The rulebook says teams "may be asked to demonstrate or explain their pre-written scripts or code during the event." (**Unconfirmed** whether AI-assisted code counts; blocked by the open question "Does the 'explain your code' rule cover AI-assisted code?")
- **Short enough to explain.** Keep every script short enough that any team member can walk through it.
- **No exploit code copied from elsewhere** without understanding it, and **no credentials or targets hard-coded**.
- **Python 3 standard library only** for the tools: no `pip install`. The full design constraints are in `tools/BUILD-SPEC.md`.

## What's here

| Path | What it is | Status |
|---|---|---|
| `scripts/logged-shell.sh` | Records every terminal session, with a one-line-per-command index. Needs util-linux `script` (default on Kali/Debian) | Built. Walkthrough: `scripts/logged-shell.md` |
| `tools/compile.py` | Assembles everyone's findings into report-ready Markdown and checks them for QA problems | **In progress:** the foundation is built (parsing findings, path safety, the findings index); the outputs, the QA checks and the command itself are not yet. Code walkthrough: `tools/compile-breakdown.md` |
| `tools/notebook.py` | A local web page for notes, new files from the templates, logs and export | Planned (design: `tools/BUILD-SPEC.md`, Tool 2) |
| `tools/tests/` | Unit tests: `python3 -m unittest discover tools/tests` | Built |
| `tools/BUILD-SPEC.md` | The design brief both tools are built from | — |

## Logging every terminal: `scripts/logged-shell.sh`

Start it in every terminal, from inside `~/cptc-work`:

```
scripts/logged-shell.sh <yourname>
```

- **Always give your name.** Without it, the logs are named after your login, and every competition Kali box may log in as `kali` (**Unconfirmed**; open question "Did every box log in as the same user?"), so nobody could tell whose log is whose.
- **What it writes:** two files per session in `~/cptc-logs/`: `<name>_<UTC time>.log` (the full transcript) and `<name>_<UTC time>.cmds.log` (one line per command: time, exit code, directory, command). Type `exit` to stop; the file paths are printed.
- **Every new terminal, automatically:** add the zsh auto-start block to `~/.zshrc` (`scripts/logged-shell.md` → "Optional: start logging automatically in every terminal"). It hasn't been tested in zsh yet; try it on your own Kali VM first.
- **Windows box:** the script is Linux-only. Start a PowerShell transcript in every PowerShell window instead (`scripts/logged-shell.md` → "On the Windows box").
- **Finding the lines for a finding:** look up the time in `*.cmds.log`, then open the full transcript with `less -R ~/cptc-logs/<file>.log` (`/` and a word to search, `q` to quit), or in the notebook's Logs view once it's built.

Full walkthrough, line by line: `scripts/logged-shell.md`.

## Assembling the report: `tools/compile.py` (in progress)

**Not runnable yet:** only the foundation is built. This section describes the finished tool as specified in `tools/BUILD-SPEC.md` (Tool 1); it's updated as each part is built and reviewed. Until then, paste findings into `report.md` by hand, ordered by severity, and run `checklists/50-report-qa.md`.

The report writer will run it from inside `~/cptc-work`:

```
python3 tools/compile.py            # draft mode: any time during the event
python3 tools/compile.py --final    # final 90 minutes, before every submission
```

**What it will read:** `findings/F-*.md`, teammates' `incoming/*/findings/F-*.md`, the `IR-`, `SU-` and `INJ-` files under `field-notes/` and `incoming/*/field-notes/`, and `tracker/findings-index.csv` (or `--index PATH`).

**What it will write** (all to `build/`, regenerated from scratch every run; it never touches `report.md`):

| File | Paste it into |
|---|---|
| `build/findings-summary.md` | Section 3 (the findings table) and the Executive Summary counts |
| `build/findings-combined.md` | Section 5: all findings, in severity order. Paste each finding once, when it's READY (R18) |
| `build/interactions-timeline.md` | Section 7: the timeline built from the `IR-`, `SU-` and `INJ-` files |
| `build/qa-report.txt` | Nothing: it's the QA results, PASS/FAIL with file and line, and READY or DRAFT for each finding |

**Draft mode** (the default) will warn but never fail: it always writes every file and exits 0, because drafts with `[[…]]` markers are normal during the event.

**`--final`** will check the Markdown report and every finding. Every QA problem becomes an error, and it exits 1 if anything fails. It also checks `report.md` for leftover markers if it's there, and prints `report.md NOT FOUND: report not checked` if it isn't. **Limit:** it can't read the exported PDF or DOCX, so the manual checks in `checklists/50-report-qa.md` still apply.

**Safety (built):** it refuses a root folder that contains `.git` (the git clone), so `build/` and event data can't land in the public repo.

**Practice runs and tests:** use a different folder with `--root`, for example `python3 tools/compile.py --root ~/cptc-practice`.

How it works, function by function: `tools/compile-breakdown.md`.

## Notes, new files and export: `tools/notebook.py` (planned)

Not built yet. The plan (`tools/BUILD-SPEC.md`, Tool 2):

```
python3 tools/notebook.py --name <yourname>    # then open http://127.0.0.1:8765
```

- **Local only:** a page on your own box, bound to `127.0.0.1`. It's not a server for the team.
- **New file:** a finding (from `templates/finding.md`, or a `findings-library/` entry) in `findings/`; a note, incident report, status update or inject response (`NOTE-`, `IR-`, `SU-`, `INJ-`) in `field-notes/<yourname>/`. File names: `templates/README.md` → File names.
- **Logs:** read-only view of `~/cptc-logs/`.
- **Export:** one zip, `cptc-export-<name>-<timestamp>.zip`, laid out so unzipping it inside the report writer's `incoming/<name>/` gives the same mirror an `rsync` pull would. This is option 3 in the comp repo `README.md` → "Getting files to the report writer".

**Until it's built:** copy templates by hand (`cp templates/finding.md findings/F-NNN-short-name.md`), and make the handover archive with `zip -r`.

## Picking up a tool fix mid-event

Never re-run the working-copy command. Copy just the changed file from a fresh clone: comp repo `README.md` → "Working copy and moving files on the day".

## Still to write (build workflow)

`tools/BUILD-SPEC.md` (Deliverables) asks this README to cover these too. They're added as each tool is finished and reviewed.

### How each tool works, section by section

`compile.py`: see `tools/compile-breakdown.md` for now.

### Manual test checklist

To do.

### Questions Operations might ask

To do. `scripts/logged-shell.md` has its own.
