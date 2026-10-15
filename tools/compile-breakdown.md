# compile.py breakdown

A walk through every block of `compile.py`, its test helpers and its tests, plus the related edits outside `tools/`. Each entry gives the line range, what the block does, and a plain answer a student can give if Operations asks about it during the event (the rulebook says teams may be asked to explain their pre-written code).

Line ranges match the code as of the end of Chunk 1 (M1 rework). The implementor updates this file at the end of every review chunk, and the code reviewer checks it against the code.

## 1. compile.py

### Module docstring - lines 1-12
Purpose, usage line and safety promises.

If Operations asks, a student can say: "This is the description at the top of the file. It says what the tool does, how to run it, and what it never does: it doesn't run commands, doesn't use the network, and only writes to `build/`."

### Imports + `MARKER_RE` - lines 14-31
One regex for a whole marker, multi-line NOTEs included. It stops at the next `[[`.

If Operations asks, a student can say: "That regex finds placeholders like `[[HOST]]` in our templates so we can ignore them when we check whether a field is filled in. It needs a capital letter right after `[[`, so it skips bash `[[ -f x ]]` tests. It can't run past the next `[[`, so a placeholder that's missing its closing brackets can't hide the next one."

### `LEFTOVER_RE` - lines 33-40
Matches the start of a leftover marker (`[[` plus a capitalised name), including an unclosed or bare one such as `[[HOST`. Same pattern as the checklist grep.

If Operations asks, a student can say: "This is the same search as the grep in our QA checklist. It flags any leftover `[[NAME` in a finding, even one missing its closing brackets, so a draft can't go into the report unnoticed."

### `strip_markers()` + `scan_leftover_markers()` - lines 43-64
Remove complete markers; list leftovers with file and 1-based line number.

If Operations asks, a student can say: "The first function removes placeholders so we can tell whether a field is really filled in. The second lists every placeholder still left, with its file and line number, like `grep -n`. That count, together with any missing required fields, decides whether a finding is READY or DRAFT."

Also: "Those are internal steps, not settings. Every run does them. The only choice the user makes is `--final`, which turns warnings into errors right before submission."

### `expand_path()` + `parse_args()` (`--root`) - lines 67-87
Expands `~`; the root defaults to `~/cptc-work`, never the current folder.

If Operations asks, a student can say: "This reads the command-line options. If you don't say where the working copy is, it uses `~/cptc-work`, never the folder you're in. That stops us from accidentally writing event data into our git repo."

### `parse_args()` (`--index`, `--final`) - lines 88-99
Optional index path (a relative path is taken from the root; the default is filled in later, from the root) and the strict-mode switch.

If Operations asks, a student can say: "`--index` lets you point at the findings list if it isn't in the usual place. `--final` is the strict pre-submission mode: any problem fails the run."

Note: the index is read-only. The tool compares its `finding_id` column with the finding files and reports missing or extra IDs.

### `RootError` + `validate_root()` - lines 102-124
The root must exist, be a folder and have no `.git`. It never creates anything.

If Operations asks, a student can say: "Before doing anything, the script checks that the folder exists and isn't our git clone (it has no `.git`). Our repo is public, so the tool refuses to run on the clone and write event data there."

### `resolve_in_root()` - lines 127-148
Refuses `..` path parts; resolves symlinks; refuses anything outside the root, naming the path.

If Operations asks, a student can say: "Every file path goes through this check. It refuses `..`, and it refuses anything that ends up outside the working copy, even through a symlink. So the tool can only touch files in our working copy."

## 2. Test helpers: tests/support.py

Shared by both tools' tests; `notebook-breakdown.md` links here instead of repeating it.

### Import setup + `TMP_DIR` - lines 1-21
Puts `tools/` on the import path; tests write only to `tools/tests/.tmp/`.

If Operations asks, a student can say: "This file is shared setup for our tests. It lets the tests find our tool, and it gives them one private scratch folder inside the repo that git ignores."

### `make_worktree()` + `write_fake_file()` - lines 24-47
Builds one fake working copy per test inside `.tmp/`, deleted when the test ends; fake files can't escape it.

If Operations asks, a student can say: "Each test builds its own fake working copy with obviously fake files, in a scratch folder inside the repo. It's deleted automatically when the test finishes."

### `COMPLETE_FINDING` + `make_complete_finding()` + `remove_worktree()` - lines 50-121
One fully filled fake finding that should pass every check; cleanup deletes only a folder sitting directly in `.tmp/`, and never follows symlinks.

If Operations asks, a student can say: "This is a sample finding with obviously fake data that should pass every check. The cleanup function only deletes the test's own scratch folder. It checks the location first and refuses anything else."

## 3. Tests

### tests/test_support.py

#### Imports + `finding_structure()` - lines 1-13
Collects a finding's `####` headings and `- **Label:**` lines, for the template drift test.

If Operations asks, a student can say: "This small helper lists the section headings and labels in a finding, so a test can compare our sample finding with the real template."

#### `MakeWorktreeTests` - lines 16-43
Four tests: the fake root sits in `.tmp/` with no `.git`; requested files are written exactly; `../` paths are refused; cleanup removes the folder but keeps `.tmp/`.

If Operations asks, a student can say: "These test our test helpers: the fake folder is created in the right place, holds exactly the files we asked for, can't write outside itself, and is deleted afterwards."

#### `MakeCompleteFindingTests` - lines 46-79
Five tests: no `[[` and an `F-001` heading; the rationale has words and References has an `https://` link; at least one step and enough indented `Expected:` lines; the headings and labels match `templates/finding.md` both ways (Attack chain left out on purpose); a custom ID and title are used.

If Operations asks, a student can say: "These prove our sample finding is really complete: no placeholders, a filled-in rationale, a fake but well-formed HTTPS reference, and every reproduction step has its expected result. One test compares it with the real template, so if someone edits the template, the test tells us our sample is out of date. Other tests rely on it being correct."

### tests/test_compile.py

#### Imports + `StripMarkersTests` (part 1) - lines 1-26
`support` is imported first so `compile` can be found. Five tests strip named, CHOOSE, TODO, multi-line NOTE and adjacent markers and check the exact text left.

If Operations asks, a student can say: "Each test gives the function some text with a placeholder in it and checks exactly what's left afterwards. We test each kind of placeholder, including ones that span several lines."

If asked about the name: `import compile` hides Python's built-in `compile()` in the test file only. That's harmless, because the tests never use the built-in, and the spec names the file.

#### `StripMarkersTests` (part 2) - lines 28-53
Edge cases: a marker inside a NOTE, unclosed markers not swallowing the next one, bash `[[ -f x ]]` left alone, and the real `templates/finding.md` stripped clean, including its NOTE example.

If Operations asks, a student can say: "These are the tricky cases: a placeholder inside another, one missing its closing brackets, and a bash `[[ ]]` test that isn't a placeholder at all. The last test runs on our real finding template, so a template change that breaks the tool fails the tests."

#### `ScanLeftoverMarkersTests` - lines 56-76
Leftovers are reported with file, 1-based line and matched text: complete, unclosed (`[[NOTE: never closed`) and bare (`[[HOST`). Bash `[[ -f x ]]` is ignored. The hit count equals the regex matches (the DRAFT banner's n).

If Operations asks, a student can say: "These check that every leftover placeholder is found and reported with its exact line number, including one missing its closing brackets, while bash `[[ ]]` tests are ignored."

#### `ValidateRootTests` - lines 79-107
Five tests: a normal root passes; a `.git` folder is refused with nothing created (file lists compared before and after); a `.git` file is refused; a missing root is refused and not created; a file as root is refused.

If Operations asks, a student can say: "These try every kind of bad root folder: one that's a git repo, one that doesn't exist, one that's a file. Each is refused with a clear message, and the test checks the tool didn't create or change anything first."

#### `ResolveInRootTests` - lines 110-157
`setUp` builds a root and a second "outside" folder, both in `.tmp/`. Allowed: a normal child, `a..b.md`, a symlink inside the root, and an absolute path inside the root (as a real `--index ~/cptc-work/...` is). Refused, with the path named in the error: `../x`, an absolute outside path, an outside `--index`, and a symlinked `incoming/alice` pointing outside.

If Operations asks, a student can say: "These try to escape the working copy every way we could think of: `..`, a full path elsewhere, the index file elsewhere, and a teammate folder that's secretly a link to somewhere else. All are refused and named in the error. Normal files, full paths that stay inside, and links that stay inside are allowed."

#### Run-directly lines - test_support.py lines 82-83, test_compile.py lines 160-161
Let a single test file be run on its own with `python3 tools/tests/test_compile.py`.

If Operations asks, a student can say: "That's just so one test file can be run by itself. Normally we run them all with `python3 -m unittest discover tools/tests`."

## 4. Related edits outside tools/

### `.gitignore` lines 60-61
A comment line, then `tools/tests/.tmp/`, so test leftovers can't be committed (S-08, CR-8).

If Operations asks, a student can say: "Tests write their temporary files in one folder, and git is told to ignore it."

### `templates/status-update.md` line 5 and `templates/inject-response.md` line 7
The time lines now take a date plus a time (S-05, S-06, OQ-01), so the timeline sorts by `YYYY-MM-DD HH:MM`.

If Operations asks, a student can say: "We added the date to these lines so our timeline can sort everything in order."

### `checklists/50-report-qa.md` line 8
The manual marker grep uses the same regex as the tool, `\[\[[A-Z_]+` (CR-1).

If Operations asks, a student can say: "The checklist's search and the tool's search are the same, so they always agree on what counts as a leftover placeholder."

### Note: `tools/BUILD-SPEC.md` Decisions log - lines 197-221
Not an edit outside `tools/` (the spec lives in `tools/`), but listed here because it isn't code. The spec records the resolved decisions, so it agrees with `dev-tasks` (S-07, M1).

If Operations asks, a student can say: "The spec ends with a dated list of every design decision we made while building, so anyone can see why the code works the way it does."
