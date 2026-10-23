# Build spec: `compile.py` and `notebook.py`

This is a handoff brief for a Claude Code session (or a teammate) building two small tools for this repo. Read the whole file before writing code. When the build is done, this spec can be deleted or kept as design notes.

## Context you need first

- **This is the app repo** (public): the tools, `scripts/`, and the templates and checklists they read, for a CPTC (Collegiate Penetration Testing Competition) team's one-day pentest engagement. Before the event it is copied into the team's competition repo (comp repo). Read `templates/README.md` and `scripts/logged-shell.md` before starting, and the comp repo's `README.md` for the game-day setup.
- **Hard deadline:** the repo locks **Fri Oct 30, 2026 at 5:00 PM** (no commits during the week before the Nov 7 event). The tools must be finished, tested and reviewed by about **Oct 27**.
- **The competition rulebook requires** that teams "may be asked to demonstrate or explain their pre-written scripts or code during the event." Every line must be explainable by a student. **Prefer simple, boring code over clever code.** Comment the *why*.
- **Event environment (Unconfirmed; blocked by the open questions "What was on the competition boxes?" and "Network layout"):** each tester has their own Kali Linux box (Python 3 is preinstalled; assume Python ≥ 3.9) and a Windows box, reached over RDP. **No internet access should be assumed.** Teammates' boxes may or may not reach each other.
- **Working copy convention** (comp repo `README.md` → "Working copy and moving files on the day"): during the event everyone works in `~/cptc-work`, a plain copy of the comp repo with no `.git`. Files from teammates arrive in `~/cptc-work/incoming/<name>/`, a **read-only mirror** (rule R18): the tools never write there. The report is `~/cptc-work/report.md`, copied from `templates/report.md` at the midpoint. How finding IDs are allocated is TBD (rule R6: a shared doc, or per-person blocks); the tools must work either way.

## Constraints (apply to both tools)

1. **Python 3 standard library only.** No `pip install`, no third-party packages, no JavaScript libraries or CDNs. Inline vanilla HTML, CSS and JS only.
2. **No network access except `127.0.0.1`.** `notebook.py` binds only to `127.0.0.1`, and neither tool makes outbound connections.
3. **No command execution.** Neither tool runs shell commands or arbitrary code from user input. The one exception: `notebook.py` may call `compile.py`'s functions by importing them, not by `subprocess`. It imports the marker regex, `strip_markers()`, `validate_root()` and `resolve_in_root()` from `compile.py` instead of keeping its own copies; `compile.py` never imports `notebook.py`.
4. **Path safety.** Every read and write must resolve inside an allowed root: the working copy, or `$LOGDIR` (default `~/cptc-logs`) for read-only log viewing. Reject any path with `..` as a whole path part (`a..b.md` is a valid filename) or resolving outside a root, and name the offending path in the error. A symlink is allowed if it resolves inside the root. An explicit `--index` path must also resolve inside `--root`. That covers path traversal. `compile.py`'s four `build/` outputs are stricter (C-21): `build/` or an output file is refused if it is a symlink (even one resolving inside the root) or an existing file with a second hard link, because writing follows links; every output path is checked before anything is written, so a refused run leaves `build/` unchanged. Both tools also refuse to run if `--root` contains a `.git` folder (the working copy must never be the repo clone), and never write inside `incoming/`.
5. **Markdown in, Markdown out.** All saved content is plain `.md` (plus small `.json` for UI state). It must follow the existing templates and the `[[…]]` marker convention in `templates/README.md`.
6. **Size guideline:** `compile.py` about 200–250 lines, `notebook.py` (including its embedded HTML) about 700–800. These are guidelines, not hard caps: what matters is that a student can explain every line. Never compress code to hit a number. At M2 (CP-01, 2026-10-21) `compile.py` was 1551 lines (763 of them code); the user accepted that size with no function splits before M2 (three possible splits are recorded in `tools/compile-breakdown.md`). **One ordered feature list** (build top to bottom; if time or size runs out, cut from the bottom up): 1. token/host checks and path safety; 2. checklists; 3. new file; 4. fill-in view; 5. export (a) zip; 6. log viewer (its copy-command button goes with it); 7. compile button; 8. export (b) combined Markdown. Items 1–4 are the core and are never cut. Renaming files is out of scope (rename by hand if needed). `compile.py` and the checklists stand alone if `notebook.py` isn't ready by the repo lock.
7. **No sample data in the repo** that resembles real hosts, credentials or client names. Tests use obviously fake data, such as `10.0.0.1`, `client-example`, `alice`.
8. **Requests from other web pages are refused (`notebook.py`).** Any page open in the same browser, including a client web app under test, can send requests to `127.0.0.1`. Two checks stop it, in about 10 lines:
    - **Per-run token:** at startup, generate a random token (`secrets.token_urlsafe(32)`) and embed it in the app's own page. Every POST must send it in a header, otherwise reject it with 403. A GET never changes anything (no state-changing GET routes, so no exceptions to remember). The Host check below applies to every request, GET included. Other sites can't read the app's page, so they can't learn the token.
    - **Host check:** reject any request whose `Host` header isn't exactly `127.0.0.1:<port>`. This blocks DNS rebinding, where a malicious domain is made to point at 127.0.0.1.
9. **File and log content is displayed as text only (`notebook.py`).** Logs and files can contain hostile HTML (`<script>`), because we are attacking things. Insert them into the page with `textContent` (or `.value` for textareas), never `innerHTML`; set no CORS headers; send `X-Frame-Options: DENY`. **Every data response** (file content, log content, lists) is JSON or `text/plain; charset=utf-8` with `X-Content-Type-Options: nosniff`, never HTML: otherwise another site could open the log URL directly and a `<script>` in the log would run on the app's own origin, where it could read the token. Only the one app page is served as HTML. Test it with a `<script>` tag inside a fake log.

## Build order

**Build `compile.py` first and get it reviewed.** It's useful on its own, even if `notebook.py` never ships.

## Tool 1: `tools/compile.py` (CLI)

**Purpose:** assemble everyone's findings into report-ready Markdown at any point in the event, and report their QA status using the checks from `checklists/50-report-qa.md`. QA problems only become blocking errors in `--final` mode, right before submission.

**Usage:** `python3 tools/compile.py [--root PATH] [--index PATH] [--final]`. `--root` defaults to `~/cptc-work` (the working copy), not the current directory and not the repo clone.

**Two modes.** Drafts with `[[…]]` markers are normal for most of the event, so they must never stop the tool from working:
- **Draft mode (default)** runs any time during the event. It always writes every output and reports problems as **warnings**, then exits 0.
    - Each finding gets a readiness line in the QA report. **READY** needs no unresolved markers, no missing required fields, a parsed severity word and a title (C-15 Q2/Q3: lowercase `high` or an empty title makes it a draft). Otherwise it is **DRAFT** with a count of unresolved markers and missing fields, plus `no severity word` and/or `no title` when they apply. The required fields are Severity, CVSS 3.1, Why this severity, Affected assets, Status and References. READY covers only leftover markers, the six required fields, the severity word and the title. Every other check is reported separately as its own problem lines, so check those too before pasting.
    - A required field is missing unless, after stripping markers, its value has at least one Unicode letter or digit (C-11). Punctuation-only remnants such as the `()` of an unfilled CVSS line count as missing; the untouched References remnant `CWE-, ATT&CK ,` counts as present.
    - In `findings-combined.md`, each draft finding is preceded by a line `[[NOTE: <readiness line>]]`, e.g. `[[NOTE: DRAFT: 0 unresolved markers, 0 missing fields, no severity word]]` (Chunk 4 CR-3), so the banner names every reason it is a draft. A draft therefore can't slip into the final report unnoticed; the marker check catches the banner itself.
- **Final mode (`--final`)** is the pre-submission check. It writes the same outputs, but every QA problem is an **error**, timeline problems included (a bad or missing time, no `#` heading, a Summary pipe problem; C-19 Q1), and it exits 1 if there is any error. The exceptions stay warnings: older-style leftovers (Tool 1 QA) and an absent, empty or header-only index (Inputs).

**Inputs:**
- `findings/F-*.md` in the root (the report writer's own findings)
- `incoming/*/findings/F-*.md` (teammates')
- the findings index (the master list of IDs): `--index PATH` if given (it must resolve inside `--root`), otherwise `<root>/tracker/findings-index.csv`. A file with only the header row counts as absent, with a warning, so an empty index doesn't flag every finding as "extra"
- `--final` only: `report.md` in the root, if present (the hand-assembled report). It is read for the marker and leftover checks only, never parsed or modified. If it's absent, print a loud line, `report.md NOT FOUND: report not checked`, in the QA report and on screen. If it is present, print `report.md checked: N problems`. It stays a warning, not an error, since the report may live in another tool.

**Parsing:** each finding file follows `templates/finding.md`.
- The heading `### F-NNN: Title` gives the ID and title (finding files use `###` for the title and `####` for sections, so they nest under the report's `## 5. Detailed Findings` without changes). If the heading still holds `[[FINDING_ID]]` (an early draft), use the ID from the filename and count the heading marker as unresolved.
- Details are labelled list lines, e.g. `- **Severity:** High`. Find each by its label:
    - `- **Severity:** …`: strip any `[[…]]` markers from the line first (a `[[CHOOSE: Critical / High / …]]` lists every word), then take the first of Critical / High / Medium / Low / Informational as a whole, case-sensitive word. If none is found, the finding has no severity: warn, and sort it last. The ID in the filename must match the ID in the heading; flag a mismatch
    - `- **CVSS 3.1:** …`: the vector (inside backticks) and the score (in parentheses)
    - `- **Affected assets:** …` and `- **Status:** …`: the rest of the line, as written
    - Before any "has text" check, strip `[[…]]` markers: an unfilled `[[SEVERITY_RATIONALE]]` is not text.
    - `- **Why this severity:** …`: must have text after the label (QA check below)
- Be tolerant of whitespace and fail loudly on missing fields. Report the file and field; don't crash.

**Outputs** (to `build/`; create it if needed; never overwrite `report.md`). Every run regenerates all its output files from scratch; there is no partial update and no history:
- `build/findings-summary.md`: the Section 3 table (`ID | Title | Severity | Affected assets | Status`), sorted Critical → Informational, then by ID. Also the Executive Summary count table (Critical / High / Medium / Low / Informational / Total, with zeros shown). Values go into the table exactly as written. The Severity column is the parsed severity word, or blank if none was found. Total counts every finding and equals the number of table rows. If a Title, Affected assets or Status value (C-16) contains a `|`, which would break the table, report a QA problem naming the finding (a warning in draft, an error in `--final`); don't alter the text. A `|` written as `\|` (backslash, pipe) is not reported, since it doesn't break the table (Chunk 4 CR-4). **Limit:** a `|` after two backslashes (`\\|`) is skipped too, though Markdown reads it as a backslash and a real `|`.
- `build/interactions-timeline.md`: the report's Section 7 table (`Time | Type | Summary | Reference`), one row per `IR-`, `SU-` and `INJ-` file found in `field-notes/*/` and `incoming/*/field-notes/*/` (only these three types; there is no separate client-request type), sorted by time. Type comes from the filename prefix (Incident / Status update / Inject). Time comes from the file's own labelled line: `- **Time reported:**` (IR), `- **Time:**` (SU), `- **Sent:**` (INJ), each holding a date and time. A value matching `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$` is sorted as text, which also sorts it by time; any other value, a leftover marker included, sorts last and is reported as a QA problem (a warning in draft, an error in `--final`; C-19 Q1). Summary is the file's `#` heading exactly as written; a `|` in it is reported the same way as in the summary table, with the same `\|` rule and Limit, and the text is not changed (C-17B, Chunk 4 CR-4). Reference is the filename without `.md`. An `IR-`, `SU-` or `INJ-` file at the root's top level or the top of `field-notes/`, or in the same two spots inside `incoming/<owner>/`, is not in the timeline; each one is reported as a QA problem naming it (a warning in draft, an error in `--final`), and no other folder is searched (Chunk 7 CR-3). This replaces any separate interaction tracker.
- `build/findings-combined.md`: all findings concatenated in that order, ready to paste into Section 5. Headings are left as written: the templates already use `###`/`####`, which nest correctly under Section 5. Warn if a finding's title isn't a `###` heading.
- `build/qa-report.txt`, the QA results. Each check is PASS, or `FAIL (E errors, W warnings)` when it has any problem, even if all of them are warnings (C-19 Q3); each problem is listed with file:line:
    - leftover markers (warning in draft mode, error in `--final`): regex `\[\[[A-Z_]+` (catches an unclosed or bare marker such as `[[HOST` too)
    - older-style leftovers: `<<`, `TODO`, `F-XXX`, `IR-XXX`, `\bXX\b`, `YYYY`, `HH:MM`. These are **warnings even in `--final`** (they can appear legitimately), and the check skips fenced code blocks and backtick spans. A `TODO` inside a `[[TODO: …]]` marker is not reported here (the marker check covers it); every other pattern still warns inside markers
    - duplicate finding IDs across `findings/` and `incoming/*/findings/` (any two files with the same ID)
    - IDs missing from, or extra to, `findings-index.csv`, matched on its `finding_id` column (skip if the file is absent)
    - CVSS vectors that aren't a full CVSS 3.1 vector: all eight base metrics in the standard order and nothing extra, the same rule as the notebook's `CVSS_VECTOR` warning (OQ-09), kept as one shared regex in `compile.py` (Chunk 3 CR-4). A valid but reordered vector therefore fails. An unfilled `[[CVSS_VECTOR]]` is skipped here, since the marker check reports it
    - findings missing a value for any of the six required fields (C-19 Q2; this widens a "Why this severity"-only check): a labelled line with no value is reported at its line, while a labelled line that is missing altogether is reported once, by file and label, under the labelled-lines check. Also findings missing reproduction steps, or at least one `http` reference (looked for on the `References:` line only, after stripping markers, so a link only inside a marker doesn't count; case-sensitive, so `HTTP://` doesn't pass; C-12). Reproduction steps pass when the `#### Reproduction steps` section has at least one numbered line (optional indent, digits, a dot, then a space or tab, e.g. `1. `; Chunk 3 CR-2: so a pasted output line starting with an IP address, such as `10.0.0.5 dc01`, isn't counted) and at least as many lines starting `Expected:` (after stripping leading whitespace; the template indents it under its step) as numbered lines. Strip multi-line `[[NOTE: …]]` markers out of the section first, because the template's own example inside the note contains a numbered line and an `Expected:`; otherwise report which finding is short
    - `--final` only: the leftover-marker and older-style checks above, run on `report.md` as well, reported under their own `report.md` heading with file:line
- **Limit:** only Markdown is checked. If the report is finished in Word, LibreOffice or a `.docx` template, the exported PDF/DOCX can't be checked by this tool, so the manual Ctrl-F search in `checklists/50-report-qa.md` stays.
- **Screen output:** the run returns and prints four `WROTE` lines (one per output file), one `WARNING` or `ERROR` line per problem, the `report.md` status line (`--final` only), then `QA: N findings; R READY; D DRAFT; W warnings; E errors`, then the optional pandoc hint below.
- **Exit code:** draft mode always 0 (unless the tool itself crashes or can't read the files). `--final` returns 1 if any problem is an error, otherwise 0; a FAIL line made only of warnings (e.g. older-style leftovers) doesn't change the exit code (C-19 Q3).

**Optional:** if `pandoc` is on `PATH`, print a hint showing the exact command to convert `report.md` to PDF or DOCX. Don't run it automatically, and don't fail if pandoc is absent.

**Tests:** `tools/tests/test_compile.py` with `unittest`, plus fake fixtures under `tools/tests/fixtures/`. The repo's `.gitignore` excludes `*.log`, `*.xml` and similar; it has an exception for `tools/tests/fixtures/`, so keep fixtures there (or generate them inside the tests). Tests write temporary files only under `tools/tests/.tmp/` (gitignored), never `/tmp` or the OS temp folder, and may delete only their own files there. Cover:
- parsing a well-formed finding
- a missing field
- leftover marker detection
- `--final` with a marker left in `report.md` (fails) and with `report.md` absent (loud warning only)
- `--index PATH`, and a header-only index treated as absent
- severity parsing with an unresolved `[[CHOOSE: Critical / High / …]]` line, and a missing severity sorting last
- filename ID not matching heading ID
- duplicate IDs across `findings/` and `incoming/`
- `build/interactions-timeline.md` from fake `IR-`, `SU-` and `INJ-` files, including one with an unfilled time (sorted last, warned)
- a correctly filled finding (indented `Expected:` lines, real reference URL, rationale filled) passes every check in `--final`
- an unfilled `[[SEVERITY_RATIONALE]]` fails the "Why this severity" check, and a References line without `http` fails
- a `|` in a title produces the warning
- a draft finding gets the DRAFT banner; a draft heading `### [[FINDING_ID]]: …` uses the filename ID
- a finding whose title isn't a `###` heading gets the warning
- refuses to run when `--root` contains `.git`
- the reproduction check on an untouched `templates/finding.md` (must fail, not pass off the note's example)
- older-style words inside a code fence (ignored)
- the CVSS version check
- sort order

## Tool 2: `tools/notebook.py` (local single-user web UI)

**Purpose:** a small UI each tester opens on their own box for checklists, field notes and filling in templates. It's a convenience layer that produces the same Markdown files the repo already uses. It is not a server for the team.

**Usage:** `python3 tools/notebook.py --name alice [--root ~/cptc-work] [--port 8765]`, then open `http://127.0.0.1:8765`. Built on `http.server`. It prints the URL and a reminder that it's local-only.

**Look and layout:** barebones. Black text on white, or white on black following the system's dark-mode setting (`prefers-color-scheme`), with a toggle button. One plain font, no styling beyond spacing.
- **Left column:** the person's files, grouped by prefix (sorting by name does this), and a **New** button. Below them: Checklists, Logs, Export, Compile.
- **Main pane:** whatever is selected in the left column.

**Features** (descriptions; build and cut order is the single list in constraint 6):
1. **Checklists:** list `checklists/*.md` and render each task line with a real checkbox; everything else is shown as preformatted text. Read the Markdown live from disk, so there's one source of truth. Save tick state to `field-notes/<name>/checklist-state.json`, keyed by the checklist's relative path, the exact task text and which occurrence of that text it is. Never modify the checklist files themselves.
2. **New file:** the user never types a filename. "New" asks for a **title** (free text) and a **type** (dropdown), and the tool builds the name and location:

    | Type | Saved as | Starts from |
    |---|---|---|
    | Note | `field-notes/<name>/NOTE-<slug>.md` | blank |
    | Incident report | `field-notes/<name>/IR-NNN-<slug>.md` | `templates/incident-report.md` |
    | Status update | `field-notes/<name>/SU-<slug>.md` | `templates/status-update.md` |
    | Inject response | `field-notes/<name>/INJ-<slug>.md` | `templates/inject-response.md` |
    | Finding | `findings/F-NNN-<slug>.md` | `templates/finding.md`, or a `findings-library/` entry picked from a second dropdown |

    - `<slug>` is the title lowercased, with anything other than `a-z`, `0-9` and `-` replaced by `-`, repeats collapsed, trimmed to 40 characters, with leading and trailing `-` stripped. Refuse an empty slug. `--name` is slugged the same way. Because the tool builds every path from a fixed folder plus a slug, the user can't write outside the allowed folders.
    - `IR-` and `F-` need an `NNN` the user types in: for `F-`, per the team's ID allocation (rule R6, TBD); for `IR-`, the tool suggests the highest existing IR number plus one (`001` if there is none), and the user can change it. Validate it against `^\d{3}$`. The other types have no number. The new file has `[[FINDING_ID]]` or `[[IR_ID]]` already filled with that ID, and `[[FINDING_TITLE]]` with the title. For a finding, the title field defaults to the chosen library entry's title; an edited title replaces only the text after `### [[FINDING_ID]]: ` in the entry's first heading, and gives the slug. Warn if a finding with that ID already exists in `findings/` or `incoming/`.
    - Otherwise the template is copied unchanged, markers included.
    - Refuse to overwrite an existing file; ask for a different title.
    - Without the notebook, the same names can be made by hand; the convention is in `templates/README.md` (File names).
3. **Fill-in view (marker-driven fields):** clicking a file shows an input box for every `[[…]]` marker still in it, then the whole file in an editable textarea below. No field lists are written into the code: the template *is* the form, so a template change shows up in the form automatically.
    - **Scanning:** scan the text with one regex that also matches markers spanning several lines (some `[[NOTE: …]]` markers contain an example). Show them in the order they appear.
    - **What each marker becomes:**
        - `[[NAME]]`: an input box labelled with the name. If the same name appears more than once, show it once; its value fills every occurrence ("same name, same value" in `templates/README.md`).
        - `[[CHOOSE: a / b / c]]`: a dropdown of the options (split on ` / `).
        - `[[TODO: …]]`: an input box, with the TODO text shown as guidance.
        - `[[NOTE: …]]`: help text, shown in place and highlighted. The app never removes a note. The writer deletes it in the textarea once they've read it and acted on it, so every note gets a deliberate decision.
    - **Box size:** a multi-line textarea when the marker is the only thing on its line apart from `[[NOTE: …]]` markers (a section body such as `[[REPRODUCTION_STEPS]]`), or when the line directly follows a heading line (any `#` level). Otherwise a one-line input (a value inside a labelled line or a heading). Ignore NOTE markers when deciding.
    - **Save** (marker boxes use an explicit Save button) applies the changes to the textarea's text, writes the file, and rescans. Before replacing, re-find each marker in the current text and warn if it is gone (the user may have edited it in the textarea). Key boxes by name for `[[NAME]]` markers and by position for the others:
        - each filled box replaces its exact marker text with the value **exactly as typed**: no escaping, trimming or reformatting of what the user wrote
        - an empty box leaves its marker in place
        - nothing else in the file is touched
    - **Status line:** "n markers left (k of them notes)" or "complete".
    - **Warnings, never blocking:** shown next to a box, and the save still happens.
        - a small lookup table of format checks by marker name: `FINDING_ID` → `F-` + 3 digits; `IR_ID` → `IR-` + 3 digits; `CVSS_VECTOR` → a full CVSS 3.1 vector with all eight base metrics in the standard order and nothing extra; `CVSS_SCORE` → 0.0–10.0; names starting `DATE` → `YYYY-MM-DD`; names starting `TIME` → `HH:MM`; `REFERENCE_URL` → starts with `http`. A name not in the table gets no check.
        - a value containing `[[`, which would look like a leftover marker to QA
    - **The textarea** is the file itself. Typing there autosaves about 2 seconds after typing stops, with a visible "saved at HH:MM:SS". Autosave never refreshes the marker boxes while any of them holds an unsaved value. The boxes show an "unsaved" indicator, and the page warns before navigating away with unsaved box values (the textarea has nothing to warn about, it autosaves).
4. **Logs:** list files in `$LOGDIR` (newest first) and view them read-only, with a search box, so output can be copied straight into a finding.
    - **Clean for display only.** Full transcripts contain terminal control codes (colours, carriage returns, backspaces) that show as junk in a browser. Strip those from what's *displayed*, so copied text is clean. Never write the cleaned text to any file, and never change the log itself.
    - Read the log with `newline=""`. Python's default newline handling turns a lone carriage return into a line break, which would show every progress-bar update as a separate line instead of only the final one.
    - **Cleaning order:** (1) turn any run of `\r` followed by `\n` (`\r\n`, `\r\r\n`) into `\n`, because Windows output (evil-winrm, HTTP headers) reaches the transcript as `\r\r\n` and would otherwise be blanked by step 2; (2) for a remaining lone `\r`, keep only the text after the last one on that line; (3) strip escape codes: CSI `\x1b\[[0-9;?]*[ -/]*[@-~]`, OSC `\x1b\][^\x07\x1b]*(\x07|\x1b\\)`, and two-character ones such as `\x1b(B`, `\x1b=`, `\x1b>` (`\x1b[()][A-Za-z0-9]` and `\x1b[=>]`); (4) apply backspace (`\x08` deletes the previous character). Codes are stripped before backspaces so a backspace never eats part of a code. Show the exact commands from `.cmds.log` alongside, since the cleaned transcript can mangle them.
    - **Raw toggle:** a checkbox switches to the uncleaned text (still shown as text, constraint 9).
    - Output that redraws the screen (progress bars, spinners, full-screen tools like `vim`) may still look messy after cleaning. Say so in the UI, and point to the terminal fallback in `checklists/40-evidence-and-logging.md`.
    - A button copies a selected log, unchanged, into `evidence/` with a name the user enters. Restrict that name to letters, digits, `.`, `_` and `-`, and refuse to overwrite. Remind the user to redact secrets before the file goes into a report.
    - **Copy terminal command:** a button next to each log puts `less -R '<full path>'` on the clipboard, for pasting into any terminal. The command is `"less -R " + shlex.quote(path)`; don't wrap the quoted path in more quotes. Also show the command as selectable text in case the clipboard is unavailable. The app never opens a terminal or runs the command itself (constraint 3).
    - If time runs short, this feature is item 6 in the cut order (constraint 6): the terminal route in the checklist always works.
5. **Export:**
    - (a) a zip named `cptc-export-<name>-<YYYYMMDDTHHMMSS>.zip`, saved to the root, laid out so unzipping it inside a teammate's `incoming/<name>/` gives exactly the mirror layout: `findings/`, `evidence/`, `field-notes/<name>/` and `tracker/` (the person's own tracker CSVs). Logs go in a `logs/` folder only if an "include logs" box is ticked (default off, they are large and may hold secrets). Every symlink is rejected from the zip. The tool never extracts a zip itself.
    - (b) **last in the cut order (constraint 6). Unconfirmed whether it's needed:** a single combined Markdown file (all of that person's findings and notes) for pasting over RDP when no file transfer works. It is saved to the root as `cptc-combined-<name>-<timestamp>.md` (ignored by `.gitignore`): findings first, then `NOTE-`, `IR-`, `SU-` and `INJ-` files, each ordered by filename, each under a heading of its relative path, separated by `---`. Build everything else first; build this last if time allows. Whether it is truly needed depends on the open question "How may teammates move files…?" (how files move between boxes), which arrives after the build, so the code must work either way.
6. **Compile** (item 7 in the cut order): a button that calls `compile.py`'s functions and shows the QA report.

**Out of scope:** multi-user access, login/authentication, syncing between machines, rich-text editing, editing `report.md`, running tools or commands, anything network-facing beyond `127.0.0.1`.

**Folder note:** use `field-notes/` for event notes.

**Tests:** unit-test:
- the marker scanner: each marker kind, a multi-line `[[NOTE]]`, a repeated name shown once, and bash `[[ -f x ]]` ignored
- the save step: a value containing `|`, backticks, `$` or `[[` is inserted byte-for-byte; text outside markers is unchanged; notes are never removed
- the format warnings
- the log display cleaner: colour codes, `\r` and backspaces removed from a fake sample; the log file on disk unchanged
- the title-to-filename builder: each type, odd characters, `../` in a title, an existing file
- the path-safety helper
- request safety: a POST without the token, or with a wrong `Host` header, gets 403 and changes nothing; a GET with a wrong `Host` gets 403
- response types: every data endpoint returns JSON or `text/plain` with `nosniff`, never `text/html`
- display safety: a fake log containing `<script>` is served so it can only be inserted as text (check the page code uses `textContent`/`.value`, never `innerHTML`)
- the log cleaner order: `\r\n` and `\r\r\n` input (Windows lines survive), lone `\r` progress lines, backspaces, CSI and OSC codes
- `--name`, the slug builder (leading/trailing `-`, empty slug) and the `NNN` check
- the export zip unpacks into the mirror layout, and the tool refuses to run when `--root` contains `.git`

Manual test checklist in `tools/README.md`.

## Deliverables

- `tools/compile.py`, `tools/notebook.py`
- `tools/tests/` (unit tests and fake fixtures)
- `tools/README.md`: a plain-language walkthrough in the style of `scripts/logged-shell.md`, covering:
    - what each tool does and doesn't do
    - how to run it
    - how it works, section by section
    - a manual test checklist
    - "Questions Operations might ask" with short answers
- Update the comp repo's `README.md` (layout table) and `checklists/00-kickoff.md` (comp repo) / `50-report-qa.md` to point to the tools where relevant. Keep those edits minimal.
- Approved edits outside `tools/`: the status-update `- **Time:**` line becomes `[[DATE]] [[TIME]]` and the inject-response `- **Sent:**` line becomes `[[DATE_SENT]] [[TIME_SENT]]`, so timeline times include a date; the `templates/finding.md` References line's NOTE becomes `[[NOTE: At least one vendor or standards link, on this line. ATT&CK mitigation IDs (M10xx) are optional.]]`, with no other byte changed (Chunk 3 CR-3); the `templates/README.md` File names table shows `field-notes/<yourname>/` before the IR, NOTE, SU and INJ names (DECISIONS 2026-10-22 Chunk 7 CR-3); `.gitignore` gains `tools/tests/.tmp/`, and `cptc-combined-*.md` beside `cptc-export-*.zip`.

## Definition of done

- `python3 -m unittest discover tools/tests` passes with no third-party packages installed.
- Running both tools against a fake `~/cptc-work` built from the test fixtures produces correct output, and with a marker left in, `compile.py` exits 0 with a DRAFT warning in default mode but exits 1 with `--final`. A marker left only in `report.md` is ignored in default mode (exit 0) and fails `--final` (exit 1).
- `notebook.py` has no option to bind anywhere but `127.0.0.1` (the address is hard-coded), and path-traversal attempts (`../../etc/passwd`) are rejected. A POST without the per-run token, or any request with a `Host` other than `127.0.0.1:<port>`, is rejected. Data endpoints never return HTML. Opening a log containing `<script>` shows the text and runs nothing. Unsaved marker values trigger the leave-page warning.
- A teammate who didn't write the code can explain each section using `tools/README.md`.
- Nothing in the repo contains real-looking client data or credentials.

## Decisions log

Resolved open questions folded into this spec on 2026-10-15. The full decisions are in the `dev-tasks` note.

- **2026-10-15 process:** tests write temporary files only under `tools/tests/.tmp/` (gitignored) and may delete only their own files there (Tool 1 Tests).
- **2026-10-15 path-safety (C-03):** `..` is checked as a whole path part, so `a..b.md` is a valid filename; every path is still resolved and must stay inside the root (Constraint 4). Confirmed by the user at M1.
- **2026-10-15 M1 (CR-1):** the leftover-marker regex is widened to `\[\[[A-Z_]+` so a bare `[[HOST` is caught and READY can be trusted; the `checklists/50-report-qa.md` grep uses the same regex (Tool 1 QA).
- **OQ-01 (2026-10-15):** status-update and inject-response times gain a date; timeline times must match `YYYY-MM-DD HH:MM`, otherwise sort last with a warning (interactions timeline, Deliverables).
- **OQ-02 (2026-10-15):** a `TODO` inside a `[[TODO: …]]` marker isn't reported by the older-style check; other patterns still are (Tool 1 QA).
- **OQ-03 (2026-10-15):** an edited library-finding title replaces only the first heading's title and gives the slug (Tool 2 New file).
- **OQ-04 (2026-10-15):** the timeline Summary is the `#` heading exactly as written (interactions timeline).
- **OQ-05 (2026-10-15):** the CVSS version check skips an unfilled `[[CVSS_VECTOR]]` (Tool 1 QA).
- **OQ-06 (2026-10-15):** an explicit `--index` must resolve inside `--root` (Constraint 4, Tool 1 Inputs).
- **OQ-07 (2026-10-15):** the IR number defaults to the highest existing one plus one, starting at `001`, and stays editable (Tool 2 New file).
- **OQ-08 (2026-10-15):** checklist lines that aren't tasks are shown as preformatted text; ticks are keyed by path, task text and occurrence (Checklists).
- **OQ-09 (2026-10-15):** the `CVSS_VECTOR` warning requires all eight base metrics in the standard order, nothing extra (Fill-in warnings).
- **OQ-10 (2026-10-15):** the combined Markdown export's name, order, headings and separators (Export (b)).
- **OQ-11 (2026-10-15):** no client-request type; the timeline stays IR/SU/INJ only (interactions timeline).
- **OQ-12 (2026-10-15):** every symlink is rejected from the zip export (Export (a)).
- **OQ-13 (2026-10-15):** `notebook.py` imports the marker regex, `strip_markers()`, `validate_root()` and `resolve_in_root()` from `compile.py`; never the other way round (Constraint 3).
- **OQ-14 (2026-10-15):** the six required fields for READY; reproduction steps are checked separately (Two modes).
- **OQ-15 (2026-10-15):** the screen output lines and their order (Tool 1 Outputs).
- **OQ-16 (2026-10-15):** the summary Severity is the parsed word or blank; Total equals the number of rows (`findings-summary.md`).
- **OQ-17 (2026-10-15):** symlinks resolving inside the root are allowed; anything outside is rejected with the path named (Constraint 4).
- **OQ-18 (2026-10-15):** `.gitignore` gains `cptc-combined-*.md` beside `cptc-export-*.zip` (Export (b), Deliverables).

Later compile decisions (2026-10-20 to 2026-10-22) folded in on 2026-10-22 (S-09, then C-23). The full entries are in the `dev-tasks` note's DECISIONS.

- **2026-10-20 C-11:** a field has a value only if, after stripping markers, it has a Unicode letter or digit; the untouched References remnant `CWE-, ATT&CK ,` counts as present (Two modes).
- **2026-10-20 C-12:** the `http` reference check strips markers first and is case-sensitive (Tool 1 QA).
- **2026-10-20 C-15 Q2:** READY also needs a parsed severity word; lowercase `high` makes a finding DRAFT. Departs from the spec's READY rule (Two modes).
- **2026-10-20 C-15 Q3:** READY also needs a title after `F-NNN:`. Departs from the spec's READY rule (Two modes).
- **2026-10-20 C-16:** a `|` in Status is reported too, not only in Title and Affected assets; the text is not changed (`findings-summary.md`).
- **2026-10-20 C-17B:** a `|` in a timeline Summary is reported, same rule as C-16; the text is not changed (interactions timeline).
- **2026-10-20 Chunk 3 CR-2:** a reproduction step needs a space or tab after its dot, so IP-first output lines aren't counted. Narrows "1., 2., …" (Tool 1 QA).
- **2026-10-20 Chunk 3 CR-3:** approved template edit: the `templates/finding.md` References NOTE wording (Deliverables).
- **2026-10-20 Chunk 3 CR-4:** the CVSS check requires the full canonical CVSS 3.1 vector (the OQ-09 regex, one shared constant), not just the `CVSS:3.1/` prefix; a valid but reordered vector blocks `--final`. Departs from the spec's prefix-only check (Tool 1 QA).
- **2026-10-20 Chunk 4 CR-3:** the draft banner shows the readiness line as-is, not the literal `[[NOTE: DRAFT: n unresolved markers]]`. Spec departure (Two modes).
- **2026-10-20 Chunk 4 CR-4:** a `|` written as `\|` isn't reported by the pipe checks (summary cells and timeline Summary); an ordinary `|` still is. Limit: `\\|` is skipped too. Spec departure (`findings-summary.md`, interactions timeline).
- **2026-10-21 C-19 Q1:** timeline problems are errors in `--final`, like every other QA problem; older-style leftovers and an absent, empty or header-only index stay warnings (the index rule comes from Inputs and C-08) (Two modes).
- **2026-10-21 C-19 Q2:** a "required fields" check reports each of the six READY fields whose labelled line has no value, at that line (a missing labelled line stays with the labelled-lines check). Widens the spec's single "Why this severity" check (Tool 1 QA).
- **2026-10-21 C-19 Q3:** a check with any problem shows `FAIL (E errors, W warnings)`, even when all are warnings; the exit code depends only on errors, so `--final` can show a FAIL line and still exit 0 (Outputs, Exit code).
- **2026-10-21 C-21 build/ links:** `build/` and the four output files are refused if a symlink (even inside the root) or an existing file with a second hard link, all checked before any write. Narrower than OQ-17, for those paths only (Constraint 4).
- **2026-10-21 CP-01/CP-02:** no function splits before M2 (three candidates recorded in `tools/compile-breakdown.md`); an ID listed twice in the findings index and a check that stops being called (it still prints PASS) stay documented Limits there; the M2 review was the Chunk 6 tests, a whole-tool tour, then the DECISIONS with these spec edits (Constraint 6).
- **2026-10-22 Chunk 7 CR-3:** an `IR-`, `SU-` or `INJ-` file at the root's top level or the top of `field-notes/` (and the same two spots inside each `incoming/<owner>/`) is reported as a QA problem under the interactions timeline check, since it is left out of the timeline; nowhere else is searched. Widens the spec's timeline line (interactions timeline).
