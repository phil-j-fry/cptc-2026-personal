# notebook.py breakdown

Every block of `notebook.py`, its tests, and the related edits outside `tools/`. The test helpers in `tests/support.py` are shared with `compile.py` and are described in [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy). The rulebook says Operations may ask us to explain our code, so each entry has a line range, a one-line description, and **If Operations asks:** a plain answer a student can give.

Line ranges match the code after the Chunk N1 review changes C-N1-01..C-N1-03 to Chunk N1 (safety and shell: N1-01..N1-08). The implementor updates this file at the end of every review chunk; the code reviewer checks it.

| Term | Meaning |
|---|---|
| working copy | `~/cptc-work`: a plain copy of the repo with no `.git`, where all event work happens |
| root | the working copy folder the notebook reads and writes (`--root`) |
| log folder | `$LOGDIR`, or `~/cptc-logs` if it isn't set: where `scripts/logged-shell.sh` saves terminal logs; the notebook only reads it |
| incoming | `incoming/<name>/`: a teammate's files copied in; the tools only read it (rule R18) |
| slug | a title turned into a safe file-name part: only `a-z`, `0-9` and `-`, at most 40 characters |
| NNN | the three-digit number in `IR-NNN` and `F-NNN` file names, e.g. `007` |
| token | a random secret made fresh each time the notebook starts; every POST must send it (Constraint 8) |
| Host header | the address the browser says it is talking to; the notebook only answers `127.0.0.1:<port>` |
| route | one URL the notebook answers, e.g. `/`, with the function that answers it |
| loopback | `127.0.0.1`, an address only this computer can reach |
| nosniff / DENY | two response headers: the browser must not guess the content type, and no other site may show the page in a frame |
| CORS | headers that would let other sites read our responses; the notebook never sends them |

## Size

Measured after the Chunk N1 review changes. The spec's guideline for the whole finished notebook, embedded page included, is about 700–800 lines (Constraint 6, "guidelines, not hard caps").

| Lines in `notebook.py` | Count |
|---|---|
| code (the 39-line `APP_PAGE` included) | 190 |
| docstrings | 54 |
| comments | 77 |
| blank | 55 |
| **total** | **376** |

Chunk N1 holds only the safety parts (feature 1 of Constraint 6) and an empty page; features 2–8 come in later chunks.

## 1. notebook.py

### Module docstring - lines 1-11
What the notebook is, how to run it, and what it never does.

**If Operations asks:** "It's the description at the top of the file. Each tester runs the notebook on their own box; it reads and writes the same Markdown files as the rest of the repo, never runs commands, and can only be served on 127.0.0.1."

### Imports - lines 13-22
Standard library only, plus `compile` (our own `compile.py`).

**If Operations asks:** "Only Python's built-in modules. It imports our `compile.py` to reuse its folder and path checks, so there is one copy of those rules. `compile.py` never imports the notebook (OQ-13)."

**Why `compile` is imported this way:** the spec says the notebook calls `compile.py`'s functions by import, never by running it as a command (Constraint 3). `ModuleSafetyTests` pins this exact import list.

### `NOT_SLUG_RE` + `REPEATED_HYPHENS_RE` + `SLUG_MAX_LENGTH` + `slugify()` - lines 24-46
Turns a free-text title into a short, safe file-name part, e.g. `"Admin Panel!"` → `admin-panel`. Raises `ValueError` if nothing usable is left.

**If Operations asks:** "The user never types a file name. We build it from the title, and only letters, digits and hyphens survive, so a title can't contain `/` or `..` and save a file somewhere else."

| Step | Example: `" ../A  B!! "` |
|---|---|
| lowercase | `" ../a  b!! "` |
| every other run of characters → `-` | `"-a-b-"` |
| repeated `-` → one | `"-a-b-"` |
| cut to 40, then strip end `-` | `"a-b"` |

**Why cut before stripping:** a cut that lands just after a `-` would otherwise leave one at the end.

### `NNN_RE` + `validate_nnn()` - lines 49-63
Accepts exactly three ASCII digits, like `007`; anything else raises `ValueError`. It only checks the format; it never picks a number.

**If Operations asks:** "Incident and finding numbers are three digits. This rejects anything else before a file name is built from it."

**⚠️ Spec departure (decided: DECISIONS 2026-10-27 Chunk N1 D1, user A):** the original task line said `^\d{3}$`. That pattern also accepts `"123\n"` (a trailing newline matches `$`) and other scripts' digits such as Arabic-Indic `١٢٣`. The code uses `[0-9]{3}` with `fullmatch()` instead. The tests include both cases.

### `is_inside()` - lines 66-68
True if a path is a folder itself or anything below it.

**If Operations asks:** "A small helper for 'is this file inside that folder?', used by the write check below."

### `readable_path()` + `readable_log_path()` - lines 71-85
A path the notebook may read: inside the working copy, or inside the log folder. Both call `compile.resolve_in_root()`.

**If Operations asks:** "Every file we read goes through the same check as `compile.py`: `..` is refused, and so is anything that ends up outside the folder, even through a symlink. A symlink that stays inside is fine (OQ-17). The error names the path."

**Why there's no `writable_log_path()`:** logs are evidence. The notebook shows them but never changes them.

### `writable_path()` - lines 88-105
A path the notebook may write: inside the working copy, but not inside `incoming/` or the log folder.

**If Operations asks:** "Writes have two extra refusals. `incoming/` holds teammates' copied files, and the log folder holds evidence, so neither is ever written."

**Why both folders are resolved first:** so a symlink can't reach them under another name. The tests try a link to `incoming/`, `incoming/` itself being a link, and the log folder being a link.

### `name_option()` - lines 108-114
Turns `--name` into a slug, e.g. `"Alice Smith"` → `alice-smith`; argparse prints a readable error for an unusable name.

**If Operations asks:** "Your name becomes your `field-notes/<name>/` folder, so it gets the same cleaning as a title: it can only ever be one plain folder name."

### `make_token()` - lines 117-121
A new random token for this run: `secrets.token_urlsafe(32)`, 43 characters.

**If Operations asks:** "Any web page open in the same browser can send requests to 127.0.0.1. Every POST must carry this secret, and other sites can't read our page to learn it."

**Carry-forward:** the token isn't in the page yet. N2-04 (the first feature that saves anything) puts it there and tests it.

### `request_refusal()` - lines 124-145
Returns the 403 text, or `None` to allow the request. Every GET and POST needs exactly one `Host: 127.0.0.1:<port>`. A POST also needs exactly one `X-CPTC-Token` equal to the token.

**If Operations asks:** "This is the guard on every GET and POST, the only kinds of request with routes. A wrong Host stops DNS rebinding, where an attacker's domain is pointed at 127.0.0.1: the browser then sends that domain as the Host. A missing or wrong token stops other sites from changing files. A refusal says `refused: use http://127.0.0.1:<port>`."

| Check | Why |
|---|---|
| `get_all("Host")` is exactly one value | a second Host header can't sneak past |
| `localhost` and a Host without a port are refused | only the exact address counts |
| `secrets.compare_digest()` on bytes | its timing doesn't show how much of the token matched; bytes because it raises an error on non-ASCII text |

### `send_body()` - lines 148-164
The one place a response is sent. Every response gets its type and length, `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`, and never a CORS header (Constraint 9). A HEAD response gets the headers only, as HTTP requires.

**If Operations asks:** "Logs can contain hostile HTML, because we're attacking things. nosniff makes the browser trust our content type, so a `<script>` in a log sent as text never runs. DENY stops other sites framing our page. With no CORS header, other sites' scripts can't read our responses."

### `send_text()` + `send_json()` + `send_page()` - lines 167-180
Plain text (`text/plain; charset=utf-8`), JSON (`application/json`), or the app page (`text/html`), all through `send_body()`.

**If Operations asks:** "Data is only ever sent as text or JSON. Only the app page itself is HTML, and only at `/`."

**Why JSON is ASCII:** `json.dumps()` escapes non-ASCII characters by default, so the body needs no charset.

### `APP_PAGE` - lines 183-225
The one HTML page: an empty left column with only a "Light / dark" button, and an empty main pane. Inline CSS and JS only.

**If Operations asks:** "Black on white, or white on black when your system is in dark mode. The button swaps them. There are no outside files or fonts, so it works with no internet. The feature chunks fill in the two columns."

| Part | What it does |
|---|---|
| `:root` and `@media (prefers-color-scheme: dark)` | follow the system's light or dark setting |
| `:root[data-theme="light"/"dark"]` | the button's choice, which wins over the system setting |
| `.columns`, `nav`, `main` | two columns with spacing only |
| `<script>` | the button sets `data-theme` to the opposite of what shows now |

**Limit:** the button's choice isn't remembered after a reload; a reload goes back to the system setting. No unit test runs the button's script (Python has no built-in browser); it was checked by hand in a browser.

### `GET_ROUTES` + `POST_ROUTES` - lines 227-230
Which function answers which URL. Only `/` exists so far; there are no POST routes yet.

**If Operations asks:** "A list of the URLs the notebook answers. GET routes never change anything, so every change has to be a POST, and every POST needs the token."

### `NotebookHandler` - lines 233-272
Answers each GET and POST: the guard first, then the route. Any other method gets the server's 501.

| Method | Lines | What it does |
|---|---|---|
| `do_GET()` / `do_POST()` | 236-240 | send GET and POST through `answer()` with their routes |
| `answer()` | 242-258 | closes the connection after this one request; the guard runs before the body is read or any route runs, so a refused POST changes nothing; then 404 for an unknown path |
| `send_error()` | 260-269 | the server's own errors (e.g. 501 for any other method, 431 for too many headers) go out as text with the safety headers instead of as an HTML page, and close the connection |
| `log_message()` | 271-272 | prints nothing per request, so the terminal stays readable |

**If Operations asks:** "Every GET and POST goes through the guard before any route runs. Any other method, like PUT, gets a plain 'not implemented' (501) and nothing runs. Each connection carries only one request."

**Why other methods get a plain 501 (DECISIONS 2026-10-27 Chunk N1 D3, user B):** only GET and POST have routes. Python's server answers any other method with 501 itself, through our `send_error()`, so it never reaches a route whatever its Host. An earlier version sent those methods through the guard too, which the user judged too clever for a case where both versions are safe.

**Why one request per connection (Chunk N1 CR-1):** a refused request's body is never read. If the connection stayed open (HTTP/1.1 keeps it open), the server would read that body as a second request, and a body holding a whole request with the right Host would pass the guard. Python's default (HTTP/1.0) already closes the connection, but `answer()` and `send_error()` set `close_connection` themselves, so a later change to the protocol version can't open that gap. `send_error()` needs it too: Python's own version closes the connection, and ours replaces it.

**Limit:** the server's own errors (400 for a bad request line, 414 for a too-long URL, 431 for too many headers, 501 for another method) are answered without the guard; no route runs and nothing changes. A request whose first line it can't parse at all gets an old-style answer with no headers, only the error text. A browser can't send such a request.

### `parse_args()` - lines 275-297
`--name` (required), `--root` (default `~/cptc-work`), `--port` (default 8765). There is deliberately no option for the address.

**If Operations asks:** "There's no setting that could open the notebook to the network: it's always 127.0.0.1. The root defaults to the working copy, never the current folder, for the same reason as `compile.py`."

### `port_option()` - lines 300-306
`--port` must be 1–65535, written in ASCII digits; otherwise argparse prints a readable error.

**If Operations asks:** "A bad port gives a clear message instead of a crash."

### `log_dir()` - lines 309-314
`$LOGDIR`, or `~/cptc-logs` if it isn't set or is empty.

**If Operations asks:** "The same rule as our logging script, so the notebook looks where the logs were written."

### `load_settings()` - lines 317-330
Reads the options and checks the root with `compile.validate_root()`: it must exist, be a folder and have no `.git`.

**If Operations asks:** "The folder check runs before the server exists, so the notebook refuses to start in a folder that has its own `.git`, like our git clone."

### `make_server()` - lines 333-342
Creates the server on the literal `("127.0.0.1", port)`, with a new token and the settings.

**If Operations asks:** "Literally 127.0.0.1: not empty or `0.0.0.0`, which would mean every network interface, and not `localhost`, a name the system looks up. Other boxes on the network can't reach it."

### `main()` + `if __name__ == "__main__"` - lines 345-376
Root check, then the server. Prints `Notebook: http://127.0.0.1:<port>` and a local-only reminder, then serves until Ctrl+C.

**If Operations asks:** "If the folder is refused or the port is taken, it prints one readable line and exits with code 2. Ctrl+C stops it cleanly with exit code 0, and the server is always closed."

| Exit code | When |
|---|---|
| 0 | stopped with Ctrl+C |
| 2 | the root is refused (e.g. it has `.git`) or the port can't be used |

## 2. Test helpers: tests/support.py

Shared with `compile.py`'s tests. See [compile-breakdown.md, section 2](compile-breakdown.md#2-test-helpers-testssupportpy). The notebook tests use `make_worktree()` for every fake folder.

## 3. Tests

### tests/test_notebook.py

#### Imports - lines 1-17
`support` is imported first so `notebook` and `compile` can be found. `ast` reads `notebook.py`'s source for `ModuleSafetyTests`. `http.client`, `socket`, `threading` and `HTTPServer` are for the tests that run a real server on 127.0.0.1; `HTMLParser` reads the app page.

**If Operations asks:** "Standard library only, like the tools."

#### `StartupTests` - lines 20-48
- a root with `.git` exits with code 2 and the message; no server is created (`HTTPServer` patched and checked) and no file is created
- `--host`, `--bind`, `--address` and `--listen` don't exist
- `--port` refuses `0`, `65536`, `-1`, `abc` and an Arabic-Indic digit; accepts `9000`

**If Operations asks:** "Starting in the git clone is refused before anything happens, and there's no option to open the notebook to the network."

#### `ServeTests` - lines 51-105
- `main()` with a fake server: it is created with exactly `("127.0.0.1", 9123)`, gets a 43+ character token and the settings, the URL and "Local only" are printed, and the server is closed
- a real server listens on `127.0.0.1` with our handler, and each server gets its own token
- a port already in use gives exit code 2 and a readable message (the test can't hang, even if the code broke)
- the page contains no `http` or `//`, so it needs no outside file

**If Operations asks:** "These prove the notebook only listens on this computer and tells you the right address."

#### `ModuleSafetyTests` - lines 108-137
Constraint 3, tested the same way as `compile.py`'s (DECISIONS 2026-10-27 Chunk N1 D2, user A). Both tests read `notebook.py`'s source with `ast`, without running it.
- the imports are exactly `argparse`, `json`, `os`, `re`, `secrets`, `sys`, `http.server`, `pathlib` and `compile` (`os` only for `$LOGDIR`)
- no name `subprocess`, `system`, `popen`, `Popen`, `exec` or `eval` appears anywhere, imported names included

**If Operations asks:** "A test checks that the notebook imports only a fixed list of modules and never names subprocess, system, popen, Popen, exec or eval. That catches the usual ways to run a command; the rest is code review."

**Limit (Chunk N1 CR-4):** the names test is a fixed list. A call such as `os.execvp()` would pass both tests, because `os` is allowed (for `$LOGDIR`) and `execvp` isn't on the list.

**Why imported names too:** `from os import popen` imports module `os`, which is allowed, so the import test alone misses it. `compile.py`'s matching test doesn't collect imported names; there `os` isn't allowed at all, so the import test catches it.

#### `SlugifyTests` - lines 140-155
- the spec's example `" ../A  B!! "` gives `a-b`
- end and repeated hyphens disappear
- at most 40 characters, with no hyphen left at the cut
- punctuation only is refused

**If Operations asks:** "Every way a title could produce a bad file name is turned into a safe one, or refused."

#### `ValidateNnnTests` - lines 158-167
- `000` and `999` pass
- `1`, `01`, `1000`, `abc`, `"123\n"` and Arabic-Indic digits fail

**If Operations asks:** "Only exactly three ordinary digits are accepted."

#### `NameOptionTests` - lines 170-176
- `"Alice Smith"` becomes `alice-smith`
- `"../"` is refused with an argparse error

**If Operations asks:** "Your name is cleaned like a title, and a name that can't be cleaned is refused."

#### `PathWrapperTests` - lines 179-258
`setUp` builds a root with `findings/` and `incoming/bob/`, a log folder, and an "outside" folder, all in `.tmp/`. Every refusal checks the path is named in the error.

| Allowed | Refused |
|---|---|
| read and write `findings/F-001-x.md` | write a log, whether the log folder is outside or inside the root |
| read a log | write in `incoming/` (read is allowed) |
| read `incoming/bob/...` | write through a link into `incoming/`, or where a linked `incoming/` really points |
| read and write through a symlink that stays inside the root | write where a linked log folder really points |
| | `../x.md`, a full path outside, a symlink that leads outside |

**If Operations asks:** "We tried every way to read or write outside the allowed folders, including symlink tricks. Each is refused and the error names the path."

#### `file_bytes()` - lines 261-264
Every file under a folder as `{path: bytes}`, compared before and after to prove nothing changed.

#### `ServerTestCase` - lines 267-332
The shared setup for the server tests; it has no tests of its own. Each test gets a real server on `127.0.0.1` with a free port, in a thread, shut down and closed when the test ends.

| Helper | What it does |
|---|---|
| `setUp()` | adds two fake routes: `/test-read` (GET) and `/test-write` (POST, which changes a file) |
| `send_full()` / `send()` | send one request with exactly the given Host (or several) and token |
| `assert_refused()` | 403 with the refusal text, no route ran, no file changed |
| `good_host()` | `127.0.0.1:<port>` |

**Why fake routes:** there are no real POST routes yet. A fake one that changes a file proves a refused POST changes nothing.

#### `RequestGuardTests` - lines 335-445
- refused (403, nothing ran, nothing changed): a wrong Host, `localhost`, a Host without a port, a second Host header, a wrong Host even with the right token, a POST with no token, a wrong token, a non-ASCII token
- the exact Host GET and the exact Host plus token POST both work
- PUT, OPTIONS, HEAD and a made-up `BREW` get a plain-text 501 with nosniff and DENY, with either Host; no route runs and nothing changes (Chunk N1 D3)
- the HEAD 501, read from a raw socket, has nothing after its headers
- a refused POST whose body is a whole GET with the right Host gets one 403 and nothing else, even with the server switched to HTTP/1.1 (Chunk N1 CR-1)
- the same for PUT, OPTIONS, HEAD and `BREW`: one 501 and nothing else, so their connections close too
- tokens differ each run and are at least 43 characters

**If Operations asks:** "Requests from other sites, or through a wrong address, are refused before anything happens. Methods we don't use get a plain 501, and nothing runs."

**Helper:** `send_with_smuggled_get()` sends one raw request with a wrong Host whose body is a whole GET with the right Host, on a server switched to HTTP/1.1, and returns everything that comes back.

#### `ResponseHeaderTests` - lines 448-525
- every real route: only `/` is HTML, everything else is JSON or plain text, and all have nosniff and DENY
- JSON and plain text come out with the right types; a log with `<script>` in it comes back as plain text
- 403, 404 and 501 responses are plain text with the headers
- the server's own 431 error (101 headers) is plain text with the headers and no CORS

**If Operations asks:** "Nothing but our own page is ever sent as HTML, so a hostile log can't run as part of the page. The test checks every route automatically, including ones added later."

#### `PageParts` - lines 528-551
A small HTML reader: what's inside `<nav>` and `<main>`, and the text a person would see.

#### `AppShellTests` - lines 554-575
- the left column holds only the theme button, the main pane is empty, and the only visible words are "Light / dark" (so no file lists or New/Checklists/Logs/Export/Compile yet)
- the page has the dark-mode media query, both button overrides and the click handler

**If Operations asks:** "The page is the empty two-column layout the spec asks for, with the light/dark switch."

**Limit:** the "no `innerHTML`" source check is left to NT4-06, which the task list says is the only test making that check.

## 4. Related edits outside tools/

None outside `tools/` in Chunk N1. One related spec edit inside it:

### `tools/BUILD-SPEC.md` (Chunk N1 review, C-N1-03)
Wording only, folding in DECISIONS 2026-10-27 Chunk N1 D1 and D3:
- Tool 2 New file: an `NNN` is validated as exactly three ASCII digits (`[0-9]{3}` with `fullmatch()`), not `^\d{3}$`
- Constraint 8: the Host check covers GET and POST, the only methods with routes; any other method gets a plain-text 501
- Decisions log: one entry each for D1 and D3

**If Operations asks:** "The spec now says what the code does: the stricter ID check and the plain 501 for methods we don't use were the user's decisions at the Chunk N1 review."
