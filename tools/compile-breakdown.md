# compile.py breakdown

Every block of `compile.py`, its test helpers, its tests, and the related edits outside `tools/`. The rulebook says Operations may ask us to explain our code, so each entry has a line range, a one-line description, and **If Operations asks:** a plain answer a student can give.

Line ranges match the code at the end of Chunk 3. The implementor updates this file at the end of every review chunk; the code reviewer checks it.

> **Status after Chunk 1:** these are building blocks only. `python3 tools/compile.py` doesn't do anything yet; the code that runs them on every finding arrives in task C-22. Don't demo it before M2. (Remove this note at M2.)

| Term | Meaning |
|---|---|
| marker | a `[[NAME]]` placeholder in a template, waiting to be filled in |
| working copy | `~/cptc-work`: a plain copy of the repo with no `.git`, where all event work happens |
| root | the working copy folder the tool reads from (`--root`) |
| READY / DRAFT | a finding's status: READY means no leftover markers and no missing required fields; anything else is DRAFT |
| `--final` | strict pre-submission mode: problems become errors and the run exits 1 |
| diagnostic | one problem found in a file, with the file name and the line (or field) it is on |
| findings index | `tracker/findings-index.csv`: the team's master list of finding IDs, in its `finding_id` column |
| incoming | `incoming/<name>/`: a teammate's files copied in; the tools only read it (rule R18) |
| older-style leftover | a placeholder from before the `[[...]]` markers, like `TODO`, `XX` or `YYYY`; always a warning |

## 1. compile.py

### Module docstring - lines 1-12
What the tool does, how to run it, and what it never does.

**If Operations asks:** "It's the description at the top of the file. It says what the tool does, how to run it, and what it never does: it doesn't run commands, doesn't use the network, and only writes to `build/`."

### Imports + `MARKER_RE` - lines 14-32
Matches one whole marker, including a multi-line NOTE. Stops at the next `[[`.

**If Operations asks:** "It finds placeholders like `[[HOST]]` so we can ignore them when checking whether a field is filled in. It needs a capital letter right after `[[`, so bash `[[ -f x ]]` tests are skipped. It can't run past the next `[[`, so a placeholder missing its closing brackets can't hide the next one."

**Limit:** names with digits, like `[[HOST2]]`, aren't matched. That's on purpose: `templates/README.md` says marker names are capitals and underscores only.

### `LEFTOVER_RE` - lines 34-41
Matches the start of any leftover marker, closed or not. Same pattern as the checklist grep.

**If Operations asks:** "It's the same search as the grep in our QA checklist. It flags any leftover `[[NAME`, even one missing its closing brackets, so a draft can't slip into the report unnoticed."

**Why two regexes:**

| Regex | Needs | Used for |
|---|---|---|
| `MARKER_RE` | the whole marker, `[[` to `]]` | removing markers from text |
| `LEFTOVER_RE` | only the start, `[[NAME` | counting leftovers, including unclosed ones |

### `strip_markers()` + `scan_leftover_markers()` - lines 44-65
Removes complete markers; lists leftovers with file and line number (counting from 1).

**If Operations asks:** "The first removes placeholders so we can tell whether a field is really filled in. The second lists every placeholder still left, with its file and line, like `grep -n`. That count, plus any missing required fields, decides READY or DRAFT. Both run every time; they aren't options."

**Why split on `"\n"`:** it gives the same line numbers as `grep -n`. `splitlines()` also splits on rare characters like form feeds, which would shift the numbers.

### `expand_path()` + `parse_args()` (`--root`) - lines 68-88
Expands `~`. The root defaults to `~/cptc-work`, never the current folder.

**If Operations asks:** "It reads the command-line options. If you don't say where the working copy is, it uses `~/cptc-work`, never the folder you're in, so we can't accidentally write event data into our git repo."

**Why expand `~` in Python:** the shell skips it inside quotes, so `--root "~/cptc-work"` arrives as a literal `~`.

### `parse_args()` (`--index`, `--final`) - lines 89-100
Optional path to the findings index (a relative path starts at the root) and the strict-mode switch.

**If Operations asks:** "`--index` points at the findings list if it isn't in the usual place. The tool only reads it, to spot IDs that are missing or extra. `--final` is the strict pre-submission mode: any problem fails the run."

### `RootError` + `validate_root()` - lines 103-125
The root must exist, be a folder, and have no `.git`. Creates nothing.

**If Operations asks:** "Before doing anything, it checks that the folder exists and isn't our git clone. Our repo is public, so the tool refuses to run anywhere event data could get committed."

**Limit:** only the root itself is checked for `.git`, not the folders above it. Checking those too would block anyone whose home folder is a git repo (dotfiles).

### `resolve_in_root()` - lines 128-149
Refuses `..`; follows symlinks; refuses anything outside the root and names the path.

**If Operations asks:** "Every file path goes through this check. It refuses `..` and anything that ends up outside the working copy, even through a symlink. So the tool can only touch files in our working copy."

### `finding_folders()` + `discover_findings()` - lines 152-194
Lists the finding files to compile: `findings/F-*.md` and `incoming/*/findings/F-*.md`, sorted by path.

**If Operations asks:** "It looks in exactly two places: our own `findings/` folder and each teammate's `incoming/<name>/findings/`. Only files named `F-something.md` count. It only lists them; it never writes in `incoming/`."

**Why check each folder before listing it:** a symlink such as `incoming/alice` could point outside the working copy. Every folder, every `incoming/<name>` entry and every file goes through `resolve_in_root()` first, so the tool never even looks inside a folder outside the root. If one points outside, `discover_findings()` raises an error naming it, instead of skipping that teammate (OQ-17).

**Why sort:** the disk lists files in no fixed order. Sorting gives the same order every run, with `findings/` before `incoming/`.

### `HEADING_RE` + `FILENAME_ID_RE` + `find_title_heading()` + `parse_finding_heading()` - lines 197-271
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

**Limit:** an ID must be `F-` plus exactly three digits. `F-0012-x.md` is not read as F-001.

**Limit:** the first matching line wins, even inside a fenced code block. A template-shaped finding starts with its title, so this doesn't come up in practice.

### `FIELD_LABELS` + `LABEL_LINE_RE` + CVSS regexes + `parse_labelled_fields()` - lines 274-342
Reads the six required detail lines (`- **Severity:** …` and so on) and splits the CVSS line into vector and score.

**If Operations asks:** "Each detail in a finding is a line like `- **Severity:** High`. This finds the six we need by their label: Severity, CVSS 3.1, Why this severity, Affected assets, Status and References. Values are kept as written, placeholders included; only spaces at the ends are dropped. A missing line is reported with the file and field name; it never crashes the run. If a label appears on more than one line, the first one is used and each extra one is reported at its own line."

**Why `rstrip()` each line:** a file saved on Windows ends every line with `\r\n`. Splitting on `\n` leaves the `\r`, which would otherwise end up inside every value (and later inside the summary table).

**CVSS line:** the vector is the text between backticks, the score is the text in parentheses outside them. `` `CVSS:3.1/AV:N/...` (9.8) `` gives the vector `CVSS:3.1/AV:N/...` and the score `9.8`.

**Why two shapes of problem:** a missing label has no line to point at, so it is `(file, label, message)`. A duplicate does have one, so it is `(file, line, message)`, like the heading problems, e.g. `duplicate Severity line; line 3 is used`.

**Limit:** the colon must be inside the bold, as in the template (`- **Severity:**`). A hand-typed `**Severity**:` is reported as missing.

### `SEVERITIES` + `SEVERITY_RE` + `severity_value()` - lines 345-372
Takes the first exact level word from the Severity line, after removing markers.

**If Operations asks:** "It reads the severity word: Critical, High, Medium, Low or Informational, spelled exactly like that. Placeholders are removed first, because the unfilled `[[CHOOSE: Critical / High / …]]` lists every word and would otherwise read as Critical. No level word means a warning, and the finding sorts last."

**Why case-sensitive:** the template offers exactly these words, so `high` means the line wasn't filled in properly.

**Why no second warning for a missing Severity line:** `parse_labelled_fields()` already reports it.

### `finding_sort_key()` - lines 375-386
Sort order: Critical → Informational, then no severity, then by ID.

**If Operations asks:** "Findings are listed most severe first, and by ID within each level. Anything without a severity goes at the end so it stands out."

### `DEFAULT_INDEX` + `load_index_ids()` - lines 389-444
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

**Limit:** an index path that can't be opened at all (e.g. no permission, or it is a folder) isn't caught here; the error is passed on, and C-22 will turn it into a nonzero exit.

### `OLDER_LEFTOVER_PATTERNS` + `CODE_SPAN_RE` - lines 447-464
The seven older-style placeholders, one regex each, and the pattern for an inline code span.

**If Operations asks:** "These are the placeholders people typed before we had `[[...]]` markers: `<<`, `TODO`, `F-XXX`, `IR-XXX`, a bare `XX`, `YYYY` and `HH:MM`. They can show up for real (a `TODO` in quoted output), so they are only ever warnings, even with `--final`."

**Why `\bXX\b`:** only a bare `XX` counts, not the `XX` in `XXE` or `F-XXX`.

**Why `(`+).*?\1`:** a code span opens and closes with the same number of backticks, so ``` ``a ` b`` ``` is one span even with a backtick inside.

### `hide_todo_marker_words()` + `scan_older_leftovers()` - lines 467-505
Lists every older-style placeholder with file and line, skipping fenced code blocks, code spans, and the `TODO` inside a `[[TODO: ...]]` marker.

**If Operations asks:** "It's the second half of the QA checklist's search. It skips fenced code blocks and code spans, because commands and output aren't prose. It also skips the word TODO inside a `[[TODO: ...]]` placeholder, because the marker check already reports that one (OQ-02). Anything else inside a placeholder, like an `F-XXX` in a NOTE, is still reported."

**Why blank TODO with spaces:** nothing else on the line moves, so `X` + `X` can't join into a new `XX`, and line numbers stay the same.

**Why both fence kinds:** Markdown code blocks open with ```` ``` ```` or `~~~`. A block closes only on the same kind it opened with.

**Limit:** hits on the same line are listed in pattern order (`<<` first, `HH:MM` last), not left to right. The line number is always right.

**Limit:** a backtick with no closing partner can hide a little text after it from this check. Code spans spanning several lines aren't recognized.

**Limit:** a code block that is never closed hides the rest of the file from this check. The leftover-marker check still sees those lines.

**Limit:** only ```` ``` ```` / `~~~` fenced blocks and code spans are skipped. Code indented 4 spaces is checked like prose (Chunk 3 CR-1).

### `REPRODUCTION_HEADING_RE` + `SECTION_END_RE` + `STEP_RE` + `reproduction_section()` + `remove_note_markers()` + `check_reproduction()` - lines 508-576
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

### `has_text()` + `missing_required_fields()` - lines 579-604
A value counts only if it still has a letter or digit once placeholders are removed. Lists which of the six required fields have no value.

**If Operations asks:** "A finding is READY only when all six detail lines (Severity, CVSS 3.1, Why this severity, Affected assets, Status, References) have something in them (OQ-14). Leftover punctuation from the template, like the `()` around an unfilled score, doesn't count. Reproduction steps are checked separately."

| Untouched template value | After removing placeholders | Counts as |
|---|---|---|
| `[[HOST]] ([[HOST_IP]]), [[URL]], [[ACCOUNT]]` | `(), ,` | missing |
| `` `[[CVSS_VECTOR]]` ([[CVSS_SCORE]]) `` | ` `` () ` | missing |
| `CWE-[[CWE_ID]], ATT&CK [[ATTACK_TECHNIQUE_ID]], [[REFERENCE_URL]]` | `CWE-, ATT&CK ,` | present |

**Why References counts as present (user decision 2026-10-20, C-11):** `CWE` and `ATT&CK` are letters, and the plain rule has no special cases. An untouched References line still can't be READY, because its markers count as leftovers. Separately, `check_references()` fails it for having no `http` link.

**Why `isalnum()`:** it accepts any Unicode letter or digit, so a value like `Café` counts.

### `check_references()` - lines 607-623
The References line must contain an `http` link.

**If Operations asks:** "Every finding needs at least one vendor or standards link. We only look on the References line, so a link somewhere else in the finding doesn't count."

**Why remove placeholders first:** a link that only appears inside a NOTE's example isn't a real reference.

**Limit:** the match is case-sensitive, so `HTTP://` doesn't pass.

**Limit:** the link must be on the `- **References:**` line itself. Links in a sub-list below it don't count, and an empty References line is then also a missing field. The template's NOTE says "on this line" (Chunk 3 CR-3).

### `FULL_CVSS31_VECTOR_RE` + `check_cvss_version()` - lines 626-657
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

## 2. Test helpers: tests/support.py

Shared with the notebook's tests; `notebook-breakdown.md` links here instead of repeating it.

### Import setup + `TMP_DIR` - lines 1-21
Lets the tests import the tools; sets the one folder tests may write to, `tools/tests/.tmp/`.

**If Operations asks:** "Shared setup for our tests. It lets the tests find our tool and gives them one scratch folder inside the repo that git ignores."

### `make_worktree()` + `write_fake_file()` - lines 24-47
One fake working copy per test, inside `.tmp/`, deleted when the test ends. Fake files can't escape it.

**If Operations asks:** "Each test builds its own fake working copy with obviously fake files. It's deleted automatically when the test finishes."

**Limit:** if a test run is stopped with Ctrl-C, cleanup doesn't run and a `worktree-*` folder stays in `.tmp/`. It's harmless (git ignores it) and can be deleted by hand.

### `COMPLETE_FINDING` + `make_complete_finding()` + `remove_worktree()` - lines 50-121
A fully filled fake finding that should pass every check. Cleanup deletes only a folder directly inside `.tmp/`, and never follows symlinks.

**If Operations asks:** "A sample finding with obviously fake data that should pass every check. Cleanup only deletes the test's own scratch folder, and checks the location first."

## 3. Tests

### tests/test_support.py

#### `finding_structure()` - lines 1-13
Lists a finding's `####` headings and `- **Label:**` lines, for the template drift test.

**If Operations asks:** "A small helper that lists a finding's headings and labels, so a test can compare our sample finding with the real template."

#### `MakeWorktreeTests` - lines 16-43
- the fake root sits in `.tmp/`, with no `.git`
- requested files are written exactly
- `../` paths are refused
- cleanup removes the folder but keeps `.tmp/`

**If Operations asks:** "These test our test helpers: the fake folder lands in the right place, holds exactly the files we asked for, can't write outside itself, and is deleted afterwards."

#### `MakeCompleteFindingTests` - lines 46-79
- no `[[`, and the heading starts `### F-001: `
- the rationale has words; References has an `https://` link
- at least one reproduction step, and an indented `Expected:` for each
- headings and labels match `templates/finding.md` both ways (Attack chain left out on purpose)
- a custom ID and title are used

**If Operations asks:** "These prove our sample finding is really complete. One compares it with the real template, so if someone edits the template, the test tells us the sample is out of date."

### tests/test_compile.py

#### Imports + `StripMarkersTests` part 1 - lines 1-26
`support` is imported first so `compile` can be found. Five tests each strip one kind of marker (named, CHOOSE, TODO, multi-line NOTE, two side by side) and check the exact text left.

**If Operations asks:** "Each test gives the function text with a placeholder in it and checks exactly what's left. We test every kind, including ones that span several lines."

**If asked about the name `compile`:** "`import compile` hides Python's built-in `compile()`, but only in the test file. That's harmless: the tests never use the built-in, and the spec names the file."

#### `StripMarkersTests` part 2 - lines 28-53
- a marker inside a NOTE: only the inner one is removed
- an unclosed marker doesn't swallow the next one
- bash `[[ -f x ]]` is left alone
- the real `templates/finding.md` strips clean, including its NOTE example

**If Operations asks:** "These are the tricky cases. The last one runs on our real finding template, so a template change that breaks the tool fails the tests."

#### `ScanLeftoverMarkersTests` - lines 56-76
- complete, unclosed (`[[NOTE: never closed`) and bare (`[[HOST`) markers are reported with file and line
- bash `[[ -f x ]]` is not reported
- the hit count equals the regex matches (the DRAFT banner's n)

**If Operations asks:** "Every leftover placeholder is found with its exact line number, even one missing its closing brackets. Bash `[[ ]]` tests are ignored."

#### `ValidateRootTests` - lines 79-107
- a normal root passes
- a `.git` folder is refused, and nothing is created (file lists compared before and after)
- a `.git` file is refused
- a missing root is refused and not created
- a file given as the root is refused

**If Operations asks:** "These try every kind of bad root folder. Each is refused with a clear message, and the test checks that nothing was created or changed."

#### `ResolveInRootTests` - lines 110-157
`setUp` builds a root and a second "outside" folder, both in `.tmp/`.

| Allowed | Refused, with the path named in the error |
|---|---|
| `findings/F-001-x.md` | `../x` |
| `findings/a..b.md` | a full path to the outside folder |
| a symlink pointing inside the root | an `--index` in the outside folder |
| a full path inside the root (like a real `--index ~/cptc-work/...`) | `incoming/alice` linked to the outside folder |

**If Operations asks:** "These try to escape the working copy every way we could think of. All are refused and named in the error. Normal files, and full paths or links that stay inside, are allowed."

#### `DiscoverFindingsTests` - lines 160-246
- local and two incoming `F-001-*.md` files come back, in path order
- `G-001.md`, a `.txt`, nested Markdown and notes folders are left out
- a folder named like a finding is skipped; no folders gives an empty list
- refused, with the path named: `incoming/alice` linked outside (with or without findings in it, or to a file), `findings/` linked outside, one finding file linked outside
- a link that stays inside the root is allowed
- nothing in `incoming/` changes

**If Operations asks:** "These prove the tool picks up exactly our findings and our teammates', ignores everything else, and refuses any link that leads outside the working copy."

#### `ParseFindingHeadingTests` - lines 249-326
- a filled `### F-001: …` heading gives the exact ID, title and line
- `[[FINDING_ID]]` uses the filename's ID and counts the marker; the untouched template gives 2 markers
- F-001 filename with an F-002 heading is flagged
- `##` instead of `###` is flagged, with its line
- no heading, or no ID anywhere, is reported without crashing
- `### F-001:` with nothing after the colon is flagged
- a Windows `\r\n` line ending isn't kept in the title
- `F-0012` isn't read as `F-001`

**If Operations asks:** "Each heading problem the spec names has a test that checks the exact message."

#### `ParseLabelledFieldsTests` - lines 329-401
- the complete sample finding returns all six labels, plus the vector and score
- removing the Status line gives exactly one problem, naming Status
- two extra Severity lines give one problem each, at their own line, and the first line's value is kept
- extra spaces and tabs are allowed
- Windows `\r\n` line endings leave no `\r` in the values
- the untouched template keeps its placeholders as written
- a bare `9.8`, or brackets inside the vector, don't give a wrong vector or score
- an empty file reports all six labels

**If Operations asks:** "These prove the tool reads every detail line from a real-shaped finding, and reports a missing or repeated one instead of crashing."

#### `severity_of()` + `SeverityValueTests` - lines 404-437
`severity_of()` parses one line the way the tool does: label first, then level.
- `High` is read
- unfilled `[[CHOOSE: …]]` and lowercase `high` give no severity, with a warning
- `Highest` doesn't count; the first level on the line wins
- a missing Severity line isn't reported twice

**If Operations asks:** "These prove an unfilled or misspelled severity is never mistaken for a real one."

#### `FindingSortKeyTests` - lines 440-465
- eight findings sort Critical, High, High, Medium, Low, Informational, then the two with no severity, with ties by ID
- a finding with no ID still sorts

**If Operations asks:** "This checks the exact order the report tables will use."

#### `INDEX_HEADER` + `LoadIndexIdsTests` - lines 468-541
`INDEX_HEADER` is the header row of `templates/tracker/findings-index.csv`.
- the default index loads an F-001 row
- an explicit `--index` inside the root wins over the default; one outside is refused
- absent, header-only and empty files warn and skip the comparison, in both modes
- a broken CSV and a `title,severity` header are warnings in draft and errors in `--final`
- a spreadsheet's invisible start marker and extra spaces are handled

**If Operations asks:** "These cover every state the index file can be in, and check that a broken one only blocks the run in `--final`."

#### `ScanOlderLeftoversTests` - lines 544-581
- all seven patterns are found in prose, with file and line
- `XXE` and `XXXL` aren't a bare `XX`
- copies inside ```` ``` ```` or `~~~` code blocks and in code spans are skipped; a `~~~` block isn't closed by ```` ``` ````
- a double-backtick span with a backtick inside is skipped; ``X`code`X`` doesn't become `XX`
- `TODO` inside `[[TODO: ...]]` is skipped, even across lines
- `F-XXX` inside a NOTE, `F-XXX` inside a TODO marker, and `TODO` inside a NOTE are still reported

**If Operations asks:** "Each old-style placeholder is caught in normal text, and copies inside code or inside a TODO placeholder are ignored, exactly as the spec says."

#### `CheckReproductionTests` - lines 584-637
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

#### `HasTextTests` - lines 640-692
- leftover punctuation like `() ,`, empty backticks and parentheses, and an unfilled rationale with a NOTE are missing
- filled values pass, including `Café`
- the untouched template gives exactly five missing fields; References counts as present (user decision)
- the complete sample finding has none missing
- a renamed label, or one punctuation-only value, is counted once
- removing the reproduction section doesn't change the missing fields

**If Operations asks:** "These prove that leftover template punctuation never passes as a filled-in value, and that the READY field count ignores reproduction steps."

#### `CheckReferencesTests` - lines 695-723
- a References line without `http` fails, at its line
- `https://example.invalid` passes
- a link elsewhere in the finding, or only inside a placeholder, doesn't count
- the untouched template fails; the complete sample finding passes
- a missing References line isn't reported twice

**If Operations asks:** "These prove only a real link on the References line counts."

#### `CheckCvssVersionTests` - lines 726-771
- the full canonical `CVSS:3.1/...` vector passes
- `CVSS:3.0/...` and a bare `9.8` (with or without backticks) fail, with the line
- a missing `/A:` metric, reordered metrics, or an extra metric fail
- an unfilled `[[CVSS_VECTOR]]`, closed or not, is skipped
- another placeholder doesn't hide a wrong version
- an empty vector fails, whether or not the score is filled
- the complete sample finding passes; a missing CVSS line isn't reported twice

**If Operations asks:** "These prove that only a full CVSS 3.1 vector passes, and that an unfilled vector is left to the marker check."

#### Run-directly lines - test_support.py lines 82-83, test_compile.py lines 774-775
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

### `tools/BUILD-SPEC.md` Decisions log - lines 197-221
Listed here because it isn't code, though it lives in `tools/`. A dated record of the decisions resolved up to 2026-10-15 (S-07). Later decisions, including Chunk 3's departures from the spec (CR-2 step format, CR-4 full CVSS vector), are in the `dev-tasks` DECISIONS section, which wins where the two differ (agents.md rule 6).

**If Operations asks:** "The spec ends with a dated list of our early design decisions. Later ones, like requiring the full CVSS 3.1 vector where the spec only checks the prefix, are in our task list's decisions section, which wins where the two differ."
