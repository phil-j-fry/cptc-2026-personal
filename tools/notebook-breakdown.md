# notebook.py breakdown

Every block of `notebook.py`, its tests, and the related edits outside `tools/`. The test helpers in `tests/support.py` are shared with `compile.py` and are described in [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy). The rulebook says Operations may ask us to explain our code, so each entry has a line range, a one-line description, and **If Operations asks:** a plain answer a student can give.

Line ranges match the code after Chunk N3 (the New form and the own-file list in the left column: N3-01..N3-05, then the Chunk N3 review changes CR-1 and D1, D2, D5). Before it came Chunk N2 (checklists and the own-file list route: N2-01..N2-05) and Chunk N1 (safety and shell: N1-01..N1-08, plus its review changes C-N1-01..C-N1-03). The implementor updates this file at the end of every review chunk; the code reviewer checks it.

| Term | Meaning |
|---|---|
| working copy | `~/cptc-work`: a plain copy of the repo with no `.git`, where all event work happens |
| root | the working copy folder the notebook reads and writes (`--root`) |
| log folder | `$LOGDIR`, or `~/cptc-logs` if it isn't set: where `scripts/logged-shell.sh` saves terminal logs; the notebook only reads it |
| incoming | `incoming/<name>/`: a teammate's files copied in; the tools only read it (rule R18) |
| slug | a title turned into a safe file-name part: only `a-z`, `0-9` and `-`, at most 40 characters |
| NNN | the three-digit number in `IR-NNN` and `F-NNN` file names, e.g. `007` |
| token | a random secret made fresh each time the notebook starts; the page carries it, and every POST must send it (Constraint 8) |
| Host header | the address the browser says it is talking to; the notebook only answers `127.0.0.1:<port>` |
| route | one URL the notebook answers, e.g. `/`, with the function that answers it |
| loopback | `127.0.0.1`, an address only this computer can reach |
| nosniff / DENY | two response headers: the browser must not guess the content type, and no other site may show the page in a frame |
| CORS | headers that would let other sites read our responses; the notebook never sends them |
| task line | a checklist line exactly `- [ ] text` or `- [x] text`; it gets a checkbox |
| record | one checklist line as the view gets it: a task (with its key and tick) or a text line |
| task key | what a tick is saved under: the checklist's path, the exact task text, and which occurrence of that text it is (OQ-08) |
| tick state | `field-notes/<name>/checklist-state.json`: `{task key: true/false}`, the person's saved ticks |
| refused (file list) | a folder or file link in the person's own folders that points outside the root; listed with its reason, never opened |
| New form | the form behind the New button: Title, Type, and (for some types) a number and a library entry; the notebook builds the file name |
| findings library | `findings-library/`: ready-written findings a new Finding can start from; each entry starts `### [[FINDING_ID]]: <title>` |
| refused (scan) | the same idea for the library list and the ID scans: one bad entry or link is reported with its reason, and the rest still counts |

## Size

Measured after Chunk N3, the same way as at Chunk N1 (that method gives N2's 481/124/146/112 on the N2 file).

| Lines in `notebook.py` | Chunk N1 | Chunk N2 | Chunk N3 |
|---|---|---|---|
| code (the `APP_PAGE` included: 39, then 146, now 328 lines) | 190 | 481 | 946 |
| docstrings | 54 | 124 | 265 |
| comments | 77 | 146 | 238 |
| blank | 55 | 112 | 183 |
| **total** | **376** | **863** | **1632** |

**The size guideline is dropped (DECISIONS 2026-10-28 size, user A):** the notebook will always be bigger than about 700–800 lines, so size is no longer flagged. What matters is that every line can be explained (R4), which is what this file is for.

## 1. notebook.py

### Module docstring - lines 1-11
What the notebook is, how to run it, and what it never does.

**If Operations asks:** "It's the description at the top of the file. Each tester runs the notebook on their own box; it reads and writes the same Markdown files as the rest of the repo, never runs commands, and can only be served on 127.0.0.1."

### Imports - lines 13-25
Standard library only, plus `compile` (our own `compile.py`). Chunk N2 added `html` (escaping the token into the page), `tempfile` (the tick state's safe write) and `urllib.parse` (reading `?path=` from a URL).

**If Operations asks:** "Only Python's built-in modules. It imports our `compile.py` to reuse its folder and path checks and its Markdown reader, so there is one copy of those rules. `compile.py` never imports the notebook (OQ-13)."

**Why `compile` is imported this way:** the spec says the notebook calls `compile.py`'s functions by import, never by running it as a command (Constraint 3). `ModuleSafetyTests` pins this exact import list.

### `NOT_SLUG_RE` + `REPEATED_HYPHENS_RE` + `SLUG_MAX_LENGTH` + `slugify()` - lines 27-49
Turns a free-text title into a short, safe file-name part, e.g. `"Admin Panel!"` → `admin-panel`. Raises `ValueError` if nothing usable is left.

**If Operations asks:** "The user never types a file name. We build it from the title, and only letters, digits and hyphens survive, so a title can't contain `/` or `..` and save a file somewhere else."

| Step | Example: `" ../A  B!! "` |
|---|---|
| lowercase | `" ../a  b!! "` |
| every other run of characters → `-` | `"-a-b-"` |
| repeated `-` → one | `"-a-b-"` |
| cut to 40, then strip end `-` | `"a-b"` |

**Why cut before stripping:** a cut that lands just after a `-` would otherwise leave one at the end.

### `NNN_RE` + `validate_nnn()` - lines 52-66
Accepts exactly three ASCII digits, like `007`; anything else raises `ValueError`. It only checks the format; it never picks a number.

**If Operations asks:** "Incident and finding numbers are three digits. This rejects anything else before a file name is built from it."

**⚠️ Spec departure (decided: DECISIONS 2026-10-27 Chunk N1 D1, user A):** the original task line said `^\d{3}$`. That pattern also accepts `"123\n"` (a trailing newline matches `$`) and other scripts' digits such as Arabic-Indic `١٢٣`. The code uses `[0-9]{3}` with `fullmatch()` instead. The tests include both cases.

### `is_inside()` - lines 69-71
True if a path is a folder itself or anything below it.

**If Operations asks:** "A small helper for 'is this file inside that folder?', used by the write check below."

### `resolve_inside()` - lines 74-82
`compile.resolve_in_root()`, plus one more refusal: a path with a NUL byte raises the same `RootError`, naming the path, instead of Python's `ValueError` (Chunk N2 CR-2).

**If Operations asks:** "A hand-typed URL can carry a NUL byte (`%00`). It gets the same readable refusal as any other bad path, instead of the connection dropping and a traceback in your terminal."

### `readable_path()` + `readable_log_path()` - lines 85-99
A path the notebook may read: inside the working copy, or inside the log folder. Both go through `resolve_inside()`.

**If Operations asks:** "Every file we read goes through the same check as `compile.py`: `..` is refused, and so is anything that ends up outside the folder, even through a symlink. A symlink that stays inside is fine (OQ-17). The error names the path."

**Why there's no `writable_log_path()`:** logs are evidence. The notebook shows them but never changes them.

### `writable_path()` - lines 102-119
A path the notebook may write: inside the working copy, but not inside `incoming/` or the log folder. Since Chunk N2 the tick state's save uses it.

**If Operations asks:** "Writes have two extra refusals. `incoming/` holds teammates' copied files, and the log folder holds evidence, so neither is ever written."

**Why both folders are resolved first:** so a symlink can't reach them under another name. The tests try a link to `incoming/`, `incoming/` itself being a link, and the log folder being a link.

### `name_option()` - lines 122-128
Turns `--name` into a slug, e.g. `"Alice Smith"` → `alice-smith`; argparse prints a readable error for an unusable name.

**If Operations asks:** "Your name becomes your `field-notes/<name>/` folder, so it gets the same cleaning as a title: it can only ever be one plain folder name."

### `make_token()` - lines 131-135
A new random token for this run: `secrets.token_urlsafe(32)`, 43 characters.

**If Operations asks:** "Any web page open in the same browser can send requests to 127.0.0.1. Every POST must carry this secret, and other sites can't read our page to learn it."

Since N2-04, `send_page()` puts it in the page (the N1 carry-forward).

### `request_refusal()` - lines 138-159
Returns the 403 text, or `None` to allow the request. Every GET and POST needs exactly one `Host: 127.0.0.1:<port>`. A POST also needs exactly one `X-CPTC-Token` equal to the token.

**If Operations asks:** "This is the guard on every GET and POST, the only kinds of request with routes. A wrong Host stops DNS rebinding, where an attacker's domain is pointed at 127.0.0.1: the browser then sends that domain as the Host. A missing or wrong token stops other sites from changing files. A refusal says `refused: use http://127.0.0.1:<port>`."

| Check | Why |
|---|---|
| `get_all("Host")` is exactly one value | a second Host header can't sneak past |
| `localhost` and a Host without a port are refused | only the exact address counts |
| `secrets.compare_digest()` on bytes | its timing doesn't show how much of the token matched; bytes because it raises an error on non-ASCII text |

### `send_body()` - lines 162-178
The one place a response is sent. Every response gets its type and length, `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`, and never a CORS header (Constraint 9). A HEAD response gets the headers only, as HTTP requires.

**If Operations asks:** "Logs can contain hostile HTML, because we're attacking things. nosniff makes the browser trust our content type, so a `<script>` in a log sent as text never runs. DENY stops other sites framing our page. With no CORS header, other sites' scripts can't read our responses."

### `send_text()` + `send_json()` - lines 181-189
Plain text (`text/plain; charset=utf-8`) or JSON (`application/json`), both through `send_body()`.

**If Operations asks:** "Data is only ever sent as text or JSON. Only the app page itself is HTML, and only at `/`."

**Why JSON is ASCII:** `json.dumps()` escapes non-ASCII characters by default, so the body needs no charset.

### `send_page()` - lines 192-201
Sends the app page at `/`, with this run's token put in its `<meta name="cptc-token">` tag (N2-04, the N1 carry-forward).

**If Operations asks:** "The page's own script reads the token from the page and sends it with every save. Other sites can't read our page, so they can't learn it."

**Why `html.escape()`:** a real token only has letters, digits, `-` and `_`, so it can't end the attribute it sits in. Escaping makes sure of it anyway; a test feeds a hostile token to prove it runs.

### `CHECKLISTS_DIR` + `list_checklists()` - lines 204-221
The checklists: the `.md` files directly in `checklists/`, as `checklists/<file>.md`, sorted by name. A missing folder gives an empty list.

**If Operations asks:** "It lists the checklist files fresh each time; nothing is kept between requests."

**Why the folder is checked first:** if `checklists/` itself is a link pointing outside the working copy, it is refused before anything is listed, so not even the outside files' names show (N2-01 adversary round 1).

**Why one constant:** where checklists 10–60 will live is still an open board decision; moving them is a one-line change.

### `read_checklist()` - lines 224-239
One checklist's text, read from disk on every request. It must pass the shared path check and be one of the listed checklists. The text comes from `compile.read_markdown()`.

**If Operations asks:** "The checklists on disk are the one source of truth: change the file and the next load shows it. The notebook only ever reads them."

| Refused | Why |
|---|---|
| `..`, a full path outside, a link pointing outside | the shared path check, with the path named (OQ-13, OQ-17) |
| anything not in the list: `findings/...`, `checklists/old/x.md` | this route reads checklists and nothing else |
| not UTF-8 (e.g. saved as Windows-1252) | `compile.read_markdown()` raises a readable error naming the file |

**Limit:** a leading byte-order mark (the invisible marker some Windows editors add) is dropped, as in `compile.py`; Windows line endings are kept.

### `TASK_RE` + `FENCE_RE` - lines 242-249
`TASK_RE`: a task line exactly as the checklists write it, `- [ ] text` or `- [x] text`, from the start of the line. `FENCE_RE`: a Markdown code-block fence, up to three spaces then three or more `` ` `` or `~`.

**If Operations asks:** "Only the exact task form becomes a checkbox. Anything else, like `- [X]` or an indented task, shows as plain text."

### `task_key()` - lines 252-260
The key a tick is saved under: `json.dumps([path, text, occurrence])`, e.g. `["checklists/10-ad.md", "Run the scan", 2]`.

**If Operations asks:** "The checklist's path, the task's exact words, and which copy of those words it is (OQ-08). The same task in two checklists, or twice in one, gets its own tick."

**Why a JSON list:** no character in a path or task can blur where one part ends, and the result is a string, so it works as a key in the JSON state file.

### `checklist_records()` - lines 263-299
Splits a checklist into records, in order: `{"type": "task", "key", "text", "checked"}` for a task line, `{"type": "text", "text"}` for every other line. `"checked"` is the file's own mark (`[x]`).

**If Operations asks:** "Task lines get a key and a checkbox; every other line is shown exactly as written. The count for repeated tasks is kept per exact text, so editing one task never moves another task's tick."

| Rule | Why |
|---|---|
| split on `\n` only, drop a trailing `\r` | a file re-saved with Windows line endings keeps the same keys |
| inside a code block every line is text | a sample `- [ ] x` in a code block isn't a real task |
| a block ends only on the same character, at least as long, with nothing after it | Markdown's own rule, so ```` ``` ```` shown inside a ```` ```` ```` block doesn't end it (N2-02 adversary round 1) |
| four spaces before ```` ``` ```` is not a fence | in Markdown that is indented code |

**Decision (DECISIONS 2026-10-29 Chunk N2 D1, user A):** `- [x]` in a file starts ticked. Once ticked or unticked in the notebook, the saved state wins (see `task_checked()`). None of the real checklists has an `[x]` today.

**Limit:** editing a task's text, even one character, makes it a new task, so its tick resets. That is the spec's key rule (OQ-08).

### `StateError` + `state_path()` - lines 302-308
The error for a tick-state file that can't be used (its message names the file), and that file's path: `field-notes/<name>/checklist-state.json`.

**If Operations asks:** "Each person's ticks live in one small JSON file in their own field-notes folder."

### `refuse_linked_state()` - lines 311-323
Raises `RootError` naming the file if `field-notes/<name>/checklist-state.json` is itself a symlink. Load and save both call it, after their usual path check (Chunk N2 CR-1).

**If Operations asks:** "The notebook only reads and writes its tick file when it's a plain file. If someone had replaced it with a link, a save would go into whatever the link points to, like a teammate's ticks or a checklist; instead it's refused with a message naming the file."

**⚠️ Stricter than the usual rule (DECISIONS 2026-10-28 Chunk N2 CR-1, user A):** elsewhere a link that stays inside the root is fine (OQ-17). For this one file the notebook writes, a link is refused even inside the root, as `compile.py` does for its build files (C-21). `os.path.islink()` looks at the file only, so a linked `field-notes/<name>` folder is still allowed.

**Why after the usual check:** a link pointing outside the root still gets the usual "outside the root" message.

### `check_state()` - lines 326-340
The tick state must be `{text key: true/false}`. Anything else (a list, `"yes"`, `1`, a non-text key) raises `StateError`.

**If Operations asks:** "A tick is only ever true or false. Anything else is refused rather than guessed at, both when loading and before saving."

**Why `bool`, not "a number":** in Python `True` is also an integer, but `1` isn't a tick. **Why keys too:** a loaded file always has text keys, but a state about to be saved might not, and `json.dumps()` would quietly turn `1` into `"1"` (N2-03 adversary round 1).

### `load_checklist_state()` - lines 343-361
The saved ticks; `{}` if nothing is saved yet. Bad JSON, a file that isn't UTF-8, or the wrong shape raise `StateError` naming the file; a refused path or a linked state file raises `RootError`.

**If Operations asks:** "No file means nothing is ticked yet. A broken file gives a readable message naming it, instead of a crash."

### `save_checklist_state()` - lines 364-388
Writes the whole tick state: shape check, then `writable_path()` (inside the root, not `incoming/` or the log folder), then `refuse_linked_state()`, then a new temp file in the same folder, swapped into place with one `os.replace()`.

**If Operations asks:** "A save is all or nothing: a crash mid-save leaves the old file as it was, never half a file."

**Why `mkstemp`:** it only ever makes a brand-new file under a random name, so a link planted under the temp name can't be written through. If anything fails, the notebook removes its own temp file and the old state stays.

**Limit (kept by DECISIONS 2026-10-28 Chunk N2 CR-1):** if the folder `field-notes/<name>` is a link to another person's folder inside the root, the ticks are saved there. Only someone making a link by hand in a shell can cause this; the notebook never makes links.

### `task_checked()` - lines 391-396
What a task shows: its saved tick if there is one, otherwise the file's own mark.

**If Operations asks:** "Your tick wins. Until you tick or untick a task, it shows what the file says."

### `own_folders()` - lines 399-405
The two folders that hold a person's own files: `findings/` and `field-notes/<name>/`.

**If Operations asks:** "Your findings and your own notes. Teammates' copies in `incoming/` and the study `notes/` folder are never listed."

### `list_own_files()` - lines 408-439
The left column's file list: the `.md` files directly in the two own folders, as root-relative paths, sorted by filename so prefixes group (F-, INJ-, IR-, NOTE-, SU-) across both folders. It also returns a `refused` list.

**If Operations asks:** "Sorting by filename groups your findings, incident reports, notes and the rest together, whichever folder they're in."

| Case | Result |
|---|---|
| a folder missing | nothing listed from it, nothing created |
| a subfolder, a `.txt`, a folder named `x.md` | not listed |
| the same filename in both folders | both listed; the full path breaks the tie |
| a folder or file link that stays inside the root | listed under its own path |
| a folder or file link pointing outside the root | in `refused` with its reason; an outside folder is never looked into |

**Decision (N2-05 Q1 A; kept by DECISIONS 2026-10-29 Chunk N2 D3, user A):** one bad link never hides the person's other files mid-event; it stays visible with its reason. This differs from the checklists, where an outside checklist file is listed and refused only when opened. Since N3-05 the left column shows each `refused` message (`showFiles()`).

### `send_own_files()` - lines 442-446
`GET /files`: `{"files": [...], "refused": [...]}` as JSON.

**If Operations asks:** "The list the left column shows. It only reads; it never creates a folder."

### `send_checklist_list()` - lines 449-456
`GET /checklists`: `{"checklists": [...]}` as JSON, or a 403 naming `checklists` if that folder points outside the root.

**If Operations asks:** "The list the Checklists button shows."

### `checklist_from_query()` - lines 459-473
Shared by the two routes that open one checklist: reads `?path=`, then `read_checklist()`. On a problem it sends the error itself and returns `None`.

| Problem | Answer |
|---|---|
| no `path`, an empty one, or two | 400 `give one checklist: ?path=checklists/<file>.md` |
| refused path, or not a listed checklist | 403 `refused: ...` naming the path |
| a NUL byte (`%00`) in the path | 403 `refused: path can't be used (embedded null byte): ...` (Chunk N2 CR-2) |
| not UTF-8, or unreadable | 500 `can't read the checklist: ...` naming the file |

**If Operations asks:** "Each of these problems gives a readable plain-text message."

### `send_checklist()` - lines 476-480
`GET /checklist?path=...`: one checklist's Markdown as plain text.

**If Operations asks:** "The raw checklist, exactly as on disk (minus a leading byte-order mark)."

### `send_checklist_view()` - lines 483-506
`GET /checklist-view?path=...`: `{"path", "records", "state_error"}` as JSON, with each task's `"checked"` already worked out by `task_checked()`.

**If Operations asks:** "What the checklist page shows. If the saved ticks can't be read, the checklist still shows with the file's own marks, and the message above it says why."

### `MAX_TICK_BYTES` + `read_tick()` - lines 509-529
One tick from a POST body: exactly `{"key": text, "checked": true/false}`. A missing or non-numeric `Content-Length`, or one over 64 KiB, is refused before anything is read; any other body gives a 400.

**If Operations asks:** "The page sends one small tick at a time. Anything else, including a typo like `check` for `checked`, is refused rather than ignored."

### `save_tick()` - lines 532-551
`POST /checklist-state`: loads the saved ticks, sets the one key, saves them all. Success sends back `{"key", "checked"}`.

**If Operations asks:** "Ticking one box changes only that box's saved tick and keeps all the others."

| Problem | Answer |
|---|---|
| bad body | 400 (`read_tick()`) |
| the state path is refused (e.g. `field-notes/<name>` links outside, or the state file is a link) | 403 `refused: ...` |
| the saved ticks can't be read, or the save fails | 500 `tick not saved: ...`; the file is unchanged |

**Decision (DECISIONS 2026-10-29 Chunk N2 D2, user A):** a broken state file refuses the tick instead of being overwritten with just the new one, which would silently lose every earlier tick. Ticks stop saving until someone fixes or deletes the file; the notebook only writes it all at once, so a broken one means it was hand-edited.

**Limit:** the key isn't checked against a real checklist task. Only a request carrying the token can save one, so in practice only the page does.

### `NEW_FILE_TYPES` + `new_file_type()` - lines 554-609
The New file table: the five types the New form offers. Each has where its file is saved (a pattern filled in later), whether it needs a number, the template it starts from, and whether it may start from the findings library instead. `new_file_type()` returns a copy of one entry, or raises `ValueError` naming the five types.

**If Operations asks:** "It's the spec's New file table written as code. The folders are written here and never come from the browser, so a new file can only go in `field-notes/<name>/` or `findings/`."

| Type | Saved as | Number | Starts from |
|---|---|---|---|
| Note | `field-notes/{name}/NOTE-{slug}.md` | no | a blank file |
| Incident report | `field-notes/{name}/IR-{nnn}-{slug}.md` | yes | `templates/incident-report.md` |
| Status update | `field-notes/{name}/SU-{slug}.md` | no | `templates/status-update.md` |
| Inject response | `field-notes/{name}/INJ-{slug}.md` | no | `templates/inject-response.md` |
| Finding | `findings/F-{nnn}-{slug}.md` | yes | `templates/finding.md`, or a library entry |

**Why exact labels only:** `note`, ` Note` or a list sent in a JSON body are refused, so the form's own labels are the only type names. **Why a copy:** a caller that changes the entry can't change the table for later requests.

### `LIBRARY_DIR` + `LIBRARY_HEADING` + `HEADING_LINE_RE` + `library_paths()` - lines 612-637
The names directly in `findings-library/` that end `.md`, never its `README.md`, as root-relative paths, sorted. A missing folder gives an empty list. `HEADING_LINE_RE` is a Markdown heading: `#` characters, then a space or tab, so `#1 priority` is prose.

**If Operations asks:** "The findings library is ready-written findings a new Finding can start from. This lists them fresh each time from disk, with no built-in list."

**Why no `is_file()` here (N3-02 adversary round 1):** `is_file()` follows a link, so calling it before the path check would look through a link to somewhere outside the working copy. Each name is checked before anything looks inside it (`list_library()`, `read_library_entry()`). If `findings-library/` itself links outside, `library_paths()` raises before listing anything, so even the outside names stay hidden; `list_library()` turns that into one refusal (Chunk N3 D1).

### `read_library_entry()` - lines 640-654
One library entry's text, read from disk now. The shared path check first (`..`, a path outside, a NUL byte, a link pointing outside), then it must be on the list and be a file, then `compile.read_markdown()`.

**If Operations asks:** "The New form can only start from a real library entry. Any other path, even another file in the working copy, is refused with the path named."

### `without_cr()` + `library_heading_index()` + `library_title()` - lines 657-691
`library_heading_index()` finds the entry's first heading. It must start with exactly `### [[FINDING_ID]]: `; otherwise, or with no heading at all, it raises `ValueError` naming the file. `library_title()` returns the rest of that line as written: the title the New form's Title box starts with (OQ-03). `without_cr()` drops a Windows line ending's `\r`.

**If Operations asks:** "Every library entry starts like the finding template, `### [[FINDING_ID]]: <title>`. We read the title from there, so adding an entry needs no code change."

| First heading | Result |
|---|---|
| `### [[FINDING_ID]]: SMB signing not required` | title `SMB signing not required` |
| `### [[FINDING_ID]]: [[FINDING_TITLE]]` (a raw template copy) | title `[[FINDING_TITLE]]`, as written |
| `### F-001: ...`, `## [[FINDING_ID]]: ...`, `###  [[FINDING_ID]]: ...` | refused, naming the file and the line |
| no heading | refused, naming the file |

**Decision (DECISIONS 2026-10-29 Chunk N3 D3, user A):** an entry copied straight from the template puts the literal text `[[FINDING_TITLE]]` in the Title box, as the spec's rule gives. The new file keeps the marker, and compile reports it as a leftover marker.

**Limit:** code blocks aren't tracked, so a `#` line inside one before the real heading would count as the first heading. Real entries put the heading on line 1.

### `list_library()` - lines 694-725
`(entries, refused)` for the New form: `{"path", "title"}` for each usable entry, and one reason per entry that can't be offered (a link pointing outside, not UTF-8, the wrong first heading, unreadable).

**If Operations asks:** "One broken library entry never hides the others in the middle of the event. It shows with its reason instead."

**Decision (App Dev Manager's N3-02 ruling, following DECISIONS 2026-10-29 Chunk N2 D3; then DECISIONS 2026-10-29 Chunk N3 D1, user A):** one bad entry is refused with its reason and the others still list. Since D1, `findings-library/` itself linked outside is also just one refusal, with nothing listed, so the New form still opens for every type. (`library_paths()` still raises for it, so a create can't read an entry through the link.)

### `checked_folder()` + `subfolders()` + `matching_files()` - lines 728-771
Three small helpers for the ID scans. `checked_folder()` is the path check, then `is_dir()`. `subfolders()` lists the folders directly in a checked folder, sorted. `matching_files()` lists the `.md` files directly in a folder whose name matches a pattern, sorted. A link pointing outside goes in `refused` with its reason; the rest is still scanned.

**If Operations asks:** "Every folder and file is checked before anything looks inside it or follows it, and a bad link is reported, not followed."

**Why not compile.py's helpers:** `compile.finding_folders()` and `child_folders()` raise on the first outside link, which stops the whole scan. The notebook keeps going and reports each link (App Dev Manager's N3-03 ruling, following Chunk N2 D3).

### `finding_id_folders()` + `ir_folders()` - lines 774-806
Where the scans look: findings in `findings/` and each `incoming/<owner>/findings/`; IR files in every `field-notes/<name>/` and every `incoming/<owner>/field-notes/<name>/`. These are the same places `compile.py` reads, and what `scripts/pull.sh` copies. A link pointing outside, even a top-level `findings/`, `incoming/` or `field-notes/`, goes in `refused` and the rest is still scanned (DECISIONS 2026-10-29 Chunk N3 D1, user A).

**If Operations asks:** "The notebook looks at the whole team's copies, not only yours, because a duplicate ID or the next IR number is a team-wide question. No person's name is written into the code."

### `finding_id_warnings()` - lines 809-832
`(warnings, refused)` for a new finding numbered NNN: one line per existing file with that ID, e.g. `F-007 already exists: findings/F-007-old.md`. Raises `ValueError` for a bad number.

**If Operations asks:** "It warns and never blocks: ID allocation is the team's rule (R6), so the person decides."

**Why compile.py's `FILENAME_ID_RE`:** the notebook warns about exactly the IDs that compile's duplicate check will later report. `F-007-x.md` and `F-007.md` match; `F-0070`, `F-007x` and `F-007_a` don't.

**Why `refused.sort()`:** a refused file link is found in the order the disk lists files, which differs between the Mac and Kali. (Removed once as dead code in N3-03, then restored when the adversary showed two file links coming back in disk order.)

### `IR_NUMBER_RE` + `NO_IR_NUMBER_LEFT` + `suggest_ir_number()` - lines 835-862
`(suggestion, refused)`: the highest IR number in use, across your and your teammates' field notes, plus one; `"001"` if there are none; `None` if IR-999 is in use, when the form shows `NO_IR_NUMBER_LEFT`. Nothing is reserved or written (OQ-07).

**If Operations asks:** "It only suggests. You can type any three-digit number instead, and the notebook never picks one for you."

| Files | Suggestion |
|---|---|
| none | `001` |
| `IR-001-a.md`, `incoming/bob/.../IR-004-b.md` | `005` |
| `IR-009-a.md`, `IR-010-b.md` | `011` (the numeric maximum) |
| `IR-999-z.md` | `None`: "IR-999 is in use, so there is no next three-digit IR number to suggest: type one in." |
| `IR-01-a.md`, `IR-1000-a.md`, `IR-abc.md`, `ir-009-a.md` | ignored |

A typed IR number that's already in use is warned about by `ir_number_warnings()` (below).

### `ir_number_warnings()` - lines 865-888
`(warnings, refused)` for a new incident report numbered NNN: one line per existing IR file with that number, in any `field-notes/<name>/` or `incoming/<owner>/field-notes/<name>/`, e.g. `IR-007 already exists: field-notes/alice/IR-007-old.md`. Raises `ValueError` for a bad number. It scans the same files `suggest_ir_number()` counts.

**If Operations asks:** "Like the finding warning, it only warns: the file is still created. It catches two people, or two incidents in a row, ending up with the same IR number."

**⚠️ Spec departure (decided: DECISIONS 2026-10-29 Chunk N3 D2, user A):** the spec asks for a duplicate warning on finding IDs only. `compile.py` doesn't catch a duplicate IR ID either, so without this nothing would. `IR-007.md` and `IR-007-x.md` match `007`; `IR-0070`, `IR-007x`, `IR-007_x` and `ir-007` don't.

### `NEW_FILE_MARKER_RE` + `fill_new_file_markers()` - lines 891-905
Fills the three markers New fills in (`templates/README.md`): `[[FINDING_ID]]` → `F-NNN`, `[[IR_ID]]` → `IR-NNN`, `[[FINDING_TITLE]]` → the title. Only these exact names: `[[FINDING_ID_EXTRA]]` or `[[PREVIOUS_FINDING_ID]]` stay as they are.

**If Operations asks:** "The new file starts with its ID and title already filled in. Every other marker is left for the person to fill."

**Why one regex pass:** a value put in is never scanned again. Filling the title first and then the ID would also replace a `[[FINDING_ID]]` the person typed in their title.

### `checked_new_number()` - lines 908-923
The number for this type: none for a Note, Status update or Inject response (a number sent anyway is refused, not ignored), and for an Incident report or Finding text that passes `validate_nnn()`.

**If Operations asks:** "Only the number the person typed is used. The suggested IR number is never filled in behind their back."

**Why the text check first:** `validate_nnn(None)` would raise `TypeError`; a JSON body's `null`, number or list gets the same readable error as a wrong number.

### `read_template()` - lines 926-936
A template's text: the shared path check, then it must be a file, then `compile.read_markdown()` (a byte-order mark dropped, Windows line endings kept, a non-UTF-8 file refused naming it).

**If Operations asks:** "The templates in the working copy are the source. Change one, and the next new file uses the new version."

### `new_file_text()` - lines 939-968
The new file's text: the template, or the chosen library entry, with the markers filled. A library entry is allowed only for a Finding. For a library entry, every line's markers are filled, then the first heading is set to `### F-NNN: ` plus the title as typed, keeping that line's own `\r`.

**If Operations asks:** "An unchanged library title gives the same heading; an edited one replaces only the text after `### [[FINDING_ID]]: ` (OQ-03). Nothing else in the entry changes."

**Decision (spec over adversary case 8, adversary agreed):** a library finding also gets `[[FINDING_TITLE]]` filled, because the spec says the new file has it filled whatever it starts from.

### `check_new_file_path()` - lines 971-995
Checks the path before anything is made: `writable_path()` (inside the root, not `incoming/` or the log folder, through any linked folder), each folder on the way really a folder, and nothing at all at the name.

**If Operations asks:** "A new file never replaces anything and never writes through a link. A refused create changes nothing on disk."

| At `field-notes/alice/NOTE-x.md` already | Result |
|---|---|
| a file, a folder, a hard-linked file | refused: already exists |
| a link (inside, outside, or broken) | refused: already exists |
| `field-notes/alice` is a file or broken link | refused: not a folder |
| `field-notes/alice` links outside, into `incoming/` or the log folder | refused by `writable_path()` |

**Why `os.path.lexists()`:** it doesn't follow the last part of the path, so it sees a link or a broken link itself. `exists()` would call a broken link "not there". This is the Chunk N2 CR-1 rule (a notebook-written file that is a link is refused) applied to new files.

### `create_new_file()` - lines 998-1044
The New form's one write: type, title (one line) and slug, number, text, path checks, and the duplicate-number warnings for a Finding or an Incident report; then the folders and the file. Returns `(path, warnings, refused)`.

**If Operations asks:** "Everything is checked first. Only then are folders made and the file created, in a mode that refuses if anything appeared at that name in the meantime."

**Why open mode `"x"`:** it creates the file only if nothing is there, as part of the open itself (it also refuses a link planted at the name). A file that appeared after the checks is never overwritten. **Why `newline=""`:** the template's own line endings are written unchanged. **If the write fails,** the notebook removes its own half-made file.

**Limit:** the folder checks and the folder creation are not one step, so a folder swapped for a link in between isn't caught. The file's own name is still protected by `"x"`. The same kind of limit as compile's `build/` checks (C-21).

**Why a title with a line break is refused (DECISIONS 2026-10-29 Chunk N3 D5, user A):** a title goes in exactly as typed, so a line break would start a new line in the file. A hand-made request could add a second `- **Severity:**` line that `compile.py` would then read. The check runs before anything is read or scanned, and the message doesn't repeat the title. Tabs and a typed backslash-n are fine.

### `send_new_data()` - lines 1047-1073
`GET /new-data`: what the New form needs, as JSON: `types` (each with `name`, `needs_nnn`, `library`, in the table's order), `library`, `library_refused`, `ir_suggestion`, `ir_note`, `ir_refused`. A folder linked outside, even a top-level one, is one of the refused reasons, so the form still opens unless a folder can't be read (500).

**If Operations asks:** "The page builds its Type list from this, so the list of types lives in one place in the code."

**Decision (DECISIONS 2026-10-29 Chunk N3 D1, user A; Chunk N3 CR-2):** before this, a top-level `findings-library/`, `field-notes/` or `incoming/` linked outside made this route answer 403, so no file of any type could be made. Now each goes in its own refused list (`library_refused`, `ir_refused`), and a Finding create with `incoming/` linked outside is still created, with the link in `refused`. Only a link made by hand causes this: `make-workcopy.sh` makes real folders and `pull.sh` refuses a linked `incoming/`.

### `MAX_NEW_FILE_BYTES` + `NEW_FILE_FIELDS` + `read_new_file_request()` - lines 1076-1107
The create request's body: exactly `{"type", "title", "nnn", "library"}`, with type and title as text and nnn and library as text or `null`. A missing, non-numeric or over-64-KiB `Content-Length`, a body that isn't UTF-8 JSON, or any other shape gives a 400.

**If Operations asks:** "There's no field for a file name or path. A request with one, or with any extra field, is refused rather than ignored."

**Why `OSError` too:** a body shorter than its `Content-Length` times out (see `NotebookHandler`), and that is answered with the same 400.

### `save_new_file()` - lines 1110-1131
`POST /new-file`: passes the fields to `create_new_file()` as sent and answers `{"path", "warnings", "refused"}`.

| Problem | Answer |
|---|---|
| bad body | 400 (`read_new_file_request()`) |
| a bad value (`ValueError`): unknown type, empty slug, a title with a line break (D5), bad number, a number or library entry the type doesn't use | 400 `not created: ...` |
| a refused path (`RootError`), including "already exists" | 403 `refused: ...` |
| an unreadable or non-UTF-8 template (`InputError`, `OSError`) | 500 `not created: ...` |

**If Operations asks:** "Each problem comes back as a readable message saying why, and nothing is created."

### `TOKEN_SLOT` + `APP_PAGE` - lines 1134-1469
The one HTML page. The left column has the "Light / dark" button, the person's own files, a "New" button and a "Checklists" button; the main pane shows what was picked. Inline CSS and JS only. `send_page()` replaces `TOKEN_SLOT` with this run's token.

**If Operations asks:** "Black on white, or white on black when your system is in dark mode; the button swaps them. The left column lists your own files. New opens a form to make a file from a template; Checklists lists the checklists, and picking one shows each task as a checkbox. There are no outside files or fonts, so it works with no internet."

| Part | Lines | What it does |
|---|---|---|
| `<meta name="cptc-token">` | 1146 | carries this run's token for the script |
| `:root` and `@media (prefers-color-scheme: dark)` | 1149-1155 | follow the system's light or dark setting; the button's choice wins |
| `body`, `.columns`, `nav`, `main`, buttons, `label input`, `pre` | 1156-1163 | spacing only; one `<pre>` per text line, and an empty line still takes up a line |
| `#file-list div`, `#file-list .selected`, `form div` | 1164-1168 | the file list's spacing, long paths wrap; the file just created in bold; form row spacing |
| `<nav>` | 1173-1178 | theme button, `div#file-list`, New, Checklists |
| theme toggle | 1182-1189 | sets `data-theme` to the opposite of what shows now |
| `element()` | 1194-1201 | makes an element and sets its text with `textContent` |
| `showMessage()`, `getJson()` | 1203-1216 | fetch a JSON route; an error shows the server's text |
| `showChecklistList()` | 1218-1232 | one button per checklist |
| `showChecklist()` | 1234-1256 | each task a `label` holding an `input type=checkbox` and a `span`; each other line a `<pre>`; a status line for problems |
| `saveTick()` | 1258-1286 | POSTs `{key, checked}` with `X-CPTC-Token`; the box is locked until the answer; if not saved, it goes back to its value from before the click and the reason shows |
| `showFiles()` | 1288-1305 | each `/files` path as a line, in the order given (grouped by prefix); the selected one in bold; each refused reason as `Not listed: ...` |
| `loadFiles()` | 1307-1320 | fetches `/files`; an error shows its text in the list |
| `addField()` | 1322-1328 | one labelled control in its own row |
| `showNewForm()` | 1330-1455 | the New form (below), with `refreshSuggestion()` |
| New button | 1457-1459 | loads `/new-data`, then the form; an error shows the route's text instead |
| Checklists button | 1461-1463 | loads the list |
| `loadFiles();` | 1465 | the file list loads when the page opens |

**The New form (`showNewForm()`):**
- **Title:** a one-line text box, so a title can't split the heading it goes into.
- **Type:** built from `/new-data`'s `types`. The Number row shows only for a type with `needs_nnn`, the library row only for one with `library`.
- **Number:** an incident report starts with the suggested number, or empty with the "no number left" note; a finding starts empty (R6). Each IR-scan refusal shows under it.
- **Start from:** `templates/finding.md`, or a library entry shown as "title (path)". Picking one puts its title in the Title box (OQ-03). Each library refusal shows under it.
- **Create:** sends exactly `{type, title, nnn, library}`, with `nnn` only when the type needs one and `library` only for a Finding with an entry picked; a hidden field's old value is never sent. The button is locked until the answer. Success shows `Created <path>`, each `Warning: ...` and each `Not checked for duplicates: ...`, then reloads the file list with the new file selected. For an incident report it also asks `/new-data` for the next suggested number (`refreshSuggestion()`, Chunk N3 CR-1), so two incident reports in a row don't both get the same one; if that fails, the box is emptied with the reason, never left at a number that may be taken. A failure shows the server's text and keeps the form as typed.

There's no file name or path field anywhere: the notebook builds the name.

**Why `textContent` everywhere, never `innerHTML`:** file names, titles, checklist text and refusal reasons (even `<script>`) only ever show as text; they can never become part of the page.

**Why the box is locked while saving (N2-04 adversary round 1):** if a quick second click could change the box before the first save answered, a failed first save would flip the newer value and show the opposite of what's saved. The Create button is locked for the same reason, so one click makes at most one file.

**⚠️ Spec departure (decided: DECISIONS 2026-10-29 Chunk N3 D4, user A):** the file just created is shown in bold (`font-weight`). The spec says "no styling beyond spacing"; the selection needs to be visible, and bold was kept.

**Limit:** a file in the list can't be opened yet; that comes with the fill-in view (N4).

**Limit:** no unit test runs the script (Python has no built-in browser); the tests check the served page's text. At N2-04 and again at N3-05 the script was run in Node against a real notebook on 127.0.0.1, with a fake page whose `innerHTML`, `outerHTML` and `insertAdjacentHTML` raise an error. At N3-05 all 25 checks passed, and after Chunk N3 CR-1 all 32: the file list, its refusals, a `<script>` file name shown as text, the five type options in order, which fields show for each type, the library title filling the Title box, create and the list reloading with the new file selected, a failed create keeping the form, an old number not sent after switching type, two incident reports in a row getting 005 then 006 (and an emptied box when the refresh fails), the IR-999 note, and Checklists and the theme toggle still working afterwards. That run is not a repo test. The layout, light and dark mode, real clicking and keyboard use, and real browser form behaviour are for the manual browser check (D-04). The theme button's choice still isn't remembered after a reload.

### `GET_ROUTES` + `POST_ROUTES` - lines 1471-1480
Which function answers which URL. GET: `/`, `/checklists`, `/checklist`, `/checklist-view`, `/files`, `/new-data`. POST: `/checklist-state`, `/new-file`.

**If Operations asks:** "A list of the URLs the notebook answers. GET routes never change anything; the two routes that save are POSTs, and every POST needs the token."

### `NotebookHandler` - lines 1483-1528
Answers each GET and POST: the guard first, then the route. Any other method gets the server's 501.

| Part | Lines | What it does |
|---|---|---|
| `timeout = 10` | 1486-1489 | a connection waiting longer than 10 seconds for more of its request is closed (N3-05) |
| `do_GET()` / `do_POST()` | 1491-1495 | send GET and POST through `answer()` with their routes |
| `answer()` | 1497-1514 | closes the connection after this one request; the guard runs before the body is read or any route runs, so a refused POST changes nothing; then the route is found by the path without its `?query` (Chunk N2); 404 for an unknown path |
| `send_error()` | 1516-1525 | the server's own errors (e.g. 501 for any other method, 431 for too many headers) go out as text with the safety headers instead of as an HTML page, and close the connection |
| `log_message()` | 1527-1528 | prints nothing per request, so the terminal stays readable |

**If Operations asks:** "Every GET and POST goes through the guard before any route runs. Any other method, like PUT, gets a plain 'not implemented' (501) and nothing runs. Each connection carries only one request."

**Why other methods get a plain 501 (DECISIONS 2026-10-27 Chunk N1 D3, user B):** only GET and POST have routes. Python's server answers any other method with 501 itself, through our `send_error()`, so it never reaches a route whatever its Host. An earlier version sent those methods through the guard too, which the user judged too clever for a case where both versions are safe.

**Why one request per connection (Chunk N1 CR-1):** a refused request's body is never read. If the connection stayed open (HTTP/1.1 keeps it open), the server would read that body as a second request, and a body holding a whole request with the right Host would pass the guard. Python's default (HTTP/1.0) already closes the connection, but `answer()` and `send_error()` set `close_connection` themselves, so a later change to the protocol version can't open that gap. `send_error()` needs it too: Python's own version closes the connection, and ours replaces it.

**Why a timeout (N3-05, adversary case 7):** the server answers one request at a time. Without it (Python's default is no limit), a request whose body is shorter than its `Content-Length` would hold the whole notebook forever. It covers the tick route too.

**Limit:** the server's own errors (400 for a bad request line, 414 for a too-long URL, 431 for too many headers, 501 for another method) are answered without the guard; no route runs and nothing changes. A request whose first line it can't parse at all gets an old-style answer with no headers, only the error text. A browser can't send such a request.

### `parse_args()` - lines 1531-1553
`--name` (required), `--root` (default `~/cptc-work`), `--port` (default 8765). There is deliberately no option for the address.

**If Operations asks:** "There's no setting that could open the notebook to the network: it's always 127.0.0.1. The root defaults to the working copy, never the current folder, for the same reason as `compile.py`."

### `port_option()` - lines 1556-1562
`--port` must be 1–65535, written in ASCII digits; otherwise argparse prints a readable error.

**If Operations asks:** "A bad port gives a clear message instead of a crash."

### `log_dir()` - lines 1565-1570
`$LOGDIR`, or `~/cptc-logs` if it isn't set or is empty.

**If Operations asks:** "The same rule as our logging script, so the notebook looks where the logs were written."

### `load_settings()` - lines 1573-1586
Reads the options and checks the root with `compile.validate_root()`: it must exist, be a folder and have no `.git`.

**If Operations asks:** "The folder check runs before the server exists, so the notebook refuses to start in a folder that has its own `.git`, like our git clone."

### `make_server()` - lines 1589-1598
Creates the server on the literal `("127.0.0.1", port)`, with a new token and the settings.

**If Operations asks:** "Literally 127.0.0.1: not empty or `0.0.0.0`, which would mean every network interface, and not `localhost`, a name the system looks up. Other boxes on the network can't reach it."

### `main()` + `if __name__ == "__main__"` - lines 1601-1632
Root check, then the server. Prints `Notebook: http://127.0.0.1:<port>` and a local-only reminder, then serves until Ctrl+C.

**If Operations asks:** "If the folder is refused or the port is taken, it prints one readable line and exits with code 2. Ctrl+C stops it cleanly with exit code 0, and the server is always closed."

| Exit code | When |
|---|---|
| 0 | stopped with Ctrl+C |
| 2 | the root is refused (e.g. it has `.git`) or the port can't be used |

## 2. Test helpers: tests/support.py

Shared with `compile.py`'s tests. See [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy). The notebook tests use `make_worktree()` for every fake folder and `write_fake_file()` for files added during a test.

## 3. Tests

### tests/test_notebook.py

#### Imports - lines 1-20
`support` is imported first so `notebook` and `compile` can be found. `ast` reads `notebook.py`'s source for `ModuleSafetyTests`. `os` reads links and folders for `tree()` and makes a hard link; `string` reads a path pattern's slots (Chunk N3). `http.client`, `socket`, `threading` and `HTTPServer` are for the tests that run a real server on 127.0.0.1; `HTMLParser` reads the app page; `quote` builds `?path=` URLs.

**If Operations asks:** "Standard library only, like the tools."

#### `StartupTests` - lines 23-51
- a root with `.git` exits with code 2 and the message; no server is created (`HTTPServer` patched and checked) and no file is created
- `--host`, `--bind`, `--address` and `--listen` don't exist
- `--port` refuses `0`, `65536`, `-1`, `abc` and an Arabic-Indic digit; accepts `9000`

**If Operations asks:** "Starting in the git clone is refused before anything happens, and there's no option to open the notebook to the network."

#### `ServeTests` - lines 54-108
- `main()` with a fake server: it is created with exactly `("127.0.0.1", 9123)`, gets a 43+ character token and the settings, the URL and "Local only" are printed, and the server is closed
- a real server listens on `127.0.0.1` with our handler, and each server gets its own token
- a port already in use gives exit code 2 and a readable message (the test can't hang, even if the code broke)
- the page contains no `http` or `//`, so it needs no outside file

**If Operations asks:** "These prove the notebook only listens on this computer and tells you the right address."

#### `ModuleSafetyTests` - lines 111-140
Constraint 3, tested the same way as `compile.py`'s (DECISIONS 2026-10-27 Chunk N1 D2, user A). Both tests read `notebook.py`'s source with `ast`, without running it.
- the imports are exactly `argparse`, `html`, `json`, `os`, `re`, `secrets`, `sys`, `tempfile`, `http.server`, `pathlib`, `urllib.parse` and `compile` (`os` for `$LOGDIR` and the tick state's safe write)
- no name `subprocess`, `system`, `popen`, `Popen`, `exec` or `eval` appears anywhere, imported names included

**If Operations asks:** "A test checks that the notebook imports only a fixed list of modules and never names subprocess, system, popen, Popen, exec or eval. That catches the usual ways to run a command; the rest is code review."

**Limit (Chunk N1 CR-4):** the names test is a fixed list. A call such as `os.execvp()` would pass both tests, because `os` is allowed and `execvp` isn't on the list.

**Why imported names too:** `from os import popen` imports module `os`, which is allowed, so the import test alone misses it. `compile.py`'s matching test doesn't collect imported names; there `os` isn't allowed at all, so the import test catches it.

#### `SlugifyTests` - lines 143-158
- the spec's example `" ../A  B!! "` gives `a-b`
- end and repeated hyphens disappear
- at most 40 characters, with no hyphen left at the cut
- punctuation only is refused

**If Operations asks:** "Every way a title could produce a bad file name is turned into a safe one, or refused."

#### `ValidateNnnTests` - lines 161-170
- `000` and `999` pass
- `1`, `01`, `1000`, `abc`, `"123\n"` and Arabic-Indic digits fail

**If Operations asks:** "Only exactly three ordinary digits are accepted."

#### `NameOptionTests` - lines 173-179
- `"Alice Smith"` becomes `alice-smith`
- `"../"` is refused with an argparse error

**If Operations asks:** "Your name is cleaned like a title, and a name that can't be cleaned is refused."

#### `PathWrapperTests` - lines 182-278
`setUp` builds a root with `findings/` and `incoming/bob/`, a log folder, and an "outside" folder, all in `.tmp/`. Every refusal checks the path is named in the error.

| Allowed | Refused |
|---|---|
| read and write `findings/F-001-x.md` | write a log, whether the log folder is outside or inside the root |
| read a log | write in `incoming/` (read is allowed) |
| read `incoming/bob/...` | write through a link into `incoming/`, or where a linked `incoming/` really points |
| read and write through a symlink that stays inside the root | write where a linked log folder really points |
| | `../x.md`, a full path outside, a symlink that leads outside |
| | a path with a NUL byte, for reading, reading a log and writing, one test each (Chunk N2 CR-2) |

**If Operations asks:** "We tried every way to read or write outside the allowed folders, including symlink tricks. Each is refused and the error names the path."

#### `file_bytes()` - lines 281-284
Every file under a folder as `{path: bytes}`, compared before and after to prove nothing changed.

#### `ServerTestCase` - lines 287-363
The shared setup for the server tests; it has no tests of its own. Each test gets a real server on `127.0.0.1` with a free port, in a thread, shut down and closed when the test ends.

| Helper | What it does |
|---|---|
| `setUp()` | adds two fake routes: `/test-read` (GET) and `/test-write` (POST, which changes a file); gives the server settings like a real run (resolved root, name `alice`, a log folder) so the real routes work |
| `send_full()` / `send()` | send one request with exactly the given Host (or several) and token |
| `assert_refused()` | 403 with the refusal text, no route ran, no file changed |
| `good_host()` | `127.0.0.1:<port>` |
| `assert_safe_headers()` | nosniff, DENY and no CORS header (moved here from `ResponseHeaderTests` in Chunk N2 so every server test can use it) |

**Why fake routes:** they keep the guard tests independent of any feature: a fake POST that changes a file proves a refused POST changes nothing.

#### `RequestGuardTests` - lines 366-476
- refused (403, nothing ran, nothing changed): a wrong Host, `localhost`, a Host without a port, a second Host header, a wrong Host even with the right token, a POST with no token, a wrong token, a non-ASCII token
- the exact Host GET and the exact Host plus token POST both work
- PUT, OPTIONS, HEAD and a made-up `BREW` get a plain-text 501 with nosniff and DENY, with either Host; no route runs and nothing changes (Chunk N1 D3)
- the HEAD 501, read from a raw socket, has nothing after its headers
- a refused POST whose body is a whole GET with the right Host gets one 403 and nothing else, even with the server switched to HTTP/1.1 (Chunk N1 CR-1)
- the same for PUT, OPTIONS, HEAD and `BREW`: one 501 and nothing else, so their connections close too
- tokens differ each run and are at least 43 characters

**If Operations asks:** "Requests from other sites, or through a wrong address, are refused before anything happens. Methods we don't use get a plain 501, and nothing runs."

**Helper:** `send_with_smuggled_get()` sends one raw request with a wrong Host whose body is a whole GET with the right Host, on a server switched to HTTP/1.1, and returns everything that comes back.

#### `ResponseHeaderTests` - lines 479-549
- every real route: only `/` is HTML, everything else is JSON or plain text, and all have nosniff and DENY (since Chunk N2 this includes the five checklist and file routes, and since Chunk N3 `/new-data` and `/new-file`, sent with no `?path=` and an empty POST body)
- JSON and plain text come out with the right types; a log with `<script>` in it comes back as plain text
- 403, 404 and 501 responses are plain text with the headers
- the server's own 431 error (101 headers) is plain text with the headers and no CORS

**If Operations asks:** "Nothing but our own page is ever sent as HTML, so a hostile log can't run as part of the page. The test checks every route automatically, including ones added later."

#### `ChecklistTests` - lines 552-707
N2-01, through the real routes `/checklists` and `/checklist`. Every response is checked for its type and nosniff/DENY/no CORS.
- two checklists written in reverse order list sorted; a missing folder lists `[]`
- only `.md` files directly in `checklists/`: not a `.txt`, a subfolder's file, or a folder named `folder.md`
- a listed checklist reads back exactly (Windows line endings and `<script>` included); an edit on disk shows on the next read; listing and reading change no bytes
- a link to a checklist inside the root is read, and read live; a linked `checklists/` folder inside the root lists and reads
- refused with the path named, and no outside text: a `checklists/` folder linked outside (its file names don't show either), a checklist linked outside, `..`, a full path outside, a subfolder checklist, a finding
- no `path`, an empty one, or two: 400
- a NUL byte (`%00`) in the path, on `/checklist` and `/checklist-view`: a plain-text 403, not a dropped connection (Chunk N2 CR-2)
- a byte-order mark is dropped and Windows line endings are kept; a Windows-1252 file gives a readable 500

**If Operations asks:** "Checklists are always read fresh from disk and only ever read. Tricks to read other files through this route are refused."

#### `ChecklistRecordTests` - lines 710-818
N2-02, `checklist_records()` directly.
- `- [ ] text` and `- [x] text` give the exact record and key
- repeated text gets occurrence 1, 2, ... even with other lines between; each text counts on its own; the same text in two checklists gets two keys
- a task keeps its key when other lines change; an edit (a full stop, a space, a capital) gives a new key and starts unticked
- headings, blank lines, prose, quotes, tables and plain bullets stay text, in order
- code blocks: ```` ``` ```` and `~~~` blocks hide task lines; a shorter fence, or one with text after it, doesn't end a block; four spaces don't start one
- near misses stay text: indented, `* [ ]`, `- [X]`, `- []`, no space after `]`, no text, `- [y]`
- Windows line endings give the same records; reading and parsing change no bytes

**If Operations asks:** "Only real task lines become checkboxes, and each keeps its tick as long as its words stay the same."

#### `ChecklistStateTests` - lines 821-981
N2-03, the load and save functions directly.
- nothing saved yet is `{}`; the first save makes the folders and writes only the state file (no temp file left)
- ticks and unticks survive a reload
- a saved tick wins over the file mark both ways; an unsaved task shows the file mark; an edited task doesn't keep the old tick
- broken JSON, a non-UTF-8 file and wrong shapes (`[]`, `"ticks"`, `null`, `1`, `"true"`, `null` values) are readable errors naming the file
- a wrong shape (including keys `1`, `True`, `None`) is never saved, and never replaces a saved state
- links: a linked `field-notes/alice` inside the root is used; refused, one test each, with the root and the outside folder unchanged: the folder linked outside, the state file linked outside, the state file linked to bob's state file inside the root (load and save, Chunk N2 CR-1), the folder linked into `incoming/`, the folder linked into the log folder
- a save that fails at the last step (`os.replace` patched to fail) keeps the old state and leaves no temp file
- loading and saving change no checklist bytes

**If Operations asks:** "Your ticks are saved all at once, never into `incoming/`, the log folder or outside the working copy, and a broken file is reported, never guessed at."

#### `ChecklistViewTests` - lines 984-1153
N2-04, through the real routes `/checklist-view` and `/checklist-state`. Every POST response is checked for JSON or plain text with nosniff/DENY/no CORS.
- the view lists every record in order as JSON data, a `<script>` line included as text; its errors (400, 403) are plain text
- saved ticks win over the file marks
- a tick changes one key and keeps the rest (another checklist's key included); ticking and unticking leave the checklist unchanged
- a POST with the token read from the served page succeeds (the N1 carry-forward)
- refused with 403 and every byte unchanged: no token, a wrong token, the token twice, a wrong Host
- refused with 400 and nothing changed: broken JSON, a non-object, a missing or extra field, a key that isn't text, a `checked` that isn't true/false, a non-UTF-8 body, an empty body, a body over 64 KiB
- a broken state file refuses the tick with its message and stays byte-identical; the view still shows the checklist with the file's marks and the message
- `field-notes/alice` linked outside gives a 403 and nothing is written
- the state file linked to bob's state file (the reviewer's Chunk N2 CR-1 probe) gives a 403 naming it, and bob's file is unchanged

**If Operations asks:** "Only our page, with this run's secret, can save a tick; it saves exactly one tick and never overwrites a broken file."

**Helper:** `post()` sends a raw body with a chosen token (this run's, another, none, or two) and Host.

#### `OwnFileTests` - lines 1156-1250
N2-05, through the real route `/files`, each test on a fresh empty root. Every call checks JSON, nosniff/DENY/no CORS, no disk change, and that the route gives the same as `list_own_files()`.
- no folders yet: empty lists, and nothing created
- F-, INJ-, IR-, NOTE- and SU- files written out of order come back in filename order, mixed across both folders
- the same filename in both folders keeps both, in a fixed order
- not listed: `incoming/`, study `notes/`, another person's field notes, the top of `field-notes/` or the root, a `.txt`, subfolders (including a same-named copy, so a search of subfolders would show a duplicate), a folder named `NOTE-folder.md`
- folder and file links inside the root are listed under their own paths
- a folder linked outside is refused and not looked into (its file name doesn't appear), while the other folder still lists; a file linked outside is refused, not listed

**If Operations asks:** "The list shows only your own files, grouped by type, and a bad link is reported without hiding the rest."

#### `NewFileTypeTests` - lines 1253-1356
N3-01, `new_file_type()` directly.
- each of the five types gives its exact entry: path pattern, number or not, template, library or not
- exactly five types, in the table's order; only Incident report and Finding need a number, and that agrees with a `{nnn}` in the path
- every path starts with `findings/F-` or `field-notes/{name}/`, and fills in nothing but `name`, `nnn` and `slug`
- the four template paths are real files in the repo (a typo would fail here)
- refused with a readable error: `Task`; near misses (`note`, `NOTE`, ` Note`, `Note `, `""`, `Incident Report`, `finding`); a type that isn't text (`None`, `1`, a list, a dict)
- changing a returned entry doesn't change the table

**If Operations asks:** "Only the five exact types exist, each with a fixed folder."

#### `LibraryTests` - lines 1359-1612
N3-02, on fake library entries only (the real `findings-library/` is never read). Every listing checks that no byte on disk changed.
- a missing or empty folder, or only `README.md`: no entries, nothing created
- two entries come back sorted with their exact titles; sorted even when the disk lists them in reverse (`glob` patched)
- titles exactly as written (punctuation, `|`, non-ASCII, a trailing space); a raw template copy gives `[[FINDING_TITLE]]`
- the first heading wins; prose and `#1 ...` before it are ignored
- renaming an entry and changing its heading shows on the next call
- only `.md` files directly in the folder: not a `.txt`, a subfolder's file, or a folder named `folder.md`
- a wrong first heading (`F-001`, `##`, `# Notes` first, two spaces, none, an empty file) is refused with its reason, and the good entry still lists
- links: a linked folder or file inside the root is used, under its own path; the folder linked outside gives no entries and one refusal naming it, without outside file names (Chunk N3 D1), while `library_paths()` still raises for it; a file linked outside, to a folder, or to nothing is refused, and a recording of every `is_file()` call shows the link is never followed before its check (N3-02 adversary round 1)
- reading one entry: `..`, an absolute path outside, a NUL byte, a file outside the library and a folder named like an entry are refused, path named; an entry reads back unchanged
- a byte-order mark is dropped, a Windows line ending leaves no `\r` in the title, a Windows-1252 entry is refused naming it

**If Operations asks:** "The library list is read fresh from disk, only ever read, and a bad entry is reported without hiding the good ones."

#### `NumberTests` - lines 1615-2060
N3-03, `finding_id_warnings()` and `suggest_ir_number()` directly. Every call checks that no byte or name on disk changed.
- `000`, `006` and `999` pass; `6`, `01`, `1000`, `abc`, `00a`, `"123\n"`, Arabic-Indic digits, a NUL, `""` and `" 007"` fail, for both the check and the warning
- no folders: no warning and `001`, nothing created
- a local or an incoming F-007 warns, naming the file; several are all reported in path order, even with the disk order reversed (`glob` and `iterdir` patched); none warns when nothing matches (an owner folder named `F-007-team` included)
- `F-070`, `F-0070`, `F-007x`, `F-07`, `.txt`, `F-007_a`, subfolders and wrong folders don't collide; `F-007-real.md` and `F-007.md` do
- the IR suggestion: `001` with none; `005` from local IR-001 and incoming IR-004; any person's folder counts; `011` from 009, 010 twice and a lower number scanned last; names that don't count (`IR-01`, `IR-1000`, `ir-`, `SU-`, wrong folders) are ignored; `IR-004.md` counts; IR-999 gives `None` and the exact message
- links inside the root count under their own paths; links outside are reported at every level and the rest still counts, one test each: `findings/`, `incoming/` and `field-notes/` (Chunk N3 D1), an owner folder, its `findings/` or `field-notes/`, a person's folder, a finding file and an IR file; top-level and deeper refusals together come back in path order; nothing is followed before its check (`is_file()` and `is_dir()` recorded); refused file links come back in path order with the disk order reversed (N3-03 adversary round 1)
- adding and renaming files changes the next result
- `ir_number_warnings()` (Chunk N3 D2): a local or an incoming IR-007 warns, naming the file; several come back in path order with the disk order reversed; `IR-07`, `IR-0070`, `IR-007x`, `IR-007_x`, `ir-007`, `.txt`, subfolders, wrong folders and Arabic-Indic digits don't collide; a refused link doesn't hide a real collision; a bad number is refused

**If Operations asks:** "Duplicate finding IDs are found across the whole team's copies, and the IR suggestion is always the highest number in use plus one, never written anywhere."

#### `tree()` + `FAKE_TEMPLATES` + `LIBRARY_ENTRY` - lines 2063-2110
`tree()` records every name under a folder (links not followed) with its bytes, its link target or "folder", so a test can prove nothing was created, changed or removed. `FAKE_TEMPLATES` are the four templates with look-alike markers (`[[IR_ID_EXTRA]]`, `[[ IR_ID ]]`, `[[FINDING_ID_EXTRA]]`, `[[PREVIOUS_FINDING_ID]]`, ...); `LIBRARY_ENTRY` is a fake library entry with a later heading of the same form.

#### `CreateNewFileTests` - lines 2113-2676
N3-04, `create_new_file()` directly. A refusal is checked by `assert_refused()`: the folder-making functions are patched to fail, and the root, the outside folder and the log folder are byte-for-byte and name-for-name unchanged. A success is checked by `assert_created()`: exactly the new file and the folders it needs.
- each type at its exact path with its exact text: Note empty; IR with every `[[IR_ID]]` filled and the look-alikes kept; Status update and Inject response byte copies; Finding with the ID and title filled; the repo's real IR and finding templates filled the same way
- a title with `|`, backticks, `$`, `é`, `[[HOST]]`, `[[FINDING_ID]]`, `\` and a trailing space goes in exactly; the file name uses only the slug
- library: an unchanged title gives the entry with only the ID filled; an edited title changes only the first heading (a later one keeps its text), with prose and Windows line endings kept; markers in a title stay as typed; `[[FINDING_TITLE]]` in an entry is filled (the spec)
- library refusals, one test each: a bad heading, `README.md`, a subfolder entry, a file outside the library, `..`, a path outside, a NUL, a link outside, a path that isn't text; a link inside the root is used; a library entry for any other type is refused; a Finding without one never reads the library
- numbers: the typed `006` is used, not the suggested `005`; bad numbers (`6`, `0006`, `"123\n"`, Arabic-Indic, `""`, `None`, `7`, a list) are refused for both types; a number for a Note, Status update or Inject response is refused; a missing number never asks for the suggestion
- the slug: `../A  B!!` stays in its folder as `NOTE-a-b.md`; an empty slug and a title that isn't text are refused; a NUL or `%00` never reaches the path
- already at the name, one test each: a file (bytes, time and size unchanged), a link inside, a link outside, a broken link, a folder, a hard-linked file
- folders: `findings/`, `field-notes/` and `field-notes/alice` linked inside are used; linked outside, into `incoming/` or into the log folder they're refused; a file or a broken link where a folder should be is refused
- templates: `templates/` or a template linked inside is used; linked outside, missing, a folder, not UTF-8 or unreadable is refused naming it; Windows line endings are kept and a byte-order mark is dropped
- a duplicate finding ID warns, with the refusals, in path order, and the file is still created; so does a duplicate IR number (Chunk N3 D2), which is checked against the typed number, not the suggestion; an F-007 doesn't warn for IR-007; a Finding is still created with `incoming/` linked outside, the link in `refused` (Chunk N3 D1)
- a title with a line feed, a carriage return or both, at the start, middle or end, is refused for all five types with "the title must be one line, with no line breaks", before any template, library entry, scan or path check runs; tabs, spaces and a typed backslash-n are fine (Chunk N3 D5)
- a file that appears after the checks is never overwritten (`lexists` patched to miss it); a failed write leaves no half-made file

**If Operations asks:** "Every way a new file could land in the wrong place, overwrite something, or go in half-made was tried, and each is refused before anything changes."

#### `NewFileRouteTests` - lines 2679-3063
N3-05, through the real routes `GET /new-data` and `POST /new-file`, each test on a fresh root with the fake templates. Every response is checked for nosniff, DENY and no CORS; a refusal is plain text and changes no file in the root or the outside folder.
- `/new-data`: the exact JSON (five types with their flags, sorted entries including a `<script>` title as text, the library refusal, `005`, the IR refusal); on an empty root `001` and nothing created; `findings-library/`, `field-notes/` or `incoming/` linked outside, alone or all three, still gives the five types with the link in its refused list (Chunk N3 D1); a bad entry doesn't hide a good one; IR-999 gives `null` and the exact note, and a typed number is still created; a raw template entry's title comes back as `[[FINDING_TITLE]]` (Chunk N3 D3)
- create: each type at its exact path with `{path, [], []}`; a library finding; the fields go to `create_new_file()` exactly as sent; duplicate-ID warnings and refusals come back in path order; a typed IR number already in use warns and is still created (Chunk N3 D2); a Finding is created with `incoming/` linked outside (Chunk N3 D1); a title with a line break (LF, CR or CRLF before an injected `- **Severity:**` line) gives a plain-text 400 that doesn't repeat the title, and nothing is created (Chunk N3 D5)
- refused with 400 before `create_new_file()` runs: a missing or extra field, `filename`, `path`, a list, a string, `null`, fields of the wrong type; bad bodies (no `Content-Length`, `abc`, `-1`, `1e3`, over 64 KiB, empty, non-UTF-8, broken JSON); a body shorter than its `Content-Length` times out with a 400 and the server goes on answering (the real timeout is 10 seconds)
- refused with 400 by the create step, with the reason: unknown type, empty slug, bad or missing number, a number for a Note, a library entry for a Note
- the guard: a wrong Host, no token, a wrong token, the token twice or another run's token gives 403 before anything runs; the token read from the served page works
- errors keep their reason: "already exists" 403, a non-UTF-8 template 500, a `PermissionError` 500
- both routes are in the route tables; `/`, `/files` and `/new-data` change nothing

**If Operations asks:** "Only our page, with this run's secret, can create a file; it can only send a type, title, number and library entry, and every problem comes back as a readable message with nothing created."

#### `PageParts` - lines 3066-3092
A small HTML reader: what's inside `<nav>` and `<main>`, the text a person would see, and the token in the `<meta name="cptc-token">` tag.

#### `AppShellTests` - lines 3095-3184
Updated in place at N3-05; still the one test class that checks the page's safety (the NT4-06 rule).
- the left column holds the theme button, the file list, New and Checklists, in that order; the main pane is empty; the only visible words are "Light / dark", "New" and "Checklists" (no Logs, Export or Compile yet); the file list loads when the page opens
- the page carries this run's token exactly once, and no leftover `TOKEN_SLOT`
- a hostile token is escaped in the page
- the script has no `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write`; both POSTs (a tick and a new file) send `X-CPTC-Token`; it makes real checkboxes, sets text with `textContent`, locks a box while saving and restores its earlier value
- the New form's request is exactly `{type, title, nnn, library}`, with a number only when the type needs one and a library entry only for a Finding; the title box is one line and there is no textarea; hidden rows follow the server's flags
- every refused list (own files, library, IR scan), the warnings, the reload with the new file selected, and the IR suggestion fetched again after a create (Chunk N3 CR-1) are in the script
- the page has the dark-mode media query, both button overrides and the click handler

**If Operations asks:** "The page has only the controls built so far, carries this run's secret safely, and never turns file text into page code."

**Limit:** these check the served script's text, not its behaviour in a browser (see `APP_PAGE`).

## 4. Related edits outside tools/

None outside `tools/` in Chunk N3, or in Chunk N2. (CS-02's `TODO.md` edit and W-01's `agents.md` edit, made on 2026-10-28 before N2 started, were separate tasks and not part of the N2 commit; `agents.md` is ignored by git.)

From Chunk N1, one related spec edit inside `tools/`:

### `tools/BUILD-SPEC.md` (Chunk N1 review, C-N1-03)
Wording only, folding in DECISIONS 2026-10-27 Chunk N1 D1 and D3:
- Tool 2 New file: an `NNN` is validated as exactly three ASCII digits (`[0-9]{3}` with `fullmatch()`), not `^\d{3}$`
- Constraint 8: the Host check covers GET and POST, the only methods with routes; any other method gets a plain-text 501
- Decisions log: one entry each for D1 and D3

**If Operations asks:** "The spec now says what the code does: the stricter ID check and the plain 501 for methods we don't use were the user's decisions at the Chunk N1 review."
