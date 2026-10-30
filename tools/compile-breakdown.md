# compile.py breakdown

Every block of `compile.py`, its test helpers, its tests, and the related edits outside `tools/`. The rulebook says Operations may ask us to explain our code, so each entry has a line range, a one-line description, and **If Operations asks:** a plain answer a student can give.

Line ranges match the code after the Chunk 7 review. Chunk 7's own tasks changed only docs, the report QA list and the CI workflow; its review added `misplaced_timeline_files()` and its tests (C-23, CT-23). Chunk 8 changed only docs (`tools/README.md`, entry in section 4, and `TODO.md`), so no code or test range moved. The implementor updates this file at the end of every review chunk; the code reviewer checks it.

| Term | Meaning |
|---|---|
| marker | a `[[NAME]]` placeholder in a template, waiting to be filled in |
| working copy | `~/cptc-work`: a plain copy of the repo with no `.git`, where all event work happens |
| root | the working copy folder the tool reads from (`--root`) |
| READY / DRAFT | a finding's status: READY means no leftover markers, no missing required fields, a severity word and a title; anything else is DRAFT |
| `--final` | strict pre-submission mode: QA problems become errors (older-style leftovers and an absent or empty index stay warnings), and any error makes the run exit 1 |
| diagnostic | one problem found in a file, with the file name and the line (or field) it is on |
| problem | a diagnostic with its level, WARNING or ERROR, as printed: `ERROR: file:line: message` |
| QA check | one named check in `build/qa-report.txt` (e.g. leftover markers), shown as PASS or FAIL with its problems |
| exit code | 0: no errors (every draft run that finishes); 1: `--final` found an error; 2: the tool couldn't run, in either mode |
| findings index | `tracker/findings-index.csv`: the team's master list of finding IDs, in its `finding_id` column |
| incoming | `incoming/<name>/`: a teammate's files copied in; the tools only read it (rule R18) |
| older-style leftover | a placeholder from before the `[[...]]` markers, like `TODO`, `XX` or `YYYY`; always a warning |
| timeline file | an `IR-` (incident report), `SU-` (status update) or `INJ-` (inject response) file in `field-notes/<name>/`; one row each in the interactions timeline (one saved in a likely wrong spot is reported instead; C-23) |

## Size and explainability (CP-01)

Measured on 2026-10-21, after the CP-01 comment fixes below. No code was compressed to reach a number (user, 2026-10-20: simplicity beats line count).

| Lines in `compile.py` | Count |
|---|---|
| code | 763 |
| docstrings | 366 |
| comments | 235 |
| blank | 187 |
| **total** | **1551** |

A line with code and a comment after it counts as code (there is 1). Since then, C-23 (Chunk 7 CR-3) added `misplaced_timeline_files()` (26 lines, 16 of them code) and 2 lines in `collect_qa()`, so the file is 1581 lines. The spec's guideline is about 200–250 lines (Constraint 6, "guidelines, not hard caps"). Code lines alone are about three times that.

**Why it is bigger than the guideline:** it does more than the spec's first estimate covered:
- 13 named QA checks, plus the two `report.md` checks in `--final`.
- Rules the user added after the spec: the required-fields check (C-19 Q2), the full CVSS 3.1 vector (Chunk 3 CR-4), extra READY conditions (C-15 Q2/Q3), the Status and Summary pipe checks (C-16, C-17B), escaped pipes (Chunk 4 CR-4), and refusing links at `build/` (C-21).
- A path check on every folder and file it reads, so a symlink can't lead outside the root.
- Guards so the QA report refuses a missing or misspelt check name, and a `--final` report without the `report.md` result.
- Readable `compile failed:` errors instead of tracebacks.

**Function size:** 65 functions and 2 small exception classes. The median function is 16 lines in total, 8 of them code.

| Longest functions | Total lines | Code lines | What makes it long |
|---|---|---|---|
| `parse_labelled_fields()` | 54 | 29 | label lines, duplicates, missing labels, then the CVSS vector and score |
| `render_qa_report()` | 54 | 31 | three guards (missing check, unknown check, no `report.md` result), then the report text |
| `parse_timeline_entry()` | 52 | 33 | heading, pipe check, time line and time format in one pass |
| `load_index_ids()` | 52 | 30 | one early return per kind of unusable index |
| `parse_finding_heading()` | 48 | 28 | five heading problems |
| `collect_qa()` | 46 | 28 | the steps of a compile, in order |
| `check_finding()` | 46 | 34 | the per-finding checks, in order |
| `write_outputs()` | 43 | 31 | check every output path before writing any |

**Possible splits (not done; each needs App Dev Manager's OK first; the adversary recommends none before M2, since the longest functions are 28–34 code lines and no defect calls for a split):**
1. `finding_folders()` could call `child_folders(root, "incoming")` instead of its own loop. Why: the same "check where it points before `is_dir()`" loop is written twice.
2. Move the CVSS vector/score part of `parse_labelled_fields()` into its own small function. Why: it is a separate job inside the longest function.
3. Move the three guards at the top of `render_qa_report()` into their own function. Why: it keeps "refuse an incomplete result" apart from "write the text".

The other long functions are plain step lists or one early return per case. Splitting them would add jumps without making them easier to explain.

**Comment fixes made in CP-01** (comments and docstrings only, no behaviour change):
- Module docstring: it said the tool "checks every finding against `checklists/50-report-qa.md`". It runs some of the checklist's checks on the Markdown files. The checklist's other items, and the search of the exported PDF/DOCX, still apply.
- `resolve_in_root()` docstring: only the outside-the-root error says where the path points. The `..` error names just the path.
- `parse_finding_heading()` docstring: the list of heading problems was missing "no ID".
- `load_index_ids()`: added why-comments. Spaces around a column name are ignored. A short row or a blank ID cell is skipped. An ID listed twice keeps its first line.
- `collect_qa()`: added a why-comment. Every check starts empty, so a check that finds nothing still shows PASS.
- `render_qa_report()` comment (and the CTX-01 test comment): narrowed. They said a check the caller "forgot to run" can't show PASS. The `render_qa_report()` comment now says what the guards do. A missing name gets a readable error instead of a bare KeyError. An unknown name is refused so its problems can't drop out of the report and the exit code. An empty list can't show whether the check ran (see Limits). The test comment says it checks each result line is there, not that the check behind it ran.

**Limits found in CP-01:**
- An ID listed twice in the findings index is not reported (checked: `F-001` on two rows loads once, with no problem). Two finding *files* with the same ID are still reported by the duplicate-ID check.
- The QA report's guards refuse a missing check *name*, not a check that was never *called*: `collect_qa()` starts every check as an empty list, and an empty list prints PASS (adversary probe: `{name: [] for name in QA_CHECKS}` prints 13 PASS lines). Catching that would need a marker that each check really ran, which is a behaviour change and needs App Dev Manager's OK.

**Python 3.9 run:** `/usr/bin/python3` is the real Python 3.9.6 from Apple's Command Line Tools. The `python3` on PATH (a pyenv shim) resolves to it.

| Command (from the repo root) | Result |
|---|---|
| `/usr/bin/python3 --version` | `Python 3.9.6` |
| `/usr/bin/python3 -m unittest discover tools/tests` | `Ran 268 tests` … `OK` (264 at CP-01; CT-23 added 4) |
| `/usr/bin/python3 -m unittest discover -s tools/tests -p 'test_compile.py'` | `Ran 259 tests` … `OK` |

## 1. compile.py

### Module docstring - lines 1-14
What the tool does, how to run it, and what it never does.

**If Operations asks:** "It's the description at the top of the file. It says what the tool does, how to run it, and what it never does: it doesn't run commands, doesn't use the network, and only writes to `build/`."

### Imports + `MARKER_RE` - lines 16-37
Matches one whole marker, including a multi-line NOTE. Stops at the next `[[`.

**Imports:** standard library only. `shutil` is used only to look pandoc up (`shutil.which`) and `shlex` only to quote the paths in its hint; neither runs anything.

**If Operations asks:** "It finds placeholders like `[[HOST]]` so we can ignore them when checking whether a field is filled in. It needs a capital letter right after `[[`, so bash `[[ -f x ]]` tests are skipped. It can't run past the next `[[`, so a placeholder missing its closing brackets can't hide the next one."

**Limit:** names with digits, like `[[HOST2]]`, aren't matched. That's on purpose: `templates/README.md` says marker names are capitals and underscores only.

### `LEFTOVER_RE` - lines 39-46
Matches the start of any leftover marker, closed or not. Same pattern as the checklist grep.

**If Operations asks:** "It's the same search as the grep in our QA checklist. It flags any leftover `[[NAME`, even one missing its closing brackets, so a draft can't slip into the report unnoticed."

**Why two regexes:**

| Regex | Needs | Used for |
|---|---|---|
| `MARKER_RE` | the whole marker, `[[` to `]]` | removing markers from text |
| `LEFTOVER_RE` | only the start, `[[NAME` | counting leftovers, including unclosed ones |

### `strip_markers()` + `scan_leftover_markers()` - lines 49-70
Removes complete markers; lists leftovers with file and line number (counting from 1).

**If Operations asks:** "The first removes placeholders so we can tell whether a field is really filled in. The second lists every placeholder still left, with its file and line, like `grep -n`. That count, plus any missing required fields, decides READY or DRAFT. Both run every time; they aren't options."

**Why split on `"\n"`:** it gives the same line numbers as `grep -n`. `splitlines()` also splits on rare characters like form feeds, which would shift the numbers.

### `expand_path()` + `parse_args()` (`--root`) - lines 73-93
Expands `~`. The root defaults to `~/cptc-work`, never the current folder.

**If Operations asks:** "It reads the command-line options. If you don't say where the working copy is, it uses `~/cptc-work`, never the folder you're in, so we can't accidentally write event data into our git repo."

**Why expand `~` in Python:** the shell skips it inside quotes, so `--root "~/cptc-work"` arrives as a literal `~`.

### `parse_args()` (`--index`, `--final`) - lines 94-106
Optional path to the findings index (a relative path starts at the root) and the strict-mode switch.

**If Operations asks:** "`--index` points at the findings list if it isn't in the usual place. The tool only reads it, to spot IDs that are missing or extra. `--final` is the strict pre-submission mode: problems become errors, and any error fails the run (exit code 1)."

### `RootError` + `validate_root()` - lines 109-131
The root must exist, be a folder, and have no `.git`. Creates nothing.

**If Operations asks:** "Before doing anything, it checks that the folder exists and isn't our git clone. Our repo is public, so the tool refuses to run anywhere event data could get committed."

**Limit:** only the root itself is checked for `.git`, not the folders above it. Checking those too would block anyone whose home folder is a git repo (dotfiles).

### `resolve_in_root()` - lines 134-156
Refuses `..`; follows symlinks; refuses anything outside the root and names the path.

**If Operations asks:** "Every file path goes through this check. It refuses `..` and anything that ends up outside the working copy, even through a symlink. So the tool can only touch files in our working copy."

### `finding_folders()` + `discover_findings()` - lines 159-201
Lists the finding files to compile: `findings/F-*.md` and `incoming/*/findings/F-*.md`, sorted by path.

**If Operations asks:** "It looks in exactly two places: our own `findings/` folder and each teammate's `incoming/<name>/findings/`. Only files named `F-something.md` count. It only lists them; it never writes in `incoming/`."

**Why check each folder before listing it:** a symlink such as `incoming/alice` could point outside the working copy. Every folder, every `incoming/<name>` entry and every file goes through `resolve_in_root()` first, so the tool never even looks inside a folder outside the root. If one points outside, `discover_findings()` raises an error naming it, instead of skipping that teammate (OQ-17).

**Why sort:** the disk lists files in no fixed order. Sorting gives the same order every run, with `findings/` before `incoming/`.

### `HEADING_RE` + `FILENAME_ID_RE` + `find_title_heading()` + `parse_finding_heading()` - lines 204-273
Reads the ID and title from the `### F-NNN: Title` line, and reports heading problems.

**If Operations asks:** "It finds the title line of a finding. If the ID is still the `[[FINDING_ID]]` placeholder, it uses the ID from the filename instead. It flags five problems: the heading and filename IDs differ, the title isn't a `###` heading, the title text after the colon is blank, there's no ID in the heading or the filename, or there's no title line at all."

| Heading | ID used | Problem reported |
|---|---|---|
| `### F-001: Title` in `F-001-x.md` | F-001 | none |
| `### [[FINDING_ID]]: Title` in `F-007-x.md` | F-007 (from the filename) | none here; the marker is counted as a leftover |
| `### F-002: Title` in `F-001-x.md` | F-002 (the heading wins: it's what goes in the report) | ID mismatch |
| `## F-001: Title` | F-001 | not a `###` heading |
| `### F-001:` with nothing after the colon | F-001 | no title text |
| `### [[FINDING_ID]]: Title` in a file without F-NNN | none | no finding ID |
| no title line | the filename's ID | no title heading |

**Why `###`:** finding files use `###` for the title and `####` for sections, so they fit under the report's `## 5. Detailed Findings` without changes.

**Blank title:** besides this warning, a blank title also makes the finding DRAFT (user decision 2026-10-20 C-15 Q3, in `finding_readiness()`).

**Limit:** an ID must be `F-` plus exactly three digits. `F-0012-x.md` is not read as F-001.

**Limit:** the first matching line wins, even inside a fenced code block. A template-shaped finding starts with its title, so this doesn't come up in practice.

### `FIELD_LABELS` + `LABEL_LINE_RE` + CVSS regexes + `parse_labelled_fields()` - lines 276-344
Reads the six required detail lines (`- **Severity:** …` and so on) and splits the CVSS line into vector and score.

**If Operations asks:** "Each detail in a finding is a line like `- **Severity:** High`. This finds the six we need by their label: Severity, CVSS 3.1, Why this severity, Affected assets, Status and References. Values are kept as written, placeholders included; only spaces at the ends are dropped. A missing line is reported with the file and field name; it never crashes the run. If a label appears on more than one line, the first one is used and each extra one is reported at its own line."

**Why `rstrip()` each line:** a file saved on Windows ends every line with `\r\n`. Splitting on `\n` leaves the `\r`, which would otherwise end up inside every value (and later inside the summary table).

**CVSS line:** the vector is the text between backticks, the score is the text in parentheses outside them. `` `CVSS:3.1/AV:N/...` (9.8) `` gives the vector `CVSS:3.1/AV:N/...` and the score `9.8`.

**Why two shapes of problem:** a missing label has no line to point at, so it is `(file, label, message)`. A duplicate does have one, so it is `(file, line, message)`, like the heading problems, e.g. `duplicate Severity line; line 3 is used`.

**Limit:** the colon must be inside the bold, as in the template (`- **Severity:**`). A hand-typed `**Severity**:` is reported as missing.

### `SEVERITIES` + `SEVERITY_RE` + `severity_value()` - lines 347-374
Takes the first exact level word from the Severity line, after removing markers.

**If Operations asks:** "It reads the severity word: Critical, High, Medium, Low or Informational, spelled exactly like that. Placeholders are removed first, because the unfilled `[[CHOOSE: Critical / High / …]]` lists every word and would otherwise read as Critical. No level word is reported as a problem (an error with `--final`), and the finding sorts last."

**Why case-sensitive:** the template offers exactly these words, so `high` means the line wasn't filled in properly.

**Why no second warning for a missing Severity line:** `parse_labelled_fields()` already reports it.

### `finding_sort_key()` - lines 377-388
Sort order: Critical → Informational, then no severity, then by ID.

**If Operations asks:** "Findings are listed most severe first, and by ID within each level. Anything without a severity goes at the end so it stands out."

### `DEFAULT_INDEX` + `index_location()` + `load_index_ids()` - lines 391-460
Reads the `finding_id` column of the findings index, to compare later with the finding files.

**If Operations asks:** "It reads the team's master list of finding IDs. If the list is missing or empty, the tool warns and skips the comparison instead of flagging every finding. If the file is broken, that's reported as a QA problem instead of crashing: a warning while drafting, an error with `--final`."

| Index file | Result | Level |
|---|---|---|
| has `finding_id` rows | the IDs, each with its line | none |
| absent | comparison skipped | warning |
| empty, or header only | comparison skipped | warning |
| not a valid CSV (e.g. a broken quote) | comparison skipped | warning in draft, error in `--final` |
| no `finding_id` column | comparison skipped | warning in draft, error in `--final` |

**Line 0:** a problem with the whole file (not found, not a readable CSV) is reported at line 0, since no single line is at fault.

**Why `utf-8-sig`:** spreadsheet programs save CSV with an invisible marker before the first column name. Without this, the column wouldn't be found.

**Why `index_location()` is its own function:** `collect_qa()` needs the same shown name for the ID membership messages, so both kinds of index problem name the same file (C-14 carry-forward).

**Limit:** an index path that can't be opened at all (e.g. no permission, or it is a folder) isn't caught here; the error is passed on, and `run()` turns it into `compile failed: ...` with exit code 2.

**Limit (found in CP-01):** an ID listed twice in the index keeps its first line and the repeat is not reported. A short row or a blank ID cell is skipped. Two finding *files* with the same ID are still reported by `check_duplicate_ids()`.

### `OLDER_LEFTOVER_PATTERNS` + `CODE_SPAN_RE` - lines 463-480
The seven older-style placeholders, one regex each, and the pattern for an inline code span.

**If Operations asks:** "These are the placeholders people typed before we had `[[...]]` markers: `<<`, `TODO`, `F-XXX`, `IR-XXX`, a bare `XX`, `YYYY` and `HH:MM`. They can show up for real (a `TODO` in quoted output), so they are only ever warnings, even with `--final`."

**Why `\bXX\b`:** only a bare `XX` counts, not the `XX` in `XXE` or `F-XXX`.

**Why `(`+).*?\1`:** a code span opens and closes with the same number of backticks, so ``` ``a ` b`` ``` is one span even with a backtick inside.

### `hide_todo_marker_words()` + `scan_older_leftovers()` - lines 483-521
Lists every older-style placeholder with file and line, skipping fenced code blocks, code spans, and the `TODO` inside a `[[TODO: ...]]` marker.

**If Operations asks:** "It's the second half of the QA checklist's search. It skips fenced code blocks and code spans, because commands and output aren't prose. It also skips the word TODO inside a `[[TODO: ...]]` placeholder, because the marker check already reports that one (OQ-02). Anything else inside a placeholder, like an `F-XXX` in a NOTE, is still reported."

**Why blank TODO with spaces:** nothing else on the line moves, so `X` + `X` can't join into a new `XX`, and line numbers stay the same.

**Why both fence kinds:** Markdown code blocks open with ```` ``` ```` or `~~~`. A block closes only on the same kind it opened with.

**Limit:** hits on the same line are listed in pattern order (`<<` first, `HH:MM` last), not left to right. The line number is always right.

**Limit:** a backtick with no closing partner can hide a little text after it from this check. Code spans spanning several lines aren't recognized.

**Limit:** a code block that is never closed hides the rest of the file from this check. The leftover-marker check still sees those lines.

**Limit:** only ```` ``` ```` / `~~~` fenced blocks and code spans are skipped. Code indented 4 spaces is checked like prose (Chunk 3 CR-1).

### `REPRODUCTION_HEADING_RE` + `SECTION_END_RE` + `STEP_RE` + `reproduction_section()` + `remove_note_markers()` + `check_reproduction()` - lines 524-592
Finds the `#### Reproduction steps` section and checks it has numbered steps, each with an `Expected:` line.

**If Operations asks:** "A finding without reproduction steps gets sent back (R7). This reads the section up to the next `###` or `####` heading, removes NOTE placeholders, then counts numbered lines (`1. `, `2. `, ..., a space after the dot) and lines starting `Expected:`. It passes with at least one step and at least as many Expected lines as steps."

**Why remove NOTEs first:** the template's own NOTE holds an example step and an `Expected:` line. Without this, an untouched template would pass.

| Section contains | Result |
|---|---|
| 2 steps, 2 indented `Expected:` | pass |
| 2 steps, 1 `Expected:` | problem: `2 numbered steps, 1 Expected: lines` |
| only the template's NOTE example | problem: `0 numbered steps, 0 Expected: lines` |
| no `#### Reproduction steps` heading | problem: missing section |

**Why the missing-section problem is `(file, "Reproduction steps", message)`:** like a missing labelled line, it has no line to point at.

**Limit:** a NOTE missing its closing `]]` isn't removed, so its example could count. The leftover-marker check reports that NOTE anyway.

**Why a space after the dot (Chunk 3 CR-2):** pasted output often starts with an IP address (`10.0.0.5 dc01`). Without the space, each of those lines would count as a step, and a correct finding would fail.

**Limit:** any line starting with digits, a dot and a space or tab counts as a step, including one inside a code block.

### `has_text()` + `missing_required_fields()` - lines 595-620
A value counts only if it still has a letter or digit once placeholders are removed. Lists which of the six required fields have no value.

**If Operations asks:** "One thing READY needs is that all six detail lines (Severity, CVSS 3.1, Why this severity, Affected assets, Status, References) have something in them (OQ-14). Leftover punctuation from the template, like the `()` around an unfilled score, doesn't count. Reproduction steps are checked separately."

| Untouched template value | After removing placeholders | Counts as |
|---|---|---|
| `[[HOST]] ([[HOST_IP]]), [[URL]], [[ACCOUNT]]` | `(), ,` | missing |
| `` `[[CVSS_VECTOR]]` ([[CVSS_SCORE]]) `` | ` `` () ` | missing |
| `CWE-[[CWE_ID]], ATT&CK [[ATTACK_TECHNIQUE_ID]], [[REFERENCE_URL]]` | `CWE-, ATT&CK ,` | present |

**Why References counts as present (user decision 2026-10-20, C-11):** `CWE` and `ATT&CK` are letters, and the plain rule has no special cases. An untouched References line still can't be READY, because its markers count as leftovers. Separately, `check_references()` fails it for having no `http` link.

**Why `isalnum()`:** it accepts any Unicode letter or digit, so a value like `Café` counts.

### `check_references()` - lines 623-639
The References line must contain an `http` link.

**If Operations asks:** "Every finding needs at least one vendor or standards link. We only look on the References line, so a link somewhere else in the finding doesn't count."

**Why remove placeholders first:** a link that only appears inside a NOTE's example isn't a real reference.

**Limit:** the match is case-sensitive, so `HTTP://` doesn't pass.

**Limit:** the link must be on the `- **References:**` line itself. Links in a sub-list below it don't count, and an empty References line is then also a missing field. The template's NOTE says "on this line" (Chunk 3 CR-3).

### `FULL_CVSS31_VECTOR_RE` + `check_cvss_version()` - lines 642-673
The CVSS vector must be a full CVSS 3.1 vector: all eight metrics, in the standard order, nothing extra.

**If Operations asks:** "Our report uses CVSS 3.1, so a vector from another version, one with a metric missing or out of order, or a score typed where the vector should be, is flagged with its file and line. An unfilled `[[CVSS_VECTOR]]` is left to the marker check, so it isn't reported twice (OQ-05)."

**Why one shared constant (Chunk 3 CR-4):** it's the same rule as the notebook's CVSS_VECTOR format warning (OQ-09), so the notebook is to import it instead of keeping a copy (N4-03).

| CVSS line | Result |
|---|---|
| `` `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8) `` | pass |
| `` `CVSS:3.0/AV:N/...` (9.8) `` | problem |
| `` `CVSS:3.1/.../I:H` `` (no `/A:`) | problem |
| `` `CVSS:3.1/AC:L/AV:N/...` `` (reordered) | problem |
| `` `CVSS:3.1/...A:H/E:P` `` (extra metric) | problem |
| `9.8` (no backticks: the whole value is checked) | problem |
| `` `[[CVSS_VECTOR]]` ([[CVSS_SCORE]]) `` | skipped |
| `` `CVSS:3.0/AV:N [[TODO: fix]]` `` | problem: only the CVSS_VECTOR placeholder is skipped |
| ` `` (9.8) ` or ` `` () ` | problem |

**Why an empty vector gets two problems:** ` `` () ` is reported here and also as a missing CVSS 3.1 field. Both are true, and avoiding the overlap would need a special case.

**Limit:** a valid vector written in another order (e.g. `AC` before `AV`) still fails, and blocks `--final`. The user accepted this (DECISIONS 2026-10-20 Chunk 3 CR-4).

### `finding_id_locations()` - lines 676-694
Lists each finding file with its ID and the line its heading is on, for the two ID checks below.

**If Operations asks:** "It collects every finding's ID with its file and line. It uses the ID the heading check chose: the heading's ID, or the filename's when the heading still says `[[FINDING_ID]]`. A finding with no ID at all is left out, because the heading check already reports it."

**Why line 1 when there's no heading:** the heading check reports a missing heading at line 1, so the ID problems point at the same place.

### `check_duplicate_ids()` - lines 697-715
Reports any finding ID used by more than one file, naming every file.

**If Operations asks:** "Two files with the same ID would give two findings the same number in the report. We report it once per ID, at the first file, and the message lists every file that uses it, ours and our teammates', so each copy can be found."

| Files | Problem |
|---|---|
| `findings/F-001-a.md`, `findings/F-001-b.md` | `duplicate finding ID F-001 in: findings/F-001-a.md, findings/F-001-b.md` |
| `findings/F-001-a.md`, `incoming/alice/findings/F-001-b.md` | one problem naming both |
| `incoming/alice/...F-004-a.md`, `incoming/bob/...F-004-b.md` | one problem naming both |
| `F-001-x.md` with an `F-002` heading, and `F-002-y.md` | duplicate F-002 (the heading's ID is used) |

**Why the ID mismatch isn't reported here:** a filename that doesn't match its heading is reported only by `parse_finding_heading()` (C-05), so it's never reported twice.

### `check_index_membership()` - lines 718-743
Compares the finding files' IDs with the findings index: IDs missing from it, and IDs in it with no file.

**If Operations asks:** "The index is the team's master list of IDs. A finding that isn't on the list is reported at the finding; an ID on the list with no finding file is reported at its line in the index. If the index is missing or broken, nothing is compared, because the loader has already warned and every finding would look extra."

| Index | Finding files | Problems |
|---|---|---|
| F-001, F-003 | F-001, F-002 | `F-002 is not in the findings index tracker/findings-index.csv` at the F-002 file; `F-003 is in the findings index but no finding file has it` at index line 3 |
| absent, header only, broken, or no `finding_id` column | any | none here (the loader warned) |

**Limit:** IDs are compared as exact text. An index row `f-001` is reported as both missing and extra.

**Why the index name is passed in:** `collect_qa()` passes `index_location()`'s name, the same one `load_index_ids()` shows, so every index problem names the same file (C-14 carry-forward).

**Limit:** an ID on two index rows isn't reported; `load_index_ids()` keeps the first row's line. If two finding files really use that ID, the duplicate check reports them once both files exist (Chunk 4 CR-2).

### `finding_readiness()` - lines 746-770
Decides READY or DRAFT for one finding, and gives the readiness line for the QA report.

**If Operations asks:** "A finding is READY when it has no leftover placeholders, none of the six required detail lines is empty, it has a real severity word, and its title isn't blank. Anything else is DRAFT, and the line says why, e.g. `DRAFT: 2 unresolved markers, 1 missing fields`. READY means nothing is left to fill in. The other checks (reproduction steps, the http reference, the CVSS version, heading problems, duplicate IDs) are reported separately in the QA report and don't change READY."

| Finding | Readiness line |
|---|---|
| the complete sample finding | `READY` |
| two leftover markers | `DRAFT: 2 unresolved markers, 0 missing fields` |
| Status is just `()` | `DRAFT: 0 unresolved markers, 1 missing fields` |
| Severity `high` (lowercase) | `DRAFT: 0 unresolved markers, 0 missing fields, no severity word` |
| `### F-001:` with no title, or no heading | `DRAFT: 0 unresolved markers, 0 missing fields, no title` |
| the untouched template | `DRAFT: 44 unresolved markers, 5 missing fields, no severity word` |

**Why a severity word and a title too (user decisions 2026-10-20 C-15 Q2/Q3):** the spec's READY rule only counts markers and missing fields. A misspelled severity would leave a blank Severity cell in the summary table, and a blank title has no marker for the leftover check to see. Both depart from the spec.

**Every DRAFT reason is also a QA problem (user decision 2026-10-21 C-19 Q2):** see `check_required_fields()`. So `--final` can't pass a DRAFT finding.

**Why only the whole-file marker count (C-15 Q1):** the heading's own markers are already among the whole-file hits. The old separate heading count was removed so nothing can add them twice.

**Limit:** a finding with no Severity line at all shows both `1 missing fields` and `no severity word`. Both are true; avoiding it would need a special case.

### `draft_banner()` - lines 773-783
The line put above a draft in the combined findings file: its readiness line inside a NOTE, e.g. `[[NOTE: DRAFT: 0 unresolved markers, 0 missing fields, no severity word]]`.

**If Operations asks:** "Every draft in the combined file gets this line above it, saying every reason it's a draft. It is itself a placeholder, so if a draft is pasted into `report.md` with its banner, the `--final` check of `report.md` (C-20) reports it."

**Why the whole readiness line (user decision 2026-10-20 Chunk 4 CR-3):** the spec's banner only counted markers, so a draft held back by its severity, title or a missing field read `0 unresolved markers`, and a writer might delete it. Departs from the spec's literal `[[NOTE: DRAFT: n unresolved markers]]`.

### `TABLE_TEXT_LABELS` + `field_value()` + `summary_row()` - lines 786-813
Collects one finding's five summary-table cells, exactly as written.

**If Operations asks:** "Each finding becomes one row: ID, title, severity, affected assets and status. Values are copied as written. A missing value is a blank cell, so the Severity cell is the severity word or blank (OQ-16)."

### `has_unescaped_pipe()` + `check_table_pipes()` - lines 816-842
Warns when a title, Affected assets or Status value contains a `|` that isn't escaped as `\|`.

**If Operations asks:** "A `|` splits a Markdown table cell, so the row would break. We report it and name the finding, e.g. `F-001: '|' in Title breaks the summary table` (a warning while drafting, an error with `--final`), but never change what the tester wrote. A `\|` is Markdown's way to write a `|` inside a table, so it isn't reported."

**Why skip `\|` (user decision 2026-10-20 Chunk 4 CR-4):** in `--final` every QA problem becomes an error (C-19), so a correctly escaped pipe would be a false fail. The check removes every `\|` from a copy of the text, then looks for `|`; `Guest \| staff | portal` still warns.

**Limit:** a `|` after two backslashes (`\\|`) is also skipped, though Markdown reads it as a backslash and a real `|`.

**Why Status too (user decision 2026-10-20 C-16):** the spec names only Title and Affected assets, but Status goes into the table as written too. ID (`F-NNN`) and Severity (a fixed word) can't hold a `|`.

**Limit:** the row is still written broken; the warning is how it gets fixed.

### `table_line()` + `summary_sort_key()` + `render_findings_summary()` - lines 845-881
Writes `build/findings-summary.md`: the findings table and the severity count table.

**If Operations asks:** "The first table lists every finding, most severe first and by ID within each level, with no-severity findings last. The second counts each level, zeros included, and Total counts every finding, so it always equals the number of rows."

```
## Findings

| ID | Title | Severity | Affected assets | Status |
| --- | --- | --- | --- | --- |
| F-002 | Default admin password on web01 | Critical | web01 (10.0.0.1), ... | Exploited |
| F-003 | Default admin password on web01 |  | web01 (10.0.0.1), ... | Exploited |

## Severity counts

| Critical | High | Medium | Low | Informational | Total |
| --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 0 | 0 | 2 |
```

**Why the `##` headings:** the file holds two tables, and the headings say which is which. The spec names no headings for this file.

**Limit:** a blank-title finding (DRAFT) is still listed, with an empty Title cell.

### `TIMELINE_TYPES` + `TIMELINE_TIME_RE` + `TOP_HEADING_RE` - lines 884-897
The three timeline file types, the time format, and the file's top `#` heading.

**If Operations asks:** "Only incident reports, status updates and inject responses go in the timeline (OQ-11). Each type has its own time line: `Time reported`, `Time` or `Sent`. A time must be `YYYY-MM-DD HH:MM`, so sorting the text also sorts by time (OQ-01)."

| Prefix | Type | Time line |
|---|---|---|
| `IR-` | Incident | `- **Time reported:**` |
| `SU-` | Status update | `- **Time:**` |
| `INJ-` | Inject | `- **Sent:**` |

**Limit:** the format check is the spec's pattern, so an impossible date like `2026-13-45 25:99` still passes.

### `child_folders()` + `timeline_folders()` + `discover_timeline_files()` - lines 900-947
Lists the timeline files: `field-notes/<name>/` and `incoming/<owner>/field-notes/<name>/`, sorted by path.

**If Operations asks:** "It looks in each person's notes folder, ours and our teammates'. Only `IR-`, `SU-` and `INJ-` files count; `NOTE-` files are personal notes, not client interactions. Like the findings list, every folder and file is checked first, so a link pointing outside the working copy is refused with its path named."

**Why a missing folder is fine:** a working copy may not have `field-notes/` yet (2026-10-19 repo split), so it gives an empty list instead of an error.

### `misplaced_timeline_files()` - lines 950-975
Reports each `IR-`, `SU-` or `INJ-` file saved in a likely wrong spot, which the timeline would otherwise leave out without a word (Chunk 7 CR-3).

**If Operations asks:** "The timeline only reads files inside a person's folder, `field-notes/<name>/`. A file saved by hand at the top of the working copy, or straight into `field-notes/`, would just be missing from it. This looks in those two spots, and the same two in each teammate's `incoming/<owner>/`, and names each such file: a warning while drafting, an error with `--final`."

| File | Printed line (draft) |
|---|---|
| `IR-001-x.md` at the top of the root | `WARNING: IR-001-x.md: not in field-notes/<name>/, so it is not in the timeline` |
| `field-notes/IR-002-x.md` | the same message, naming `field-notes/IR-002-x.md` |
| `incoming/bob/SU-x.md`, `incoming/bob/field-notes/INJ-y.md` | one line each |
| `field-notes/alice/IR-003-x.md` | none: it's in the timeline |
| a `NOTE-` file anywhere | none: not a timeline file |

**Why line 0:** the problem is the whole file, so it's printed as `file: message` with no line number, as for the findings index.

**Why under the `interactions timeline` check:** that check is already in `QA_CHECKS`, so these lines can't drop out of the report, and they get the same levels as other timeline problems (C-19 Q1).

**Why check each file before `is_file()`:** `is_file()` follows a link, so, as in `child_folders()`, a file linked outside the working copy is refused with its name first.

**Limit:** only those two spots are searched (the user rejected searching everywhere). A file in a deeper folder, like `field-notes/alice/old/`, or in any other folder, like `findings/`, is still left out of the timeline with no line.

### `parse_timeline_entry()` - lines 978-1029
Reads one timeline file into its row: time, type, summary and reference.

**If Operations asks:** "The type comes from the filename, the time from that type's labelled line, the summary from the file's `#` heading exactly as written (OQ-04), and the reference is the filename without `.md`. A missing or badly written time is reported, and that file goes at the end of the timeline. It's a warning while drafting and an error with `--final` (user decision 2026-10-21 C-19 Q1), because an unfilled time is only caught here: timeline files aren't checked for leftover markers."

| File | Row | Problem |
|---|---|---|
| `IR-001-lockout.md`, Time reported `2026-11-07 09:05` | `2026-11-07 09:05` / Incident / `Incident Report IR-001` / `IR-001-lockout` | none |
| Time `09:05` | sorted last | `Time is not YYYY-MM-DD HH:MM: 09:05; sorted last` |
| the untouched template time `[[DATE_REPORTED]] [[TIME_REPORTED]]` | sorted last | the same warning, with the markers |
| no time line | sorted last | `missing labelled line '- **Time:**'; sorted last` |
| no `# ` heading | blank Summary | `no '# ' heading; Summary left blank` |
| a pipe character in the heading, not escaped with a backslash | text kept | the Summary pipe warning, e.g. for `SU-x.md` it names `SU-x` |

**Why the Summary `|` warning (user decision 2026-10-20 C-17B):** the same rule as the summary table, including skipping an escaped `\|` (Chunk 4 CR-4). The spec doesn't ask for it.

**Why IR uses Time reported:** the spec names `Time reported` for incidents. The template's `Time detected` line is ignored.

**Limit:** if a file has its time line twice, the first one is used, with no warning.

**Limit:** the first `# ` line wins, even one inside a code block. The templates start with their heading, so this doesn't come up in practice.

### `timeline_sort_key()` + `render_timeline()` - lines 1032-1055
Writes `build/interactions-timeline.md`: one row per timeline file, sorted by time.

**If Operations asks:** "Valid times come first, in time order. Files with a missing or bad time come after them, so they stand out. Ties go by filename, so every run gives the same order. Values are shown as written, so an unfilled time keeps its placeholders, and the `--final` check of `report.md` (C-20) catches it if it's pasted there."

```
| Time | Type | Summary | Reference |
| --- | --- | --- | --- |
| 2026-11-07 09:05 | Incident | Incident Report IR-001 | IR-001-lockout |
| 2026-11-07 10:00 | Status update | Client Status Update | SU-midpoint |
| [[DATE_SENT]] [[TIME_SENT]] | Inject | Inject Response: Scope | INJ-scope |
```

### `combined_sort_key()` + `render_combined_findings()` - lines 1058-1089
Writes `build/findings-combined.md`: every finding's full text, in report order, with a banner above each draft.

**If Operations asks:** "It joins all the findings, most severe first, ready to paste under the report's Section 5. Each finding's text is copied unchanged, except that a missing final line break is added, so its `###` and `####` headings fit. A draft gets its `[[NOTE: DRAFT: ...]]` readiness line right above its heading, so it can't slip into the report unnoticed."

**Why add a missing final line break:** without one, the next finding's heading would be glued onto this finding's last line. It's the only change made here; an invisible start marker (BOM) was already dropped when the file was read (see `read_markdown()`).

**Why a blank line between findings:** it keeps each finding a separate block in Markdown.

**Limit:** two files with the same ID stay in path order (the duplicate check reports them).

### `QA_CHECKS` + `ALWAYS_WARNING_CHECKS` - lines 1092-1112
The 13 named checks in `qa-report.txt`, in report order, and the one check that is always only a warning.

**If Operations asks:** "These are checks from our QA checklist plus the ones the spec adds. Every check gets a PASS or FAIL line every run, so a check can't silently drop out of the report."

| Check | Reports | From |
|---|---|---|
| finding headings | ID mismatch, not a `###` heading, no title text, no ID, no title line | `parse_finding_heading()` |
| labelled lines | a missing or repeated detail line | `parse_labelled_fields()` |
| severity | no severity word | `severity_value()` |
| required fields | a detail line with no value | `check_required_fields()` |
| leftover markers | every `[[NAME` still in a finding | `scan_leftover_markers()` |
| older-style leftovers | `<<`, `TODO`, `F-XXX`, `IR-XXX`, `XX`, `YYYY`, `HH:MM` | `scan_older_leftovers()` |
| reproduction steps | too few steps or `Expected:` lines, or no section | `check_reproduction()` |
| references | no `http` link on the References line | `check_references()` |
| CVSS version | not a full CVSS 3.1 vector | `check_cvss_version()` |
| duplicate finding IDs | one ID in two or more files | `check_duplicate_ids()` |
| findings index | an unusable index; IDs missing from it or extra | `load_index_ids()`, `check_index_membership()` |
| summary table | a `\|` that would break a table row | `check_table_pipes()` |
| interactions timeline | a bad or missing time, no `#` heading, a `\|` in the Summary | `parse_timeline_entry()` |

### `check_required_fields()` - lines 1115-1130
Reports each of the six required detail lines that is there but has no value, at its line, e.g. `Status has no value`.

**If Operations asks:** "READY needs all six detail lines filled in. This makes each empty one a QA problem, so `--final` can't pass a finding that is still DRAFT. It uses the same rule as READY, so leftover punctuation like `()` doesn't count as a value."

**Why all six (user decision 2026-10-21 C-19 Q2):** the spec's QA list only names "Why this severity". Without the other five, a finding held back only by, say, Status `-` is DRAFT, but nothing fails, so `--final` would pass it. Widens the spec.

| Why the finding is DRAFT | QA problem that fails `--final` |
|---|---|
| leftover markers | leftover markers |
| a detail line with no value | required fields (this function) |
| a detail line missing altogether | labelled lines |
| no severity word | severity |
| no title, or no title line | finding headings |

**Why a missing line isn't reported here:** `parse_labelled_fields()` already reports it.

**Limit:** some problems show up twice, because two checks are both right. An unfilled Severity is a severity problem, a required-fields problem and a leftover marker. An empty CVSS vector is a CVSS version problem and a required-fields problem. Avoiding that would need special cases.

### `qa_level()` - lines 1133-1142
Gives each problem its level: always a warning in draft mode; an error in `--final`, except for older-style leftovers.

**If Operations asks:** "While drafting, every problem is a warning, so the tool never gets in anyone's way. With `--final`, problems become errors and fail the run. Older-style leftovers like `TODO` can be real text, so they stay warnings."

| Problem | Draft | `--final` |
|---|---|---|
| older-style leftover | warning | warning |
| index absent, empty or header only | warning | warning (the loader's own level, C-08) |
| index not a readable CSV, or no `finding_id` column | warning | error (the loader's own level, C-08) |
| timeline problem | warning | error (user decision 2026-10-21 C-19 Q1) |
| every other problem | warning | error |

### `hit_diagnostics()` + `check_problems()` - lines 1145-1173
Turns every shape of problem into one: (level, file, line, message).

**If Operations asks:** "The checks report problems in a few slightly different shapes. Before printing, they're all turned into one shape: level, file, line, message. A problem that isn't on one line, like a missing detail line, gets no line number."

| Comes as | From | Becomes |
|---|---|---|
| (file, line, message) | headings, duplicate labels, severity, required fields, reproduction, references, CVSS, duplicate IDs, index membership, table pipes, timeline | (level, file, line, message) |
| (file, label, message) | a missing labelled line, a missing Reproduction section, a missing timeline time line | line None |
| (file, line, matched text) | both leftover scanners | first `hit_diagnostics()`: message `leftover marker [[HOST` or `older-style leftover TODO` |
| (level, file, line, message) | `load_index_ids()` | added as it is; line 0 means the whole file |

### `problem_location()` + `problem_line()` - lines 1176-1188
Prints one problem as `ERROR: file:line: message`, or `ERROR: file: message` when it has no line.

**If Operations asks:** "Every problem shows the file and line, like `grep -n`, so it can be found straight away. A problem with the whole file has no line to show."

### `count_levels()` + `check_status()` - lines 1191-1208
Counts warnings and errors; a check is `PASS`, or `FAIL (E errors, W warnings)`.

**If Operations asks:** "A check with no problems is PASS. Anything else is FAIL with its counts, so you can see at a glance whether it blocks `--final` (errors) or is only worth a look (warnings)."

**Why FAIL even with only warnings (user decision 2026-10-21 C-19 Q3):** the problems stay visible. So a `--final` run can show a FAIL line and still exit 0; only errors decide the exit code.

### `InputError` + `read_markdown()` - lines 1211-1228
Reads a file's text as it is on disk, minus an invisible start marker (BOM) if there is one; a file that isn't UTF-8 stops the run with an error naming it.

**If Operations asks:** "Every Markdown file is read the same way. Windows line endings are kept, so the combined findings file copies each finding unchanged. An invisible start marker that some Windows editors add is dropped. If a file isn't plain UTF-8 text, the run stops and names the file."

**Why drop the BOM (`utf-8-sig`, Chunk 5 CR-1):** older Windows Notepad and PowerShell 5.1 (`Set-Content -Encoding UTF8`) save UTF-8 with an invisible marker first. Kept, it sits before the `# ` on line 1, so a complete finding got "no finding title heading" (an error in `--final`) and a status update lost its Summary. Files made from the templates start without one; a file saved by another editor, program or script may have one (whether a notebook save keeps an existing BOM is up to N4-05). `load_index_ids()` already drops it for the same reason.

**Why `InputError`:** Python's own decoding error doesn't say which file it was.

**Limit:** a file saved in another encoding (e.g. Windows-1252) stops the run (exit code 2) instead of being guessed at.

### `REPORT_FILE` + `check_report()` - lines 1231-1267
In `--final` only: checks `report.md` for leftover markers (errors) and older-style leftovers (warnings). Draft mode doesn't open it.

**If Operations asks:** "`report.md` is put together by hand at the midpoint, so draft runs leave it alone. The final check looks for anything left unfilled in it, like a pasted draft banner. It only reads the file; it never changes it."

| Mode | `report.md` | Result |
|---|---|---|
| draft | anything | not opened; no `report.md` section |
| `--final` | absent | `report.md NOT FOUND: report not checked`, no problem |
| `--final` | present | `report.md checked: N problems`; each marker an error, each older-style leftover a warning |

**Why absent isn't an error:** the report may be finished in another tool (Word, LibreOffice). The loud line makes sure nobody thinks it was checked.

**Why the same scanners:** they're the two checks the QA checklist runs by hand on the report, with the same rules as for findings. Code blocks and code spans are skipped for older-style leftovers only; a marker inside a code block is still a leftover marker, so it's an error in `--final`.

### `render_qa_report()` - lines 1270-1323
Writes `build/qa-report.txt`: the mode, one readiness line per finding, then PASS or FAIL for every check with its problems, then the `report.md` section in `--final`.

**If Operations asks:** "It's the QA checklist's result for every file at once. Each finding says READY or why it's a draft, and each check says PASS or FAIL with the exact file and line of every problem."

```
QA report (--final): any ERROR below fails the run

Findings:
  findings/F-001-x.md: READY
  incoming/alice/findings/F-002-y.md: DRAFT: 1 unresolved markers, 1 missing fields

Checks:
PASS finding headings
PASS labelled lines
PASS severity
FAIL (1 errors, 0 warnings) required fields
  ERROR: incoming/alice/findings/F-002-y.md:9: Status has no value
FAIL (1 errors, 0 warnings) leftover markers
  ERROR: incoming/alice/findings/F-002-y.md:7: leftover marker [[HOST
FAIL (0 errors, 1 warnings) older-style leftovers
  WARNING: incoming/alice/findings/F-002-y.md:19: older-style leftover TODO
PASS reproduction steps
...
FAIL (1 errors, 0 warnings) interactions timeline
  ERROR: field-notes/bob/SU-mid.md:3: Time is not YYYY-MM-DD HH:MM: [[DATE]] [[TIME]]; sorted last

report.md:
report.md checked: 1 problems
FAIL (1 errors, 0 warnings) leftover markers
  ERROR: report.md:3: leftover marker [[EXEC_SUMMARY
PASS older-style leftovers
```

**Why every check must be given:** a missing check name gives a readable error (`QA check not run: <name>`) instead of a bare KeyError. An unknown (e.g. misspelt) name is refused because its problems would otherwise be dropped from both the report and the exit code, which read only `QA_CHECKS` names. A `--final` report without the `report.md` result is refused too.

**Limit:** an empty list is read as "ran and found nothing". `collect_qa()` starts every check as an empty list, so if a later change stopped calling one check, the report would still show PASS for it; this guard can't catch that.

**Why the readiness line as it is (C-15 carry-forward):** it's the same text as the draft banner, so the two always agree.

**Limit:** problems are grouped by check, not by file. One finding's problems can be spread over several checks.

### `check_finding()` - lines 1326-1371
Runs every check that looks at one finding on its own, and builds its summary row, its combined-file entry and its readiness line.

**If Operations asks:** "This is where one finding goes through every per-finding check. The checks that compare files with each other (duplicate IDs, the index) run afterwards, once every finding is read."

### `collect_qa()` - lines 1374-1421
Reads every input and runs every check: each finding, then duplicate IDs and the index across all findings, then each timeline file and any misplaced one, then `report.md` (`--final` only).

**If Operations asks:** "It reads our findings and our teammates', the index and everyone's timeline files, and collects every problem by check. It only reads; writing comes next, in `write_outputs()`."

**Why file names are shown relative to the root:** `findings/F-001-x.md` is the same on every tester's machine; the full path isn't.

### `all_problems()` + `qa_summary_line()` - lines 1424-1442
Lists every problem, `report.md`'s included, and writes the closing line, e.g. `QA: 2 findings; 1 READY; 1 DRAFT; 1 warnings; 4 errors`.

**If Operations asks:** "The last line sums up the run: how many findings, how many are READY, and how many warnings and errors there are in total."

### `BUILD_FOLDER` + `OUTPUT_FILES` + `build_path()` - lines 1445-1471
The four output files, and the check that each one is safe to write.

**If Operations asks:** "Writing a file follows links. So before writing anything, every output path is checked: a link there could make the tool overwrite `report.md` or write into a teammate's `incoming/` folder. The tool creates `build/` itself, so a link only gets there if someone makes one by hand."

| At `build/` or an output file | Result |
|---|---|
| an output file: nothing yet, or a plain file | written |
| `build/` itself is a plain file, not a folder | the run stops (`compile failed: ... File exists`, exit code 2); nothing is written |
| a symlink, even one pointing inside the working copy | refused, with the path named |
| a file with a second hard link (the same file under another name) | refused |
| a folder or other non-file at an output path (checked in `write_outputs()`) | refused |

**Why stricter than the usual path rule (user decision 2026-10-21 C-21 build/ links):** the spec's path-safety rule (Constraint 4, OQ-17) allows a symlink that resolves inside the root. For `build/` and the four output files, any symlink is refused, and so is a file with a second hard link. A link that stays inside the working copy can still point at `report.md` or into `incoming/`, which the tool must never write. Departs from the spec, for these paths only.

**If Operations asks why a link inside the working copy is refused here:** "Reading through a link inside the working copy is harmless, so the tool allows it everywhere else. Writing through one could overwrite the report or a teammate's files, so for the files the tool writes, no link is allowed at all."

**Why `st_nlink`:** it counts a file's names. A hard link to `report.md` has two, and writing one name would change the other. Folders always have more than one, so only files are checked.

### `readiness_lines()` + `write_outputs()` - lines 1474-1521
Writes the four `build/` files from scratch and returns the screen lines.

**If Operations asks:** "Every run rewrites all four files completely, so nothing old is left in them. `report.md` is never written. Every output path is checked before the first write, so a refused run leaves `build/` exactly as it was."

```
WROTE /home/alice/cptc-work/build/findings-summary.md
WROTE /home/alice/cptc-work/build/interactions-timeline.md
WROTE /home/alice/cptc-work/build/findings-combined.md
WROTE /home/alice/cptc-work/build/qa-report.txt
ERROR: incoming/alice/findings/F-002-y.md:9: Status has no value
ERROR: incoming/alice/findings/F-002-y.md:7: leftover marker [[HOST
WARNING: incoming/alice/findings/F-002-y.md:19: older-style leftover TODO
ERROR: field-notes/bob/SU-mid.md:3: Time is not YYYY-MM-DD HH:MM: [[DATE]] [[TIME]]; sorted last
ERROR: report.md:3: leftover marker [[EXEC_SUMMARY
report.md checked: 1 problems
QA: 2 findings; 1 READY; 1 DRAFT; 1 warnings; 4 errors
```

**Why the full path on WROTE lines:** `--root` can point anywhere, so `build/x` alone wouldn't say which working copy.

**Why the readiness list has its own function:** `run()` renders the same QA report text, and both must list the findings the same way.

**Limit:** other files in `build/` are left alone; the tool never deletes anything.

**Limit:** if the disk fills up halfway, the files already written stay written. The path checks only rule out a refused run changing anything.

### `pandoc_hint()` - lines 1524-1537
If pandoc is installed, a last line with the exact command to turn `report.md` into a Word file. The tool never runs it.

**If Operations asks:** "pandoc converts Markdown to Word or PDF. If it's installed, we print the command so it can be copied. Our tool runs no commands at all, so it only shows it."

**Why `shutil.which()`:** it only looks pandoc up on the PATH; it starts nothing.

**Why `shlex.quote()`:** a path with spaces stays one argument when the command is pasted.

**Limit:** the hint shows even when `report.md` doesn't exist yet, and in draft mode.

### `run()` - lines 1540-1566
Does a whole compile and returns (exit code, QA report text, screen lines), printing nothing, so the notebook's Compile button can call it too.

**If Operations asks:** "It runs every step in order: check the root, read and check everything, write the four files, add the pandoc hint. It doesn't print, so the notebook can show the same result in the browser."

| Exit code | When |
|---|---|
| 0 | draft mode, whatever it finds; or `--final` with no errors |
| 1 | `--final` with at least one error |
| 2 | the tool couldn't run: bad root (missing, or the git clone), a path outside the root, a file it can't read or write. One line `compile failed: <reason>`, no Python traceback |

**Why 2 for a failure:** it's different from 1, so a script can tell "the report has problems" from "the tool couldn't run". Python's argparse also uses 2 for a bad option.

### `main()` + `if __name__ == "__main__"` - lines 1569-1581
Reads the options, runs, prints each line and exits with the code.

**If Operations asks:** "This is what runs when you type `python3 tools/compile.py`. Importing the file (as the notebook does) runs nothing."

## 2. Test helpers: tests/support.py

Shared with the notebook's tests; `notebook-breakdown.md` links here instead of repeating it.

### Import setup + `TMP_DIR` - lines 1-22
Lets the tests import the tools; sets the one folder tests may write to, `tools/tests/.tmp/`. `os` (added in Chunk N7) only sets the fake logs' times.

**If Operations asks:** "Shared setup for our tests. It lets the tests find our tool and gives them one scratch folder inside the repo that git ignores."

### `make_worktree()` + `write_fake_file()` - lines 25-48
One fake working copy per test, inside `.tmp/`, deleted when the test ends. Fake files can't escape it.

**If Operations asks:** "Each test builds its own fake working copy with obviously fake files. It's deleted automatically when the test finishes."

**Limit:** if a test run is stopped with Ctrl-C, cleanup doesn't run and a `worktree-*` folder stays in `.tmp/`. It's harmless (git ignores it) and can be deleted by hand.

### `COMPLETE_FINDING` + `make_complete_finding()` - lines 51-108
A fully filled fake finding that should pass every check.

**If Operations asks:** "A sample finding with obviously fake data that should pass every check."

### `LIBRARY_ENTRY` + `make_library_entry()` - lines 111-150
A short fake findings-library entry: general text written, event fields still `[[...]]` markers, as `findings-library/README.md` describes a finished entry.

**If Operations asks:** "Our real library is empty in this repo until finished entries come back from the team Drive, so the tests use a clearly fake entry of the same shape. It still has placeholders, so it's always DRAFT."

### `HOSTILE_LOG` + `HOSTILE_LOG_CLEANED` + `HOSTILE_CMDS` + `make_hostile_logs()` - lines 153-241
Notebook Chunk N7, N6-00. A fake terminal transcript shaped like what `scripts/logged-shell.sh` saves, holding every case the log viewer's cleaner must handle: a `<script>` tag in a fake HTTP answer, CRLF and CRCRLF lines (a blank one too), a progress bar redrawn twice with lone CRs, a typo fixed with Backspace (BS then `ESC [ K`), CSI codes (colour, `?` mode, an intermediate byte), OSC ended by BEL and by ESC backslash, and the two-character escapes `ESC ( B`, `ESC ) 0`, `ESC =`, `ESC >`. `HOSTILE_LOG_CLEANED` is the same text after the spec's four cleaning steps, worked out by hand (a throwaway spec-order probe reproduced it; `CleanLogTextTests` checks the cleaner against it). `HOSTILE_CMDS` is the matching command index, in `logged-shell.sh`'s line format. `make_hostile_logs(logdir, base, mtime)` writes `<base>.log` and `<base>.cmds.log` as exact bytes and returns both paths.

**If Operations asks:** "The log tests use a generated fake log full of terminal junk and a `<script>` tag; no real log or committed sample file is used."

**Why generated, not a committed `.log` file:** `.gitignore` excludes `*.log`, and the bytes must be exact, which a text editor could quietly change.

**Why the guards:** the log folder must be inside `.tmp/`, both names are checked to land directly in it before either is written (`../x` or an absolute base writes nothing; N6-00 adversary round 1), and an existing file is never replaced (`"xb"`), so two calls with the same base fail loudly. `mtime` sets both files' time, so list tests can order several logs.

### `remove_worktree()` - lines 244-255
Cleanup deletes only a folder directly inside `.tmp/`, and never follows symlinks.

**If Operations asks:** "Cleanup only deletes the test's own scratch folder, and checks the location first."

## 3. Tests

### tests/test_support.py

#### `finding_structure()` - lines 1-14
Lists a finding's `####` headings and `- **Label:**` lines, for the template drift test.

**If Operations asks:** "A small helper that lists a finding's headings and labels, so a test can compare our sample finding with the real template."

#### `MakeWorktreeTests` - lines 17-44
- the fake root sits in `.tmp/`, with no `.git`
- requested files are written exactly
- `../` paths are refused
- cleanup removes the folder but keeps `.tmp/`

**If Operations asks:** "These test our test helpers: the fake folder lands in the right place, holds exactly the files we asked for, can't write outside itself, and is deleted afterwards."

#### `MakeCompleteFindingTests` - lines 47-80
- no `[[`, and the heading starts `### F-001: `
- the rationale has words; References has an `https://` link
- at least one reproduction step, and an indented `Expected:` for each
- headings and labels match `templates/finding.md` both ways (Attack chain left out on purpose)
- a custom ID and title are used

**If Operations asks:** "These prove our sample finding is really complete. One compares it with the real template, so if someone edits the template, the test tells us the sample is out of date."

#### `MakeHostileLogsTests` - lines 83-206
Notebook Chunk N7, N6-00 (the adversary's cases 1-3).
- both files land in the log folder with the right names, not under `fixtures/`, and go when the worktree is cleaned up
- a log folder outside `.tmp/` is refused and not made; a base with `../` or an absolute path is refused with nothing written
- the files' bytes are exactly the constants; the transcript holds every hostile case, a plain CRLF as well as CRCRLF, and a progress line with two lone CRs
- the command index's commands appear, as typed, in the cleaned transcript; the cleaned text has no control codes, keeps the `<script>` line and has as many lines as the transcript
- two calls with different bases don't collide and keep their own times; the same base twice is refused and the first file is unchanged

**If Operations asks:** "These test the fake-log helper itself: every hostile case is really in it, and it can't write outside its test folder."

### tests/test_compile.py

#### Imports + `StripMarkersTests` part 1 - lines 1-33
`support` is imported first so `compile` can be found. The other imports (`ast`, `contextlib`, `importlib.util`, `io`, `os`, `shlex`, `mock`) are for the Chunk 5 tests. Five tests each strip one kind of marker (named, CHOOSE, TODO, multi-line NOTE, two side by side) and check the exact text left.

**If Operations asks:** "Each test gives the function text with a placeholder in it and checks exactly what's left. We test every kind, including ones that span several lines."

**If asked about the name `compile`:** "`import compile` hides Python's built-in `compile()`, but only in the test file. That's harmless: the tests never use the built-in, and the spec names the file."

#### `StripMarkersTests` part 2 - lines 35-60
- a marker inside a NOTE: only the inner one is removed
- an unclosed marker doesn't swallow the next one
- bash `[[ -f x ]]` is left alone
- the real `templates/finding.md` strips clean, including its NOTE example

**If Operations asks:** "These are the tricky cases. The last one runs on our real finding template, so a template change that breaks the tool fails the tests."

#### `ScanLeftoverMarkersTests` - lines 63-83
- complete, unclosed (`[[NOTE: never closed`) and bare (`[[HOST`) markers are reported with file and line
- bash `[[ -f x ]]` is not reported
- the hit count equals the regex matches (the DRAFT banner's n)

**If Operations asks:** "Every leftover placeholder is found with its exact line number, even one missing its closing brackets. Bash `[[ ]]` tests are ignored."

#### `ValidateRootTests` - lines 86-114
- a normal root passes
- a `.git` folder is refused, and nothing is created (file lists compared before and after)
- a `.git` file is refused
- a missing root is refused and not created
- a file given as the root is refused

**If Operations asks:** "These try every kind of bad root folder. Each is refused with a clear message, and the test checks that nothing was created or changed."

#### `ResolveInRootTests` - lines 117-164
`setUp` builds a root and a second "outside" folder, both in `.tmp/`.

| Allowed | Refused, with the path named in the error |
|---|---|
| `findings/F-001-x.md` | `../x` |
| `findings/a..b.md` | a full path to the outside folder |
| a symlink pointing inside the root | an `--index` in the outside folder |
| a full path inside the root (like a real `--index ~/cptc-work/...`) | `incoming/alice` linked to the outside folder |

**If Operations asks:** "These try to escape the working copy every way we could think of. All are refused and named in the error. Normal files, and full paths or links that stay inside, are allowed."

#### `DiscoverFindingsTests` - lines 167-253
- local and two incoming `F-001-*.md` files come back, in path order
- `G-001.md`, a `.txt`, nested Markdown and notes folders are left out
- a folder named like a finding is skipped; no folders gives an empty list
- refused, with the path named: `incoming/alice` linked outside (with or without findings in it, or to a file), `findings/` linked outside, one finding file linked outside
- a link that stays inside the root is allowed
- nothing in `incoming/` changes

**If Operations asks:** "These prove the tool picks up exactly our findings and our teammates', ignores everything else, and refuses any link that leads outside the working copy."

#### `ParseFindingHeadingTests` - lines 256-337
- a filled `### F-001: …` heading gives the exact ID, title and line
- `[[FINDING_ID]]` uses the filename's ID; the whole-file leftover scan counts its marker (1 hit), and 2 on the untouched template's heading
- F-001 filename with an F-002 heading is flagged
- `##` instead of `###` is flagged, with its line
- no heading, or no ID anywhere, is reported without crashing
- `### F-001:` with nothing after the colon is flagged
- a Windows `\r\n` line ending isn't kept in the title
- `F-0012` isn't read as `F-001`

**If Operations asks:** "Each heading problem the spec names has a test that checks the exact message."

#### `ParseLabelledFieldsTests` - lines 340-412
- the complete sample finding returns all six labels, plus the vector and score
- removing the Status line gives exactly one problem, naming Status
- two extra Severity lines give one problem each, at their own line, and the first line's value is kept
- extra spaces and tabs are allowed
- Windows `\r\n` line endings leave no `\r` in the values
- the untouched template keeps its placeholders as written
- a bare `9.8`, or brackets inside the vector, don't give a wrong vector or score
- an empty file reports all six labels

**If Operations asks:** "These prove the tool reads every detail line from a real-shaped finding, and reports a missing or repeated one instead of crashing."

#### `severity_of()` + `SeverityValueTests` - lines 415-448
`severity_of()` parses one line the way the tool does: label first, then level.
- `High` is read
- unfilled `[[CHOOSE: …]]` and lowercase `high` give no severity, with a warning
- `Highest` doesn't count; the first level on the line wins
- a missing Severity line isn't reported twice

**If Operations asks:** "These prove an unfilled or misspelled severity is never mistaken for a real one."

#### `FindingSortKeyTests` - lines 451-476
- eight findings sort Critical, High, High, Medium, Low, Informational, then the two with no severity, with ties by ID
- a finding with no ID still sorts

**If Operations asks:** "This checks the exact order the report tables will use."

#### `INDEX_HEADER` + `LoadIndexIdsTests` - lines 479-552
`INDEX_HEADER` is the header row of `templates/tracker/findings-index.csv`.
- the default index loads an F-001 row
- an explicit `--index` inside the root wins over the default; one outside is refused
- absent, header-only and empty files warn and skip the comparison, in both modes
- a broken CSV and a `title,severity` header are warnings in draft and errors in `--final`
- a spreadsheet's invisible start marker and extra spaces are handled

**If Operations asks:** "These cover every state the index file can be in, and check that a broken one only blocks the run in `--final`."

#### `ScanOlderLeftoversTests` - lines 555-592
- all seven patterns are found in prose, with file and line
- `XXE` and `XXXL` aren't a bare `XX`
- copies inside ```` ``` ```` or `~~~` code blocks and in code spans are skipped; a `~~~` block isn't closed by ```` ``` ````
- a double-backtick span with a backtick inside is skipped; ``X`code`X`` doesn't become `XX`
- `TODO` inside `[[TODO: ...]]` is skipped, even across lines
- `F-XXX` inside a NOTE, `F-XXX` inside a TODO marker, and `TODO` inside a NOTE are still reported

**If Operations asks:** "Each old-style placeholder is caught in normal text, and copies inside code or inside a TODO placeholder are ignored, exactly as the spec says."

#### `CheckReproductionTests` - lines 595-648
- 2 steps with 2 indented `Expected:` lines pass
- 2 steps with 1 `Expected:` fail, with both counts and the heading's line
- a step followed by a code block of IP-first lines (`10.0.0.5 dc01`) passes; the IP lines aren't steps
- `Expected:` with no steps fails
- the real `templates/finding.md` fails, though its NOTE has an example (the test first proves the example is in the section)
- the complete sample finding passes
- an `Expected:` under the next `####` heading doesn't count; a `#####` heading doesn't end the section
- Windows `\r\n` line endings work
- a missing section is reported

**If Operations asks:** "These prove a finding needs a real Expected line for each step, and that the template's example can't pass for real steps."

#### `HasTextTests` - lines 651-703
- leftover punctuation like `() ,`, empty backticks and parentheses, and an unfilled rationale with a NOTE are missing
- filled values pass, including `Café`
- the untouched template gives exactly five missing fields; References counts as present (user decision)
- the complete sample finding has none missing
- a renamed label, or one punctuation-only value, is counted once
- removing the reproduction section doesn't change the missing fields

**If Operations asks:** "These prove that leftover template punctuation never passes as a filled-in value, and that the READY field count ignores reproduction steps."

#### `CheckReferencesTests` - lines 706-734
- a References line without `http` fails, at its line
- `https://example.invalid` passes
- a link elsewhere in the finding, or only inside a placeholder, doesn't count
- the untouched template fails; the complete sample finding passes
- a missing References line isn't reported twice

**If Operations asks:** "These prove only a real link on the References line counts."

#### `CheckCvssVersionTests` - lines 737-782
- the full canonical `CVSS:3.1/...` vector passes
- `CVSS:3.0/...` and a bare `9.8` (with or without backticks) fail, with the line
- a missing `/A:` metric, reordered metrics, or an extra metric fail
- an unfilled `[[CVSS_VECTOR]]`, closed or not, is skipped
- another placeholder doesn't hide a wrong version
- an empty vector fails, whether or not the score is filled
- the complete sample finding passes; a missing CVSS line isn't reported twice

**If Operations asks:** "These prove that only a full CVSS 3.1 vector passes, and that an unfilled vector is left to the marker check."

#### `id_locations()` + `FindingIdLocationsTests` - lines 785-812
`id_locations()` discovers and parses a fake root's findings the way the tool does.
- the heading's ID and line are used (an F-002 heading in `F-001-x.md` gives F-002)
- an unfilled `[[FINDING_ID]]` uses the filename's ID
- no heading points at line 1
- a finding with no ID anywhere is left out

**If Operations asks:** "These prove the ID checks use the same ID and line as the heading check."

#### `CheckDuplicateIdsTests` - lines 815-874
- duplicates within one folder, local versus incoming, and across two incoming owners, each with the exact message
- three copies give one problem naming every path
- unique IDs pass
- the heading's ID is compared; the filename mismatch is left to the heading check
- an unfilled heading counts by its filename ID

**If Operations asks:** "Every way two teammates could pick the same ID is caught, and every copy is named."

#### `CheckIndexMembershipTests` - lines 877-909
- index {F-001, F-003} against files {F-001, F-002} reports extra F-002 and missing F-003, with exact text and lines
- a matching index passes
- an absent, header-only, broken or column-less index reports neither

**If Operations asks:** "These prove missing and extra IDs are both reported, and a broken index never floods the report."

#### `readiness_of()` + `FindingReadinessTests` - lines 912-977
`readiness_of()` runs one finding through the checks that decide READY or DRAFT, plus the banner.
- the complete sample finding is READY
- two leftover markers give DRAFT and `[[NOTE: DRAFT: 2 unresolved markers, 0 missing fields]]`
- a heading marker is counted once
- a `()`-only Status counts one missing field
- lowercase `high`, a blank title, or no heading each make it DRAFT; the first two also check that the banner names the reason
- the untouched template gives its exact line: markers, 5 missing fields, no severity word

**If Operations asks:** "These prove a finding is READY only when nothing is left to fill in, and that a DRAFT line always says why."

#### `library_entries()` + `check_whole_finding()` + `FindingsLibraryTests` - lines 980-1031
`library_entries()` lists a library folder's entries without its README; `check_whole_finding()` runs every per-finding check.
- every real `findings-library/*.md` entry parses; the test first checks `README.md` is there, so an empty list can't hide a wrong path. Today the loop runs 0 times (2026-10-19 repo split)
- three fake entries (finished, a multi-line `[[TODO: ...]]`, severity left as `[[CHOOSE: ...]]`) are listed, README left out, and each is DRAFT because of its leftover markers

**If Operations asks:** "When finished library entries are added, this test runs every one through every check automatically. Until then, fake entries of the same shape stand in."

#### `summary_inputs()` + `SUMMARY_GOLDEN` + `RenderFindingsSummaryTests` - lines 1034-1117
- golden text: both headers, the order Critical, High, Low, then no severity, a blank cell for lowercase `high`, a blank title still listed, counts 1/1/0/1/0 with Total 4, and the pipe warning naming F-001
- `|` in Affected assets and Status warns at each line, text unchanged
- no `|` gives no warning; missing fields give blank cells; no findings give all zeros
- an escaped `\|` in Title and Status gives no warning; `Guest \| staff | portal` still warns

**If Operations asks:** "We compare the whole output with a hand-written copy, so any change in the tables shows up."

#### `filled_template()` + `DiscoverTimelineFilesTests` - lines 1120-1188
`filled_template()` reads a real template and fills some markers.
- local and incoming `IR-`, `SU-`, `INJ-` files are found, in path order
- `NOTE-`, `.txt`, nested, loose and outside-`field-notes` files are left out; no folder gives an empty list
- a person's folder, an incoming `field-notes`, or one file linked outside the root is refused with its path; a link inside is allowed

**If Operations asks:** "These prove the timeline reads exactly the three file types from everyone's notes, and nothing outside the working copy."

#### `incident_file()` + `MISPLACED` + `MisplacedTimelineFilesTests` - lines 1191-1255
`incident_file()` gives a small `IR-` file with a valid time; `MISPLACED` is the message.
- the Chunk 7 CR-3 probe (IR-001 at the root, IR-002 in `field-notes/`, IR-003 in `field-notes/alice/`): the timeline has only IR-003; two warnings name IR-001 and IR-002 and the exit is 0; with `--final` they are the only errors and the exit is 1
- the same two spots inside `incoming/bob/` give one line each; `incoming/bob/field-notes/bob/` gives none
- a person's folder, a deeper folder, `findings/`, `NOTE-` files, a `.txt` and a folder named like a file give no line
- a file at the root linked outside the root is refused with its name

**If Operations asks:** "These prove a timeline file in the wrong folder is reported instead of silently dropped, and that files in the right folder, or that aren't timeline files, give no extra lines."

#### `ParseTimelineEntryTests` - lines 1258-1333
- the real IR, SU and INJ templates give the exact type, time, summary and reference
- an unfilled `[[IR_ID]]` stays in the summary as written
- `09:05`, `around nine` and the untouched marker time each warn at their line
- the incident uses Time reported, not Time detected
- a missing time line and a missing heading warn; Windows line endings work

**If Operations asks:** "These run our real templates through the timeline reader, so a template change that breaks it fails the tests."

#### `TIMELINE_GOLDEN` + `RenderTimelineTests` - lines 1336-1386
- golden text: `09:05` before `10:00`, a 10:00 tie by reference, then the two bad times by reference; header plus one row per entry
- no entries give the header only
- a `|` in a Summary warns at its line and the row keeps the text
- an escaped `\|` gives no warning; one next to an unescaped `|` still warns

**If Operations asks:** "This checks the exact order the timeline table will use."

#### `combined_entry()` + `RenderCombinedFindingsTests` - lines 1389-1457
- golden text: High F-002 first, then the banner and Low F-001
- headings are byte-identical; exactly one banner, right above the draft's heading
- a finding with no severity word goes last; its banner says `no severity word`
- Windows line endings are kept exactly; a missing final line break is added
- no findings give empty text

**If Operations asks:** "These prove the combined file is our findings unchanged (only a missing final line break is added), in report order, with every draft marked."

#### `whole_report()` + `no_problems()` + `QA_GOLDEN` + `RenderQaReportTests` - lines 1460-1592
`whole_report()` puts fake findings through `compile.check_finding()` and the duplicate-ID check, then renders the QA report. `no_problems()` is a checks dict where every check ran and found nothing.
- golden text: a complete finding is READY and every check, run for real, is PASS
- the `--final` header is `any ERROR below fails the run`
- the same leftover marker is a WARNING in draft mode and an ERROR in `--final`, with file and line
- an older-style `TODO` is a WARNING in both modes
- a draft's empty Status is an ERROR in `--final` (C-19 Q2)
- the readiness lines: `READY`, and `DRAFT: 2 unresolved markers, 1 missing fields`
- every check has exactly one PASS or FAIL line, with the counts
- no findings gives `no finding files found`
- a misspelt or missing check name is refused
- the level rule, including timeline problems as errors in `--final` (C-19 Q1)

**If Operations asks:** "These prove the QA report shows every check, gives each problem the right level for the mode, and points at the exact file and line."

#### `CheckRequiredFieldsTests` - lines 1595-1629
- the complete sample finding passes
- an unfilled `[[SEVERITY_RATIONALE]]` fails "Why this severity", at line 5
- two empty fields are each reported at their line
- a missing line isn't reported twice
- the untouched template reports its five empty fields

**If Operations asks:** "These prove an empty detail line is always reported, the same way READY counts it."

#### `QaProblemShapeTests` - lines 1632-1684
One test per problem shape (C-19 carry-forward), each checking the exact printed line:
- (file, line, message): a heading ID mismatch prints `file:1:`
- (file, label, message): a missing labelled line, a missing Reproduction section and a missing timeline time print `file:` with no line
- (file, line, matched text): a leftover marker prints `file:2: leftover marker [[HOST`
- (level, file, line, message): an absent index keeps its WARNING in `--final` and has no line; a `title,severity` header keeps its ERROR and its line 1

**If Operations asks:** "Every kind of problem prints as file and line, so none of them can come out garbled."

#### `CheckReportTests` - lines 1687-1759
- a marker only in `report.md` is ignored in draft mode and is an ERROR in `--final`, with the exact `report.md:` section
- draft mode never opens `report.md` (bytes that aren't UTF-8 would make any read fail)
- an older-style `TODO` in `report.md` is only a WARNING
- an absent `report.md` gives the exact `report.md NOT FOUND: report not checked` line and no problem
- a clean `report.md` gives `0 problems` and two PASS lines
- `report.md`'s bytes never change; a link outside the root is refused
- a `--final` report without the `report.md` result is refused

**If Operations asks:** "These prove the final check reads the report, catches anything left unfilled in it, and never changes it."

#### `WriteOutputsTests` - lines 1762-1965
`setUp` builds a working copy with a complete finding, a teammate's draft, an index, a status update and a `report.md`.
- the exact screen lines in draft mode and in `--final`, including the `report.md` status (`--final` only) and the QA line's counts
- an absent `report.md` gives the NOT FOUND line
- the four files hold exactly what the renderers return; nothing else is in `build/`
- stale content is gone after a run
- `report.md` is never written, in either mode; `incoming/` is unchanged
- refused before anything is written, with every existing file left byte for byte: `build/` linked outside, `build/` linked into `incoming/`, an output linked to `report.md`, a folder at an output path, an output hard-linked to `report.md`
- with `--index`, ID problems name the same index file
- timeline and table-pipe problems are collected
- Windows line endings reach `findings-combined.md` unchanged
- a BOM is dropped: a finding with one is READY with no problems in `--final` and reaches `findings-combined.md` without it; a status update with one keeps its Summary
- an empty working copy gives four WROTE lines, the index warning and `QA: 0 findings`

**If Operations asks:** "These run the real tool on fake working copies and check every file it writes and every line it prints, and that it never writes anywhere it mustn't."

#### `RunTests` - lines 1968-2088
- `run()` prints nothing and returns the exit code, the QA text (equal to `build/qa-report.txt`) and the lines
- a marker gives exit 0 in draft mode and 1 in `--final`
- `--final` with only warnings, or with `report.md` absent and nothing else wrong, gives 0
- a marker only in `report.md` gives 0 in draft mode and 1 in `--final`
- exit 2 with a `compile failed:` line: the git clone (and no `build/` is made), a missing root, a finding that isn't UTF-8 (named), an index outside the root
- ID problems name the `--index` file; an index `f-002` is reported as both missing and extra
- with pandoc installed, exactly one HINT line, last, with the exact quoted command; without it, none

**If Operations asks:** "These prove the exit codes the spec asks for, and that the tool only ever shows the pandoc command, never runs it."

#### `MainTests` - lines 2091-2112
- `main()` prints exactly `run()`'s lines and returns its exit code (0 draft, 1 final)
- `--help` exits 0

**If Operations asks:** "This checks the command-line entry point prints the same thing `run()` returns."

#### `ModuleSafetyTests` - lines 2115-2149
- importing a fresh copy of `compile.py` prints nothing
- the only imported modules are `argparse`, `csv`, `re`, `shlex`, `shutil`, `sys` and `pathlib`: no `subprocess`, no `os`
- none of `subprocess`, `system`, `popen`, `Popen`, `exec` or `eval` is used as a name or attribute in the parsed code

**If Operations asks:** "These read our own source code and check that it imports only the listed modules and uses none of the banned names. That's a check, not a proof that it can't run commands. They also check that importing it prints nothing."

#### `CompleteRunTests` - lines 2152-2221
CTX-01. A whole event-shaped working copy, every part filled in: your own finding, a teammate's finding in `incoming/bob/`, an index listing both, one status update and a clean `report.md`.
- `--final` returns 0. After the four WROTE lines come only `report.md checked: 0 problems` and `QA: 2 findings; 2 READY; 0 DRAFT; 0 warnings; 0 errors`, so there is no WARNING or ERROR line
- the QA report has `PASS <name>` for every name in `QA_CHECKS`, in order, plus the two `report.md` checks. "required fields" (the rationale), "reproduction steps" (the indented `Expected:` lines) and "references" (the `https://` link) are among them
- all four `build/` files are written with the expected content: `qa-report.txt` equals the returned text, both summary rows and the counts row, the status-update timeline row, both findings unchanged in `findings-combined.md` with no DRAFT banner; `report.md` is unchanged

**Limit:** "every check is PASS" means every result line is there and says PASS. It doesn't prove the check behind each line ran (see `render_qa_report()`).

**If Operations asks:** "This is the spec's 'a correctly filled finding passes every check in `--final`', run end to end through the real tool on a fake working copy."

#### `DoneMatrixTests` - lines 2224-2276
CTX-02. The spec's Definition-of-done table, one row per case, each in a fresh fake working copy:

| Case | Draft exit | `--final` exit | Finding | `--final` ERROR lines |
|---|---|---|---|---|
| marker in a finding (`[[HOST]]`) | 0 | 1 | DRAFT | the `[[HOST` leftover marker, at line 7 |
| marker only in `report.md` | 0 | 1 | READY | the `[[EXEC_SUMMARY` leftover marker in `report.md`, at line 3 |
| `report.md` absent | 0 | 0 | READY | none; the `report.md NOT FOUND` line is shown |

- each draft run also shows the DRAFT banner exactly for the draft, no screen line that mentions `report.md` (draft mode ignores it; the pandoc hint is patched out) and no ERROR line
- each `--final` run's ERROR lines are exactly the listed ones, so the exit code 1 comes from the intended marker

**If Operations asks:** "This is the table from our definition of done, as one test: a draft never stops the tool, and `--final` blocks a leftover marker whether it's in a finding or in the report."

#### Manual CLI check of the first row (V-02; not code, no line range)
The tests call `compile.run()`; this checks the same thing through the real command line once, by hand. It repeats only the first `DoneMatrixTests` row (a marker in a finding), not the whole matrix.

1. From the repo root, start `python3 -i` and paste this. It uses the test helpers, so the fake working copy lands in `tools/tests/.tmp/` and nothing outside the repo is touched:

```
import sys, unittest
sys.path.insert(0, "tools/tests")
import support
case = unittest.TestCase()
finding = support.make_complete_finding().replace("web01 (10.0.0.1), http", "[[HOST]] (10.0.0.1), http")
index = "finding_id,title,severity,cvss_score,owner,status,in_report\nF-001,,,,,,\n"
root = support.make_worktree(case, {"findings/F-001-default-admin-password.md": finding, "tracker/findings-index.csv": index})
print(root)
```

2. Leave that session open. In a second terminal, also at the repo root, set `ROOT` to the printed path and run both modes:

```
ROOT=<the path printed in step 1>
python3 tools/compile.py --root "$ROOT"; echo "exit: $?"
python3 tools/compile.py --root "$ROOT" --final; echo "exit: $?"
ls "$ROOT/build"
```

3. Back in the session, `case.doCleanups()` deletes the fake working copy; then `exit()`. `tools/tests/.tmp/` should be empty again.

Recorded on 2026-10-22 with Python 3.9.6 (no `pandoc` installed, so no hint line; `<root>` stands for the printed path):

| Run | Screen lines after the four `WROTE <root>/build/...` lines | Exit |
|---|---|---|
| draft | `WARNING: findings/F-001-default-admin-password.md:7: leftover marker [[HOST`, then `QA: 1 findings; 0 READY; 1 DRAFT; 1 warnings; 0 errors` | 0 |
| `--final` | `ERROR: findings/F-001-default-admin-password.md:7: leftover marker [[HOST`, `report.md NOT FOUND: report not checked`, then `QA: 1 findings; 0 READY; 1 DRAFT; 0 warnings; 1 errors` | 1 |

`build/` then held the four files: `findings-combined.md` (starting with the banner `[[NOTE: DRAFT: 1 unresolved markers, 0 missing fields]]`), `findings-summary.md` (one Critical row, Total 1), `interactions-timeline.md` (header only: no timeline files) and `qa-report.txt` (the DRAFT line and one FAIL, `leftover markers`). This matches the `DoneMatrixTests` row. For a practice run with your own files, use the example in `tools/README.md` instead.

**If Operations asks:** "Besides the automated tests, we ran the real command once by hand on a fake folder and checked it gave the same results and exit codes."

#### `EVENT_F001` + `EVENT_F002` - lines 2279-2321
Findings A and B from the event-scenario note, copied exactly: a clean finding, and one with one real step followed by pasted output that starts with an IP address (`10.0.0.5 dc01 signing:false`). All names and addresses are fake.

**If Operations asks:** "Two realistic fake findings from the practice scenario we used to review each chunk."

#### `EventScenarioTests` - lines 2324-2437
CTX-03. One fake working copy holding the traps that already caused a review finding or a fix, one problem-causing trap per file. The files are written as bytes so the BOM and CRLF reach the disk exactly.

| File | Trap | Expected |
|---|---|---|
| `findings/F-001` | saved with a UTF-8 BOM (Chunk 5 CR-1) | READY; its title is in the summary; no BOM in `findings-combined.md` |
| `incoming/bob/findings/F-002` | CRLF line endings (Chunk 2 card) and the IP-first output line (Chunk 3 CR-2) | READY; reproduction steps PASS; its CRLF text copied unchanged |
| `findings/F-003` | lowercase `high` (C-15 Q2) | DRAFT: `0 unresolved markers, 0 missing fields, no severity word`, plus the "no severity" problem |
| `findings/F-004` | a second Severity line (Chunk 2 fix) | READY, plus the `duplicate Severity line; line 3 is used` problem |
| `field-notes/alice/SU-midpoint.md` | saved with a UTF-8 BOM (Chunk 5 CR-1) | timeline row `2026-11-07 14:00`, Summary `Client Status Update` |

- draft returns 0 with exactly the two problems as WARNING lines; `--final` returns 1 with exactly the same two as ERROR lines
- the readiness lines are the same in both modes, and exactly one DRAFT banner is written
- every source file is byte-for-byte unchanged after both runs

**Why these outcomes:** the expected outcomes come from the DECISIONS entries (Chunk 3 CR-2, C-15 Q2), which win over the note's wording.

**If Operations asks:** "These are the real mistakes we expect on the day, like a file saved by Windows Notepad, Windows line endings, pasted command output and a lowercase severity. The test proves the tool handles each one the way we decided."

#### Run-directly lines - test_support.py lines 82-83, test_compile.py lines 2440-2441
Let one test file run on its own: `python3 tools/tests/test_compile.py`.

**If Operations asks:** "So one test file can be run by itself. Normally we run them all with `python3 -m unittest discover tools/tests`."

## 4. Related edits outside tools/

### `.gitignore` lines 60-61
A comment, then `tools/tests/.tmp/`, so test leftovers can't be committed (S-08, CR-8).

**If Operations asks:** "Tests write their temporary files in one folder, and git ignores it."

### `templates/status-update.md` line 5 and `templates/inject-response.md` line 7
The time lines now take a date plus a time (S-05, S-06, OQ-01), so the timeline sorts by `YYYY-MM-DD HH:MM`.

**If Operations asks:** "We added the date so our timeline can sort everything in order."

### `templates/finding.md` line 12
The References NOTE now says the link goes "on this line" (Chunk 3 CR-3), because `check_references()` only looks at that line. No other byte changed.

**If Operations asks:** "The template now tells the writer where the link has to go, so a link in a sub-list below doesn't fail the check by surprise."

### `checklists/50-report-qa.md` line 8
The manual marker grep uses the same regex as the tool, `\[\[[A-Z_]+` (CR-1).

**If Operations asks:** "The checklist's search and the tool's search are the same, so they always agree on what counts as a leftover placeholder."

### `checklists/50-report-qa.md` lines 6-7 (Chunk 7, D-08)
"Run these from inside `~/cptc-work`" now comes first, because the compile command below it uses the relative path `tools/compile.py`. The compile line now says to run `--final` first, fix every `ERROR` (it exits 1 while any is left) and check every `WARNING`. It names what the tool covers (the finding files, the `IR-`/`SU-`/`INJ-` files, the findings index, and `report.md` for leftover markers and older-style leftovers only), says it never reads the exported file, mentions draft mode, and points to `tools/README.md`. The greps, the exported-file Ctrl-F and the PDF/DOCX checks are unchanged.

**If Operations asks:** "The report QA list starts with our tool's strict check, says what the tool can't see, and keeps the manual searches for the exported PDF or Word file."

### `tools/BUILD-SPEC.md` (Chunk 7, S-09)
Listed here because it isn't code, though it lives in `tools/`. Wording only. The compile decisions from 2026-10-20 and 2026-10-21 are now written into the spec sections they change:
- Constraint 4: C-21, no links at `build/` or its output files
- Constraint 6: CP-01/CP-02, the size the user accepted at M2
- Two modes: C-15 Q2/Q3 (READY also needs a severity word and a title), C-11 (has-text rule), Chunk 4 CR-3 (the banner shows the readiness line), C-19 Q1 (timeline problems are errors in `--final`), and the two kinds of problem that stay warnings
- Outputs: C-16, C-17B and Chunk 4 CR-4 (pipe checks, with the double-backslash Limit), and C-19 Q3 (`FAIL (E errors, W warnings)`; the exit code depends only on errors)
- Tool 1 QA: Chunk 3 CR-4 (full CVSS 3.1 vector), C-19 Q2 (required-fields check), C-12 (References check), Chunk 3 CR-2 (step format)
- Deliverables: Chunk 3 CR-3, the `templates/finding.md` References NOTE

The Decisions log (lines 198-242) gained one dated line per decision.

Chunk 7 review: line 39 now says READY covers only leftover markers, the six required fields, the severity word and the title, and that every other check is reported separately (C7-01, Chunk 7 CR-1). The Outputs timeline line (line 62) names the misplaced-file problem, and the Decisions log gained the 2026-10-22 Chunk 7 CR-3 line (C-23). Deliverables (line 188) now lists the `templates/README.md` File names edit among the approved edits outside `tools/` (C7-02, Chunk 7 CR-3). The `dev-tasks` DECISIONS section still has the full entries and wins where the two differ (agents.md rule 6).

**If Operations asks:** "Our design brief now describes the tool as built, including the decisions we made along the way, like requiring the full CVSS 3.1 vector where the first draft only checked the prefix. Each one is dated in its decisions log."

### `tools/README.md` compile section - lines 40-278 (Chunk 7, D-01 and D-02)
Listed here because it isn't code, though it lives in `tools/`. The plain-language guide for the report writer, replacing the "in progress" placeholder: why the tool exists, what it does NOT do, what it needs, how to run it, what it writes and prints, the exit codes, the 13 checks, the `report.md` limits, "one ID = one file", and a practice run. The practice run's output is real: it was captured from the README's own commands in a fake folder under `tools/tests/.tmp/`. The "What's here" table row for `compile.py` now says Built. Chunk 7 review: line 127 says what READY covers in the same words as the spec (C7-01), and the `interactions timeline` row of the checks table (line 143) names the misplaced-file problem (C-23).

**If Operations asks:** "That's the walkthrough any of us can follow on the day. The example output in it is what the tool really printed, not something we typed."

### `tools/README.md` manual checks and Operations questions - lines 299-351 (Chunk 8, D-04C and D-05C)
Listed here because it isn't code, though it lives in `tools/`. Three parts:
- **Heading (line 299):** "Still to write (build workflow)" is now "Walkthrough, manual checks and Operations questions", since two of its three parts are written. Its intro (line 301) says each tool's part is added once that tool is finished and reviewed. Nothing moved.
- **Manual test checklist (lines 307-338, D-04C):** a `#### compile.py` part, so the notebook checks can go in a part of their own later. It starts from steps 1-3 of the practice run, then has 9 checks with the result to expect: `--help`, the `~/cptc-work` default root (run with `HOME` pointed at a missing folder, so a real `~/cptc-work` is never touched), the four outputs, `--final` passing with only warnings, a marker only in `report.md`, a timeline file outside `field-notes/<name>/` (C-23), `--index`, three refused paths (`..`, outside the root, a symlink out of `incoming/`) that leave `build/` unchanged, and the git-clone refusal. Every expected line and exit code was captured by running the real command on a fake practice copy under `tools/tests/.tmp/`, built from the README's own setup block.
- **Questions Operations might ask (lines 340-351, D-05C):** a `#### compile.py` part with six short answers: where it came from (with the same Unconfirmed AI-assistance note as `scripts/logged-shell.md`), explaining how it works (reviewed function by function), targets and network, running commands, changing files (it never changes a file it reads; it writes only the four `build/` files), and what it checks and doesn't (only the checks in the README's checks table, mostly the labelled lines, reproduction steps, leftover placeholders, file names and IDs; it doesn't judge whether a finding is right or complete, such as the technical content, the CVSS score against the vector or the severity, or whether sections like Remediation are there; in `report.md`, only leftover markers and older-style leftovers; never the exported PDF or DOCX). They agree with the "If Operations asks" lines in this file.

**If Operations asks:** "That's the list we work through by hand before the repo lock, with the output to expect, plus our short answers to your likely questions. Each expected result is what the tool really printed in a practice run."

### `templates/README.md` File names - lines 46-47 (Chunk 7 review, C7-02)
The incident report, note, status update and inject response names now start with `field-notes/<yourname>/` (Chunk 7 CR-3). The finding row and everything else are unchanged.

**If Operations asks:** "The template guide now shows the folder as well as the file name, because the timeline only reads files inside a person's `field-notes/` folder."

### `.github/workflows/tests.yml` - lines 1-42 (Chunk 7, S-10)
CI: on every push and pull request, GitHub runs `python -m unittest discover tools/tests` on Ubuntu 24.04 with Python 3.9 and 3.13. It installs nothing, uses no secrets and deploys nothing; the job's token is read-only and isn't kept in the checkout. The runner is pinned because Python 3.9 builds exist for Ubuntu 22.04 and 24.04 but not 26.04. The actions are pinned to exact tags (`actions/checkout@v7.0.1`, `actions/setup-python@v7.0.0`). It hadn't run on GitHub yet when Chunk 7 was written; the first push is its first run.

**If Operations asks:** "We develop on Macs, but the event runs Kali Linux with a newer Python. This runs our tests on Linux with the oldest and a newer Python every time we push, so a difference shows up before the event."
