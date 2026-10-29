"""notebook.py: a local web page for checklists, field notes and templates.

Each tester runs it on their own box. It reads and writes the same Markdown
files the repo already uses, in the working copy.

Usage: python3 tools/notebook.py --name alice [--root ~/cptc-work] [--port 8765]

Python 3 standard library only. It never runs commands, and it has no option
to serve on any address but 127.0.0.1. It uses compile.py's root check;
compile.py imports nothing from here.
"""

import argparse
import html
import json
import os
import re
import secrets
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import compile

# Any run of characters that aren't allowed in a slug.
NOT_SLUG_RE = re.compile(r"[^a-z0-9-]+")
# Two or more hyphens in a row.
REPEATED_HYPHENS_RE = re.compile(r"-{2,}")
SLUG_MAX_LENGTH = 40


def slugify(text):
    """Return text as a short filename part, e.g. "Admin Panel!" -> "admin-panel".

    Raises ValueError if nothing usable is left, e.g. for "!!!".
    """
    slug = text.lower()
    # Only a-z, 0-9 and "-" survive, so a title can't add "/", "..", spaces
    # or any other character that changes where a file is saved.
    slug = NOT_SLUG_RE.sub("-", slug)
    slug = REPEATED_HYPHENS_RE.sub("-", slug)
    # Trim before stripping the end hyphens, so a cut that lands just after
    # a "-" doesn't leave one at the end.
    slug = slug[:SLUG_MAX_LENGTH].strip("-")
    if not slug:
        raise ValueError("no letters or digits to make a file name from: " + repr(text))
    return slug


# The number in IR-NNN and F-NNN: exactly three ASCII digits. [0-9], not \d,
# because \d also matches other scripts' digits (e.g. Arabic-Indic), and
# fullmatch() is used because "$" would also accept a trailing newline.
NNN_RE = re.compile(r"[0-9]{3}")


def validate_nnn(text):
    """Return text if it is a three-digit number like 007, else raise ValueError.

    It only checks the format. The number itself is typed in by the user;
    this never picks or reserves one.
    """
    if not NNN_RE.fullmatch(text):
        raise ValueError("the number must be exactly three digits, e.g. 007: " + repr(text))
    return text


def is_inside(path, folder):
    """Return True if path is folder itself or anything below it."""
    return path == folder or folder in path.parents


def resolve_inside(root, path):
    """compile.resolve_in_root(), with a NUL byte refused as RootError too."""
    try:
        return compile.resolve_in_root(root, path)
    except ValueError as error:
        # Path.resolve() raises ValueError for a NUL byte, which a hand-typed
        # URL (%00) can carry. As a RootError it gets the same readable 403
        # as any other refused path, instead of a dropped connection.
        raise compile.RootError("path can't be used (" + str(error) + "): " + repr(str(path)))


def readable_path(root, path):
    """Return path, resolved, if it is inside the working copy; else raise RootError."""
    # One shared check (OQ-13): `..`, an absolute path outside the root, and a
    # symlink pointing outside are all refused by compile.py, with the path
    # named, while a symlink that stays inside the root is allowed (OQ-17).
    return resolve_inside(root, path)


def readable_log_path(logdir, path):
    """Return path, resolved, if it is inside the log folder; else raise RootError.

    The log folder is only ever read: there is no writable version of this.
    """
    # The same check as the working copy, with the log folder as the root.
    return resolve_inside(logdir, path)


def writable_path(root, logdir, path):
    """Return path, resolved, if the notebook may write it; else raise RootError.

    It must be inside the working copy, and not inside incoming/ or the
    log folder, which are read-only.
    """
    resolved = resolve_inside(root, path)
    # Both folders are resolved, so a symlink can't be used to write into them
    # through another name.
    incoming = (Path(root) / "incoming").resolve()
    if is_inside(resolved, incoming):
        # incoming/ holds teammates' copied files, which the tools only read
        # (R18); each person edits their own files on their own box.
        raise compile.RootError("incoming/ is read-only, not writing: " + str(path))
    if is_inside(resolved, Path(logdir).resolve()):
        # Logs are evidence: the notebook shows them but never changes them.
        raise compile.RootError("the log folder is read-only, not writing: " + str(path))
    return resolved


def name_option(text):
    """Turn --name into the slug used for field-notes/<name>/, e.g. "Alice Smith" -> "alice-smith"."""
    try:
        return slugify(text)
    except ValueError as error:
        # argparse shows this message with its usage line, instead of a traceback.
        raise argparse.ArgumentTypeError(str(error))


def make_token():
    """Return a new random token for this run (Constraint 8)."""
    # Put in the app's own page; other sites can't read that page, so they
    # can't learn it, and without it their POSTs are refused.
    return secrets.token_urlsafe(32)


def request_refusal(method, headers, port, token):
    """Return the 403 text if a request must be refused, or None to allow it.

    Every GET and POST needs Host exactly 127.0.0.1:<port>; a POST also
    needs the X-CPTC-Token header with this run's token.
    """
    refusal = "refused: use http://127.0.0.1:" + str(port)
    # A page on another site can make the browser send requests here. An
    # exact Host stops DNS rebinding, where an attacker's domain is pointed
    # at 127.0.0.1: the browser then sends that domain as the Host.
    # get_all() so a request can't sneak a second Host header past the check.
    if headers.get_all("Host") != ["127.0.0.1:" + str(port)]:
        return refusal
    if method == "POST":
        given = headers.get_all("X-CPTC-Token") or []
        # compare_digest() is built so its timing doesn't show how much of
        # the token matched. Bytes, because it raises an error on non-ASCII
        # text, which a header could contain.
        if len(given) != 1 or not secrets.compare_digest(given[0].encode("utf-8"),
                                                         token.encode("utf-8")):
            return refusal
    return None


def send_body(handler, status, content_type, body):
    """Send a response with the safety headers every response gets (Constraint 9)."""
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    # The browser must use the type above, not guess HTML from the content:
    # a log with "<script>" in it must never run as part of this page.
    handler.send_header("X-Content-Type-Options", "nosniff")
    # No other site may show the page inside a frame of its own.
    handler.send_header("X-Frame-Options", "DENY")
    # Deliberately no Access-Control-Allow-Origin (CORS) header, so other
    # sites' scripts can't read any response.
    handler.end_headers()
    # A HEAD response is headers only (HTTP says so); Content-Length still
    # gives the size the body would have, as the stdlib's own errors do.
    if handler.command != "HEAD":
        handler.wfile.write(body)


def send_text(handler, status, text):
    """Send a plain-text response: file and log content, and messages."""
    send_body(handler, status, "text/plain; charset=utf-8", text.encode("utf-8"))


def send_json(handler, status, data):
    """Send data (e.g. a file list) as JSON."""
    # ensure_ascii (the default) escapes non-ASCII text, so the body is plain ASCII.
    send_body(handler, status, "application/json", json.dumps(data).encode("ascii"))


def send_page(handler):
    """Send the app's one HTML page, with this run's token in it.

    Only "/" uses this; data is never HTML.
    """
    # The page's own script sends the token with every POST (Constraint 8).
    # token_urlsafe() uses only letters, digits, "-" and "_", so it can't end
    # the attribute it sits in; escape() makes sure of it anyway.
    page = APP_PAGE.replace(TOKEN_SLOT, html.escape(handler.server.token, quote=True))
    send_body(handler, 200, "text/html; charset=utf-8", page.encode("utf-8"))


# The checklists' folder in the working copy. Kept in this one place because
# where checklists 10-60 will live is still being decided.
CHECKLISTS_DIR = "checklists"


def list_checklists(root):
    """Return the checklists as paths relative to root, sorted, e.g. "checklists/10-ad.md".

    Only the .md files directly in checklists/; an empty list if it's missing.
    Raises compile.RootError if checklists/ is a symlink pointing outside the root.
    """
    # Checked before listing, so a linked folder outside the root is never
    # looked into: even its file names stay hidden.
    folder = readable_path(root, CHECKLISTS_DIR)
    # glob("*.md") doesn't look in subfolders, and is_file() leaves out a
    # folder named like "x.md". Sorted, because glob's order depends on the disk.
    return sorted(CHECKLISTS_DIR + "/" + path.name
                  for path in folder.glob("*.md") if path.is_file())


def read_checklist(root, path):
    """Return one listed checklist's text as it is on disk now.

    Raises compile.RootError if path is refused or isn't a listed checklist,
    and compile.InputError if the file isn't UTF-8 text.
    """
    # The shared path check first (OQ-13): `..`, an absolute path outside the
    # root and a symlink pointing outside are refused with the path named.
    resolved = readable_path(root, path)
    # Then only what the list shows, so this route reads checklists and
    # nothing else in the working copy (e.g. findings or subfolders).
    if path not in list_checklists(root):
        raise compile.RootError("not a checklist: " + str(path))
    # Read from disk on every request, never kept, so an edit to the file
    # shows on the next load. It is only read: the checklist never changes.
    return compile.read_markdown(resolved)


# A task line exactly as the checklists write it: "- [ ] text" or "- [x] text"
# at the start of the line. Anything else, e.g. "  - [ ] x" or "- [X] x", is
# shown as plain text.
TASK_RE = re.compile(r"- \[([ x])\] (.+)")
# A code-block fence line, as Markdown defines it: up to three spaces, then
# three or more ` or ~, then the rest of the line. Four spaces is indented
# code, not a fence.
FENCE_RE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")


def task_key(path, text, occurrence):
    """Return the key a task's tick is saved under (OQ-08), as one string.

    E.g. '["checklists/10-ad.md", "Run the scan", 2]' for the second
    "Run the scan" task in that checklist.
    """
    # A JSON list, so no character in a path or task text can blur where
    # one part ends; JSON because the ticks are saved in a JSON file.
    return json.dumps([path, text, occurrence])


def checklist_records(path, text):
    """Split a checklist into records, in order, for the checklist view.

    path is the checklist's relative path, e.g. "checklists/10-ad.md". Each
    record is {"type": "task", "key", "text", "checked"} for a task line, or
    {"type": "text", "text"} for any other line, shown as-is (OQ-08).
    "checked" is the file's own mark ("- [x]").
    """
    records = []
    seen = {}
    fence = None
    # Split on "\n" only, like compile.py's line numbers; a "\r" is dropped so
    # a file saved with Windows line endings keeps the same keys.
    for line in text.split("\n"):
        line = line[:-1] if line.endswith("\r") else line
        fence_line = FENCE_RE.match(line)
        if fence_line:
            # Inside a code block every line is text, even one that looks
            # like a task. As in Markdown, only a run of the same character,
            # at least as long, with nothing after it, ends the block, so
            # "```" shown inside a "````" block doesn't end it.
            run, rest = fence_line.group(1), fence_line.group(2)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not rest.strip():
                fence = None
        match = TASK_RE.fullmatch(line) if fence is None else None
        if match is None:
            records.append({"type": "text", "text": line})
            continue
        task = match.group(2)
        # Counts each exact text separately, so a repeated task gets its own
        # key, and editing one task's text never moves another task's key.
        seen[task] = seen.get(task, 0) + 1
        records.append({"type": "task", "key": task_key(path, task, seen[task]),
                        "text": task, "checked": match.group(1) == "x"})
    return records


class StateError(Exception):
    """The tick-state file can't be used. The message names the file."""


def state_path(name):
    """Return the tick-state file for this person, relative to the root."""
    return "field-notes/" + name + "/checklist-state.json"


def refuse_linked_state(root, name):
    """Raise RootError if the tick-state file itself is a symlink.

    DECISIONS 2026-10-28 Chunk N2 CR-1 (user, A): stricter than the usual
    "a link inside the root is fine" (OQ-17) for this one file the notebook
    writes, as compile.py is for its build files (C-21).
    """
    # Otherwise a save would write through the link into the file it points
    # to, e.g. another person's tick state or a checklist. islink() looks at
    # the file only, so a linked field-notes/<name> folder is still allowed.
    shown = state_path(name)
    if os.path.islink(os.path.join(str(root), shown)):
        raise compile.RootError("the tick-state file is a link, not a plain file: " + shown)


def check_state(state, shown):
    """Return state if it is {key: true/false}; else raise StateError naming `shown`."""
    # Anything else (a list, "yes", 1) would make ticks show wrongly, so it
    # is refused rather than guessed at.
    if not isinstance(state, dict):
        raise StateError(shown + " is not a {task: true/false} object")
    for key, value in state.items():
        # A loaded file always has text keys, but a state about to be saved
        # might not, and json.dumps() would quietly turn 1 into "1".
        if not isinstance(key, str):
            raise StateError(shown + ": a task key is not text: " + repr(key))
        # bool, not int: in Python True is also an int, but 1 isn't a tick.
        if not isinstance(value, bool):
            raise StateError(shown + ": the value for " + key + " is not true or false")
    return state


def load_checklist_state(root, name):
    """Return the saved ticks as {key: True/False}; {} if nothing is saved yet.

    Raises StateError if the file isn't valid tick state, and
    compile.RootError if its path is refused or the file is a symlink.
    """
    shown = state_path(name)
    path = readable_path(root, shown)
    refuse_linked_state(root, name)
    if not path.exists():
        return {}
    try:
        # Decoded like every other file the tools read (a BOM is dropped).
        with path.open(encoding="utf-8-sig") as handle:
            state = json.load(handle)
    except (ValueError, OSError) as error:
        # ValueError covers both bad JSON and text that isn't UTF-8.
        raise StateError(shown + " can't be read (" + str(error) + ")")
    return check_state(state, shown)


def save_checklist_state(root, logdir, name, state):
    """Write the ticks to field-notes/<name>/checklist-state.json, all at once.

    Raises StateError for a bad state and compile.RootError if the path is
    refused (outside the root, incoming/ or the log folder) or the file is a
    symlink.
    """
    shown = state_path(name)
    check_state(state, shown)
    path = writable_path(root, logdir, shown)
    refuse_linked_state(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, indent=2, sort_keys=True) + "\n"
    # Written to a new temp file beside it, then swapped in with one rename,
    # so a crash never leaves half a file. mkstemp only ever makes a new
    # file, so a symlink planted under the temp name can't be written through.
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".checklist-state-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as temp:
            temp.write(text)
        os.replace(temp_name, str(path))
    except BaseException:
        # Our own temp file only: a failed save leaves the old state as it was.
        os.unlink(temp_name)
        raise


def task_checked(record, state):
    """Return whether a task shows ticked: its saved tick, else the file's own mark."""
    # Once ticked or unticked in the notebook, the saved value wins; until
    # then "- [x]" in the file starts ticked (N2-02 Q1 A). An edited task has
    # a new key, so an old tick never carries over to it.
    return state.get(record["key"], record["checked"])


def own_folders(name):
    """Return the two folders that hold a person's own files, relative to the root.

    Their findings and their own field notes; never incoming/ (teammates'
    copies) or study notes/.
    """
    return ["findings", "field-notes/" + name]


def list_own_files(root, name):
    """Return (files, refused) for the left column.

    files: the .md files directly in the two own folders, as root-relative
    paths, sorted by filename so prefixes group (F-, INJ-, IR-, NOTE-, SU-).
    refused: one message per folder or file whose link points outside the
    root; it is never looked into or listed, but the rest still is.
    """
    files = []
    refused = []
    for folder in own_folders(name):
        try:
            # Checked before listing, so an outside folder's names stay hidden.
            resolved = readable_path(root, folder)
        except compile.RootError as error:
            refused.append(str(error))
            continue
        # glob("*.md") doesn't look in subfolders; a missing folder lists nothing.
        for path in resolved.glob("*.md"):
            relative = folder + "/" + path.name
            try:
                # is_file() after the check leaves out a folder named "x.md".
                if readable_path(root, relative).is_file():
                    files.append(relative)
            except compile.RootError as error:
                # One bad link must not hide the person's other files mid-event.
                refused.append(str(error))
    # By filename first, so both folders' files mix by prefix; the full path
    # breaks a tie, so the order never depends on the disk.
    files.sort(key=lambda path: (path.rsplit("/", 1)[1], path))
    refused.sort()
    return files, refused


def send_own_files(handler):
    """GET /files: the person's own files as JSON, with any refused links."""
    settings = handler.server.settings
    files, refused = list_own_files(settings["root"], settings["name"])
    send_json(handler, 200, {"files": files, "refused": refused})


def send_checklist_list(handler):
    """GET /checklists: the checklists' paths as JSON."""
    try:
        checklists = list_checklists(handler.server.settings["root"])
    except compile.RootError as error:
        send_text(handler, 403, "refused: " + str(error))
        return
    send_json(handler, 200, {"checklists": checklists})


def checklist_from_query(handler):
    """Return (path, text) for the ?path= checklist, or None after sending the error."""
    paths = parse_qs(urlsplit(handler.path).query).get("path", [])
    if len(paths) != 1:
        send_text(handler, 400, "give one checklist: ?path=checklists/<file>.md")
        return None
    try:
        return paths[0], read_checklist(handler.server.settings["root"], paths[0])
    except compile.RootError as error:
        send_text(handler, 403, "refused: " + str(error))
    except (compile.InputError, OSError) as error:
        # e.g. a checklist saved as Windows-1252, or deleted just now: a
        # readable message instead of a dropped connection.
        send_text(handler, 500, "can't read the checklist: " + str(error))
    return None


def send_checklist(handler):
    """GET /checklist?path=checklists/<file>.md: one checklist's Markdown as plain text."""
    checklist = checklist_from_query(handler)
    if checklist is not None:
        send_text(handler, 200, checklist[1])


def send_checklist_view(handler):
    """GET /checklist-view?path=...: the checklist's records as JSON, ticks filled in.

    Each task's "checked" is what it shows (task_checked()). If the saved
    ticks can't be read, the file's own marks show and "state_error" says why.
    """
    checklist = checklist_from_query(handler)
    if checklist is None:
        return
    path, text = checklist
    settings = handler.server.settings
    state_error = None
    try:
        state = load_checklist_state(settings["root"], settings["name"])
    except (StateError, compile.RootError) as error:
        # The checklist is still worth showing; saving a tick will refuse
        # with the same message, so a broken file is never overwritten.
        state, state_error = {}, str(error)
    records = []
    for record in checklist_records(path, text):
        if record["type"] == "task":
            record = dict(record, checked=task_checked(record, state))
        records.append(record)
    send_json(handler, 200, {"path": path, "records": records, "state_error": state_error})


# Far more than one tick needs ({"key": ..., "checked": ...}); a bigger body
# is refused before it is read.
MAX_TICK_BYTES = 64 * 1024


def read_tick(handler):
    """Return (key, checked) from a tick POST's JSON body, or None after sending a 400."""
    length = handler.headers.get("Content-Length", "")
    if not (length.isascii() and length.isdigit()) or int(length) > MAX_TICK_BYTES:
        send_text(handler, 400, "send one tick as JSON, at most " + str(MAX_TICK_BYTES) + " bytes")
        return None
    try:
        tick = json.loads(handler.rfile.read(int(length)).decode("utf-8"))
    except ValueError:
        tick = None
    # Exactly these two fields, so a typo like "check" is refused, not ignored.
    if (not isinstance(tick, dict) or set(tick) != {"key", "checked"}
            or not isinstance(tick["key"], str) or not isinstance(tick["checked"], bool)):
        send_text(handler, 400, 'send {"key": "<task key>", "checked": true or false}')
        return None
    return tick["key"], tick["checked"]


def save_tick(handler):
    """POST /checklist-state: save one task's tick, keeping every other saved tick."""
    tick = read_tick(handler)
    if tick is None:
        return
    key, checked = tick
    settings = handler.server.settings
    try:
        # Load first: if the saved ticks can't be read, refuse rather than
        # replace them with this one tick (N2-03, agreed with the adversary).
        state = load_checklist_state(settings["root"], settings["name"])
        state[key] = checked
        save_checklist_state(settings["root"], settings["logdir"], settings["name"], state)
    except compile.RootError as error:
        send_text(handler, 403, "refused: " + str(error))
        return
    except (StateError, OSError) as error:
        send_text(handler, 500, "tick not saved: " + str(error))
        return
    send_json(handler, 200, {"key": key, "checked": checked})


# Where send_page() puts this run's token in the page.
TOKEN_SLOT = "CPTC_TOKEN_SLOT"

# The app page: a left column (nav) and a main pane. Inline CSS and JS only,
# no outside files (Constraint 1). Black on white, or white on black when the
# system is in dark mode; the button swaps them by hand. No styling beyond
# spacing. The script builds everything with textContent, never innerHTML, so
# text from a file (even "<script>") only ever shows as text.
APP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="cptc-token" content="CPTC_TOKEN_SLOT">
<title>CPTC notebook</title>
<style>
:root { --text: black; --background: white; }
@media (prefers-color-scheme: dark) {
  :root { --text: white; --background: black; }
}
/* Set by the toggle button; these win over the system setting above. */
:root[data-theme="light"] { --text: black; --background: white; }
:root[data-theme="dark"] { --text: white; --background: black; }
body { margin: 0; color: var(--text); background: var(--background); font-family: sans-serif; }
.columns { display: flex; gap: 2rem; padding: 1rem; }
nav { width: 15rem; flex-shrink: 0; }
main { flex-grow: 1; }
nav button { display: block; margin-bottom: 0.5rem; }
label input { margin-right: 0.5rem; }
/* One <pre> per checklist line; an empty line still takes up a line. */
pre { margin: 0; min-height: 1.2em; white-space: pre-wrap; }
</style>
</head>
<body>
<div class="columns">
<nav id="nav">
<button type="button" id="theme-toggle">Light / dark</button>
<button type="button" id="checklists-button">Checklists</button>
</nav>
<main id="main"></main>
</div>
<script>
/* Swap light and dark, starting from whatever is showing now. */
document.getElementById("theme-toggle").addEventListener("click", function () {
  var root = document.documentElement;
  var dark = root.dataset.theme
    ? root.dataset.theme === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
});

var TOKEN = document.querySelector('meta[name="cptc-token"]').content;
var main = document.getElementById("main");

/* A new element, with its text (if any) set as plain text. */
function element(tag, text) {
  var made = document.createElement(tag);
  if (text !== undefined) {
    made.textContent = text;
  }
  return made;
}

/* Empty the main pane and show one message, e.g. the server's error text. */
function showMessage(text) {
  main.textContent = "";
  main.appendChild(element("p", text));
}

/* GET a JSON route and pass its data to show(); an error shows the server's text. */
function getJson(url, show) {
  fetch(url).then(function (response) {
    return response.ok ? response.json().then(show) : response.text().then(showMessage);
  }).catch(function (error) {
    showMessage("The notebook isn't answering: " + error);
  });
}

function showChecklistList(data) {
  main.textContent = "";
  main.appendChild(element("h2", "Checklists"));
  if (data.checklists.length === 0) {
    main.appendChild(element("p", "No checklists found."));
  }
  data.checklists.forEach(function (path) {
    var button = element("button", path);
    button.type = "button";
    button.addEventListener("click", function () {
      getJson("/checklist-view?path=" + encodeURIComponent(path), showChecklist);
    });
    main.appendChild(element("div")).appendChild(button);
  });
}

/* Each task gets a real checkbox; every other line is shown as it is. */
function showChecklist(data) {
  main.textContent = "";
  main.appendChild(element("h2", data.path));
  /* Saving problems show here; empty when all is well. */
  var status = main.appendChild(element("p", data.state_error || ""));
  data.records.forEach(function (record) {
    if (record.type === "text") {
      main.appendChild(element("pre", record.text));
      return;
    }
    var box = element("input");
    box.type = "checkbox";
    box.checked = record.checked;
    box.addEventListener("change", function () {
      saveTick(record.key, box, status);
    });
    var label = element("label");
    label.appendChild(box);
    label.appendChild(element("span", record.text));
    main.appendChild(element("div")).appendChild(label);
  });
}

/* Save one tick. If it isn't saved, the box goes back and the reason shows. */
function saveTick(key, box, status) {
  var wanted = box.checked;
  /* Locked until this save answers, so a quick second click can't be
     undone by the first click's answer arriving after it. */
  box.disabled = true;
  function saved() {
    box.disabled = false;
    status.textContent = "";
  }
  function notSaved(text) {
    box.checked = !wanted;
    box.disabled = false;
    status.textContent = text;
  }
  fetch("/checklist-state", {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CPTC-Token": TOKEN},
    body: JSON.stringify({key: key, checked: wanted})
  }).then(function (response) {
    if (response.ok) {
      saved();
      return;
    }
    return response.text().then(notSaved);
  }).catch(function (error) {
    notSaved("Tick not saved: " + error);
  });
}

document.getElementById("checklists-button").addEventListener("click", function () {
  getJson("/checklists", showChecklistList);
});
</script>
</body>
</html>
"""

# The app's routes: path -> function(handler). The feature tasks add the rest.
# GET routes must never change anything (Constraint 8).
GET_ROUTES = {"/": send_page,
              "/checklists": send_checklist_list,
              "/checklist": send_checklist,
              "/checklist-view": send_checklist_view,
              "/files": send_own_files}
POST_ROUTES = {"/checklist-state": save_tick}


class NotebookHandler(BaseHTTPRequestHandler):
    """Answers each request; the server must have a `token` attribute."""

    def do_GET(self):
        self.answer("GET", GET_ROUTES)

    def do_POST(self):
        self.answer("POST", POST_ROUTES)

    def answer(self, method, routes):
        """Refuse a bad request before any route runs, else run its route."""
        # One request per connection, whatever protocol_version says. A refused
        # request's body is never read, so on a kept-open connection the
        # server would read it as a second request, which could pass the guard.
        self.close_connection = True
        port = self.server.server_address[1]
        refusal = request_refusal(method, self.headers, port, self.server.token)
        if refusal is not None:
            # Nothing has been read or changed yet, so a refused POST changes nothing.
            send_text(self, 403, refusal)
            return
        # Routes are found by the path alone; a route reads its own ?query.
        route = routes.get(urlsplit(self.path).path)
        if route is None:
            send_text(self, 404, "not found: " + self.path)
            return
        route(self)

    def send_error(self, code, message=None, explain=None):
        # The stdlib sends its own errors (e.g. 501 for a method other than
        # GET and POST, 431 for too many headers) as an HTML page without the
        # safety headers; send them as text instead.
        # Limit: for a request line it can't parse, the stdlib sends no status
        # line or headers at all (old HTTP/0.9 style), only this text.
        # Close the connection, as the stdlib's own version does: the body was
        # never read, and must not be read as a second request (see answer()).
        self.close_connection = True
        send_text(self, code, message or self.responses.get(code, ("error",))[0])

    def log_message(self, format, *args):
        """Don't print a line for every request; the terminal stays readable."""


def parse_args(argv=None):
    """Read the command-line options. argv=None means use sys.argv."""
    parser = argparse.ArgumentParser(
        description="A local notebook for checklists, field notes and templates.",
    )
    # Required, so every file the notebook makes lands in the right person's
    # field-notes/<name>/ folder instead of a guessed one. It is slugged like
    # a title, so it can only ever be one plain folder name.
    parser.add_argument("--name", required=True, type=name_option,
                        help="your name, e.g. alice")
    parser.add_argument(
        "--root",
        type=compile.expand_path,
        # The working copy, never the current folder, for the same reason as
        # compile.py: running from the repo clone must not write into it.
        default=Path("~/cptc-work").expanduser(),
        help="the working copy to work in (default: ~/cptc-work)",
    )
    parser.add_argument("--port", type=port_option, default=8765,
                        help="the port to listen on (default: 8765)")
    # There is deliberately no option for the address: the page is only ever
    # served on 127.0.0.1, so no setting can open it to the network.
    return parser.parse_args(argv)


def port_option(text):
    """Turn --port into a number from 1 to 65535, the range a port can be."""
    # isascii() too, because isdigit() also accepts other scripts' digits.
    if not (text.isascii() and text.isdigit()) or not 1 <= int(text) <= 65535:
        # argparse shows this message with its usage line, instead of a traceback.
        raise argparse.ArgumentTypeError("the port must be a number from 1 to 65535: " + repr(text))
    return int(text)


def log_dir():
    """Return the terminal log folder: $LOGDIR, or ~/cptc-logs if it isn't set."""
    # Same rule as scripts/logged-shell.sh (${LOGDIR:-$HOME/cptc-logs}), so the
    # notebook reads the folder the logs were written to; an empty value
    # counts as unset there too.
    return compile.expand_path(os.environ.get("LOGDIR") or "~/cptc-logs")


def load_settings(argv=None):
    """Return the startup settings as a dict, or raise compile.RootError.

    The keys are name, root (resolved), port and logdir.
    """
    args = parse_args(argv)
    return {
        "name": args.name,
        # Checked before the server exists, so a refused root (e.g. the git
        # clone) is never served from or written to.
        "root": compile.validate_root(args.root),
        "port": args.port,
        "logdir": log_dir(),
    }


def make_server(settings):
    """Return the server, listening on 127.0.0.1 only, with a new token for this run."""
    # The literal address, never "" or "0.0.0.0" (every network interface) or
    # "localhost" (a name the system looks up, which may not be 127.0.0.1), so
    # other boxes on the network can't reach the notebook (Constraint 2).
    server = HTTPServer(("127.0.0.1", settings["port"]), NotebookHandler)
    server.token = make_token()
    # For the routes the feature tasks add: they reach these as handler.server.settings.
    server.settings = settings
    return server


def main(argv=None):
    """Run from the command line and return the exit code."""
    try:
        settings = load_settings(argv)
    except compile.RootError as error:
        # A readable line instead of a traceback, with compile.py's exit code
        # for "couldn't run".
        print("notebook failed: " + str(error))
        return 2
    try:
        server = make_server(settings)
    except OSError as error:
        # Usually the port is already in use, e.g. by a second notebook.
        print("notebook failed: can't listen on 127.0.0.1:" + str(settings["port"])
              + ": " + str(error))
        return 2
    print("Notebook: http://127.0.0.1:" + str(server.server_address[1]))
    print("Local only: it listens on 127.0.0.1, so only this box can open it. Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C is the normal way to stop it, so no traceback.
        print("Notebook stopped.")
    finally:
        server.server_close()
    return 0


# Only runs when started as `python3 tools/notebook.py`, never on import, so
# the tests can import this file without side effects.
if __name__ == "__main__":
    sys.exit(main())
